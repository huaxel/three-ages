#!/usr/bin/env python3
"""Offline regression tests for notice-evidence queue regeneration."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('three-ages') / 'training' / 'extract_notice_evidence.py'
REVIEW = {
    'construction_era': '1850-1892', 'phase_years': '1882',
    'evidence': 'Décision humaine, pas une suggestion.', 'reviewer': 'Reviewer',
    'reviewed_at': '2026-10-24', 'confidence': 'high',
}
STALE = {
    'identity_name': 'Stale name', 'suggested_era': 'post-1975',
    'rebuild_flag': 'review', 'notice_excerpt': 'Stale excerpt',
    'notice_sources': 'description', 'notice_years': '1999',
    'primary_years': '1999', 'evidence_strength': 'construction',
}
VALID = json.dumps({'identity': {'name': 'Current name'},
                    'description': {'html': 'Cette maison fut construite en 1882.'}})


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


class NoticeEvidenceTests(unittest.TestCase):
    def run_cli(self, queue, out, scraped, force=True):
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--queue', str(queue), '--out', str(out),
             '--scraped', str(scraped)] + (['--force'] if force else []),
            capture_output=True, text=True, check=False,
        )

    def test_regeneration_preserves_review_and_refreshes_all_evidence(self):
        for content in (None, '{broken', '[]', '{}', VALID):
            for in_place in (False, True):
                with self.subTest(content=content, in_place=in_place), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    queue = root / 'queue.csv'
                    out = queue if in_place else root / 'out.csv'
                    # Separate source deliberately lacks reviewer columns: the output's
                    # human edits must survive regardless of source CSV schema.
                    write_csv(queue, [{'building_id': '123', **STALE,
                                       **(REVIEW if in_place else {})}])
                    if not in_place:
                        write_csv(out, [{'building_id': '123', **STALE, **REVIEW}])
                    if content is not None:
                        (root / '123.fr.json').write_text(content, encoding='utf-8')
                    original_source = queue.read_bytes()
                    result = self.run_cli(queue, out, root)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    rows = read_csv(out)
                    self.assertEqual(len(rows), 1)
                    row = rows[0]
                    self.assertEqual({key: row.get(key) for key in REVIEW}, REVIEW)
                    if content == VALID:
                        self.assertEqual(row['suggested_era'], '1850-1892')
                        self.assertEqual(row['identity_name'], 'Current name')
                        self.assertEqual(row['rebuild_flag'], '')
                    else:
                        self.assertEqual({key: row.get(key) for key in STALE},
                                         {key: 'none' if key == 'evidence_strength' else ''
                                          for key in STALE})
                    self.assertEqual(json.loads(result.stdout)['reviewed_rows_preserved'], 1)
                    first = out.read_bytes()
                    rerun = self.run_cli(queue, out, root)
                    self.assertEqual(rerun.returncode, 0, rerun.stderr)
                    self.assertEqual(out.read_bytes(), first)
                    if not in_place:
                        self.assertEqual(queue.read_bytes(), original_source)

    def test_removed_reviewed_ids_refuse_without_mutating_any_file(self):
        # Partial reviews count too; even a depicts-only decision must not vanish.
        for review in (REVIEW, {'depicts_building': 'no'}, {'evidence': 'Human note'}):
            with self.subTest(review=review), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                queue, out = root / 'queue.csv', root / 'out.csv'
                write_csv(queue, [{'building_id': '123', **STALE}])
                write_csv(out, [{'building_id': '123', **review},
                                {'building_id': '456', **review}])
                (root / '123.fr.json').write_text(VALID, encoding='utf-8')
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                result = self.run_cli(queue, out, root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('456', result.stderr)
                self.assertIn('reviewed', result.stderr)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_preservation_count_includes_source_reviews_not_only_output_overrides(self):
        for existing_output in (False, True):
            with self.subTest(existing_output=existing_output), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                queue, out = root / 'queue.csv', root / 'out.csv'
                write_csv(queue, [{'building_id': '123', **REVIEW},
                                  {'building_id': '456', **{k: '' for k in REVIEW}}])
                if existing_output:
                    # A removed but untouched output row is safe to drop.
                    write_csv(out, [{'building_id': '456', **REVIEW},
                                    {'building_id': '789', **{k: '' for k in REVIEW}}])
                before = queue.read_bytes()
                result = self.run_cli(queue, out, root)
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = read_csv(out)
                self.assertEqual([r['building_id'] for r in rows], ['123', '456'])
                self.assertEqual({k: rows[0][k] for k in REVIEW}, REVIEW)
                self.assertEqual(json.loads(result.stdout)['reviewed_rows_preserved'],
                                 2 if existing_output else 1)
                self.assertEqual(queue.read_bytes(), before)

    def test_later_output_review_adds_columns_missing_from_source_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue, out = root / 'queue.csv', root / 'out.csv'
            write_csv(queue, [{'building_id': '123'}, {'building_id': '456'}])
            write_csv(out, [{'building_id': '123', **{k: '' for k in REVIEW}},
                            {'building_id': '456', **REVIEW}])
            result = self.run_cli(queue, out, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_csv(out)
            self.assertEqual({k: rows[1].get(k) for k in REVIEW}, REVIEW)
            self.assertEqual(json.loads(result.stdout)['reviewed_rows_preserved'], 1)

    def test_gap_years_stay_unresolved(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('notice_evidence', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for year in (1915, 1916, 1917, 1941, 1942, 1943, 1944):
            self.assertEqual(module.bin_of(year), '', f'gap year {year}')
        self.assertEqual(module.bin_of(1914), '1893-1914')
        self.assertEqual(module.bin_of(1918), '1918-1940')
        self.assertEqual(module.bin_of(1940), '1918-1940')
        self.assertEqual(module.bin_of(1945), '1945-1975')
        record = {'identity': {'name': 'Pont'},
                  'description': {'html': 'Ouvrage inaugur\u00e9 le 23.12.1943.'}}
        self.assertEqual(module.extract(record)['suggested_era'], '')

    def test_without_force_leaves_existing_output_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / 'queue.csv'
            write_csv(queue, [{'building_id': '123', **REVIEW}])
            before = queue.read_bytes()
            result = self.run_cli(queue, queue, root, force=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--force', result.stderr)
            self.assertEqual(queue.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

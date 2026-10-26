#!/usr/bin/env python3
"""Offline stdlib-only capture-sequence evidence checks; no real corpus touched."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TRAINING = Path(__file__).resolve().parent / "three-ages" / "training"
sys.path.insert(0, str(TRAINING))
from sequence_metadata import sequence_groups, sequence_id


def row(source_id="1", seq="", building="a", split="train", **extra):
    return dict(source_filename=source_id, sequence_id=seq, building_id=building,
                split=split, **extra)


class SequenceTests(unittest.TestCase):
    def test_native_forms(self):
        self.assertEqual(sequence_id({"sequence_id": " s ", "sequence": {"id": "s"}}), "s")
        self.assertEqual(sequence_id({"sequence": 12, "sequence_id": "12"}), "12")
        self.assertEqual(sequence_id({"sequence": {"id": 0}}), "0")
        self.assertEqual(sequence_id({"sequence_id": "", "sequence": "s"}), "s")

    def test_unknown(self):
        for value in ({}, {"sequence_id": None}, {"sequence": " "},
                      {"sequence": {"id": None}}):
            self.assertEqual(sequence_id(value), "")

    def test_malformed(self):
        for value in (True, False, 1.0, -1, [], {}, {"name": "s"}, {"id": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sequence_id({"sequence": value})
        with self.assertRaises(ValueError):
            sequence_id({"sequence_id": "one", "sequence": {"id": "two"}})

    def test_no_heuristic(self):
        rows = [row(str(i), username="same", shot_date="1000", sequence="ignored")
                for i in range(2)]
        result = sequence_groups(rows)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["unknown_rows"], 2)
        self.assertEqual(result["unknown_unique_sources"], 2)
        self.assertEqual(result["cross_split_groups"], [])
        self.assertEqual(sequence_id(rows[0]), "ignored")
        self.assertEqual(sequence_id({"username": "same", "shot_date": "1000"}), "")

    def test_partial_coverage_and_unique_sources(self):
        result = sequence_groups([row("1", "s"), row("1"), row("2")])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["row_coverage"], 1 / 3)
        self.assertEqual(result["unique_source_coverage"], 1 / 2)
        self.assertEqual(result["unknown_rows"], 2)
        self.assertEqual(result["unknown_unique_sources"], 1)

    def test_cross_split_is_not_building_identity(self):
        result = sequence_groups([row("1", "s"), row("2", "s", "b", "test")])
        self.assertEqual(result["status"], "COMPLETE")
        group = result["cross_split_groups"][0]
        self.assertEqual(group["key"], "mapillary:s")
        self.assertEqual(group["source_ids"], ["mapillary:1", "mapillary:2"])
        self.assertEqual(group["building_ids"], ["a", "b"])
        self.assertEqual(group["splits"], ["test", "train"])
        self.assertIn("not building identity", result["interpretation"])

    def test_partial_duplicate_source_keeps_cross_split_dependence(self):
        rows = [row('42', 's', 'a', 'train'), row('42', '', 'b', 'test')]
        original = [dict(r) for r in rows]
        report = sequence_groups(rows)
        self.assertEqual(report['status'], 'PARTIAL')
        self.assertEqual(report['known_rows'], 1)
        self.assertEqual(report['unknown_rows'], 1)
        self.assertEqual(report['propagated_rows'], 1)
        self.assertEqual(report['cross_split_groups'][0]['splits'], ['test', 'train'])
        self.assertEqual(report['cross_split_groups'][0]['propagated_rows'], 1)
        self.assertEqual(report, sequence_groups(reversed(rows)))
        self.assertEqual(rows, original)

    def test_source_conflict(self):
        with self.assertRaisesRegex(ValueError, "mapillary:1"):
            sequence_groups([row("1", "s"), row("1", "t")])

    def test_namespace_and_empty(self):
        result = sequence_groups([row("1", "s", source="publisher")])
        self.assertEqual(result["excluded_rows"], 1)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["row_coverage"])
        self.assertEqual(sequence_groups([])["status"], "UNKNOWN")


class SequenceCLITests(unittest.TestCase):
    def test_unknown_is_explicit_and_source_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, output = root/'manifest.csv', root/'report.json'
            manifest.write_text('source_filename,building_id,split,username,shot_date\n1,a,train,same,1000\n2,b,test,same,1000\n')
            original = manifest.read_bytes()
            command = [sys.executable, str(TRAINING/'sequence_metadata.py'), '--manifest', str(manifest), '--out', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report['evidence']['status'], 'UNKNOWN')
            self.assertFalse(report['sequence_column_present'])
            self.assertEqual(report['evidence']['unknown_rows'], 2)
            self.assertIn('not established', report['isolation'])
            self.assertEqual(manifest.read_bytes(), original)
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)

    def test_invalid_rows_refuse_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, output = root/'bad.csv', root/'report.json'
            manifest.write_text('source_filename,building_id,split\n1,a,unknown\n')
            result = subprocess.run([sys.executable, str(TRAINING/'sequence_metadata.py'),
                '--manifest', str(manifest), '--out', str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inbox = self.root / "inbox"
        self.manifest = self.inbox / "building-a" / "manifest.json"
        self.manifest.parent.mkdir(parents=True)
        self.out = self.root / "out.csv"

    def save(self, images):
        self.manifest.write_text(json.dumps({"images": images}), encoding="utf-8")

    def image(self, **kwargs):
        return {"image_id": "42", "filename": "a.jpg", "shot_date": "1700000000000", **kwargs}

    def run_cli(self):
        return subprocess.run([sys.executable, str(TRAINING / "build_mapillary_manifest.py"),
                               "--inbox", str(self.inbox), "--out", str(self.out)],
                              capture_output=True, text=True)

    def test_cli_preserves_native_evidence_and_source(self):
        self.save([self.image(sequence={"id": 123}),
                   self.image(image_id="43", filename="b.jpg", username="same", shot_date="1700000000000")])
        original = self.manifest.read_bytes()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.out.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([r["sequence_id"] for r in rows], ["123", ""])
        self.assertEqual([r["source_filename"] for r in rows], ["42", "43"])
        self.assertEqual(self.manifest.read_bytes(), original)
        before = self.out.read_bytes()
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.out.read_bytes(), before)

    def test_duplicate_paths_and_cache_identity_refuse(self):
        for images in ([self.image(), self.image(image_id='43')],
                       [self.image(filename='../outside.jpg')],
                       [self.image(filename='..\\\\outside.jpg')]):
            self.save(images)
            self.assertNotEqual(self.run_cli().returncode, 0)
            self.assertFalse(self.out.exists())
        self.manifest.write_text(json.dumps({'building_id': 'another-building', 'images': [self.image()]}))
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertFalse(self.out.exists())

    def test_null_optional_fields_remain_unknown(self):
        self.save([self.image(username=None, page_url=None, sequence=None)])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.out.open(newline='') as handle:
            row_ = next(csv.DictReader(handle))
        self.assertEqual(row_['username'], '')
        self.assertEqual(row_['page_url'], '')
        self.assertEqual(row_['sequence_id'], '')

    def test_existing_output_symlinks(self):
        self.save([self.image()])
        for target_exists in (False, True):
            target = self.root / "target"
            if target_exists:
                target.write_text("pinned")
            self.out.symlink_to(target)
            result = self.run_cli()
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(self.out.is_symlink())
            if target_exists:
                self.assertEqual(target.read_text(), "pinned")
            else:
                self.assertFalse(target.exists())
            self.out.unlink()

    def test_invalid_inputs_never_create_partial_output(self):
        for images in ([], [self.image(), self.image(sequence=True)],
                       [self.image(sequence_id="s"), self.image(filename='b.jpg', sequence_id="t")],
                       [self.image(), self.image(filename=[])],
                       [self.image(shot_date="not a date")], [self.image(image_id=True)],
                       [self.image(), 123]):
            with self.subTest(images=images):
                self.save(images)
                original = self.manifest.read_bytes()
                self.assertNotEqual(self.run_cli().returncode, 0)
                self.assertFalse(self.out.exists())
                self.assertEqual(self.manifest.read_bytes(), original)

    def test_malformed_document_and_missing_inbox(self):
        for content in ("not-json", "[]", '{}', '{"images": {}}'):
            self.manifest.write_text(content)
            self.assertNotEqual(self.run_cli().returncode, 0)
            self.assertFalse(self.out.exists())
        self.manifest.unlink()
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()

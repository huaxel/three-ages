#!/usr/bin/env python3
"""Offline tests for the epoch-model data definitions.

Self-contained fixtures only: no network, no torch, no crawl output, so the
prototype gate stays light. Covers era binning, style-family mapping, split
stability, and manifest typing.
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "three-ages"
sys.path.insert(0, str(ROOT))

from epoch_data import (  # noqa: E402
    CAPTURE_ERAS,
    CONSTRUCTION_ERAS,
    FAMILY_NAMES,
    capture_era,
    load_manifest,
    load_reviewed_labels,
    split_of,
    style_family,
    with_reviewed_labels,
)


def test_capture_era_boundaries() -> None:
    assert capture_era(1348) == "pre-1900"
    assert capture_era(1899) == "pre-1900"
    assert capture_era(1900) == "1900-1929"
    assert capture_era(1929) == "1900-1929"
    assert capture_era(1930) == "1930-1959"
    assert capture_era(1959) == "1930-1959"
    assert capture_era(1960) == "1960-1989"
    assert capture_era(1989) == "1960-1989"
    assert capture_era(1990) == "1990-2009"
    assert capture_era(2009) == "1990-2009"
    assert capture_era(2010) == "2010+"
    assert capture_era(2026) == "2010+"
    assert capture_era(None) == ""
    assert CAPTURE_ERAS == ["pre-1900", "1900-1929", "1930-1959",
                            "1960-1989", "1990-2009", "2010+"], \
        "eras must stay oldest-first for ±1 scoring"


def test_style_families_cover_known_styles() -> None:
    known = ["Éclectisme", "Néoclassicisme", "Modernisme", "Art Déco", "Beaux-Arts",
             "Art nouveau", "Néo-Renaissance flamande", "Brutalisme", "Néogothique",
             "Baroque", "Paquebot", "Sécession viennoise", "Nieuwe eenvoud",
             "Architecture rurale", "Néo-égyptien", "Gothique"]
    for style in known:
        assert style_family(style) in FAMILY_NAMES, style
    assert style_family("Style inventé pour le test") == "other"


def test_many_to_many_is_representable() -> None:
    # The user's core observation: same year -> many styles. Families must not
    # collapse that: two buildings with the same caption year keep distinct labels.
    assert style_family("Art nouveau") != style_family("Éclectisme")


def test_split_is_deterministic_and_stable() -> None:
    first = [split_of(str(bid)) for bid in (12, 100, 18704, 99999)]
    assert [split_of(str(bid)) for bid in (12, 100, 18704, 99999)] == first
    assert set(first) <= {"train", "val", "test"}
    counts = {"train": 0, "val": 0, "test": 0}
    for bid in range(20000):
        counts[split_of(str(bid))] += 1
    assert 0.75 < counts["train"] / 20000 < 0.85
    assert 0.05 < counts["val"] / 20000 < 0.15
    assert 0.05 < counts["test"] / 20000 < 0.15


def test_load_manifest_typing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "manifest.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "building_id", "municipality", "filename", "caption", "caption_year",
                "capture_era", "drawing_flag", "styles", "contributor_years", "source_filename", "sequence_id",
                "latitude", "longitude", "split"])
            writer.writeheader()
            writer.writerow({"building_id": "7", "municipality": "X", "filename": "a.JPG",
                             "caption": "Rue X 7, 1998", "caption_year": "1998",
                             "source_filename": "original.JPG", "sequence_id": "native-sequence",
                             "capture_era": "1990-2009", "drawing_flag": "1",
                             "styles": "Art nouveau|Éclectisme", "contributor_years": "1904",
                             "latitude": "50.8", "longitude": "4.3", "split": ""})
            writer.writerow({"building_id": "8", "municipality": "Y", "filename": "b.JPG",
                             "caption": "sans date", "caption_year": "", "capture_era": "",
                             "drawing_flag": "", "styles": "", "contributor_years": "",
                             "latitude": "", "longitude": "", "split": "test"})
        rows = load_manifest(path)
        assert rows[0]["source_filename"] == "original.JPG"
        assert rows[0]['sequence_id'] == 'native-sequence'
        assert rows[1]['sequence_id'] == ''
        assert rows[1]["source_filename"] == "b.JPG"
        assert rows[0]["caption_year"] == 1998
        assert rows[0]["drawing_flag"] is True
        assert rows[0]["families"] == ["art_nouveau", "eclectic"]
        assert rows[0]["split"] == split_of("7"), "empty split falls back to the stable rule"
        assert rows[1]["caption_year"] is None
        assert rows[1]["families"] == []
        assert rows[1]["split"] == "test", "explicit split is respected"


def test_load_manifest_keeps_distinct_files_sharing_a_raw_name() -> None:
    # Listings sharing a raw filename are distinct rows once the builder has
    # mapped them to collision-aware disk names: 571 live groups checked out
    # as different URLs and different bytes, so dropping them loses pictures.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "manifest.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "building_id", "municipality", "filename", "caption", "caption_year",
                "capture_era", "drawing_flag", "styles", "contributor_years",
                "latitude", "longitude", "split"])
            writer.writeheader()
            for filename, year in (("c.JPG", "2022"), ("duplicate__c.JPG", "2002")):
                writer.writerow({"building_id": "9", "municipality": "Z",
                                 "filename": filename, "caption": f"Rue X 9, {year}",
                                 "caption_year": year, "capture_era": "", "drawing_flag": "",
                                 "styles": "", "contributor_years": "", "latitude": "",
                                 "longitude": "", "split": ""})
        rows = load_manifest(path)
        assert len(rows) == 2
        assert sorted(r["caption_year"] for r in rows) == [2002, 2022]


def _write_labels(tmp: str, entries: list[tuple[str, str]]) -> Path:
    path = Path(tmp) / "reviewed.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "building_id", "construction_era", "evidence",
            "reviewer", "reviewed_at", "confidence"])
        writer.writeheader()
        for building_id, era in entries:
            writer.writerow({"building_id": building_id, "construction_era": era,
                             "evidence": "notice", "reviewer": "t",
                             "reviewed_at": "2026-10-22", "confidence": "high"})
    return path


def test_reviewed_labels_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reviewed = load_reviewed_labels(_write_labels(tmp, [("7", "1893-1914")]), labels_only=True)
        assert reviewed == {"7": "1893-1914"}
        assert set(reviewed.values()) <= set(CONSTRUCTION_ERAS)


def test_reviewed_labels_reject_unknown_bin() -> None:
    # A typo must fail loudly, never train silently on a wrong era.
    with tempfile.TemporaryDirectory() as tmp:
        try:
            load_reviewed_labels(_write_labels(tmp, [("7", "1893-1915")]))
        except ValueError:
            pass
        else:
            raise AssertionError("unknown bin accepted")


def test_reviewed_join_excludes_unreviewed() -> None:
    # No silent fallback to contributor-year proxies: unreviewed rows are out.
    rows = [{"building_id": "7"}, {"building_id": "9"}]
    assert with_reviewed_labels(rows, {"7": "1893-1914"}, labels_only=True) == [{"building_id": "7"}]


def test_training_gate_requires_explicit_applicability_and_excludes_drawings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_labels(tmp, [('7', '1893-1914')])
        # Missing applicability is excluded even when a label is complete.
        assert load_reviewed_labels(path) == {}
        with path.open(newline='') as handle:
            row = next(csv.DictReader(handle))
        for status in ('', 'partially', 'no', 'yes'):
            row['depicts_building'] = status
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            reviewed = load_reviewed_labels(path)
            assert bool(reviewed) == (status == 'yes')
            rows = [{'building_id': '7', 'drawing_flag': False},
                    {'building_id': '7', 'drawing_flag': True},
                    {'building_id': '7'}]
            assert with_reviewed_labels(rows, reviewed) == (rows[:1] if status == 'yes' else [])


def test_review_metadata_and_conflicting_duplicates_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_labels(tmp, [('7', '1893-1914')])
        with path.open(newline='') as handle:
            valid = next(csv.DictReader(handle))
        valid['depicts_building'] = 'yes'

        def write_rows(rows):
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(valid))
                writer.writeheader()
                writer.writerows(rows)

        for field, value in [('building_id', ''), ('reviewer', ' '),
                             ('evidence', ''), ('reviewed_at', ''),
                             ('reviewed_at', '2026-02-30'), ('confidence', 'certain'),
                             ('depicts_building', 'maybe')]:
            write_rows([dict(valid, **{field: value})])
            with unittest.TestCase().assertRaises(ValueError):
                load_reviewed_labels(path)
        write_rows([valid, valid])
        assert load_reviewed_labels(path) == {'7': '1893-1914'}
        for field, value in [('construction_era', 'pre-1850'),
                             ('reviewer', 'someone else'), ('evidence', 'different'),
                             ('depicts_building', 'no')]:
            write_rows([valid, dict(valid, **{field: value})])
            with unittest.TestCase().assertRaisesRegex(ValueError, 'conflicting duplicate'):
                load_reviewed_labels(path)


def test_unknown_drawing_flags_fail_closed_through_csv_join() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'manifest.csv'
        with path.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['building_id', 'filename', 'drawing_flag'])
            writer.writeheader()
            for index, flag in enumerate(('', 'unknown', '0', '1')):
                writer.writerow({'building_id': '7', 'filename': str(index), 'drawing_flag': flag})
        rows = load_manifest(path)
        assert [r['drawing_flag'] for r in rows] == [None, None, False, True]
        assert [r['filename'] for r in with_reviewed_labels(rows, {'7': '1893-1914'})] == ['2']


def load_tests(loader, tests, pattern):
    # These historically were bare functions: running this file did no tests.
    return unittest.TestSuite(unittest.FunctionTestCase(value)
                              for name, value in sorted(globals().items())
                              if name.startswith('test_') and callable(value))


if __name__ == '__main__':
    unittest.main()

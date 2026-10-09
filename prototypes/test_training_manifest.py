#!/usr/bin/env python3
"""Offline tests for the BALaT training-manifest exporter."""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("three-ages") / "export_training_manifest.py"
spec = importlib.util.spec_from_file_location("export_training_manifest", SCRIPT)
manifest = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(manifest)


def row(photo_id, **overrides):
    record = {
        "photo_id": photo_id, "preview": f"data/historical/balat/balat-{photo_id.lower()}.jpg",
        "preview_sha256": "abc", "facade_label": "Art Nouveau", "photo_date_taken": "1944",
        "fiche_urls": "https://monument.heritage.brussels/fr/x/1/101",
        "case_ids": "art_nouveau:101:1:0", "source_url": "https://balat.kikirpa.be/en/photo/X/",
        "image_url": "https://iiif.kikirpa.be/iiif/2/X/full/!800,800/0/default.jpg",
        "photo_page_title": "maison, Rue X 1", "credit": "KIK-IRPA, Brussels (Belgium), cliché X",
        "licence": "CC BY 4.0", "reviewer": "Reviewer", "reviewed_at": "2026-10-09",
        "confidence": "high", "facade_observation": "obs",
    }
    record.update(overrides)
    return record


class TrainingManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def export(self, rows):
        (self.tmp / "balat-photo-reviews.json").write_text(
            json.dumps({"record_count": len(rows), "records": rows}), encoding="utf-8")
        manifest.main(self.tmp)
        return json.loads((self.tmp / "balat-training-manifest.json").read_text(encoding="utf-8"))

    def test_exports_reviewed_row_with_stable_split(self):
        out = self.export([row("P1"), row("P2", fiche_urls="https://x/102")])
        self.assertEqual(out["record_count"], 2)
        self.assertEqual(out["excluded_count"], 0)
        first = self.export([row("P1")])
        self.assertEqual(first["records"][0]["split"], out["records"][0]["split"]
                         if out["records"][0]["photo_id"] == "P1" else
                         [r for r in out["records"] if r["photo_id"] == "P1"][0]["split"])

    def test_excludes_non_vocabulary_and_non_ccby_rows(self):
        out = self.export([
            row("P1", facade_label="pretty old house"),
            row("P2", licence="© KIK-IRPA/urban.brussels"),
            row("P3", reviewer=""),
            row("P4"),
        ])
        self.assertEqual(out["record_count"], 1)
        self.assertEqual(out["records"][0]["photo_id"], "P4")
        self.assertEqual(sorted(out["excluded_photo_ids"]), ["P1", "P2", "P3"])

    def test_accepts_historical_vocabulary_terms(self):
        out = self.export([row("P1", facade_label="Louis XIV")])
        self.assertEqual(out["record_count"], 1)


if __name__ == "__main__":
    unittest.main()

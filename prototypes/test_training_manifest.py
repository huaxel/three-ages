#!/usr/bin/env python3
"""Offline tests for the BALaT training-manifest exporter."""
from __future__ import annotations

import csv
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

    def export(self, rows, adjudications=None, independent_rows=None):
        balat_rows = [item for item in rows if not item["photo_id"].startswith("commons-")]
        commons_rows = [item for item in rows if item["photo_id"].startswith("commons-")]
        for filename, selected in (("balat-photo-reviews.json", balat_rows), ("commons-photo-reviews.json", commons_rows)):
            (self.tmp / filename).write_text(json.dumps({"record_count": len(selected), "records": selected}), encoding="utf-8")
        independent_rows = independent_rows or [
            {"photo_id": item["photo_id"], "identity_verdict": "confirmed",
             "facade_label": item.get("facade_label", ""), "facade_observation": "independent observation",
             "reviewer": "Reviewer B", "reviewed_at": "2026-10-10"}
            for item in rows
        ]
        adjudications = adjudications or [
            {"photo_id": item["photo_id"], "agreement": "agree", "rationale": "Both reviews support the label.",
             "disposition": "Use resolved label.", "adjudicator": "Reviewer C", "adjudicated_at": "2026-10-10",
             "resolved_facade_label": item.get("facade_label", ""), "primary_reviewer": item.get("reviewer", ""),
             "primary_annotation": f"facade_label: {item.get('facade_label', '')}\nfacade_observation: {item.get('facade_observation', '')}",
             "independent_reviewer": "Reviewer B", "independent_reviewed_at": "2026-10-10",
             "independent_annotation": f"identity_verdict: confirmed\nfacade_label: {item.get('facade_label', '')}\nfacade_observation: independent observation"}
            for item in rows
        ]
        independent_fields = ["photo_id", "identity_verdict", "facade_label", "facade_observation", "reviewer", "reviewed_at"]
        for filename, selected in (
            ("balat-independent-photo-review.csv", [item for item in independent_rows if not item["photo_id"].startswith("commons-")]),
            ("commons-independent-photo-review.csv", [item for item in independent_rows if item["photo_id"].startswith("commons-")]),
        ):
            with (self.tmp / filename).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=independent_fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(selected)
        adjudication_fields = list(adjudications[0]) if adjudications else ["photo_id"]
        for filename, selected in (
            ("balat-photo-adjudication.csv", [item for item in adjudications if not item["photo_id"].startswith("commons-")]),
            ("commons-photo-adjudication.csv", [item for item in adjudications if item["photo_id"].startswith("commons-")]),
        ):
            with (self.tmp / filename).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=adjudication_fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(selected)
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

    def test_excludes_ineligible_photos_even_when_labeled(self):
        out = self.export([row("P1", label_eligibility="ineligible",
                               label_eligibility_reason="photo predates building")])
        self.assertEqual(out["record_count"], 0)
        self.assertEqual(out["excluded_photo_ids"], ["P1"])

    def test_accepts_historical_vocabulary_terms(self):
        out = self.export([row("P1", facade_label="Louis XIV")])
        self.assertEqual(out["record_count"], 1)

    def test_requires_independent_resolution_and_uses_resolved_label(self):
        photo = row("P1")
        no_adjudication = {"photo_id": "P1", "agreement": "agree"}
        out = self.export([photo], [no_adjudication])
        self.assertEqual(out["record_count"], 0)
        complete = {"photo_id": "P1", "agreement": "disagree", "rationale": "Independent label differs.",
                    "disposition": "Accept the independent label.", "adjudicator": "Reviewer C",
                    "adjudicated_at": "2026-10-10", "resolved_facade_label": "Eclecticism",
                    "primary_reviewer": "Reviewer", "primary_annotation": "facade_label: Art Nouveau\nfacade_observation: obs",
                    "independent_reviewer": "Reviewer B", "independent_reviewed_at": "2026-10-10",
                    "independent_annotation": "identity_verdict: confirmed\nfacade_label: Eclecticism\nfacade_observation: independent observation"}
        second = {"photo_id": "P1", "identity_verdict": "confirmed", "facade_label": "Eclecticism",
                  "facade_observation": "independent observation", "reviewer": "Reviewer B", "reviewed_at": "2026-10-10"}
        out = self.export([photo], [complete], [second])
        self.assertEqual(out["record_count"], 1)
        self.assertEqual(out["records"][0]["facade_label"], "Eclecticism")
        self.assertEqual(out["records"][0]["adjudication"]["independent_reviewer"], "Reviewer B")
        stale = {**second, "facade_observation": "changed after adjudication"}
        out = self.export([photo], [complete], [stale])
        self.assertEqual(out["record_count"], 0)

    def test_accepts_open_commons_licences_with_sharealike_flag(self):
        out = self.export([
            row("commons-a", licence="CC BY-SA 4.0", preview="data/historical/commons/commons-a.jpg"),
            row("commons-b", licence="CC0", preview="data/historical/commons/commons-b.jpg"),
            row("commons-c", licence="© Some Photographer"),
        ])
        self.assertEqual(out["record_count"], 2)
        by_id = {r["photo_id"]: r for r in out["records"]}
        self.assertEqual(by_id["commons-a"]["sharealike"], "yes")
        self.assertEqual(by_id["commons-b"]["sharealike"], "no")
        self.assertEqual(out["excluded_photo_ids"], ["commons-c"])


if __name__ == "__main__":
    unittest.main()

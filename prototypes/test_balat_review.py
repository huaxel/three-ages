#!/usr/bin/env python3
"""Offline tests for the BALaT photo-review worksheet pipeline."""
from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("three-ages") / "export_balat_review.py"
spec = importlib.util.spec_from_file_location("export_balat_review", SCRIPT)
review = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(review)


def case(case_id, photo_id, **overrides):
    record = {
        "case_id": case_id, "street": "Rue Haute", "number": "13",
        "class": "Baroque", "selection_class": "baroque", "source_style": "Baroque",
        "built": None, "lon": 4.35, "lat": 50.84,
        "fiche": "https://monument.heritage.brussels/fr/x/13/1",
        "matched": True, "photo_id": photo_id,
        "photo_page_title": "maison, Rue Haute 13",
        "photo_date_taken": "1944", "photo_represented_detail": "facade",
        "photo_view_scope": "facade",
        "credit_line": "KIK-IRPA, Brussels (Belgium), cliché X",
        "source_url": f"https://balat.kikirpa.be/en/photo/{photo_id}/",
        "image_url": f"https://iiif.kikirpa.be/iiif/2/{photo_id}/full/!800,800/0/default.jpg",
        "preview": f"data/historical/balat/balat-{photo_id.lower()}.jpg",
        "preview_sha256": "abc123", "licence": "CC BY 4.0",
    }
    record.update(overrides)
    return record


class BalatReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.data.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_provenance(self, records):
        (self.data / "balat-photo-provenance.json").write_text(
            json.dumps({"batch": "test", "records": records,
                        "coverage": review.coverage_report(records, "test")}
                       if hasattr(review, "coverage_report") else
                       {"batch": "test", "records": records}),
            encoding="utf-8")

    def test_collapses_shared_photo_and_compiles_completed_rows(self):
        self.write_provenance([case("baroque:1:13:0", "P1"), case("baroque:1:15:1", "P1", number="15"),
                               case("baroque:2:77:0", "P2", street="Rue Basse", number="77")])
        review.main(self.data)
        with (self.data / "balat-photo-review.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        shared = next(r for r in rows if r["photo_id"] == "P1")
        self.assertIn("13", shared["addresses"])
        self.assertIn("15", shared["addresses"])
        self.assertEqual(shared["annotation_status"], "pending reviewer annotation")
        compiled = json.loads((self.data / "balat-photo-reviews.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["record_count"], 0)

        # Complete one review and regenerate: fields preserved and compiled.
        rows[0]["facade_label"] = "Baroque"
        rows[0]["reviewer"] = "Test Reviewer"
        rows[0]["confidence"] = "high"
        with (self.data / "balat-photo-review.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(review.ALL_COLUMNS), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        review.main(self.data)
        compiled = json.loads((self.data / "balat-photo-reviews.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["record_count"], 1)
        self.assertEqual(compiled["records"][0]["facade_label"], "Baroque")

    def test_refuses_review_after_provenance_change(self):
        self.write_provenance([case("baroque:1:13:0", "P1")])
        review.main(self.data)
        with (self.data / "balat-photo-review.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["facade_label"] = "Baroque"
        with (self.data / "balat-photo-review.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(review.ALL_COLUMNS), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        self.write_provenance([case("baroque:1:13:0", "P1", preview_sha256="changed")])
        with self.assertRaisesRegex(RuntimeError, "after provenance changed"):
            review.main(self.data)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Offline tests for the Commons photo-review worksheet pipeline."""
from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("three-ages") / "export_commons_review.py"
spec = importlib.util.spec_from_file_location("export_commons_review", SCRIPT)
review = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(review)


def case(case_id, photo_id, **overrides):
    record = {
        "case_id": case_id, "photo_id": photo_id,
        "commons_file": "Example 13.jpg",
        "street": "Rue Haute", "number": "13",
        "class_suggestion": "Baroque", "source_style": "Baroque", "built": None,
        "fiche": "https://monument.heritage.brussels/fr/x/13/1",
        "matched": True, "title": "Example 13.jpg",
        "photo_view_scope": "facade",
        "agent_verdict": "accept", "agent_verdict_reason": "full facade",
        "credit": "Example Contributor",
        "licence": "CC BY-SA 4.0", "sharealike": "yes",
        "attribution": "Example 13.jpg — Example Contributor (CC BY-SA 4.0)",
        "source_url": "https://commons.wikimedia.org/wiki/File:Example_13.jpg",
        "image_url": "https://upload.wikimedia.org/example.jpg",
        "preview": "data/historical/commons/commons-example-13.jpg",
        "preview_sha256": "abc123",
    }
    record.update(overrides)
    return record


class CommonsReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.data.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_provenance(self, records):
        (self.data / "commons-photo-provenance.json").write_text(
            json.dumps({"batch": "test", "records": records}), encoding="utf-8")

    def test_collapses_shared_photo_and_compiles_completed_rows(self):
        self.write_provenance([case("commons-a:13", "commons-a"), case("commons-a:15", "commons-a", number="15"),
                               case("commons-b:77", "commons-b", street="Rue Basse", number="77")])
        review.main(self.data)
        with (self.data / "commons-photo-review.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        shared = next(r for r in rows if r["photo_id"] == "commons-a")
        self.assertIn("13", shared["addresses"])
        self.assertIn("15", shared["addresses"])
        self.assertEqual(shared["sharealike"], "yes")
        self.assertEqual(shared["annotation_status"], "pending reviewer annotation")
        compiled = json.loads((self.data / "commons-photo-reviews.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["record_count"], 0)

        rows[0]["facade_label"] = "Baroque"
        rows[0]["reviewer"] = "Test Reviewer"
        rows[0]["confidence"] = "high"
        with (self.data / "commons-photo-review.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(review.ALL_COLUMNS), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        review.main(self.data)
        compiled = json.loads((self.data / "commons-photo-reviews.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["record_count"], 1)
        self.assertEqual(compiled["records"][0]["facade_label"], "Baroque")

    def test_refuses_review_after_provenance_change(self):
        self.write_provenance([case("commons-a:13", "commons-a")])
        review.main(self.data)
        with (self.data / "commons-photo-review.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["facade_label"] = "Baroque"
        with (self.data / "commons-photo-review.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(review.ALL_COLUMNS), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        self.write_provenance([case("commons-a:13", "commons-a", preview_sha256="changed")])
        with self.assertRaisesRegex(RuntimeError, "after provenance changed"):
            review.main(self.data)


if __name__ == "__main__":
    unittest.main()

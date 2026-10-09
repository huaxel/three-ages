#!/usr/bin/env python3
"""Tests for deterministic, building-deduplicated Irismonument samples."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import map_irismonument_corpus as mapper  # noqa: E402


class IrismonumentSelectionTests(unittest.TestCase):
    def test_prefers_primary_fiche_address_and_deduplicates_buildings(self):
        candidates = [
            {"id": "1", "street": "Rue A", "number": "7", "fiche": "https://example/9/1", "lon": 4.0, "lat": 50.0},
            {"id": "1", "street": "Rue A", "number": "9", "fiche": "https://example/9/1", "lon": 4.1, "lat": 50.1},
            {"id": "2", "street": "Rue B", "number": "2", "fiche": "https://example/2/2"},
        ]
        sample, unique_count = mapper.sample_buildings(candidates)
        self.assertEqual(unique_count, 2)
        self.assertEqual(len(sample), 2)
        self.assertEqual(next(c for c in sample if c["id"] == "1")["number"], "9")

    def test_evenly_spreads_unique_cases_across_year_and_id_order(self):
        candidates = [
            {"id": str(i), "street": f"Rue {i}", "number": "1", "built": str(1900 + 10 * i),
             "fiche": f"https://example/1/{i}"}
            for i in range(5)
        ]
        sample, unique_count = mapper.sample_buildings(candidates, limit=3)
        self.assertEqual(unique_count, 5)
        self.assertEqual([c["id"] for c in sample], ["0", "2", "4"])

    def test_single_sample_selects_middle_candidate(self):
        candidates = [{"id": str(i), "built": str(1900 + i), "fiche": f"https://example/1/{i}"} for i in range(5)]
        sample, _ = mapper.sample_buildings(candidates, limit=1)
        self.assertEqual(sample[0]["id"], "2")

    def test_additional_sample_avoids_first_stage_buildings(self):
        candidates = [{"id": str(i), "fiche": f"https://example/1/{i}"} for i in range(5)]
        first, _ = mapper.sample_buildings(candidates, limit=2)
        first_ids = {candidate["id"] for candidate in first}
        second, remaining = mapper.sample_buildings(candidates, limit=3, exclude_ids=first_ids)
        self.assertEqual(remaining, 3)
        self.assertTrue({candidate["id"] for candidate in second}.isdisjoint(first_ids))
        self.assertEqual(len(second), 3)


if __name__ == "__main__":
    unittest.main()

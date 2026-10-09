#!/usr/bin/env python3
"""Offline tests for BALaT matching and corpus coverage accounting."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("fetch_balat_photos.py")
spec = importlib.util.spec_from_file_location("fetch_balat_photos", SCRIPT)
balat = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(balat)


class BalatAcquisitionTests(unittest.TestCase):
    def test_seroval_encoder_uses_current_primitive_tags_and_container_ids(self):
        encoded = balat.seroval_envelope({"enabled": True, "count": 2, "none": None})
        self.assertEqual(encoded["f"], 127)
        self.assertEqual(encoded["m"], [])
        self.assertEqual(encoded["t"], {
            "t": 10, "i": 0,
            "p": {"k": ["data"], "v": [{
                "t": 10, "i": 1,
                "p": {"k": ["enabled", "count", "none"], "v": [
                    {"t": 2, "s": 2}, {"t": 0, "s": 2}, {"t": 2, "s": 0},
                ]},
                "o": 0,
            }]},
            "o": 0,
        })

    def test_photo_metadata_requires_visible_cc_by_and_captures_credit(self):
        original_get_body = balat.get_body
        balat._PHOTO_METADATA_CACHE.clear()
        balat.get_body = lambda url: (
            b'<span>Title</span><span><span>maison, Rue Haute 6</span></span>'
            b'<span>Date taken</span><span><span>1942</span></span>'
            b'<span>Represented detail</span><span>fa\xc3\xa7ade principale</span>'
            b'<span>Credit line</span><span>KIK-IRPA, Brussels (Belgium), clich\xc3\xa9 T000001</span>'
            b'<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>'
        )
        try:
            metadata = balat.photo_metadata("T000001")
        finally:
            balat.get_body = original_get_body
            balat._PHOTO_METADATA_CACHE.clear()
        self.assertEqual(metadata["title"], "maison, Rue Haute 6")
        self.assertEqual(metadata["date_taken"], "1942")
        self.assertEqual(metadata["represented_detail"], "façade principale")
        self.assertEqual(metadata["credit_line"], "KIK-IRPA, Brussels (Belgium), cliché T000001")
        self.assertEqual(metadata["licence"], "CC BY 4.0")

    def test_view_scope_does_not_mistake_door_details_for_full_facades(self):
        self.assertEqual(balat.view_scope("façade principale à front de rue"), "facade")
        self.assertEqual(balat.view_scope("vue partielle de la façade principale"), "partial-facade")
        self.assertEqual(balat.view_scope("façade principale: porte d'entrée"), "detail")
        self.assertEqual(balat.view_scope("Porche"), "detail")
        self.assertEqual(balat.view_scope(""), "not-stated")

    def test_address_requires_street_and_whole_house_number(self):
        score = balat.match_score
        self.assertEqual(score("Rue Haute", "6", "Maison, Rue Haute 6, Bruxelles"), 4)
        self.assertEqual(score("Rue Haute", "6", "Maison, Rue Haute 16, Bruxelles"), 0)
        self.assertEqual(score("Rue Haute", "6", "Maison, Rue Haute 60, Bruxelles"), 0)
        self.assertEqual(score("Rue Haute", "6", "Maison, Rue Haute, Bruxelles"), 0)
        self.assertEqual(score("Rue Haute", "21-22", "Rue Haute 21–22, Bruxelles"), 4)
        self.assertEqual(score("Rue Haute", "6", "Rue Basse 6, Bruxelles"), 0)
        self.assertEqual(score("Place du Nouveau Marché aux Grains", "8", "place du Nouveau-Marché-aux-Grains 8 - rue Antoine Dansaert 92"), 4)
        self.assertEqual(score("Petite rue de l'Eglise", "12", "maison, Petite rue de l’Eglise 12"), 4)
        self.assertEqual(score("Rue Haute", "6", "Rue Haute 6-8, Bruxelles"), 4)
        self.assertEqual(score("Rue Haute", "6", "Rue Haute 16, Bruxelles"), 0)

    def test_selection_loader_uses_only_bounded_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection.json"
            path.write_text(json.dumps({"classes": {
                "eclectic": {"label": "Eclecticism", "sample": [
                    {"id": "1", "street": "Rue A", "number": "1", "fiche": "url"},
                    {"id": "2", "street": "Rue B", "number": "2", "fiche": "url"},
                ]},
                "deco": {"label": "Art Deco", "sample": [
                    {"id": "3", "street": "Rue C", "number": "3", "fiche": "url"},
                ]},
            }}), encoding="utf-8")
            cases = balat.load_selection(path, limit_per_class=1)
            next_cases = balat.load_selection(path, limit_per_class=1, offset_per_class=1)
            with self.assertRaises(ValueError):
                balat.load_selection(path, sample_field="unknown")
        self.assertEqual(len(cases), 2)
        self.assertEqual([case["class_label"] for case in cases], ["Eclecticism", "Art Deco"])
        self.assertEqual(cases[0]["case_id"], "eclectic:1:1:0")
        self.assertEqual([case["case_id"] for case in next_cases], ["eclectic:2:2:1"])

    def test_coverage_keeps_unmatched_and_undownloaded_counts_visible(self):
        result = balat.coverage_report([
            {"class": "Art Deco", "matched": True, "preview_sha256": "abc", "photo_id": "P1", "fiche": "https://x/101", "photo_view_scope": "facade"},
            {"class": "Art Deco", "matched": False, "fiche": "https://x/101"},
            {"class": "Brutalism", "matched": True, "fiche": "https://x/202"},
        ], "test")
        self.assertEqual(result["total_cases"], 3)
        self.assertEqual(result["unique_buildings"], 2)
        self.assertEqual(result["unique_photos"], 1)
        self.assertEqual(result["unique_photo_view_scopes"], {"facade": 1})
        self.assertEqual(result["classes"]["Art Deco"], {
            "cases": 2, "matched": 1, "downloaded": 1, "view_scope_counts": {"facade": 1}, "unique_buildings": 1, "unique_photos": 1,
        })
        self.assertEqual(result["classes"]["Brutalism"], {
            "cases": 1, "matched": 1, "downloaded": 0, "view_scope_counts": {}, "unique_buildings": 1, "unique_photos": 0,
        })


if __name__ == "__main__":
    unittest.main()

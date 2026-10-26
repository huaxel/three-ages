#!/usr/bin/env python3
"""Shared data definitions for the facade-epoch probes.

Pure standard library: importable without torch or sklearn so the offline
test suite and the prototype gate stay light. Heavy dependencies live only in
build_embeddings.py and train_probe.py; see requirements-ml.txt.

Discipline carried over from the annotation spec: source-derived fields are
proxies, not labels. The construction-era head has bins and candidate fields
defined here but no training-grade label; train_probe.py refuses to train it
without a human-reviewed labels file.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path

# Ordered oldest-first so "within one era" is meaningful.
CAPTURE_ERAS = ["pre-1900", "1900-1929", "1930-1959", "1960-1989", "1990-2009", "2010+"]

# Construction eras follow Brussels building history, not round numbers.
# Wartime years 1915-1917 and 1941-1944 belong to no bin: bin_of() returns ''
# so a 1943 construction (bridge 39723, opened 23.12.1943) stays unresolved
# instead of silently joining a neighbouring era.
CONSTRUCTION_ERAS = ["pre-1850", "1850-1892", "1893-1914", "1918-1940", "1945-1975", "post-1975"]


def load_reviewed_labels(path: str | Path, *, labels_only: bool = False) -> dict[str, str]:
    """Read validated construction reviews, failing closed on applicability.

    By default only explicit ``depicts_building=yes`` is eligible. This is an
    interim BUILDING-level gate, not evidence that each image was reviewed.
    ``labels_only=True`` reads building source truth without this interim gate.
    Training may use it only together with the stronger per-image applicability
    contract; it is never sufficient by itself. Metadata validation always applies.
    Identical duplicate reviews coalesce; conflicting duplicates are rejected.
    """
    reviewed: dict[str, str] = {}
    seen: dict[str, tuple[str, ...]] = {}
    fields = ("construction_era", "evidence", "reviewer", "reviewed_at",
              "confidence", "depicts_building", "phase_years")
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            bid = (row.get("building_id") or "").strip()
            values = {key: (row.get(key) or "").strip() for key in fields}
            era = values["construction_era"]
            if not bid:
                raise ValueError("review needs nonempty building_id")
            if era not in CONSTRUCTION_ERAS:
                raise ValueError(f"unknown construction_era {era!r} for {bid!r}")
            for key in ("evidence", "reviewer", "reviewed_at"):
                if not values[key]:
                    raise ValueError(f"missing {key} for {bid!r}")
            try:
                datetime.fromisoformat(values["reviewed_at"].replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"invalid reviewed_at for {bid!r}") from exc
            if values["confidence"] not in {"low", "medium", "high"}:
                raise ValueError(f"invalid confidence for {bid!r}")
            if values["depicts_building"] not in {"", "yes", "partially", "no"}:
                raise ValueError(f"invalid depicts_building for {bid!r}")
            signature = tuple(values[key] for key in fields)
            if bid in seen and seen[bid] != signature:
                raise ValueError(f"conflicting duplicate building_id {bid!r}")
            seen[bid] = signature
            if labels_only or values["depicts_building"] == "yes":
                reviewed[bid] = era
    return reviewed


def with_reviewed_labels(rows: list[dict], reviewed: dict[str, str], *,
                         labels_only: bool = False) -> list[dict]:
    """Join eligible reviews; construction training also excludes drawings.

    This source join is not a complete image-eligibility check. Construction
    training must additionally apply construction_image_reviews. Missing drawing
    status fails closed. Explicit ``labels_only=True`` is for label analysis.
    """
    return [r for r in rows if r["building_id"] in reviewed
            and (labels_only or r.get("drawing_flag") is False)]

# Style families compress the source's 43 styles (long tail below n=50) into
# heads with support. Raw per-record styles stay in the manifest; families are
# the training target. Boundaries are reviewable, not canonical.
STYLE_FAMILIES: dict[str, str] = {}
for _family, _members in {
    "eclectic": ["Éclectisme", "Éclectisme tardif", "Historicisme"],
    "neoclassical": ["Néoclassicisme", "Néoclassicisme (du 18e siècle)", "Empire",
                     "Second Empire", "Louis-Philippe"],
    "beauxarts": ["Beaux-Arts"],
    "art_nouveau": ["Art nouveau", "Sécession viennoise", "École d'Amsterdam"],
    "art_deco": ["Art Déco", "Paquebot", "Classicisme moderne"],
    "modernist": ["Modernisme", "Fonctionnalisme", "Pré-modernisme", "Nieuwe eenvoud"],
    "brutalist_contemporary": ["Brutalisme", "Postmodernisme", "Architecture high-tech",
                               "Architecture d'intégration"],
    "neo_medieval": ["Néogothique", "Néo-roman", "Gothique", "Roman"],
    "neo_renaissance": ["Néo-Renaissance", "Néo-Renaissance flamande", "Renaissance flamande"],
    "baroque": ["Baroque", "Néo-baroque", "Baroque classicisant", "Rococo", "Régence"],
    "traditional": ["Architecture traditionnelle", "Architecture traditionaliste",
                    "Architecture pittoresque", "Architecture régionaliste", "Architecture rurale"],
    "other": ["Mauresque", "Néo-égyptien", "Néo-byzantin"],
}.items():
    for _style in _members:
        STYLE_FAMILIES[_style] = _family
del _family, _members, _style

FAMILY_NAMES = sorted(set(STYLE_FAMILIES.values()))

LABEL_VALUES = ("photo", "drawing", "mixed", "unusable")


def capture_era(year: int | None) -> str:
    """Map a caption year to its capture-era bin; '' when undated."""
    if year is None:
        return ""
    if year < 1900:
        return "pre-1900"
    if year < 1930:
        return "1900-1929"
    if year < 1960:
        return "1930-1959"
    if year < 1990:
        return "1960-1989"
    if year < 2010:
        return "1990-2009"
    return "2010+"


def style_family(style: str) -> str:
    """Map a source style value to its family; unseen values fall to 'other'."""
    return STYLE_FAMILIES.get(style, "other")


def split_of(building_id: str) -> str:
    """Deterministic building-level split, stable as the crawl grows.

    Same sha256 rule used when the manifest was built: 80 train / 10 val / 10 test.
    """
    bucket = int(hashlib.sha256(building_id.encode()).hexdigest(), 16) % 100
    if bucket < 10:
        return "test"
    if bucket < 20:
        return "val"
    return "train"


def _typed_row(raw: dict) -> dict:
    year = raw.get("caption_year") or ""
    return {
        "building_id": raw["building_id"],
        "municipality": raw.get("municipality", ""),
        "filename": raw["filename"],
        "source_filename": raw.get("source_filename") or raw["filename"],
        "sequence_id": (raw.get("sequence_id") or "").strip(),
        "caption": raw.get("caption", ""),
        "caption_year": int(year) if str(year).strip().isdigit() else None,
        "capture_era": raw.get("capture_era", ""),
        "drawing_flag": ({"0": False, "1": True}.get(str(raw.get("drawing_flag", "")).strip())),
        "styles": [s for s in (raw.get("styles") or "").split("|") if s],
        "families": sorted({style_family(s) for s in (raw.get("styles") or "").split("|") if s}),
        "contributor_years": raw.get("contributor_years", ""),
        "latitude": raw.get("latitude", ""),
        "longitude": raw.get("longitude", ""),
        "split": raw.get("split") or split_of(raw["building_id"]),
    }


def load_manifest(path: str | Path) -> list[dict]:
    """Read the training manifest with light typing; caption_year -> int|None.

    One row per physical file: filenames are the collision-aware disk names
    written by build_manifest, so distinct digital objects sharing a raw name
    are already distinct rows. No dedupe here -- an earlier version dropped
    same-named listings as duplicates, but 571 such groups checked out as
    different URLs and different bytes (2026-10-20), i.e. real pictures.
    """
    with open(path, newline="", encoding="utf-8") as handle:
        return [_typed_row(raw) for raw in csv.DictReader(handle)]

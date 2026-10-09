#!/usr/bin/env python3
"""Export reviewer-completed BALaT photo labels as a training manifest.

Reads data/balat-photo-reviews.json (compiled completed rows) and writes
data/balat-training-manifest.json: one record per reviewed photo with image
reference + SHA-256, vocabulary label, capture epoch, provenance and reviewer
fields, licence matrix entry, and a deterministic building-grouped split
assignment (all cases of one heritage fiche share one split, so epochs of a
building never straddle train/eval).

Gates (refuse rather than guess):
- facade_label must be a signed-off vocabulary term (CLASS_LABELS values or
  the six Grand Place historical terms in docs/facade-style-vocabulary.md);
- licence must be exactly "CC BY 4.0" (the KIK-IRPA BALaT route; anything
  else, including SPRB-agent inventory photos, is excluded);
- preview SHA-256 and reviewer identity must be present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REVIEWS = DATA / "balat-photo-reviews.json"
MANIFEST = DATA / "balat-training-manifest.json"

CLASS_LABELS = (
    "Baroque", "Baroque with classical features", "Neoclassical", "Second Empire",
    "Eclecticism", "Historicist neo-styles", "Beaux-Arts", "Art Nouveau", "Art Deco",
    "Paquebot style", "Functionalism", "Modernism (interwar)", "Modernism (post-war)",
    "Modernism (Expo 58)", "Modernism (late)", "Modernism (period undetermined)",
    "Brutalism", "Postmodernism", "Contemporary",
)
# Grand Place historical terms (docs/facade-style-vocabulary.md, signed off 2026-10-09).
HISTORICAL_TERMS = (
    "Louis XIV", "Antique classical orders", "Mixed Antique+Baroque",
    "Baroque with Renaissance elements",
)
ALLOWED_LABELS = frozenset(CLASS_LABELS + HISTORICAL_TERMS + (
    "Baroque", "Baroque with classical features"))
REQUIRED_LICENCE = "CC BY 4.0"
EVAL_FRACTION = 0.2


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def split_for(group_key: str) -> str:
    """Deterministic building-grouped split: stable across runs and machines."""
    digest = hashlib.sha256(group_key.encode("utf-8")).hexdigest()
    threshold = int(0x100000000 * EVAL_FRACTION)
    return "eval" if int(digest[:8], 16) < threshold else "train"


def manifest_record(row: dict) -> dict | None:
    """Return a manifest record, or None when the row fails a gate (reported)."""
    label = (row.get("facade_label") or "").strip()
    if label not in ALLOWED_LABELS:
        return None
    if (row.get("licence") or "") != REQUIRED_LICENCE:
        return None
    if not (row.get("preview_sha256") or "").strip() or not (row.get("reviewer") or "").strip():
        return None
    group_key = (row.get("fiche_urls") or row.get("photo_id") or "").split(";")[0].strip()
    return {
        "photo_id": row.get("photo_id"),
        "image": row.get("preview"),
        "sha256": row.get("preview_sha256"),
        "facade_label": label,
        "epoch": row.get("photo_date_taken") or "",
        "split": split_for(group_key),
        "split_group": group_key,
        "provenance": {
            "source_url": row.get("source_url"),
            "image_url": row.get("image_url"),
            "title": row.get("photo_page_title"),
            "credit": row.get("credit"),
        },
        "licence": {"photo": row.get("licence"), "metadata": "CC0 (BALaT descriptive metadata)"},
        "reviewer": row.get("reviewer"),
        "reviewed_at": row.get("reviewed_at") or "",
        "confidence": row.get("confidence") or "",
        "facade_observation": row.get("facade_observation") or "",
    }


def main(data_dir: Path = DATA) -> None:
    reviews = json.loads((data_dir / "balat-photo-reviews.json").read_text(encoding="utf-8"))
    rows = reviews.get("records", [])
    records, excluded = [], []
    for row in rows:
        record = manifest_record(row)
        (records if record else excluded).append(record or row.get("photo_id"))
    # Split-safety invariant: one group, one split.
    group_splits = {}
    for record in records:
        group_splits.setdefault(record["split_group"], set()).add(record["split"])
    require(all(len(splits) == 1 for splits in group_splits.values()),
            "building group straddles train/eval")
    payload = {
        "source": "reviewer-completed BALaT labels; CC BY 4.0 photos only; building-grouped splits",
        "record_count": len(records),
        "excluded_count": len(excluded),
        "excluded_photo_ids": sorted(excluded),
        "records": sorted(records, key=lambda r: (r["split"], r["photo_id"])),
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                     dir=data_dir, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, data_dir / "balat-training-manifest.json")
    print(f"manifest: {len(records)} records ({len(excluded)} excluded) -> {MANIFEST.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()
    sys.exit(main(args.data_dir))

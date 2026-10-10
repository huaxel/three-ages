#!/usr/bin/env python3
"""Export reviewer-completed photo labels as a training manifest.

Reads data/balat-photo-reviews.json and data/commons-photo-reviews.json
(compiled completed rows) and writes data/balat-training-manifest.json: one
record per reviewed photo with image reference + SHA-256, vocabulary label,
capture epoch, provenance and reviewer fields, licence matrix entry, and a
deterministic building-grouped split assignment (all cases of one heritage
fiche share one split, so epochs of a building never straddle train/eval).

Gates (refuse rather than guess):
- facade_label must be a signed-off vocabulary term (CLASS_LABELS values or
  the six Grand Place historical terms in docs/facade-style-vocabulary.md);
- licence must be exactly "CC BY 4.0" for BALaT rows (the KIK-IRPA route;
  anything else, including SPRB-agent inventory photos, is excluded) or a
  pinned open licence for Commons rows (ShareAlike flagged; weights
  publication needs care);
- preview SHA-256 and reviewer identity must be present;
- independent reviewer must differ from the primary reviewer, and a complete
  agreement/rationale/disposition with a resolved vocabulary label is required.
"""
from __future__ import annotations

import argparse
import csv
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
# Commons files enter under their own per-file open licence (pinned at
# acquisition). ShareAlike files ride with a flag; publishing model weights
# trained on them needs care (see the licence doc) and stays an owner call.
COMMONS_LICENCES = frozenset({
    "CC BY 4.0", "CC BY 3.0", "CC BY 2.0",
    "CC BY-SA 4.0", "CC BY-SA 3.0", "CC0", "Public domain",
})
EVAL_FRACTION = 0.2


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_unique_csv_index(path: Path, key_field: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or key_field not in reader.fieldnames:
            raise RuntimeError(f"{path.name} is missing required key column {key_field}")
        indexed = {}
        for row in reader:
            key = (row.get(key_field) or "").strip()
            if not key or key in indexed:
                raise RuntimeError(f"{path.name} contains missing or duplicate {key_field}: {key}")
            indexed[key] = row
    return indexed


def split_for(group_key: str) -> str:
    """Deterministic building-grouped split: stable across runs and machines."""
    digest = hashlib.sha256(group_key.encode("utf-8")).hexdigest()
    threshold = int(0x100000000 * EVAL_FRACTION)
    return "eval" if int(digest[:8], 16) < threshold else "train"


def manifest_record(row: dict, adjudication: dict | None = None,
                    independent: dict | None = None) -> dict | None:
    """Return a manifest record only after a current independent disposition."""
    adjudication = adjudication or {}
    independent = independent or {}
    label = (adjudication.get("resolved_facade_label") or "").strip()
    if label not in ALLOWED_LABELS:
        return None
    is_commons = (row.get("photo_id") or "").startswith("commons-")
    licence = row.get("licence") or ""
    if is_commons:
        if licence not in COMMONS_LICENCES:
            return None
    elif licence != REQUIRED_LICENCE:
        return None
    if (row.get("label_eligibility") or "eligible") != "eligible":
        return None
    if not (row.get("preview_sha256") or "").strip() or not (row.get("reviewer") or "").strip():
        return None
    if (adjudication.get("agreement") or "") not in {"agree", "partial", "disagree"}:
        return None
    if not all((adjudication.get(field) or "").strip() for field in (
            "rationale", "disposition", "adjudicator", "adjudicated_at",
            "primary_reviewer", "independent_reviewer", "independent_reviewed_at", "primary_annotation",
            "independent_annotation")):
        return None
    if adjudication.get("primary_reviewer") == adjudication.get("independent_reviewer"):
        return None
    primary_text = "\n".join(
        f"{field}: {(row.get(field) or '').strip()}"
        for field in ("facade_label", "facade_observation")
        if (row.get(field) or "").strip())
    independent_text = "\n".join(
        f"{field}: {(independent.get(field) or '').strip()}"
        for field in ("identity_verdict", "facade_label", "facade_observation")
        if (independent.get(field) or "").strip())
    if (adjudication.get("primary_reviewer") != row.get("reviewer")
            or adjudication.get("primary_annotation") != primary_text
            or adjudication.get("independent_reviewer") != independent.get("reviewer")
            or adjudication.get("independent_reviewed_at") != independent.get("reviewed_at")
            or adjudication.get("independent_annotation") != independent_text):
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
        "licence": {"photo": row.get("licence"), "metadata": (
            "per-file Commons licence; see file page" if is_commons
            else "CC0 (BALaT descriptive metadata)")},
        "sharealike": "yes" if "BY-SA" in (row.get("licence") or "") else "no",
        "reviewer": row.get("reviewer"),
        "reviewed_at": row.get("reviewed_at") or "",
        "confidence": row.get("confidence") or "",
        "facade_observation": row.get("facade_observation") or "",
        "adjudication": {
            "agreement": adjudication["agreement"],
            "rationale": adjudication["rationale"],
            "disposition": adjudication["disposition"],
            "primary_reviewer": adjudication["primary_reviewer"],
            "independent_reviewer": adjudication["independent_reviewer"],
            "independent_reviewed_at": adjudication["independent_reviewed_at"],
            "independent_annotation": adjudication["independent_annotation"],
            "adjudicator": adjudication["adjudicator"],
            "adjudicated_at": adjudication["adjudicated_at"],
        },
    }


def main(data_dir: Path = DATA) -> None:
    rows = []
    for name, adjudication_name, independent_name in (
        ("balat-photo-reviews.json", "balat-photo-adjudication.csv", "balat-independent-photo-review.csv"),
        ("commons-photo-reviews.json", "commons-photo-adjudication.csv", "commons-independent-photo-review.csv"),
    ):
        path = data_dir / name
        adjudication_path = data_dir / adjudication_name
        adjudications = read_unique_csv_index(adjudication_path, "photo_id") if adjudication_path.exists() else {}
        independent_path = data_dir / independent_name
        independent = read_unique_csv_index(independent_path, "photo_id") if independent_path.exists() else {}
        if path.exists():
            reviews = json.loads(path.read_text(encoding="utf-8"))
            rows.extend((row, adjudications.get(row.get("photo_id", "")), independent.get(row.get("photo_id", ""))) for row in reviews.get("records", []))
    records, excluded = [], []
    for row, adjudication, independent in rows:
        record = manifest_record(row, adjudication, independent)
        (records if record else excluded).append(record or row.get("photo_id"))
    # Split-safety invariant: one group, one split.
    group_splits = {}
    for record in records:
        group_splits.setdefault(record["split_group"], set()).add(record["split"])
    require(all(len(splits) == 1 for splits in group_splits.values()),
            "building group straddles train/eval")
    payload = {
        "source": ("independently reviewed and adjudicated BALaT (CC BY 4.0) + Commons "
                   "(per-file open licence, ShareAlike flagged) labels; building-grouped splits"),
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

#!/usr/bin/env python3
"""Pair completed primary and independent annotations for human adjudication.

This does not decide whether annotations agree. A reviewer must complete the
agreement, rationale, disposition and adjudicator fields in the output.
"""
from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
CHANNELS = {
    "image": {
        "primary": "three-ages-image-review.csv",
        "independent": "three-ages-independent-image-review.csv",
        "output": "three-ages-image-adjudication.csv",
        "key": ("asset_id",),
        "annotation": ("identity_verdict", "facade_label", "facade_observation"),
        "primary_annotation": ("identity_note", "facade_observation"),
        "primary_reviewer": "reviewer",
        "primary_date": "reviewed_at",
        "photo": True,
    },
    "structural": {
        "primary": "three-ages-structural-review.csv",
        "independent": "three-ages-independent-structural-review.csv",
        "output": "three-ages-structural-adjudication.csv",
        "key": ("source_id", "comparison_id"),
        "annotation": ("structural_observation",),
        "primary_annotation": ("structural_observation",),
        "primary_reviewer": "reviewer",
        "primary_date": "reviewed_at",
    },
    "balat": {
        "primary": "balat-photo-review.csv",
        "independent": "balat-independent-photo-review.csv",
        "output": "balat-photo-adjudication.csv",
        "key": ("photo_id",),
        "annotation": ("identity_verdict", "facade_label", "facade_observation"),
        "primary_annotation": ("facade_label", "facade_observation"),
        "primary_reviewer": "reviewer",
        "primary_date": "reviewed_at",
        "photo": True,
    },
    "commons": {
        "primary": "commons-photo-review.csv",
        "independent": "commons-independent-photo-review.csv",
        "output": "commons-photo-adjudication.csv",
        "key": ("photo_id",),
        "annotation": ("identity_verdict", "facade_label", "facade_observation"),
        "primary_annotation": ("facade_label", "facade_observation"),
        "primary_reviewer": "reviewer",
        "primary_date": "reviewed_at",
        "photo": True,
    },
}
DECISION_FIELDS = ("agreement", "rationale", "disposition", "adjudicator", "adjudicated_at")
PHOTO_DECISION_FIELDS = DECISION_FIELDS + ("resolved_facade_label",)
DECISION_OPTIONS = {"agree", "partial", "disagree", "not-comparable"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError(f"missing CSV header: {path}")
        return list(reader)


def write_rows(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def key_for(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def index_rows(rows: list[dict[str, str]], fields: tuple[str, ...], label: str) -> dict[tuple[str, ...], dict[str, str]]:
    indexed = {}
    for row in rows:
        key = key_for(row, fields)
        if not all(key) or key in indexed:
            raise RuntimeError(f"{label} contains missing or duplicate review key: {key}")
        indexed[key] = row
    return indexed


def compare(data_dir: Path, channel: str) -> Path:
    config = CHANNELS[channel]
    primary_rows = read_rows(data_dir / config["primary"])
    independent_rows = read_rows(data_dir / config["independent"])
    keys = config["key"]
    primary = index_rows(primary_rows, keys, f"primary {channel} review")
    independent = index_rows(independent_rows, keys, f"independent {channel} review")
    if primary.keys() != independent.keys():
        raise RuntimeError(f"{channel} primary and independent worksheets cover different evidence")

    decision_fields = PHOTO_DECISION_FIELDS if config.get("photo") else DECISION_FIELDS
    output = data_dir / config["output"]
    prior = {}
    if output.exists():
        with output.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            expected_prefix = list(keys) + ["primary_reviewer", "primary_reviewed_at", "primary_annotation", "independent_reviewer", "independent_reviewed_at", "independent_annotation"]
            if not reader.fieldnames or reader.fieldnames[:len(expected_prefix)] != expected_prefix or reader.fieldnames[len(expected_prefix):] != list(decision_fields):
                raise RuntimeError(f"existing {channel} adjudication worksheet has unexpected columns")
            for row in reader:
                key = key_for(row, keys)
                if not all(key) or key in prior:
                    raise RuntimeError(f"existing {channel} adjudication worksheet has missing or duplicate keys")
                prior[key] = row

    fields = list(keys) + [
        "primary_reviewer", "primary_reviewed_at", "primary_annotation",
        "independent_reviewer", "independent_reviewed_at", "independent_annotation",
        *decision_fields,
    ]
    result = []
    for key in sorted(primary):
        first, second = primary[key], independent[key]
        p_reviewer = first.get(config["primary_reviewer"], "").strip()
        s_reviewer = second.get("reviewer", "").strip()
        p_date = first.get(config["primary_date"], "").strip()
        s_date = second.get("reviewed_at", "").strip()
        p_text = "\n".join(f"{field}: {first.get(field, '').strip()}" for field in config["primary_annotation"] if first.get(field, "").strip())
        s_text = "\n".join(f"{field}: {second.get(field, '').strip()}" for field in config["annotation"] if second.get(field, "").strip())
        if (not p_reviewer or not s_reviewer or not p_date or not s_date or not p_text
                or any(not second.get(field, "").strip() for field in config["annotation"])):
            raise RuntimeError(f"{channel} review {key} lacks a completed annotation, reviewer or date")
        if p_reviewer == s_reviewer:
            raise RuntimeError(f"{channel} review {key} is not independent: both annotations name {p_reviewer}")
        old = prior.get(key, {})
        provenance = {
            **dict(zip(keys, key)),
            "primary_reviewer": p_reviewer,
            "primary_reviewed_at": p_date,
            "primary_annotation": p_text,
            "independent_reviewer": s_reviewer,
            "independent_reviewed_at": s_date,
            "independent_annotation": s_text,
        }
        prefix = fields[:len(fields) - len(decision_fields)]
        if old and any(old.get(field, "") != provenance[field] for field in prefix):
            raise RuntimeError(f"refusing to preserve adjudication for {key} after annotations changed")
        decision = {field: old.get(field, "") for field in decision_fields}
        if decision["agreement"] and decision["agreement"] not in DECISION_OPTIONS:
            raise RuntimeError(f"{channel} adjudication {key} has invalid agreement value")
        if any(decision.values()) and not all(decision.values()):
            raise RuntimeError(f"{channel} adjudication {key} is incomplete; fill all disposition fields together")
        result.append({**provenance, **decision})
    write_rows(output, tuple(fields), result)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--channel", choices=(*CHANNELS, "all"), default="all")
    args = parser.parse_args()
    for channel in CHANNELS if args.channel == "all" else (args.channel,):
        print(f"adjudication worksheet: {compare(args.data_dir, channel)}")


if __name__ == "__main__":
    main()

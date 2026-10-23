#!/usr/bin/env python3
"""Compare two Three Ages browser review-session exports."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise SystemExit(f"{path}: unsupported or missing schema_version")
    if not isinstance(payload.get("records"), list):
        raise SystemExit(f"{path}: records must be a list")
    return payload


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: compare-review-sessions.py FIRST.json SECOND.json")
    first_path, second_path = map(Path, sys.argv[1:])
    first, second = load(first_path), load(second_path)
    left = {record["key"]: record for record in first["records"]}
    right = {record["key"]: record for record in second["records"]}
    if len(left) != len(first["records"]) or len(right) != len(second["records"]):
        raise SystemExit("session contains duplicate record keys")

    print(f"# Review comparison: {first.get('reviewer', '(unnamed)')} vs {second.get('reviewer', '(unnamed)')}")
    print()
    disagreements = 0
    for key in sorted(set(left) | set(right)):
        one, two = left.get(key), right.get(key)
        if one is None or two is None:
            print(f"- **{key}**: missing from {'first' if one is None else 'second'} session")
            disagreements += 1
            continue
        if one.get("fingerprint") != two.get("fingerprint"):
            print(f"- **{key}**: provenance fingerprint mismatch; do not merge")
            disagreements += 1
            continue
        fields = set(one.get("fields", {})) | set(two.get("fields", {}))
        differences = [(field, one.get("fields", {}).get(field, ""), two.get("fields", {}).get(field, "")) for field in sorted(fields) if one.get("fields", {}).get(field, "") != two.get("fields", {}).get(field, "")]
        if differences:
            disagreements += 1
            print(f"- **{key}**")
            for field, left_value, right_value in differences:
                print(f"  - `{field}`: {left_value!r} vs {right_value!r}")

    print()
    print(f"Disagreements: {disagreements}")
    if not disagreements:
        print("No differences found in the submitted session records.")


if __name__ == "__main__":
    main()

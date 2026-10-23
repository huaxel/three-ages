#!/usr/bin/env python3
"""Integration-test the primary reviewer path end to end, in a completed state.

Every other test runs against the repository as it is: no completed reviews. That is the
one state in which several contracts are trivially satisfied, so a defect can hide there —
for example validation that asserted the identity gate was still `pending`, which made the
gate impossible to resolve through the documented workflow.

This test copies the tree, records a reviewer's completed work across the interesting cases
(a curated pilot case, a facade-only building, a shared-facade unit, and the gated building
after resolving its gate), then runs the exporter, the snapshot validator and the UI smoke
test against that completed state.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "three-ages" / "data"
EXCLUDED = {"_opam", "_build", "node_modules", "local", ".git", "__pycache__"}

# (worksheet, source_id, asset_id, fields)
IMAGE_REVIEWS = [
    ("005", "T084580", "baroque", "high", "Concave lateral spans and an elaborate crowning."),
    ("007", "commons-br-ssel-grand-place", "other", "medium", "Flamboyant Gothic frontage with a dominant tower."),
    (
        "015",
        "commons-maison-des-ducs-de-brabant-brussels-full-frontal-facade-",
        "baroque",
        "medium",
        "Unified composition: giant order spanning two upper floors.",
    ),
    (
        "024",
        "commons-maison-de-la-balance-rue-de-la-colline-24-bruxelles",
        "classical french",
        "low",
        "Restrained stone frontage on the Rue de la Colline side.",
    ),
]
REGISTER_GATE = "confirmed with qualification"


def copy_tree(destination: Path) -> None:
    for entry in ROOT.iterdir():
        if entry.name in EXCLUDED:
            continue
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, ignore=shutil.ignore_patterns(*EXCLUDED))
        else:
            shutil.copy2(entry, target)


def update(path: Path, match: dict[str, str], values: dict[str, str]) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    hits = 0
    for row in rows:
        if all(row.get(key) == value for key, value in match.items()):
            row.update(values)
            hits += 1
    if not hits:
        raise AssertionError(f"no row matched {match} in {path.name}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return hits


def run(tree: Path, *args: str, expect_success: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, *args] if args[0].endswith(".py") else list(args),
        cwd=tree,
        capture_output=True,
        text=True,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(f"{args[0]} failed in the completed state:\n{result.stdout}\n{result.stderr}")
    return result


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory) / "repo"
        tree.mkdir()
        copy_tree(tree)
        data = tree / "prototypes" / "three-ages" / "data"

        # 1. A gated building must refuse image reviews until the gate is resolved.
        # Match the exact asset: matching on source_id alone would touch all of the
        # building's images and leave stray reviews that then compile.
        # The repository may ship a resolved gate; simulate the unresolved state first.
        update(data / "three-ages-register-review.csv", {"source_id": "024"}, {
            "identity_gate": "pending",
            "identity_gate_note": "",
        })
        base_images = json.loads((data / "three-ages-image-reviews.json").read_text(encoding="utf-8"))
        base_image_assets = {(r["source_id"], r["asset_id"]) for r in base_images["records"]}
        base_register_count = json.loads((data / "three-ages-register-reviews.json").read_text(encoding="utf-8"))["record_count"]
        gate_asset = IMAGE_REVIEWS[-1][1]
        update(data / "three-ages-image-review.csv", {"source_id": "024", "asset_id": gate_asset}, {
            "facade_style": "classical french",
            "facade_observation": "Premature observation.",
            "reviewer": "Reviewer One",
            "reviewed_at": "2026-03-01",
            "confidence": "low",
        })
        blocked = run(tree, "prototypes/three-ages/export_pilot.py", expect_success=False)
        if blocked.returncode == 0 or "identity gate is unresolved" not in (blocked.stdout + blocked.stderr):
            raise AssertionError("a gated building accepted an image review before the gate was resolved")

        # 2. Resolve the gate, then record the reviewer's completed work.
        update(data / "three-ages-register-review.csv", {"source_id": "024"}, {
            "identity_gate": REGISTER_GATE,
            "identity_gate_note": "City names the square frontage; heritage and the British Library name the Rue de la Colline facade.",
            "register_decision": "retain as reconstruction evidence",
            "register_observation": "Crosswalk confirmed with qualification.",
            "reviewer": "Reviewer One",
            "reviewed_at": "2026-03-01",
            "confidence": "medium",
        })
        for source_id, asset_id, style, confidence, observation in IMAGE_REVIEWS:
            update(data / "three-ages-image-review.csv", {"source_id": source_id, "asset_id": asset_id}, {
                "facade_style": style,
                "facade_observation": observation,
                "reviewer": "Reviewer One",
                "reviewed_at": "2026-03-01",
                "confidence": confidence,
            })

        # 3. Export and validate the completed state.
        run(tree, "prototypes/three-ages/export_pilot.py")
        run(tree, "prototypes/validate_snapshots.py")
        run(tree, "prototypes/three-ages/generate_review_briefing.py")

        compiled_images = json.loads((data / "three-ages-image-reviews.json").read_text(encoding="utf-8"))
        new_image_assets = {(s, a) for s, a, _, _, _ in IMAGE_REVIEWS} - base_image_assets
        if compiled_images["record_count"] != base_images["record_count"] + len(new_image_assets):
            raise AssertionError(f"expected {base_images['record_count'] + len(new_image_assets)} compiled image reviews, got {compiled_images['record_count']}")
        compiled_register = json.loads((data / "three-ages-register-reviews.json").read_text(encoding="utf-8"))
        if compiled_register["record_count"] != base_register_count:
            raise AssertionError(f"expected {base_register_count} compiled register reviews, got {compiled_register['record_count']}")

        # The resolved gate must survive regeneration, and a completed review must not be lost.
        gate = next(row for row in csv.DictReader((data / "three-ages-register-review.csv").open(newline="", encoding="utf-8")) if row["source_id"] == "024")
        if gate["identity_gate"] != REGISTER_GATE:
            raise AssertionError("the resolved identity gate did not survive regeneration")
        reviewed_assets = {(record["source_id"], record["asset_id"]) for record in compiled_images["records"]}
        if not {(s, a) for s, a, _, _, _ in IMAGE_REVIEWS} <= reviewed_assets:
            raise AssertionError(f"a completed image review was lost: {reviewed_assets}")
        if not base_image_assets <= reviewed_assets:
            raise AssertionError(f"a pre-existing image review was lost: {reviewed_assets}")

        # 4. The UI must render the completed state, not only the empty one.
        run(tree, "node", "prototypes/smoke_ui.js")

    print("Three Ages completed-state end-to-end review passed")


if __name__ == "__main__":
    main()

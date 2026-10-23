#!/usr/bin/env python3
"""Integration-test structural crop preflight and no-mutation failure behavior."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GENERATOR = ROOT / "three-ages" / "generate_structural_crops.py"
SOURCE_DATA = ROOT / "three-ages" / "data"
TARGET_CROP = Path("structural/005-bruciel-grand-place-1935.png")
MANIFEST = Path("three-ages-structural-crops.json")
SENTINEL = b"must remain untouched after preflight failure\n"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_fails(data: Path, message: str) -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--data-dir", str(data)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 or message not in result.stderr:
        raise AssertionError(f"expected crop failure containing {message!r}: {result.stderr}")


def require_unchanged(data: Path, manifest: bytes) -> None:
    if (data / TARGET_CROP).read_bytes() != SENTINEL:
        raise AssertionError("crop preflight failure modified an existing derived image")
    if (data / MANIFEST).read_bytes() != manifest:
        raise AssertionError("crop preflight failure modified the structural manifest")


def scenario(root: Path, name: str) -> Path:
    data = root / name
    shutil.copytree(SOURCE_DATA, data)
    (data / TARGET_CROP).write_bytes(SENTINEL)
    return data


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        stale_data = scenario(root, "stale-data")
        stale_manifest = (stale_data / MANIFEST).read_bytes()
        (stale_data / "structural/stale.png").write_bytes(b"stale\n")
        run_fails(stale_data, "stale structural crops")
        require_unchanged(stale_data, stale_manifest)

        invalid_data = scenario(root, "invalid-geometry-data")
        invalid_manifest = (invalid_data / MANIFEST).read_bytes()
        buildings_path = invalid_data / "grand-place-buildings.json"
        buildings = json.loads(buildings_path.read_text(encoding="utf-8"))
        second_case = next(record for record in buildings["records"] if record["id"] == "009")
        second_case["latitude"] = 0
        second_case["longitude"] = 0
        write_json(buildings_path, buildings)
        run_fails(invalid_data, "falls outside the aligned area image")
        require_unchanged(invalid_data, invalid_manifest)

    print("Structural crop preflight no-mutation integration passed")


if __name__ == "__main__":
    main()

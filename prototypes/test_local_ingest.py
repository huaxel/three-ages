#!/usr/bin/env python3
"""Integration-test the local-only image ingest rights gate.

The ingest script exists so images from sources without bulk image reuse terms
can be used locally without entering the repository. These tests pin the
boundary: an unstated, unelaborated or refused rights basis must never produce
a cached copy or a provenance record that implies reuse is settled.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Git commands must run from the repository root: resolving them from prototypes/
# would inspect prototypes/local/, which does not exist, and the guard below
# would pass no matter what is tracked at the real local/ directory.
REPO_ROOT = ROOT.parent
INGEST = ROOT / "three-ages" / "ingest_local_images.py"
SOURCE_DATA = ROOT / "three-ages" / "data"
MANIFEST_COLUMNS = [
    "file",
    "house_name",
    "grand_place_number",
    "source_url",
    "rights_basis",
    "credit",
    "capture_date",
]

# A genuine 1x1 JPEG is written at run time; the ingest script sniffs content
# signatures, so the fixture must be a real image rather than a stub.
def write_tiny_jpeg(path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (120, 90, 60)).save(path, format="JPEG", quality=85)


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def row(name: str, rights: str) -> dict[str, str]:
    return {
        "file": name,
        "house_name": "The Swan",
        "grand_place_number": "9",
        "source_url": "https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/9/31126",
        "rights_basis": rights,
        "credit": "urban.brussels - Inventaire du patrimoine architectural",
        "capture_date": "2019-04-02",
    }


def run(data: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(INGEST), "--data-dir", str(data), *args],
        capture_output=True,
        text=True,
    )
    # The script reports per-row status on stdout and only the summary on stderr.
    result.all_output = result.stdout + result.stderr
    return result


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp)

        # Nothing may be written outside the local working tree.
        if run(data, "--init").returncode != 0:
            raise AssertionError("--init failed")
        manifest = data / "facade-manifest.csv"
        inbox = data / "facade-inbox"
        records = data / "facade-local-records.json"
        for path in (manifest, inbox, records.parent):
            if not path.exists():
                raise AssertionError(f"--init did not create {path}")

        # A refused basis must be reported even before the file is downloaded,
        # so no download effort is spent on an image that cannot be recorded.
        write_manifest(manifest, [row("refused.jpg", "academic fair use")])
        result = run(data)
        if result.returncode == 0:
            raise AssertionError("an academic fair use basis was accepted")
        if "academic fair use" not in result.all_output:
            raise AssertionError(f"refusal did not name the rejected basis: {result.all_output}")
        if "not in" in result.all_output and "yet" in result.all_output:
            raise AssertionError("a refused basis was reported as merely pending")

        # A blank basis is not an implicit permission.
        write_manifest(manifest, [row("blank.jpg", "")])
        result = run(data)
        if result.returncode == 0 or "'(blank)'" not in result.all_output:
            raise AssertionError("a blank rights basis was accepted")

        # Missing provenance fields are refused.
        write_manifest(manifest, [{**row("noprov.jpg", "written-permission"), "credit": ""}])
        result = run(data)
        if result.returncode == 0 or "credit is required" not in result.all_output:
            raise AssertionError("a row without credit was accepted")

        # Content that is not an image must not be cached as if it were one.
        (inbox / "fake.jpg").write_text("<!doctype html><title>403</title>", encoding="utf-8")
        write_manifest(manifest, [row("fake.jpg", "public-domain")])
        result = run(data)
        if result.returncode == 0 or "does not look like an image" not in result.all_output:
            raise AssertionError("a saved HTML page was accepted as an image")
        (inbox / "fake.jpg").unlink()

        # An accepted basis copies the file and records provenance locally.
        write_tiny_jpeg(inbox / "allowed.jpg")
        write_manifest(manifest, [row("allowed.jpg", "written-permission")])
        result = run(data)
        if result.returncode != 0:
            raise AssertionError(f"an explicit written-permission basis was refused: {result.all_output}")

        payload = json.loads(records.read_text(encoding="utf-8"))
        if len(payload["records"]) != 1:
            raise AssertionError(f"expected exactly one local record, got {len(payload['records'])}")
        record = payload["records"][0]
        if record["rights_basis"] != "written-permission" or record["committed"] is not False:
            raise AssertionError(f"local record misstates reuse status: {record}")
        cached = data / record["cached_as"]
        if not cached.exists():
            raise AssertionError(f"accepted image was not cached: {cached}")

        # Re-running is idempotent: no duplicate records, no re-copy.
        before = cached.read_bytes()
        result = run(data)
        if result.returncode != 0 or "unchanged 1" not in result.stdout:
            raise AssertionError(f"re-running was not idempotent: {result.stdout}")
        payload = json.loads(records.read_text(encoding="utf-8"))
        if len(payload["records"]) != 1 or cached.read_bytes() != before:
            raise AssertionError("idempotent re-run changed the local record set or cached bytes")

    # The tracked repository must contain no local cache output.
    tracked = subprocess.run(
        ["git", "ls-files", "local"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if tracked:
        raise AssertionError(f"local cache files are tracked in git: {tracked}")

    ignored = subprocess.run(
        ["git", "check-ignore", "local/facade-inbox/probe.jpg"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if ignored.returncode != 0:
        raise AssertionError("local/ is not gitignored")

    print("Three Ages local ingest rights-gate integration passed")


if __name__ == "__main__":
    main()

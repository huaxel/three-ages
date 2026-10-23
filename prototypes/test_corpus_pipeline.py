#!/usr/bin/env python3
"""Offline integration test for `scripts/monument-corpus-pipeline.sh`.

The pipeline is the component that runs unattended for days, and until this file it had
no automated test at all: every check on it had been a manual run, which is exactly how a
mis-sequenced stage or an always-zero exit code stays hidden. It is exercised here end to
end, with no network and no writes outside a temporary directory.

What makes that possible:

* a **pre-seeded robots cache** inside the corpus (`--robots-cache "$OUT/robots.txt"`),
  so the scraper parses a policy instead of fetching one;
* pictures already stored on disk, so the picture pass has nothing to fetch;
* a synthetic index, so the coordinate amendment runs offline;
* overridable process patterns, so the duplicate-pass guard does not collide with a real
  run happening on the same machine.

The pipeline is *expected* to fail a stage here — the place crawl has no targets to
enumerate from a two-record corpus — and the point of the test is that its **exit code
agrees with the verdict in its own `[FINAL]` line**.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PIPELINE = REPO / "scripts" / "monument-corpus-pipeline.sh"
SCRAPER = ROOT / "three-ages" / "scrape_monument.py"
FIXTURES = ROOT / "three-ages" / "tests" / "fixtures"
# Two real notices, so the corpus has records the verifiers can read.
NOTICES = (("building-23775.fr.html", "23775"), ("building-30991.fr.html", "30991"))
def jpeg_bytes(width: int, height: int) -> bytes:
    """A real JPEG at the declared size.

    It has to decode and match the record's declared width and height, because the
    picture audit compares the file's own dimensions against the notice and would
    rightly report a mismatch. Hand-built bytes were tried first and were correctly
    rejected as "not actually a picture" — the audit earning its keep on its own test.
    """
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (30, 60, 90)).save(buffer, format="JPEG")
    return buffer.getvalue()


def load_scraper():
    spec = importlib.util.spec_from_file_location("scrape_monument", SCRAPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_corpus(root: Path, scraper) -> tuple[Path, Path]:
    """A two-record corpus whose pictures are already stored, plus a policy and index."""
    out = root / "scraped"
    out.mkdir(parents=True)
    images = root / "inbox"
    index_features = []
    for filename, building_id in NOTICES:
        html = (FIXTURES / filename).read_text(encoding="utf-8")
        record = scraper.build_record(
            html, scraper.building_url(building_id, "fr"), building_id, "fr"
        )
        # The record must agree with the synthetic index, or the amendment rewrites it.
        record["coordinates"] = {"latitude": 50.85, "longitude": 4.35}
        # No addresses: the place crawl enumerates streets from them, and a two-record
        # corpus would then visit two real pages. This test must stay offline.
        record["addresses"] = []
        scraper.write_record(record, scraper.record_path(out, building_id, "fr"))

        building_dir = images / building_id
        building_dir.mkdir(parents=True)
        entries = []
        for image, name in zip(record["images"], scraper.local_names(record["images"])):
            payload = jpeg_bytes(int(image["width"]), int(image["height"]))
            (building_dir / name).write_bytes(payload)
            entries.append({
                "url": image["url"], "filename": name, "variant": "full", "format": "jpeg",
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                "rights_hint": None, "credit_holders": [],
            })
        manifest = scraper.manifest_skeleton(record, scraper.CONDITIONAL_BASIS)
        manifest["images"] = entries
        scraper.write_manifest(building_dir, manifest)
        index_features.append({
            "properties": {"id": building_id},
            "geometry": {"coordinates": [4.35, 50.85]},
        })
        # The record must agree with the index or the amendment rewrites it — which is
        # fine, but it keeps the test's expectation simple to have them agree already.
        record["coordinates"] = {"latitude": 50.85, "longitude": 4.35}
        scraper.write_record(record, scraper.record_path(out, building_id, "fr"))

    # A robots.txt the scraper can parse instead of fetching.
    shutil.copyfile(FIXTURES / "robots.txt", out / "robots.txt")
    index = root / "monuments.fr.json"
    index.write_text(json.dumps({"type": "FeatureCollection", "features": index_features}),
                     encoding="utf-8")
    return out, images


def run_pipeline(out: Path, images: Path, root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "MONUMENT_OUT": str(out),
        "MONUMENT_IMAGES": str(images),
        "MONUMENT_PLACES_OUT": str(root / "scraped-places"),
        "MONUMENT_SWEEP_LOG": str(root / "sweep.log"),
        "MONUMENT_INDEX_FILE": str(root / "monuments.fr.json"),
        "MONUMENT_LANG": "fr",
        "MONUMENT_EXPECTED_RECORDS": "2",
        # No real sweep or picture pass on this machine may block or attract the run.
        "MONUMENT_SWEEP_PATTERN": "^python3 .*no-such-sweep-process$",
        "MONUMENT_IMAGES_PATTERN": "^python3 .*no-such-picture-pass$",
    })
    return subprocess.run(
        ["bash", str(PIPELINE)], env=env, capture_output=True, text=True, timeout=900,
        cwd=str(REPO),
    )


def final_codes(log: str) -> dict[str, str]:
    """The stage verdicts the pipeline states in its own last line."""
    line = [row for row in log.splitlines() if "[FINAL] pipeline done" in row]
    assert line, f"no [FINAL] pipeline line in:\n{log[-2000:]}"
    verdicts = line[-1].split("[FINAL] pipeline done:", 1)[1]
    codes = {}
    for part in verdicts.split(","):
        # Keys contain spaces ("picture pass"), so take the last token as the code.
        key, _, value = part.strip().rpartition(" ")
        if value.isdigit():
            codes[key.strip()] = value
    return codes


def test_pipeline_runs_stages_and_reports_truthfully() -> None:
    """It must reach its later stages, run offline, and exit non-zero if a stage failed."""
    scraper = load_scraper()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out, images = build_corpus(root, scraper)
        result = run_pipeline(out, images, root)
        log = result.stdout + result.stderr

        # Every stage announced itself, including the verifiers.
        for stage in ("stage 0/7", "stage 1/7", "stage 2/7", "stage 3/7",
                      "stage 4/7", "stage 5/7", "stage 6/7"):
            assert stage in log, f"{stage} never ran:\n{log[-3000:]}"
        assert "[FINAL] pipeline done" in log, log[-2000:]

        # Nothing was fetched: the pictures were already stored.
        plan = [row for row in log.splitlines() if row.startswith("plan:")]
        assert plan and plan[0].startswith("plan: 0 picture(s) to fetch"), plan

        # The previews were derived and the picture tree verified clean.
        assert "preview(s) derived" in log or "already current" in log, log[-2000:]
        assert "0 defect(s)" in log, log[-2000:]
        # The record check ran and passed.
        assert "integrity: PASS" in log, log[-2000:]

        # The place crawl has no targets from a two-record corpus, so that stage fails —
        # and the exit code must say so rather than reporting success.
        codes = final_codes(log)
        assert codes, log[-2000:]
        failed = any(value != "0" for value in codes.values())
        assert failed, f"expected a failing stage in this synthetic run: {codes}"
        assert result.returncode != 0, (
            "the pipeline reported a failed stage but exited 0; a supervisor would see success"
        )
        assert result.returncode == 1, result.returncode

        # Nothing leaked outside the temporary directory.
        assert not (REPO / "local" / "metropolis-not-a-real-path").exists()


def test_pipeline_refuses_to_start_beside_a_picture_pass() -> None:
    """Two picture passes on one host would double the crawl rate the site asked for."""
    scraper = load_scraper()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out, images = build_corpus(root, scraper)
        env = dict(os.environ)
        env.update({
            "MONUMENT_OUT": str(out),
            "MONUMENT_IMAGES": str(images),
            "MONUMENT_PLACES_OUT": str(root / "scraped-places"),
            # Matches this test's own command line well enough to look like a live pass,
            # which is exactly the case the guard exists for.
            "MONUMENT_IMAGES_PATTERN": "test_corpus_pipeline",
        })
        result = subprocess.run(
            ["bash", str(PIPELINE)], env=env, capture_output=True, text=True, timeout=300,
            cwd=str(REPO),
        )
        log = result.stdout + result.stderr
        assert "refusing to start" in log, log[-1500:]
        assert result.returncode == 2, result.returncode


def test_documented_commands_are_real() -> None:
    """The READMEs advertise commands, so those commands have to exist and parse.

    Documentation is the entry point to this workstream, and a command that has drifted is
    how a reader loses an hour. The flags are checked with the real parser, so a renamed
    option fails here rather than in someone's terminal; nothing is executed, so this
    makes no request.
    """
    import shlex

    scraper = load_scraper()
    problems = []
    checked = 0
    for document in ("README.md", "prototypes/README.md"):
        text = (REPO / document).read_text(encoding="utf-8")
        for block in __import__("re").findall(r"```bash\n(.*?)```", text, __import__("re").S):
            for line in block.replace("\\\n", " ").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                head = shlex.split(line)[0:2]
                if head[:1] != ["python3"] or head[1:2] == ["-m"]:
                    continue  # a module invocation, not a path to a script
                script = head[1]
                # The READMEs are run from the repository root and from prototypes/, so a
                # relative path is resolved against both before being called missing.
                candidates = (REPO / script, REPO / Path(document).parent / script)
                if not any(candidate.exists() for candidate in candidates):
                    problems.append(f"{document}: no such script: {line}")
                    continue
                if script.endswith("scrape_monument.py"):
                    try:
                        scraper.build_parser().parse_args(shlex.split(line)[2:])
                    except SystemExit:
                        problems.append(f"{document}: arguments rejected: {line}")
                checked += 1
    assert checked > 0, "no documented commands were found, so the check proved nothing"
    assert not problems, problems


def main() -> None:
    tests = [
        test_pipeline_runs_stages_and_reports_truthfully,
        test_pipeline_refuses_to_start_beside_a_picture_pass,
        test_documented_commands_are_real,
    ]
    for test in tests:
        test()
    print(f"Three Ages corpus pipeline passed ({len(tests)} offline checks)")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Test reviewer-session comparison and provenance-safe worksheet application."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "scripts/apply-review-session.py"
COMPARE = ROOT / "scripts/compare-review-sessions.py"


def _load_apply_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("apply_review_session", APPLY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprint_from_row(kind: str, row: dict[str, str]) -> str:
    """Build a fingerprint the way the tools do, so a test cannot invent its own shape."""
    fields = _load_apply_module().FIELDS[kind]
    return "|".join(f"{field}={row.get(field, '')}" for field in fields)


def assert_fingerprint_contract() -> None:
    """The browser workbench and the apply tool must fingerprint identical fields.

    A copy of the field list once omitted source_style_text, so every image session the
    workbench exported was refused as a provenance mismatch.
    """
    import re
    import runpy

    canonical = runpy.run_path(str(ROOT / "prototypes" / "three-ages" / "export_pilot.py"))["SESSION_FINGERPRINT_FIELDS"]
    tool_fields = _load_apply_module().FIELDS
    if tool_fields != canonical:
        raise AssertionError(f"apply tool fingerprint fields drifted from the exporter: {tool_fields}")
    html = (ROOT / "prototypes" / "three-ages" / "review.html").read_text(encoding="utf-8")
    body = re.search(r"function immutable\(type,row\)\{(.*?)\}", html, re.S)
    if not body:
        raise AssertionError("review workbench does not declare immutable()")
    # The lists appear positionally as image / structural / register inside the ternary.
    lists = [[item.strip().strip("'") for item in group.split(",")] for group in re.findall(r"\[([^\]]+)\]", body.group(1))]
    if len(lists) != 3:
        raise AssertionError(f"review workbench declares {len(lists)} fingerprint field lists, expected 3")
    for kind, workbench in zip(("image", "structural", "register"), lists):
        if workbench != canonical[kind]:
            raise AssertionError(f"workbench {kind} fingerprint fields drifted from the exporter: {workbench}")


def assert_write_guard() -> None:
    """A session may only write review fields.

    A forged session can carry a valid fingerprint, because the fingerprint is checked
    against the current row. If it could also write provenance, it would defeat the check.
    """
    import runpy

    canonical = runpy.run_path(str(ROOT / "prototypes" / "three-ages" / "export_pilot.py"))
    writable = canonical["SESSION_WRITABLE_FIELDS"]
    fingerprints = canonical["SESSION_FINGERPRINT_FIELDS"]
    module = _load_apply_module()
    if module.WRITABLE != writable:
        raise AssertionError(f"apply tool writable fields drifted from the exporter: {module.WRITABLE}")
    for kind in ("image", "structural", "register"):
        overlap = sorted(set(writable[kind]) & set(fingerprints[kind]))
        if overlap:
            raise AssertionError(f"{kind} fields are both fingerprinted and writable: {overlap}")


def assert_forged_session_refused() -> None:
    module = _load_apply_module()
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        worksheet = ROOT / "prototypes" / "three-ages" / "data" / "three-ages-image-review.csv"
        with worksheet.open(newline="", encoding="utf-8") as handle:
            row = next(r for r in csv.DictReader(handle) if r["asset_id"] == "T084580")
        session = temp / "forged.json"
        session.write_text(json.dumps({
            "schema_version": 1,
            "reviewer": "Mallory",
            "records": [{
                "type": "image", "key": "image:005:T084580", "fingerprint": module.fingerprint("image", row),
                "source_id": "005", "asset_id": "T084580",
                "fields": {
                    "facade_style": "baroque", "facade_observation": "ok", "reviewer": "Mallory",
                    "reviewed_at": "2026-03-01", "confidence": "high",
                    "source_url": "https://evil.test/forged", "preview_sha256": "0" * 64, "licence": "CC0",
                },
            }],
        }), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(APPLY), "--type", "image", str(session), str(worksheet), str(temp / "out.csv")],
            capture_output=True, text=True,
        )
        if result.returncode == 0 or "attempts to write non-review field" not in (result.stdout + result.stderr):
            raise AssertionError("a session was allowed to rewrite provenance fields")


def assert_gate_requires_rationale() -> None:
    """A resolved identity gate must carry a recorded reason."""
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        data = temp / "data"
        shutil.copytree(ROOT / "prototypes" / "three-ages" / "data", data)
        worksheet = data / "three-ages-register-review.csv"
        with worksheet.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            rows = list(reader)
        for row in rows:
            if row["source_id"] == "024":
                row["identity_gate"] = "confirmed"
                row["identity_gate_note"] = ""
        with worksheet.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        result = subprocess.run(
            [sys.executable, str(ROOT / "prototypes" / "three-ages" / "export_pilot.py"), "--data-dir", str(data)],
            capture_output=True, text=True,
        )
        if result.returncode == 0 or "no rationale is recorded" not in (result.stdout + result.stderr):
            raise AssertionError("an identity gate was resolved with no recorded rationale")


def main() -> None:
    assert_fingerprint_contract()
    assert_write_guard()
    assert_forged_session_refused()
    assert_gate_requires_rationale()
    assert_write_guard()
    assert_forged_session_refused()
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        worksheet = temp / "review.csv"
        worksheet.write_text(
            "source_id,claim_id,reported_value,date_semantics,source_comparison,source_kind,source_record_id,source_url,register_decision,register_observation,reviewer,reviewed_at,confidence\n"
            "005,register-005,1697,heritage-inventory reconstruction date,agrees,inventory,31123,https://example.test/source,,,,,\n",
            encoding="utf-8",
        )
        original_worksheet = worksheet.read_bytes()
        session = temp / "session.json"
        base = "|".join([
            "source_id=005", "claim_id=register-005", "reported_value=1697",
            "date_semantics=heritage-inventory reconstruction date", "source_comparison=agrees",
            "source_kind=inventory", "source_record_id=31123", "source_url=https://example.test/source",
        ])
        session.write_text(json.dumps({
            "schema_version": 1,
            "reviewer": "Reviewer One",
            "records": [{
                "type": "register", "key": "register:005:register-005", "fingerprint": base,
                "source_id": "005", "claim_id": "register-005",
                "fields": {
                    "register_decision": "accept proxy for MVP",
                    "register_observation": "Matches the city reconstruction history.",
                    "reviewer": "Reviewer One", "reviewed_at": "2026-09-21", "confidence": "medium",
                },
            }],
        }, indent=2) + "\n", encoding="utf-8")
        output = temp / "reviewed.csv"
        subprocess.run([sys.executable, str(APPLY), "--type", "register", str(session), str(worksheet), str(output)], check=True)
        row = next(csv.DictReader(output.open(newline="", encoding="utf-8")))
        if row["register_decision"] != "accept proxy for MVP" or worksheet.read_bytes() != original_worksheet:
            raise AssertionError("valid session was not applied safely")
        changed = json.loads(session.read_text(encoding="utf-8"))
        changed["records"][0]["fingerprint"] = "stale"
        stale = temp / "stale.json"
        stale.write_text(json.dumps(changed), encoding="utf-8")
        refused = subprocess.run([sys.executable, str(APPLY), "--type", "register", str(stale), str(worksheet), str(temp / "refused.csv")], capture_output=True, text=True)
        if refused.returncode == 0 or "provenance mismatch" not in refused.stderr:
            raise AssertionError("stale session was not refused")

        second = temp / "second.json"
        second.write_text(session.read_text(encoding="utf-8").replace("accept proxy for MVP", "retain as reconstruction evidence"), encoding="utf-8")
        comparison = subprocess.run([sys.executable, str(COMPARE), str(session), str(second)], check=True, capture_output=True, text=True)
        if "register:005:register-005" not in comparison.stdout or "Disagreements: 1" not in comparison.stdout:
            raise AssertionError("session comparison missed a disagreement")

        img_worksheet = temp / "image_review.csv"
        img_worksheet.write_text(
            "source_id,facade_unit_id,name,address,asset_id,epoch,source_url,image_url,preview,preview_sha256,licence,credit,source_style_text,source_observation,annotation_status,identity_note,facade_style,facade_observation,structural_observation,reviewer,reviewed_at,confidence\n"
            "005,gp-005,The Horn,\"Grand-Place, 6\",T084580,1942,https://example.test/source,https://example.test/image.jpg,data/historical/test.jpg,hash123,CC BY 4.0,Credit,Baroque source text,Source obs,source preview; no reviewer annotation,,,,,,,\n",
            encoding="utf-8",
        )
        img_orig = img_worksheet.read_bytes()
        img_session = temp / "img_session.json"
        img_row_source = next(csv.DictReader(img_worksheet.open(newline="", encoding="utf-8")))
        img_base = fingerprint_from_row("image", img_row_source)
        img_session.write_text(json.dumps({
            "schema_version": 1,
            "reviewer": "Reviewer One",
            "records": [{
                "type": "image", "key": "image:005:T084580", "fingerprint": img_base,
                "source_id": "005", "asset_id": "T084580",
                "fields": {
                    "facade_style": "baroque",
                    "facade_observation": "Baroque gable and detailing.",
                    "reviewer": "Reviewer One", "reviewed_at": "2026-09-21", "confidence": "high",
                },
            }],
        }, indent=2) + "\n", encoding="utf-8")
        img_output = temp / "img_reviewed.csv"
        subprocess.run([sys.executable, str(APPLY), "--type", "image", str(img_session), str(img_worksheet), str(img_output)], check=True)
        img_row = next(csv.DictReader(img_output.open(newline="", encoding="utf-8")))
        if img_row["facade_style"] != "baroque" or img_row["facade_observation"] != "Baroque gable and detailing." or img_worksheet.read_bytes() != img_orig:
            raise AssertionError("valid image review session was not applied safely")

        # Identity gate: a session must be able to resolve the gate, and the gate must not
        # be part of the provenance fingerprint, because it is reviewer state, not source state.
        gate_worksheet = temp / "gate_review.csv"
        gate_worksheet.write_text(
            "source_id,claim_id,reported_value,date_semantics,source_comparison,source_kind,source_record_id,source_url,identity_note,identity_gate,register_decision,register_observation,reviewer,reviewed_at,confidence\n"
            "024,register-024,1698,reconstruction date,agrees,inventory,30991,https://example.test/balance,crosswalk needs confirmation,pending,,,,,\n",
            encoding="utf-8",
        )
        gate_original = gate_worksheet.read_bytes()
        gate_base = "|".join([
            "source_id=024", "claim_id=register-024", "reported_value=1698",
            "date_semantics=reconstruction date", "source_comparison=agrees",
            "source_kind=inventory", "source_record_id=30991", "source_url=https://example.test/balance",
        ])
        gate_session = temp / "gate_session.json"
        gate_session.write_text(json.dumps({
            "schema_version": 1,
            "reviewer": "Reviewer Two",
            "records": [{
                "type": "register", "key": "register:024:register-024", "fingerprint": gate_base,
                "source_id": "024", "claim_id": "register-024",
                "fields": {
                    "identity_gate": "confirmed with qualification",
                    "identity_gate_note": "City names the square frontage; heritage and the British Library name the Rue de la Colline facade.",
                    "register_decision": "retain as reconstruction evidence",
                    "register_observation": "Crosswalk confirmed with qualification.",
                    "reviewer": "Reviewer Two", "reviewed_at": "2026-02-01", "confidence": "medium",
                },
            }],
        }, indent=2) + "\n", encoding="utf-8")
        gate_output = temp / "gate_applied.csv"
        subprocess.run([sys.executable, str(APPLY), "--type", "register", str(gate_session), str(gate_worksheet), str(gate_output)], check=True)
        gate_row = next(csv.DictReader(gate_output.open(newline="", encoding="utf-8")))
        if gate_row["identity_gate"] != "confirmed with qualification" or gate_worksheet.read_bytes() != gate_original:
            raise AssertionError("identity gate session was not applied safely")

        # A stale fingerprint must still be refused when the gate is the only change.
        stale_session = temp / "stale_gate_session.json"
        payload = json.loads(gate_session.read_text(encoding="utf-8"))
        payload["records"][0]["fingerprint"] = gate_base.replace("source_id=024", "source_id=999")
        stale_session.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        stale = subprocess.run(
            [sys.executable, str(APPLY), "--type", "register", str(stale_session), str(gate_worksheet), str(temp / "never.csv")],
            capture_output=True, text=True,
        )
        if stale.returncode == 0 or "provenance mismatch" not in (stale.stdout + stale.stderr):
            raise AssertionError("a stale identity-gate session was applied")

    print("Review-session safety tests passed")


if __name__ == "__main__":
    main()

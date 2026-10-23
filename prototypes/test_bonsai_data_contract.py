#!/usr/bin/env python3
"""Check the OCaml/Bonsai slice's data contract against the committed JSON.

The Bonsai slice embeds JSON files at build time and parses them with a fixed set of
field lookups. Its build runs in a separate, slower CI job, so a data change that drops
or renames a field it reads would otherwise only surface there.

This test extracts the fields the OCaml actually reads and verifies them against the
embedded files, so a breaking data change fails the fast Python gate instead.

It does not check the OCaml UI scope. The slice renders the curated pilot's own
image_evidence, so it shows fewer images than the review worksheet contains; that gap is
recorded in ocaml/README.md rather than frozen here.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OCAML = ROOT / "ocaml"
DATA = ROOT / "prototypes" / "three-ages" / "data"

# The artifacts the Bonsai slice embeds. If dune gains another embed, this list must be
# updated deliberately rather than silently widening what this test covers.
EMBEDDED = {
    "pilot_data.ml": "three-ages-pilot.json",
    "buildings_data.ml": "grand-place-buildings.json",
    "image_reviews_data.ml": "three-ages-image-reviews.json",
    "structural_reviews_data.ml": "three-ages-structural-reviews.json",
    "register_reviews_data.ml": "three-ages-register-reviews.json",
    "structural_data.ml": "three-ages-structural-crops.json",
}

FIELD_LOOKUP = re.compile(r'(?:string_field|optional_string|to_string|member)\s+"([a-z_]+)"')


def embedded_targets() -> dict[str, str]:
    """Read the embed rules from dune so the test notices a new or removed embed."""
    dune = (OCAML / "dune").read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for target, dep in re.findall(r"\(targets (\w+\.ml)\)\s*\(deps ([\w./-]+)\)", dune):
        found[target] = Path(dep).name
    return found


def required_fields() -> set[str]:
    fields: set[str] = set()
    for path in OCAML.glob("*.ml"):
        fields.update(FIELD_LOOKUP.findall(path.read_text(encoding="utf-8")))
    return fields


def main() -> int:
    declared = embedded_targets()
    if declared != EMBEDDED:
        raise SystemExit(
            "ocaml/dune embed list changed; update EMBEDDED in this test. "
            f"declared={sorted(declared.items())} expected={sorted(EMBEDDED.items())}"
        )

    documents: dict[str, dict] = {}
    for target, name in EMBEDDED.items():
        path = DATA / name
        if not path.is_file():
            raise SystemExit(f"{target} embeds {name}, which does not exist")
        try:
            documents[name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SystemExit(f"{name} is not valid JSON: {error}") from error

    records = {name: doc.get("records") for name, doc in documents.items()}
    for name, value in records.items():
        if not isinstance(value, list):
            raise SystemExit(f"{name} has no records list; the OCaml slice reads one")

    problems: list[str] = []

    # data.ml reads these fields from each pilot case and each evidence entry.
    evidence_fields = {"asset_id", "epoch", "observation", "source_url", "preview", "licence", "credit"}
    pilot = documents["three-ages-pilot.json"]
    for case in pilot["records"]:
        for field in ("source_id", "register", "facade", "structure"):
            if field not in case:
                problems.append(f"pilot case {case.get('source_id')} is missing {field}")
        for claim in ("facade", "structure"):
            for field in ("value", "status"):
                if field not in case.get(claim, {}):
                    problems.append(f"pilot {case.get('source_id')}.{claim} is missing {field}")
        for asset in case.get("image_evidence") or []:
            missing = evidence_fields - set(asset)
            if missing:
                problems.append(f"pilot evidence {asset.get('asset_id')} is missing {sorted(missing)}")

    # reviews.ml reads review fields with tolerant accessors, but the keys must exist.
    review_fields = {"facade_observation", "structural_observation", "register_observation"}
    for name in ("three-ages-image-reviews.json", "three-ages-structural-reviews.json", "three-ages-register-reviews.json"):
        for record in documents[name]["records"]:
            if not (set(record) & review_fields):
                problems.append(f"{name} record for {record.get('source_id')} carries no observation field")

    # Buildings, structural crops and the pilot's evidence list are also read by the slice.
    for record in documents["grand-place-buildings.json"]["records"]:
        for field in ("id", "name", "address"):
            if field not in record:
                problems.append(f"building record {record.get('id')} is missing {field}")
    for record in documents["three-ages-structural-crops.json"]["records"]:
        if not isinstance(record.get("assets"), list):
            problems.append(f"structural crop record {record.get('source_id')} has no assets list")
            continue
        for asset in record["assets"]:
            for field in ("asset_id", "epoch", "crop_preview", "source_preview"):
                if field not in asset:
                    problems.append(f"structural crop asset {asset.get('asset_id')} is missing {field}")
    for case in pilot["records"]:
        if not isinstance(case.get("image_evidence"), list):
            problems.append(f"pilot case {case.get('source_id')} has no image_evidence list")

    # Completeness guard: if the OCaml starts reading a new field, this test must be extended
    # rather than silently under-covering the slice's data contract.
    checked = {
        "records", "source_id", "asset_id", "epoch", "observation", "source_url", "preview",
        "licence", "credit", "register", "facade", "structure", "value", "status", "note",
        "facade_observation", "structural_observation", "register_observation", "image_evidence",
        "id", "name", "address", "assets", "crop_preview",
    }
    unchecked = sorted(required_fields() - checked)
    if unchecked:
        raise SystemExit(
            "the OCaml slice reads field(s) this contract test does not check: "
            + ", ".join(unchecked)
            + ". Extend the checks above rather than removing them from `checked`."
        )

    if problems:
        raise SystemExit("OCaml slice data contract broken:\n  " + "\n  ".join(problems))

    embedded_evidence = sum(len(case.get("image_evidence") or []) for case in pilot["records"])
    worksheet = json.loads((DATA / "three-ages-image-cases.json").read_text(encoding="utf-8"))
    print(
        f"Bonsai data contract holds: {len(documents)} embedded artifacts, "
        f"{len(pilot['records'])} pilot cases, {embedded_evidence} embedded images "
        f"(of {worksheet['record_count']} reviewable)"
    )
    print("note: the Bonsai slice renders the curated pilot only; see ocaml/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build Commons photo provenance from agent-accepted staged rows (one-off build).

Reads the staged verdict CSVs in /tmp/commons-curation (produced by the
Wikidata/category/WLM curation waves), copies the SHA-pinned 800px previews
into data/historical/commons/, and writes data/commons-photo-provenance.json
as match records (one per fiche; shared files collapse per photo in the
worksheet exporter, mirroring the BALaT pipeline).

Only rows with an agent accept/accept-caveat verdict enter. Nothing here is a
reviewed label: the worksheet review fields start blank and the training
manifest stays at 0 records until dual human review (TODO-65a73811).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from map_irismonument_corpus import CLASS_LABELS, classify_term, modernism_class

REPO_STAGE = Path(__file__).resolve().parent / "three-ages" / "data" / "commons-stage"
STAGE = REPO_STAGE if REPO_STAGE.exists() else Path("/tmp/commons-curation")
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "three-ages" / "data"
OUT_DIR = DATA / "historical" / "commons"

STAGED = ["wikidata-join-candidates.csv", "cat-candidates-clean.csv", "wlm-candidates.json"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def view_scope(reason: str) -> str:
    """Map the agent identity-gate note to a catalogue view scope."""
    text = reason.lower()
    if "detail" in text or "portal" in text:
        return "detail"
    if "ground-floor" in text or "ground floor" in text:
        return "partial-facade"
    return "facade"


def vocabulary_labels(style: str, built: str) -> str:
    """Map a raw STYLE_FR compound onto signed-off vocabulary labels."""
    labels = []
    for cls in classify_term(style or ""):
        if cls == "modernism":
            cls = (modernism_class(built) if (built or "").isdigit()
                   else "modernism_other")
        if cls in CLASS_LABELS and CLASS_LABELS[cls] not in labels:
            labels.append(CLASS_LABELS[cls])
    return "; ".join(labels)


def slug(filename: str) -> str:
    import unicodedata
    base = unicodedata.normalize("NFD", filename.rsplit(".", 1)[0].lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    out = "".join(c if c.isascii() and c.isalnum() else "-" for c in base)
    return "commons-" + "-".join(p for p in out.split("-") if p)[:80]


def main() -> None:
    meta = json.loads((STAGE / "canonical-meta.json").read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    staged_rows: list[dict] = []
    stale = STAGE / "wlm-candidates.csv"
    require(not stale.exists(), f"stale {stale} shadows wlm-candidates.json; delete it")
    for name in STAGED:
        path = STAGE / name
        if not path.exists():
            continue
        if path.suffix == ".json":
            staged_rows.extend(json.loads(path.read_text(encoding="utf-8")))
        else:
            staged_rows.extend(csv.DictReader(path.open(encoding="utf-8")))
    records = []
    seen_files: dict[str, str] = {}
    for row in staged_rows:
            if not (row.get("verdict") or "").startswith("accept"):
                continue
            if not row.get("fiche"):
                continue
            filename = row["file"]
            info = meta.get(filename, {})
            licence = row.get("licence") or info.get("licence") or ""
            if licence not in {"CC BY-SA 4.0", "CC BY-SA 3.0", "CC BY 4.0",
                               "CC BY 3.0", "CC BY 2.0", "CC0", "Public domain"}:
                raise RuntimeError(f"unexpected licence for {filename}: {licence!r}")
            src_preview = Path(row["local"])
            digest = hashlib.sha256(src_preview.read_bytes()).hexdigest()
            if row.get("sha256") and row["sha256"] != digest:
                raise RuntimeError(f"staged preview changed on disk: {filename}")
            photo_id = slug(filename)
            if filename in seen_files and seen_files[filename] != photo_id:
                raise RuntimeError(f"slug collision for {filename}")
            for other_file, other_id in seen_files.items():
                if other_file != filename and other_id == photo_id:
                    raise RuntimeError(f"slug collision: {filename!r} and {other_file!r} both map to {photo_id!r}")
            seen_files[filename] = photo_id
            target = OUT_DIR / f"{photo_id}.jpg"
            if target.exists():
                existing = hashlib.sha256(target.read_bytes()).hexdigest()
                if existing != digest:
                    raise RuntimeError(f"committed preview differs: {target}")
            else:
                target.write_bytes(src_preview.read_bytes())
                target.chmod(0o644)
            file_url = ("https://commons.wikimedia.org/wiki/File:"
                        + urllib.parse.quote(filename.replace(" ", "_")))
            records.append({
                "case_id": f"{photo_id}:{row.get('number')}",
                "photo_id": photo_id,
                "commons_file": filename,
                "file_page_url": file_url,
                "street": row.get("street") or "",
                "number": str(row.get("number") or ""),
                "class_suggestion": vocabulary_labels(row.get("style") or "", row.get("built") or ""),
                "source_style": (row.get("style") or ""),
                "built": row.get("built") or "",
                "fiche": row.get("fiche") or "",
                "matched": True,
                "title": filename,
                "photo_date_taken": "",
                "photo_view_scope": view_scope(row.get("verdict_reason") or ""),
                "agent_verdict": row.get("verdict") or "",
                "agent_verdict_reason": row.get("verdict_reason") or "",
                "credit": info.get("artist") or "",
                "licence": licence,
                "sharealike": "yes" if "BY-SA" in licence else "no",
                "attribution": f"{filename} — {info.get('artist') or 'Wikimedia Commons contributor'} ({licence}); {file_url}",
                "source_url": file_url,
                "image_url": info.get("url") or "",
                "preview": f"data/historical/commons/{photo_id}.jpg",
                "preview_sha256": digest,
            })
    if len({r["photo_id"] for r in records}) != len(seen_files):
        raise RuntimeError("photo_id accounting mismatch")
    payload = {
        "batch": "commons-curation-waves",
        "source": ("Wikidata P6375 join + Commons style-category sweep + WLM filename join; "
                   "agent visual identity gate; per-file Commons licence + artist pinned"),
        "note": ("Staged discovery previews, not reviewed training labels. ShareAlike files "
                 "carry a sharealike flag; model-weights publication needs care (see licence doc). "
                 "Promotion to labels requires owner second-look + dual annotation."),
        "records": sorted(records, key=lambda r: (r["photo_id"], r["case_id"])),
    }
    out = DATA / "commons-photo-provenance.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(records)} records / {len(seen_files)} photos -> {out}")


if __name__ == "__main__":
    main()

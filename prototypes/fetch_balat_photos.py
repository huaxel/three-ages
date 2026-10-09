#!/usr/bin/env python3
"""Acquire KIK-IRPA BALaT facade photos for Irismonument cases (CC BY 4.0 route).

For each case (street + number) the pipeline:
1. searches BALaT photos via its public server-function API (seroval envelope),
2. resolves each candidate photo's related object page to its address,
3. matches the object address to the case address (accent-insensitive),
4. downloads the 800px IIIF preview with SHA-256 pinning and records provenance.

Only photos whose rights_consent_status is free (the KIK attribution formula,
"CC-BY KIK-IRPA, Brussels, photo number") enter the corpus; SPRB-agent inventory
photos are excluded (see docs/irismonument-image-licence.md).

The seroval request/response envelope is implemented locally (subset: objects,
arrays, strings, numbers, booleans) so the pipeline needs no Node dependency.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "three-ages" / "data"
OUT_DIR = DATA / "historical" / "balat"
PROVENANCE_OUT = DATA / "balat-photo-provenance.json"

PHOTO_SEARCH_FN = "https://balat.kikirpa.be/_serverFn/45382eea2c2664d5bcdd6f94fef3822e567ce4bb9fcd3f00c0902af196a32bfd"
OBJECT_URL = "https://balat.kikirpa.be/en/object/{priref}/"
IIIF_URL = "https://iiif.kikirpa.be/iiif/2/{oid}/full/!800,800/0/default.jpg"
USER_AGENT = "three-ages-evidence-prototype/1.0 (educational corpus research)"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
SLEEP = 1.0  # gentle rate limit for the server functions


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


# --- seroval subset (encode requests, decode responses) ---------------------

def seroval_encode(value, counter=None) -> dict:
    """Encode the plain JSON-compatible Seroval subset used by BALaT's current client."""
    counter = counter if counter is not None else {"i": 0}
    if value is None:
        return {"t": 2, "s": 0}
    if isinstance(value, bool):
        return {"t": 2, "s": 2 if value else 3}
    if isinstance(value, (int, float)):
        return {"t": 0, "s": value}
    if isinstance(value, str):
        return {"t": 1, "s": value}
    if isinstance(value, (list, tuple)):
        i = counter["i"]
        counter["i"] += 1
        return {"t": 9, "i": i, "a": [seroval_encode(v, counter) for v in value], "o": 0}
    if isinstance(value, dict):
        i = counter["i"]
        counter["i"] += 1
        return {
            "t": 10, "i": i,
            "p": {"k": list(value.keys()), "v": [seroval_encode(v, counter) for v in value.values()]},
            "o": 0,
        }
    raise TypeError(f"unsupported seroval value: {type(value)}")


def seroval_envelope(data: dict) -> dict:
    """Equivalent to toJSONAsync({data}) for the JSON-compatible request subset."""
    encoded = seroval_encode({"data": data})
    return {"t": encoded, "f": 127, "m": []}


def seroval_decode(node, references=None) -> object:
    references = references if references is not None else {}
    if not isinstance(node, dict):
        return node
    t = node.get("t")
    if t in (0, 1):
        return node.get("s")
    if t == 2:
        return {0: None, 1: None, 2: True, 3: False}.get(node.get("s"))
    if t == 4:
        return references.get(node.get("i"))
    if t == 9:
        result = [seroval_decode(x, references) for x in node.get("a", [])]
        references[node.get("i")] = result
        return result
    if t in (10, 11):
        properties = node.get("p", {})
        result = {k: seroval_decode(v, references) for k, v in zip(properties.get("k", []), properties.get("v", []))}
        references[node.get("i")] = result
        return result
    return {"RAW": node}


def get_json(url: str, payload: dict) -> object:
    query = urllib.parse.urlencode({"payload": json.dumps(payload, separators=(",", ":"))})
    separator = "&" if "?" in url else "?"
    request = urllib.request.Request(
        f"{url}{separator}{query}",
        headers={"Accept": "application/x-ndjson, application/json", "x-tsr-serverFn": "true", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    require(len(raw) <= MAX_RESPONSE_BYTES, f"response exceeds {MAX_RESPONSE_BYTES:,} bytes")
    return seroval_decode(json.loads(raw))


def get_body(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    require(len(body) <= MAX_RESPONSE_BYTES, f"response exceeds {MAX_RESPONSE_BYTES:,} bytes")
    return body


# --- BALaT API helpers ------------------------------------------------------

SEARCH_FIELDS = None  # loaded lazily from the app bundle constant


def search_fields() -> str:
    global SEARCH_FIELDS
    if SEARCH_FIELDS is None:
        html = get_body("https://balat.kikirpa.be/en/").decode("utf-8", "replace")
        bundle = re.search(r'"/assets/main-[^"]+\.js"', html)
        require(bool(bundle), "could not locate the BALaT main bundle")
        js = get_body(f"https://balat.kikirpa.be{bundle.group(0).strip(chr(34))}").decode("utf-8", "replace")
        m = re.search(r'ER="([^"]+)"', js)
        require(bool(m), "could not locate the BALaT search field constants")
        SEARCH_FIELDS = m.group(1)
    return SEARCH_FIELDS


def search_photos(term: str, limit: int = 40) -> list[dict]:
    payload = {
        "searchTerm": term, "advanced": False, "wildcard": True, "fuzzy": False,
        "hierarchy": True, "defaultOperator": "and",
        "searchfieldsAccentInsensitive": search_fields(),
        "searchfieldsHierarchyAccentInsensitive": "",
        "page": 1, "limit": limit, "sort": "relevance", "withAggs": False,
    }
    result = get_json(PHOTO_SEARCH_FN, seroval_envelope(payload))
    hits = (((result or {}).get("result") or {}).get("hits") or {}).get("hits") or []
    return [h.get("_source", {}) for h in hits]


_OBJECT_ADDRESS_CACHE: dict[str, str] = {}
_PHOTO_METADATA_CACHE: dict[str, dict] = {}


def object_address(priref: str) -> str:
    if priref in _OBJECT_ADDRESS_CACHE:
        return _OBJECT_ADDRESS_CACHE[priref]
    address = ""
    try:
        html = get_body(OBJECT_URL.format(priref=priref)).decode("utf-8", "replace")
        # JSON-LD name often carries the full address: "maison - Maison X, Bruxelles, Grand-Place 6"
        m = re.search(r'"name":"([^"]+)"', html)
        if m:
            address = m.group(1)
        else:
            m = re.search(r'Emplacement / Address:([^<]+)', html)
            if m:
                address = m.group(1).strip()
    except Exception:
        pass
    time.sleep(SLEEP / 4)
    _OBJECT_ADDRESS_CACHE[priref] = address
    return address


def photo_metadata(photo_id: str) -> dict:
    """Read the public photo record's own title, displayed licence, and credit line."""
    if photo_id in _PHOTO_METADATA_CACHE:
        return _PHOTO_METADATA_CACHE[photo_id]
    page = get_body(f"https://balat.kikirpa.be/en/photo/{urllib.parse.quote(photo_id)}/").decode("utf-8", "replace")

    def field(label: str) -> str:
        pattern = rf">{re.escape(label)}</span>\s*<span[^>]*>(.*?)</span>"
        match = re.search(pattern, page, re.DOTALL | re.IGNORECASE)
        if not match:
            return ""
        return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()

    metadata = {
        "title": field("Title"),
        "date_taken": field("Date taken"),
        "represented_detail": field("Represented detail"),
        "credit_line": field("Credit line"),
        "licence": "CC BY 4.0" if re.search(r"href=\"https://creativecommons\.org/licenses/by/4\.0/\"[^>]*>.*?CC BY 4\.0", page, re.DOTALL) else "",
        "source_url": f"https://balat.kikirpa.be/en/photo/{photo_id}/",
    }
    time.sleep(SLEEP / 4)
    _PHOTO_METADATA_CACHE[photo_id] = metadata
    return metadata


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    # BALaT hyphenates multi-word street names ("Nouveau-Marché-aux-Grains"); treat
    # hyphens, dashes, underscores and apostrophe variants as word separators.
    value = re.sub(r"[‐‑‒–—―\-_’‘`ʼ']", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def view_scope(represented_detail: str) -> str:
    """Classify catalogue view scope conservatively; missing detail stays unknown."""
    detail = normalize(represented_detail or "")
    if not detail:
        return "not-stated"
    if any(term in detail for term in ("porte", "door", "detail", "ornement", "porche", "portail", "entree", "entry")):
        return "detail"
    if any(term in detail for term in ("partie", "partielle", "partiel", "vue sup", "upper")):
        return "partial-facade"
    if "facad" in detail:
        return "facade"
    return "other"


# --- acquisition ------------------------------------------------------------

def match_score(case_street: str, case_number: str, object_name: str) -> int:
    """Only an address with both street and whole house number is a training match."""
    name = normalize(object_name)
    street = normalize(case_street)
    number = normalize(case_number or "")
    if not street or street not in name or not number:
        return 0
    # Avoid matching house 6 to 16 or 60; allow BALaT punctuation between number parts.
    parts = [part for part in re.split(r"[\s,.\-/]+", number) if part]
    if not parts:
        return 0
    number_pattern = r"[\s,.\-–/]+?".join(re.escape(part) for part in parts)
    if re.search(rf"(?<![a-z0-9]){number_pattern}(?![a-z0-9])", name):
        return 4
    return 0


def acquire_case(case: dict) -> dict:
    """case: {street, number, class_label, fiche, id}. Returns a provenance record."""
    street = case.get("street") or ""
    number = case.get("number") or ""
    term = f"{street} {number}".strip()
    candidates = search_photos(term)
    time.sleep(SLEEP)

    ranked = []
    for src in candidates:
        refs = src.get("related_object_reference")
        refs = [refs] if isinstance(refs, str) else (refs or [])
        best_score = 0
        best_priref = None
        for priref in refs:
            if priref is None:
                continue
            obj_name = object_address(str(priref))
            score = match_score(street, number, obj_name)
            if score > best_score:
                best_score = score
                best_priref = str(priref)
        if best_score:
            rights = src.get("rights_consent_status") or []
            source_title = src.get("title") or ""
            if isinstance(source_title, list):
                source_title = source_title[0] if source_title else ""
            ranked.append({
                "photo_id": src.get("object_number"),
                "search_title": source_title,
                "priref": best_priref,
                "object_name": object_address(best_priref),
                "score": best_score,
                "rights": rights,
                "permission": src.get("DAMS_permission_level"),
                "media_reference": src.get("media_reference"),
            })

    ranked.sort(key=lambda r: (-r["score"], r["photo_id"] or ""))
    best = None
    for candidate in ranked:
        if candidate["score"] != 4 or "free" not in candidate["rights"] or not candidate["photo_id"]:
            continue
        metadata = photo_metadata(candidate["photo_id"])
        candidate.update(metadata)
        candidate["photo_title_score"] = match_score(street, number, metadata["title"])
        if candidate["photo_title_score"] == 4 and metadata["licence"] == "CC BY 4.0":
            best = candidate
            break

    record = {
        "case_id": case.get("case_id") or case.get("id"),
        "street": street,
        "number": number,
        "class": case.get("class_label"),
        "selection_class": case.get("selection_class"),
        "source_style": case.get("style"),
        "built": case.get("built"),
        "lon": case.get("lon"),
        "lat": case.get("lat"),
        "fiche": case.get("fiche"),
        "matched": best is not None,
        "photo_id": best["photo_id"] if best else None,
        "title": best["title"] if best else None,
        "object_name": best["object_name"] if best else None,
        "photo_page_title": best.get("title") if best else None,
        "photo_date_taken": best.get("date_taken") if best else None,
        "photo_represented_detail": best.get("represented_detail") if best else None,
        "photo_view_scope": view_scope(best.get("represented_detail", "")) if best else None,
        "credit_line": best.get("credit_line") if best else None,
        "score": best["score"] if best else 0,
        "rights": (best or {}).get("rights", []),
        "candidates": [{"photo_id": r["photo_id"], "search_title": r["search_title"], "object_name": r["object_name"],
                        "score": r["score"], "photo_title_score": r.get("photo_title_score"),
                        "photo_page_title": r.get("title"), "licence": r.get("licence")} for r in ranked[:5]],
    }
    if best and best.get("photo_id"):
        record["image_url"] = IIIF_URL.format(oid=best["photo_id"])
        record["licence"] = best["licence"]
        record["attribution"] = best["credit_line"]
        record["source_url"] = best["source_url"]
    return record


def download(record: dict) -> str | None:
    if not record.get("matched") or not record.get("image_url"):
        return None
    filename = f"balat-{record['photo_id'].lower()}.jpg"
    target = OUT_DIR / filename
    body = get_body(record["image_url"])
    require(body.startswith(b"\xff\xd8\xff"), f"BALaT preview is not a JPEG: {record['photo_id']}")
    digest = hashlib.sha256(body).hexdigest()
    if target.exists():
        existing = hashlib.sha256(target.read_bytes()).hexdigest()
        require(existing == digest, f"BALaT photo {record['photo_id']} changed on disk")
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=OUT_DIR, delete=False) as handle:
            handle.write(body)
            temporary = Path(handle.name)
        temporary.chmod(0o644)
        os.replace(temporary, target)
    record["preview"] = f"data/historical/balat/{filename}"
    record["preview_sha256"] = digest
    time.sleep(SLEEP)
    return filename


def coverage_report(records: list[dict], batch_name: str) -> dict:
    """Summarize acquisition outcomes by vocabulary class without obscuring failures."""
    classes: dict[str, dict] = {}
    for record in records:
        label = record.get("class") or "(unlabelled)"
        summary = classes.setdefault(label, {
            "cases": 0, "matched": 0, "downloaded": 0, "view_scope_counts": {},
            "unique_buildings": set(), "unique_photos": set(),
        })
        summary["cases"] += 1
        summary["matched"] += bool(record.get("matched"))
        summary["downloaded"] += bool(record.get("preview_sha256"))
        fiche = record.get("fiche") or ""
        building_id = fiche.rstrip("/").rsplit("/", 1)[-1] if fiche else record.get("case_id")
        if building_id:
            summary["unique_buildings"].add(building_id)
        if record.get("preview_sha256") and record.get("photo_id"):
            summary["unique_photos"].add(record["photo_id"])
            scope = record.get("photo_view_scope")
            if scope:
                summary["view_scope_counts"][scope] = summary["view_scope_counts"].get(scope, 0) + 1
    for summary in classes.values():
        for key in ("unique_buildings", "unique_photos"):
            summary[key] = len(summary[key])
    unique_photos = {record["photo_id"] for record in records if record.get("preview_sha256") and record.get("photo_id")}
    unique_buildings = {
        (record.get("fiche") or "").rstrip("/").rsplit("/", 1)[-1] or record.get("case_id")
        for record in records
    }
    unique_buildings.discard(None)
    photo_scopes = {}
    for record in records:
        if record.get("photo_id") and record.get("preview_sha256") and record.get("photo_view_scope"):
            photo_scopes.setdefault(record["photo_id"], record["photo_view_scope"])
    unique_scope_counts = {}
    for scope in photo_scopes.values():
        unique_scope_counts[scope] = unique_scope_counts.get(scope, 0) + 1
    return {
        "batch": batch_name, "total_cases": len(records),
        "unique_buildings": len(unique_buildings), "unique_photos": len(unique_photos),
        "unique_photo_view_scopes": unique_scope_counts,
        "classes": classes,
    }


def load_selection(
    path: Path, limit_per_class: int | None = None, offset_per_class: int = 0,
    sample_field: str = "sample",
) -> list[dict]:
    if sample_field not in ("sample", "additional_sample"):
        raise ValueError(f"unknown sample field: {sample_field}")
    selection = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for class_key, class_data in selection["classes"].items():
        candidates = class_data.get(sample_field, [])
        start = offset_per_class
        stop = None if limit_per_class is None else start + limit_per_class
        candidates = candidates[start:stop]
        for index, candidate in enumerate(candidates, start=start):
            cases.append({
                **candidate,
                "case_id": f"{class_key}:{candidate.get('id')}:{candidate.get('number')}:{index}",
                "selection_class": class_key,
                "class_label": class_data["label"],
            })
    return cases


def main(cases: list[dict], batch_name: str = "batch", output: Path = PROVENANCE_OUT) -> None:
    provenance = []
    for case in cases:
        try:
            record = acquire_case(case)
            download(record)
        except Exception as error:
            record = {
                "case_id": case.get("case_id") or case.get("id"),
                "street": case.get("street"), "number": case.get("number"),
                "class": case.get("class_label"), "selection_class": case.get("selection_class"),
                "source_style": case.get("style"), "built": case.get("built"),
                "lon": case.get("lon"), "lat": case.get("lat"), "fiche": case.get("fiche"),
                "matched": False, "photo_id": None, "error": f"{type(error).__name__}: {error}",
            }
        provenance.append(record)
        write_json(output, {"batch": batch_name, "records": provenance,
                            "coverage": coverage_report(provenance, batch_name)})
        print(f"{'OK ' if record['matched'] else 'NO '} {record.get('street')} {record.get('number')} "
              f"-> {record.get('photo_id') or '-'} (score {record.get('score', 0)})")
    matched = sum(1 for r in provenance if r["matched"])
    print(f"batch {batch_name}: {matched}/{len(provenance)} matched; provenance -> {output}")


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, help="process per-class candidate samples from this selection JSON")
    parser.add_argument("--limit-per-class", type=int, help="bound selection sample size for a validation run")
    parser.add_argument("--offset-per-class", type=int, default=0, help="skip this many selector samples in each class")
    parser.add_argument("--sample-field", default="sample", choices=["sample", "additional_sample"], help="select first- or second-stage unique-building samples")
    parser.add_argument("--output", type=Path, default=PROVENANCE_OUT, help="provenance output path")
    args = parser.parse_args()
    if args.limit_per_class is not None and args.limit_per_class < 1:
        parser.error("--limit-per-class must be positive")
    if args.offset_per_class < 0:
        parser.error("--offset-per-class must be non-negative")
    if args.selection:
        cases = load_selection(args.selection, args.limit_per_class, args.offset_per_class, args.sample_field)
        if not cases:
            parser.error("selection contains no cases")
        main(cases, batch_name="irismonument-selection-sample", output=args.output)
        return
    # Default remains the small identity-validation pilot; no surprise corpus crawl.
    pilot_cases = [
        {"id": "005", "street": "Grand-Place", "number": "6", "class_label": "Baroque", "fiche": "31123"},
        {"id": "009", "street": "Grand-Place", "number": "9", "class_label": "Louis XIV", "fiche": "40020"},
        {"id": "022", "street": "Grand-Place", "number": "21-22", "class_label": "Baroque", "fiche": "31138"},
        {"id": "023", "street": "Grand-Place", "number": "23", "class_label": "Baroque", "fiche": "31139"},
        {"id": "024", "street": "Rue de la Colline", "number": "24", "class_label": "Baroque", "fiche": "30991"},
        {"id": "026", "street": "Grand-Place", "number": "26-27", "class_label": "Baroque with Renaissance elements", "fiche": "31141"},
    ]
    main(pilot_cases, batch_name="pilot-validation", output=args.output)


if __name__ == "__main__":
    cli()

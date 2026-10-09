#!/usr/bin/env python3
"""Map Irismonument style terms onto the signed-off facade vocabulary and select per-class training cases.

Reads data/irismonument-inventory.json (see fetch_irismonument.py), normalizes the 340
raw STYLE_FR terms onto the reviewer-agreed classes in docs/facade-style-vocabulary.md,
and writes two committed artifacts:

1. data/irismonument-style-mapping.json  — term -> classes (machine-readable mapping)
2. data/irismonument-case-selection.json — per-class candidate counts, criteria, sample

Vocabulary decisions recorded 2026-10-09 with the project owner (see
docs/facade-style-vocabulary.md "Corpus extension"): Neoclassical and Beaux-Arts are own
classes; Second Empire is an own class and the other 19th-c. French period styles
(Empire, Louis-Philippe, Rococo, Régence, Mauresque) fold into Historicist neo-styles;
École d'Amsterdam, Nieuwe eenvoud and Classicisme moderne fold into Modernism; High-tech
folds into Contemporary; Modernism sub-periods are bucketed by build year (BULT).

Descriptor terms (Architecture régionaliste, pittoresque, rurale, traditionnelle,
traditionaliste, d'intégration) describe approach rather than period and stay out of
positive labels, mirroring the vocabulary's "style not named in source" class.
"""
from __future__ import annotations

import collections
import json
import os
import tempfile
import unicodedata
from pathlib import Path

from lambert_wgs84 import lambert72_to_wgs84

ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "three-ages" / "data" / "irismonument-inventory.json"
MAPPING_OUT = ROOT / "three-ages" / "data" / "irismonument-style-mapping.json"
SELECTION_OUT = ROOT / "three-ages" / "data" / "irismonument-case-selection.json"

# Canonical vocabulary class keys (docs/facade-style-vocabulary.md + corpus extension).
CLASS_LABELS = {
    "baroque": "Baroque",
    "baroque_classical": "Baroque with classical features",
    "neoclassical": "Neoclassical",
    "second_empire": "Second Empire",
    "eclecticism": "Eclecticism",
    "historicist_neo": "Historicist neo-styles",
    "beaux_arts": "Beaux-Arts",
    "art_nouveau": "Art Nouveau",
    "art_deco": "Art Deco",
    "paquebot": "Paquebot style",
    "functionalism": "Functionalism",
    "modernism_interwar": "Modernism (interwar)",
    "modernism_postwar": "Modernism (post-war)",
    "modernism_expo58": "Modernism (Expo 58)",
    "modernism_late": "Modernism (late)",
    "modernism_other": "Modernism (period undetermined)",
    "brutalism": "Brutalism",
    "postmodernism": "Postmodernism",
    "contemporary": "Contemporary",
}
# Descriptor bucket: excluded from positive labels (approach terms, not periods).
DESCRIPTOR = "descriptor (non-period; excluded from positive labels)"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = text.replace("\u2019", "'").replace("\u2018", "'")  # curly -> straight apostrophe
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


# substring -> class key | None (decision) | DESCRIPTOR. Order matters (longest first).
RULES = [
    ("ecole d'amsterdam", "modernism_other"),      # folds into Modernism (decided)
    ("nieuwe eenvoud", "modernism_other"),
    ("classicisme moderne", "modernism_other"),
    ("pre-modernisme", "modernism_other"),
    ("second empire", "second_empire"),            # before "empire"
    ("neoclassicisme", "neoclassical"),
    ("eclectisme", "eclecticism"),                 # includes "Éclectisme tardif"
    ("art deco", "art_deco"),
    ("art nouveau", "art_nouveau"),
    ("secession viennoise", "art_nouveau"),        # geometric Art Nouveau (glossary)
    ("postmodernisme", "postmodernism"),
    ("modernisme", "modernism"),                   # sub-period by BULT
    ("paquebot", "paquebot"),
    ("fonctionnalisme", "functionalism"),
    ("brutalisme", "brutalism"),
    ("high-tech", "contemporary"),
    ("neogothique", "historicist_neo"),
    ("neo-renaissance", "historicist_neo"),
    ("neo-baroque", "historicist_neo"),
    ("neo-roman", "historicist_neo"),
    ("neo-egyptien", "historicist_neo"),
    ("gothique", "historicist_neo"),
    ("roman", "historicist_neo"),
    ("renaissance flamande", "historicist_neo"),
    ("empire", "historicist_neo"),                 # folds (decided)
    ("louis-philippe", "historicist_neo"),
    ("rococo", "historicist_neo"),
    ("regence", "historicist_neo"),
    ("mauresque", "historicist_neo"),
    ("classicisant", "baroque_classical"),         # before "baroque": Baroque classicisant
    ("baroque", "baroque"),
    ("beaux-arts", "beaux_arts"),
    ("historicisme", "historicist_neo"),
    ("architecture regionaliste", DESCRIPTOR),
    ("architecture pittoresque", DESCRIPTOR),
    ("architecture rurale", DESCRIPTOR),
    ("architecture traditionnelle", DESCRIPTOR),
    ("architecture traditionaliste", DESCRIPTOR),
    ("architecture d'integration", DESCRIPTOR),
]

MODERNISM_SUBPERIOD = [
    (1920, 1940, "modernism_interwar"),
    (1940, 1950, "modernism_postwar"),
    (1950, 1966, "modernism_expo58"),
    (1966, 1981, "modernism_late"),
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def classify_term(term: str) -> list[str]:
    classes = []
    for part in [p.strip() for p in term.split(",")]:
        pn = norm(part)
        for rule, cls in RULES:
            if rule in pn:
                if cls not in classes:
                    classes.append(cls)
                break
        else:
            classes.append(f"UNMAPPED:{part}")
    return classes


def modernism_class(bult) -> str:
    for lo, hi, cls in MODERNISM_SUBPERIOD:
        if lo <= int(bult) < hi:
            return cls
    return "modernism_other"


def build_mapping(rows) -> dict:
    counts = collections.Counter((r.get("STYLE_FR") or "").strip() for r in rows)
    counts.pop("", None)
    mapping = {term: {"count": n, "classes": classify_term(term)} for term, n in counts.items()}
    require(all(term.strip() for term in mapping), "empty style term in mapping")
    require(
        all(not any(c.startswith("UNMAPPED:") for c in entry["classes"]) for entry in mapping.values()),
        "unmapped style terms remain; extend RULES before committing",
    )
    return mapping


def sample_buildings(
    candidates: list[dict], limit: int = 10, exclude_ids: set[str] | None = None,
) -> tuple[list[dict], int]:
    """Choose unique-fiche examples spread over available years and fiche IDs."""
    grouped: dict[str, dict] = {}
    exclude_ids = exclude_ids or set()

    def preferred(candidate: dict) -> tuple[int, int, str]:
        path_parts = candidate.get("fiche", "").rstrip("/").split("/")
        fiche_number = path_parts[-2] if len(path_parts) >= 2 else ""
        number = str(candidate.get("number") or "")
        primary_address_penalty = 0 if fiche_number and number == fiche_number else 1
        coordinate_penalty = 0 if candidate.get("lon") is not None and candidate.get("lat") is not None else 1
        return primary_address_penalty, coordinate_penalty, number

    for candidate in candidates:
        key = str(candidate.get("id") or candidate.get("fiche") or "")
        if not key or key in exclude_ids:
            continue
        if key not in grouped or preferred(candidate) < preferred(grouped[key]):
            grouped[key] = candidate

    unique = sorted(
        grouped.values(),
        key=lambda c: (
            int(c["built"]) if str(c.get("built") or "").isdigit() else 9999,
            str(c.get("id") or ""), str(c.get("street") or ""), str(c.get("number") or ""),
        ),
    )
    if len(unique) <= limit:
        return unique, len(unique)
    if limit == 1:
        return [unique[len(unique) // 2]], len(unique)
    indices = [round(i * (len(unique) - 1) / (limit - 1)) for i in range(limit)]
    return [unique[index] for index in indices], len(unique)


def select_cases(rows, mapping) -> dict:
    by_class: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        term = (row.get("STYLE_FR") or "").strip()
        if not term:
            continue
        classes = mapping.get(term, {}).get("classes", [])
        for cls in classes:
            if cls == "modernism":
                cls = modernism_class(row.get("BULT")) if (row.get("BULT") or "").isdigit() else "modernism_other"
            if cls in CLASS_LABELS:  # positive label classes only
                candidate = {
                    "id": row.get("ID_BATI_DMS"),
                    "street": row.get("STREET_FR"),
                    "number": row.get("NUMBER"),
                    "style": term,
                    "built": row.get("BULT"),
                    "fiche": row.get("URL_FR"),
                    "x": row.get("x"),
                    "y": row.get("y"),
                }
                if candidate["x"] and candidate["y"]:
                    try:
                        lon, lat = lambert72_to_wgs84(float(candidate["x"]), float(candidate["y"]))
                        candidate["lon"], candidate["lat"] = round(lon, 6), round(lat, 6)
                    except (TypeError, ValueError):
                        pass
                by_class[cls].append(candidate)

    selection = {
        "criteria": "records whose STYLE_FR maps to a positive label class; retain available BULT and Lambert-72 coordinates (converted to WGS84 lon/lat via prototypes/lambert_wgs84.py, validated against pyproj). Missing build years remain unknown; Modernism sub-periods use BULT when available (1920-40 interwar, 1940-50 post-war, 1950-66 Expo 58, 1966-81 late)",
        "sample_strategy": "deduplicate by building fiche ID, prefer the fiche's primary address then a geocoded address, sort by available build year and fiche ID, and select up to ten evenly spaced unique buildings; not a probability sample",
        "decisions_recorded": "2026-10-09 (see docs/facade-style-vocabulary.md Corpus extension)",
        "classes": {},
    }
    for cls, label in CLASS_LABELS.items():
        candidates = by_class.get(cls, [])
        sample, unique_buildings = sample_buildings(candidates)
        sampled_ids = {str(candidate.get("id") or candidate.get("fiche") or "") for candidate in sample}
        additional_sample, remaining_buildings = sample_buildings(candidates, exclude_ids=sampled_ids)
        selection["classes"][cls] = {
            "label": label,
            "count": len(candidates),
            "unique_buildings": unique_buildings,
            "sample": sample,
            "additional_sample": additional_sample,
            "remaining_unique_buildings": remaining_buildings,
        }
    return selection


def main() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rows = inventory["records"]
    mapping = build_mapping(rows)
    write_json(MAPPING_OUT, {
        "source": "Irismonument WFS snapshot (data/irismonument-inventory.json)",
        "decisions": "reviewer-agreed 2026-10-09; see docs/facade-style-vocabulary.md",
        "mapping": mapping,
    })
    selection = select_cases(rows, mapping)
    write_json(SELECTION_OUT, selection)
    print(f"mapped {len(mapping)} style terms; selection classes: {len(selection['classes'])}")
    for cls, info in selection["classes"].items():
        print(f"  {info['count']:6}  {info['label']}")


if __name__ == "__main__":
    main()
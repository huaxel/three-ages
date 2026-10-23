#!/usr/bin/env python3
"""Validate and summarise a scraped inventory corpus.

A full sweep writes one JSON file per notice, which is useful to a program but
opaque to a human and impossible to eyeball for corruption. This reads the corpus
back, proves it is internally consistent, and turns it into counts.

Integrity checks (any failure means exit 1):

* every record parses as **strict** JSON, so no ``NaN``/``Infinity`` slipped in;
* each record carries the expected schema version and required keys;
* ``building_id`` is unique and matches its filename;
* every ``content_hash`` is a 64-character digest;
* every interest ``criteria_ref`` resolves in the shared rubric store, which is
  what would break first if a long run were interrupted mid-way.

Usage
-----
    python3 prototypes/three-ages/summarise_corpus.py
    python3 prototypes/three-ages/summarise_corpus.py --csv /tmp/corpus.csv
    python3 prototypes/three-ages/summarise_corpus.py local/scraped --index local/monument-index/monuments.fr.json
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import importlib.util
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]

REQUIRED_KEYS = (
    "schema_version",
    "building_id",
    "url",
    "identity",
    "city",
    "images",
    "tags",
    "interests",
    "extraction",
    "details",
)


def load_scraper_constants() -> dict[str, object]:
    """Read the producer's constants so this validator cannot drift from it."""
    spec = importlib.util.spec_from_file_location(
        "scrape_monument", ROOT / "scrape_monument.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return {
        "schema_version": module.SCHEMA_VERSION,
        "non_canonical": tuple(module.NON_CANONICAL_FIELDS),
        # Taken from the producer so this check cannot drift from it.
        "building_url": module.building_url,
    }


ENCODING_DAMAGE = "\ufffd"  # the replacement character: unambiguous corruption


def strict_loads(text: str) -> object:
    """Parse JSON strictly and refuse encoding damage.

    `\\ufffd` means bytes were decoded with the wrong charset, so any text in the record may
    be mangled — descriptions especially, since they are the point of this corpus. Measured
    clean across all 26,419 records when this was added, and nothing else would have caught it.
    """
    if ENCODING_DAMAGE in text:
        raise ValueError("contains U+FFFD replacement characters (encoding damage)")

    def reject(value: str) -> None:
        raise ValueError(f"non-standard JSON constant {value}")

    return json.loads(text, parse_constant=reject)


def strict_load(path: Path) -> object:
    return strict_loads(path.read_text(encoding="utf-8"))


def date_like_roles(record: dict) -> list[str]:
    """Contributor roles that are really mis-parsed date fragments.

    The notices emit year ranges as two spans (1850 then -1875), so a role that
    starts with a dash or a digit means the range was split wrong. This is the
    single definition behind both the integrity check and ``--suspect-ids``, so a
    repair can never work from a different rule than the check that found the
    problem.
    """
    return [
        role
        for person in record.get("contributors", [])
        for role in person.get("roles", [])
        if str(role).startswith("-") or str(role)[:1].isdigit()
    ]


def load_corpus(
    directory: Path, lang: str, expected_schema: object, building_url
) -> tuple[list[dict], dict[str, dict], list[str]]:
    """Read every record, returning (records, rubric store, problems)."""
    problems: list[str] = []
    records: list[dict] = []

    if not directory.is_dir():
        return [], {}, [f"{directory} is not a directory"]

    store_path = directory / f"rubrics.{lang}.json"
    store: dict[str, dict] = {}
    if store_path.exists():
        try:
            store = strict_load(store_path).get("rubrics", {})
        except (ValueError, json.JSONDecodeError, AttributeError) as error:
            problems.append(f"{store_path.name}: unreadable rubric store ({error})")

    seen: dict[str, str] = {}
    for path in sorted(directory.glob(f"*.{lang}.json")):
        # rubrics.<lang>.json and _failures.<lang>.json share the suffix but are
        # not records.
        if path.name.startswith(("rubrics.", "_")):
            continue
        try:
            record = strict_load(path)
        except (ValueError, json.JSONDecodeError) as error:
            problems.append(f"{path.name}: not strict JSON ({error})")
            continue
        if not isinstance(record, dict):
            problems.append(f"{path.name}: top level is not an object")
            continue

        missing = [key for key in REQUIRED_KEYS if key not in record]
        if missing:
            problems.append(f"{path.name}: missing keys {', '.join(missing)}")
            continue

        if record["schema_version"] != expected_schema:
            problems.append(
                f"{path.name}: schema_version {record['schema_version']!r} "
                f"!= {expected_schema!r}"
            )

        building_id = str(record["building_id"])
        if path.name != f"{building_id}.{lang}.json":
            problems.append(f"{path.name}: filename does not match id {building_id}")
        # The record must point at the page it came from. Nothing else ties a record to its
        # notice, and this host has a URL shape that looks like one notice but is another
        # (the street page), so the identity is worth asserting rather than assuming.
        expected_url = building_url(str(building_id), lang)
        if str(record.get("url") or "") != expected_url:
            problems.append(
                f"{path.name}: url is {record.get('url')!r}, not {expected_url}"
            )
        # Provenance: when this notice was taken. A naive or unparseable stamp makes the
        # corpus undatable, which matters because it is a record of a moment in time.
        try:
            moment = datetime.datetime.fromisoformat(str(record.get("retrieved_at") or ""))
            if moment.tzinfo is None:
                raise ValueError("no timezone offset")
        except ValueError as error:
            problems.append(f"{path.name}: retrieved_at is not an ISO 8601 instant ({error})")
        if building_id in seen:
            problems.append(f"{path.name}: duplicate building_id also in {seen[building_id]}")
        seen[building_id] = path.name

        digest = record.get("extraction", {}).get("content_hash")
        if not isinstance(digest, str) or len(digest) != 64:
            problems.append(f"{path.name}: content_hash is not a 64-char digest")

        for interest in record.get("interests", []):
            ref = interest.get("criteria_ref")
            if ref is not None and ref not in store:
                problems.append(f"{path.name}: criteria_ref {ref!r} missing from the store")

        # A contributor role that looks like a date means a split year range was
        # mis-parsed; the notices emit ranges as two spans, e.g. 1850 then -1875.
        for role in date_like_roles(record):
            problems.append(
                f"{path.name}: contributor role {role!r} looks like a date"
            )

        records.append(record)

    return records, store, problems


def corpus_rows(records: list[dict]) -> list[dict[str, object]]:
    """Flatten each record into one CSV-friendly row."""
    rows = []
    for record in records:
        identity = record["identity"]
        city = record["city"]
        description = record.get("description") or {}
        legal = record.get("legal_status") or {}
        images = record.get("images", [])
        rows.append(
            {
                "building_id": record["building_id"],
                "city_code": city.get("id"),
                "city": city.get("name"),
                "street": identity.get("street"),
                "house_number": identity.get("house_number"),
                "name": identity.get("name"),
                "extra_streets": len(record.get("addresses", [])) - 1,
                "protection_date": legal.get("date"),
                "interests": "|".join(i["value"] for i in record.get("interests", [])),
                "typologies": "|".join(record.get("typologies", [])),
                "styles": "|".join(record.get("styles", [])),
                "pictures": len(images),
                "credited_pictures": sum(1 for i in images if i.get("credit_holders")),
                "has_description": bool(description.get("text")),
                "description_chars": len(description.get("text", "")),
                "url": record["url"],
            }
        )
    return rows


def index_points(path: Path) -> dict[str, list[tuple[float, float]]]:
    """The index's own (lat, lon) for every building id, from its GeoJSON.

    The index carries one feature per entrance, so a corner building has several
    points, and coordinates arrive as GeoJSON ``[lon, lat]``.
    """
    points: dict[str, list[tuple[float, float]]] = {}
    try:
        payload = strict_load(path)
        for feature in payload.get("features", []):
            building_id = str(feature.get("properties", {}).get("id", "")).strip()
            coordinates = (feature.get("geometry") or {}).get("coordinates") or []
            if building_id and len(coordinates) == 2:
                points.setdefault(building_id, []).append(
                    (float(coordinates[1]), float(coordinates[0]))
                )
    except (ValueError, json.JSONDecodeError, OSError, TypeError, IndexError):
        return {}
    return points


def metres_apart(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance in metres, exact enough at city scale."""
    dx = (lon1 - lon2) * math.cos(math.radians((lat1 + lat2) / 2)) * 111320.0
    dy = (lat1 - lat2) * 110540.0
    return math.hypot(dx, dy)


# Beyond this a notice does not place a building where the publisher's own index
# does. Measured agreement is a median of 0 m and a 90th percentile of 2.3 m, so
# this is well clear of ordinary variation between the two sources' points.
COORDINATE_TOLERANCE_METRES = 25.0


def coordinate_divergence(
    records: list[dict], points: dict[str, list[tuple[float, float]]]
) -> tuple[int, int, list[tuple[float, str, float, float]], list[tuple[int, tuple[float, float]]]]:
    """Compare each notice's coordinates with the publisher's index for that id.

    Returns (checked, divergent, worst, repeated): the records compared, the count
    that do not sit where the index puts them, the most distant few, and any single
    coordinate shared by many notices. That last shape is the source's placeholder:
    2,406 notices carry one identical value, 230 km from the city. A placeholder is
    a source defect rather than a corpus error, so it is reported separately and
    never fails the integrity check.
    """
    checked = divergent = 0
    worst: list[tuple[float, str, float, float]] = []
    seen: collections.Counter[tuple[float, float]] = collections.Counter()
    for record in records:
        coordinates = record.get("coordinates") or {}
        try:
            latitude = float(coordinates["latitude"])
            longitude = float(coordinates["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        candidates = points.get(str(record.get("building_id")))
        if not candidates:
            continue
        checked += 1
        distance = min(metres_apart(latitude, longitude, lat, lon) for lat, lon in candidates)
        if distance <= COORDINATE_TOLERANCE_METRES:
            continue
        divergent += 1
        seen[(round(latitude, 5), round(longitude, 5))] += 1
        worst.append((distance, str(record.get("building_id")), latitude, longitude))
    worst.sort(reverse=True)
    repeated = sorted(((n, c) for c, n in seen.items() if n > 1), reverse=True)
    return checked, divergent, worst[:5], repeated[:3]


# A picture's own date is written into its caption ("Rue X 86, 1998"), and the
# newest captions carry the current year, which is what identifies the trailing
# year as the capture date rather than a year the building was merely mentioned in.
CAPTION_YEAR_RE = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")


def caption_years(records: list[dict]) -> dict[str, int]:
    """How much of the picture set is dated, and over what span.

    This is the corpus's temporal axis. A comparison across eras needs pictures of
    the same building from different years, so the counts that matter are how many
    pictures carry a date at all and how many buildings are covered in more than one
    decade. A caption that names a year for another reason (a building date inside a
    longer caption) is not separated out; the share and the span are robust to those,
    and the newest captions carrying the current year are the sanity check that the
    trailing year really is the capture date.
    """
    years: list[int] = []
    total = 0
    decades: dict[str, set[int]] = collections.defaultdict(set)
    for record in records:
        for image in record.get("images") or []:
            total += 1
            found = CAPTION_YEAR_RE.findall(str(image.get("caption") or ""))
            if not found:
                continue
            year = int(found[-1])
            years.append(year)
            decades[str(record.get("building_id"))].add((year // 10) * 10)
    if not years:
        return {"dated": 0, "total": total, "multi_decade": 0}
    years.sort()
    return {
        "dated": len(years),
        "total": total,
        "min": years[0],
        "max": years[-1],
        "median": years[len(years) // 2],
        "multi_decade": sum(1 for spans in decades.values() if len(spans) > 1),
    }


def build_report(
    records: list[dict],
    store: dict[str, dict],
    problems: list[str],
    index_ids: list[str] | None = None,
    target: Path | None = None,
    csv_path: Path | None = None,
    points: dict[str, list[tuple[float, float]]] | None = None,
) -> str:
    """Render the integrity verdict and corpus counts."""
    lines: list[str] = []
    total = len(records)
    lines.append(f"corpus: {target}")
    lines.append(f"records: {total} · shared rubrics: {len(store)}")
    if index_ids:
        have = {str(r["building_id"]) for r in records}
        missing = [i for i in index_ids if i not in have]
        lines.append(
            f"index coverage: {len(index_ids) - len(missing)}/{len(index_ids)} "
            f"({100 * (len(index_ids) - len(missing)) / len(index_ids):.1f}%)"
            + (f" · {len(missing)} still to fetch" if missing else " · complete")
        )
    if csv_path is not None:
        lines.append(f"csv: {csv_path}")
    lines.append(f"integrity: {'FAIL' if problems else 'PASS'}" + (
        f" ({len(problems)} problem(s))" if problems else ""
    ))
    if problems:
        for problem in problems[:25]:
            lines.append(f"  ! {problem}")
        if len(problems) > 25:
            lines.append(f"  ... and {len(problems) - 25} more")
    if points:
        checked, divergent, worst, repeated = coordinate_divergence(records, points)
        lines.append(
            f"coordinates vs index: {checked - divergent}/{checked} within "
            f"{COORDINATE_TOLERANCE_METRES:.0f} m · {divergent} divergent"
        )
        for count, (latitude, longitude) in repeated:
            lines.append(
                f"  ! one value recurs across {count} notice(s): {latitude}, "
                f"{longitude} — the source's placeholder, not a building location"
            )
        for distance, building_id, latitude, longitude in worst:
            # Sub-kilometre divergence is expected here (a long or multi-number building
            # whose entrance differs from its centroid), so it must not be printed as
            # "0 km", which reads as agreement in a line that says divergent.
            extent = f"{distance:.0f} m" if distance < 1000 else f"{distance / 1000:.0f} km"
            lines.append(
                f"  ! building {building_id} at {latitude:.5f}, {longitude:.5f} is "
                f"{extent} from where the index puts it"
            )
    if not total:
        return "\n".join(lines)

    with_prose = sum(1 for r in records if (r.get("description") or {}).get("text"))
    lines.append(
        f"descriptions: {with_prose}/{total} ({100 * with_prose / total:.1f}%) · "
        f"median {statistics.median([len((r.get('description') or {}).get('text', '')) for r in records]):,.0f} chars"
    )
    images = [len(r["images"]) for r in records]
    credited = sum(1 for r in records for i in r["images"] if i.get("credit_holders"))
    lines.append(
        f"pictures: {sum(images)} total · median {statistics.median(images):.0f} · "
        f"max {max(images)} · raw URLs only ({credited} carry a credit)"
    )
    dated = caption_years(records)
    if dated["dated"]:
        lines.append(
            f"caption years: {dated['dated']}/{dated['total']} dated "
            f"({100 * dated['dated'] / max(dated['total'], 1):.1f}%) · "
            f"{dated['min']}-{dated['max']} · median {dated['median']} · "
            f"{dated['multi_decade']} building(s) span 2+ decades"
        )
    dates = [d for r in records if (d := (r.get("legal_status") or {}).get("date"))]
    lines.append(f"protection dates: {len(dates)}/{total}")

    lines.append("\nby municipality")
    by_city = collections.defaultdict(list)
    for record in records:
        by_city[(record["city"].get("id"), record["city"].get("name"))].append(record)
    lines.append(f"  {'code':6} {'records':>7} {'prose':>7} {'pics':>6}  name")
    for (code, name), group in sorted(by_city.items(), key=lambda kv: -len(kv[1])):
        prose = sum(1 for r in group if (r.get("description") or {}).get("text"))
        pics = sum(len(r["images"]) for r in group)
        lines.append(
            f"  {code or '?':6} {len(group):>7} "
            f"{100 * prose / len(group):>6.0f}% {pics:>6}  {(name or '')[:34]}"
        )

    lines.append("\ntag frequencies (interests)")
    interests = collections.Counter(i["value"] for r in records for i in r.get("interests", []))
    for value, count in interests.most_common(10):
        lines.append(f"  {count:6}  {value}")

    lines.append("\ntag frequencies (typologies, top 10)")
    typologies = collections.Counter(t for r in records for t in r.get("typologies", []))
    for value, count in typologies.most_common(10):
        lines.append(f"  {count:6}  {value[:64]}")

    styles = collections.Counter(t for r in records for t in r.get("styles", []))
    if styles:
        lines.append(f"\nstyles: {len(styles)} distinct · " + ", ".join(
            f"{v} ({c})" for v, c in styles.most_common(6)
        ))

    multi = sum(1 for r in records if len(r.get("addresses", [])) > 1)
    lines.append(f"\nmulti-street notices: {multi}")
    return "\n".join(lines)


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarise a scraped inventory corpus"
    )
    parser.add_argument("directory", nargs="?", type=Path,
                        default=REPO_ROOT / "local" / "scraped",
                        help="corpus directory (default: local/scraped)")
    parser.add_argument("--lang", default="fr", help="record language suffix (default: fr)")
    parser.add_argument("--csv", type=Path, default=None, help="also export a flat CSV")
    parser.add_argument("--suspect-ids", action="store_true",
                        help="print the building ids whose contributor dates were "
                             "mis-parsed, one per line, for a targeted re-fetch")
    parser.add_argument("--index", type=Path,
                        default=REPO_ROOT / "local" / "monument-index" / "monuments.fr.json",
                        help="index JSON to measure coverage against")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    constants = load_scraper_constants()
    records, store, problems = load_corpus(
        args.directory, args.lang, constants["schema_version"], constants["building_url"]
    )

    if args.suspect_ids:
        # Only the mis-parsed records, so a repair costs a handful of requests
        # instead of re-fetching a correct 26,000-notice corpus.
        for record in records:
            if date_like_roles(record):
                print(record["building_id"])
        return 1 if problems else 0

    index_ids = None
    points = None
    if args.index.exists():
        try:
            payload = strict_load(args.index)
            index_ids = [
                str(f.get("properties", {}).get("id", "")).strip()
                for f in payload.get("features", [])
            ]
            index_ids = [i for i in dict.fromkeys(index_ids) if i]
            points = index_points(args.index)
        except (ValueError, json.JSONDecodeError, AttributeError):
            index_ids = None
            points = None

    csv_path = None
    if args.csv is not None and records:
        write_csv(corpus_rows(records), args.csv)
        csv_path = args.csv

    print(build_report(records, store, problems, index_ids, args.directory, csv_path, points))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

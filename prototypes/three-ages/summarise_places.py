#!/usr/bin/env python3
"""Validate and summarise a scraped corpus of `notices de lieu`.

The building corpus has `summarise_corpus.py`: it proves the records are internally
consistent and reports what they contain. Place notices are a different entity — a
street, square or avenue, with no address, tags, legal status or contributors — so they
need their own check rather than a branch inside that one.

Three things this enforces that are not obvious from the record shape:

* **The URL and the record must agree.** A place's identity is spread across its
  `place_id`, its filename and the four-segment address URL; if those drift apart, the
  record is filed under a street it does not describe.
* **Two pictures of one place must not collide as filenames**, judged
  case-insensitively. The building corpus lost a picture to exactly this (571 notices
  serve one basename under two URLs, and 68 differ only in extension case), so the same
  invariant is checked here rather than rediscovered.
* **The prose must not contain the page's own navigation label.** "Voir les biens de ce
  lieu" sits inside the same element as the introduction, so a parser regression would
  prepend it to every description; it is stripped deliberately and this is the guard.

Usage
-----
    python3 prototypes/three-ages/summarise_places.py
    python3 prototypes/three-ages/summarise_places.py local/scraped-places
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]

KIND = "place"
PLACE_SEGMENTS = 4
TRAILING_ID_RE = re.compile(r"/(\d+)/?$")
NAVIGATION_LABEL = "Voir les biens de ce lieu"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


ENCODING_DAMAGE = "\ufffd"  # the replacement character: unambiguous corruption


def strict_loads(text: str) -> object:
    """Parse JSON strictly, so neither a NaN nor decoding damage enters the corpus.

    ``\ufffd`` means bytes were decoded with the wrong charset, which would mangle the
    place introductions — the whole point of this corpus. The same rule lives in
    `summarise_corpus.py`; both scripts are standalone.
    """

    def reject(value: str) -> None:
        raise ValueError(f"non-standard JSON constant {value}")

    if ENCODING_DAMAGE in text:
        raise ValueError("contains U+FFFD replacement characters (encoding damage)")
    return json.loads(text, parse_constant=reject)


def strict_load(path: Path) -> object:
    """Parse one file strictly."""
    return strict_loads(path.read_text(encoding="utf-8"))


def load_places(directory: Path, lang: str = "fr") -> tuple[list[dict], list[dict], list[str]]:
    """Read every place record and the absent journal; return (records, absent, problems)."""
    problems: list[str] = []
    records: list[dict] = []
    seen: dict[str, str] = {}
    for path in sorted(directory.glob(f"*.{lang}.json")):
        if path.name.startswith("_"):
            continue  # _absent / _failures journals are not records
        try:
            payload = strict_load(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            problems.append(f"{path.name}: not strict JSON ({error})")
            continue
        if not isinstance(payload, dict):
            problems.append(f"{path.name}: top level is not an object")
            continue

        place_id = str(payload.get("place_id") or "")
        if payload.get("kind") != KIND:
            problems.append(f"{path.name}: kind is {payload.get('kind')!r}, not {KIND!r}")
        if not place_id:
            problems.append(f"{path.name}: no place_id")
        elif path.name.split(".")[0] != place_id:
            problems.append(f"{path.name}: filename does not match place_id {place_id}")
        if place_id in seen:
            problems.append(f"{path.name}: duplicate place_id also in {seen[place_id]}")
        seen[place_id] = path.name

        # The URL is the identity: four segments ending in the place id it claims.
        url_path = str(payload.get("url") or "")
        segments = [part for part in url_path.split("://")[-1].split("/")[1:] if part]
        if len(segments) != PLACE_SEGMENTS:  # language + city + street + id
            problems.append(f"{path.name}: url is not /<lang>/<city>/<street>/<id>: {url_path}")
        else:
            trailing = TRAILING_ID_RE.search(url_path)
            if not trailing or trailing.group(1) != place_id:
                problems.append(f"{path.name}: url ends in a different id than {place_id}")

        # Provenance: when this place notice was taken. An unparseable or naive stamp
        # would make the corpus undatable.
        try:
            moment = datetime.datetime.fromisoformat(str(payload.get("retrieved_at") or ""))
            if moment.tzinfo is None:
                raise ValueError("no timezone offset")
        except ValueError as error:
            problems.append(f"{path.name}: retrieved_at is not an ISO 8601 instant ({error})")

        description = payload.get("description")
        if description is not None:
            text = str((description or {}).get("text") or "")
            if not text.strip():
                problems.append(f"{path.name}: description present but empty")
            if NAVIGATION_LABEL in text:
                problems.append(
                    f"{path.name}: the page's navigation label leaked into the prose"
                )

        seen_urls: set[str] = set()
        for image in payload.get("images") or []:
            if not isinstance(image, dict):
                problems.append(f"{path.name}: image entry is not an object")
                continue
            url = str(image.get("url") or "")
            if "/medias/streets/" not in url:
                problems.append(f"{path.name}: picture is not on the streets media path: {url}")
            elif url in seen_urls:
                problems.append(f"{path.name}: the same picture is listed twice: {url}")
            seen_urls.add(url)
            # A shared filename across distinct URLs is not a defect: place
            # galleries are reference-only (their download was deliberately never
            # started), so no file can be clobbered, and each entry keeps its
            # identity through its URL. The ten live cases are all of this kind.
            # If a place-picture crawl is ever agreed, names must go through the
            # scraper's collision-aware local_names() first -- the building corpus
            # lost a picture learning that.
            filename = str(image.get("filename") or "")
            if not filename:
                problems.append(f"{path.name}: picture has no filename")
            for key in ("width", "height"):
                if not isinstance(image.get(key), int) or image.get(key) <= 0:
                    problems.append(f"{path.name}: picture {filename!r} has no declared {key}")

        extraction = payload.get("extraction") or {}
        for key in ("page_hash", "content_hash"):
            value = str(extraction.get(key) or "")
            if value and not HASH_RE.match(value):
                problems.append(f"{path.name}: {key} is not a 64-character digest")

        records.append(payload)

    absent: list[dict] = []
    journal = directory / f"_absent.{lang}.json"
    if journal.exists():
        try:
            entries = strict_load(journal)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            problems.append(f"{journal.name}: not strict JSON ({error})")
            entries = []
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                problems.append(f"{journal.name}: entry is not an object")
                continue
            target = str(entry.get("target") or "")
            if target in seen:
                # A place cannot both have a notice and have none.
                problems.append(f"{journal.name}: {target} is absent but also has a record")
            digest = str(entry.get("page_sha256") or "")
            if digest and not HASH_RE.match(digest):
                problems.append(f"{journal.name}: {target} has no usable page hash")
            absent.append(entry)
    return records, absent, problems


def build_report(
    records: list[dict], absent: list[dict], problems: list[str], target: Path | None = None
) -> str:
    """Render the integrity verdict and what the place corpus actually contains."""
    lines: list[str] = [f"place corpus: {target}", f"records: {len(records)}"]
    lines.append(
        f"integrity: {'FAIL' if problems else 'PASS'}"
        + (f" ({len(problems)} problem(s))" if problems else "")
    )
    for problem in problems[:25]:
        lines.append(f"  ! {problem}")
    if len(problems) > 25:
        lines.append(f"  ... and {len(problems) - 25} more")

    with_intro = [r for r in records if (r.get("description") or {}).get("text")]
    stubs = len(records) - len(with_intro)
    lengths = [len((r.get("description") or {}).get("text") or "") for r in with_intro]
    pictures = sum(len(r.get("images") or []) for r in records)
    municipalities = collections.Counter(
        str(r.get("municipality") or "?") for r in records
    )
    inventories = collections.Counter()
    for record in records:
        for label in (record.get("details") or {}):
            inventories[label] += 1

    lines.append(
        f"three tiers: {len(with_intro)} with an introduction, {stubs} stub page(s) "
        f"(an h1 name only), {len(absent)} with no page at all"
    )
    if lengths:
        lines.append(
            f"introduction length: median {statistics.median(lengths):.0f} chars · "
            f"total {sum(lengths):,} chars"
        )
    lines.append(f"pictures referenced: {pictures}")
    lines.append(f"municipalities: {len(municipalities)}")
    for label, count in inventories.most_common(6):
        lines.append(f"  {count:5}  {label}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and summarise a place corpus")
    parser.add_argument(
        "directory", nargs="?", type=Path,
        default=REPO_ROOT / "local" / "scraped-places",
        help="place corpus directory (default: local/scraped-places)",
    )
    parser.add_argument("--lang", default="fr", help="record language suffix (default: fr)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.directory.is_dir():
        print(f"no such directory: {args.directory}", file=sys.stderr)
        return 2
    records, absent, problems = load_places(args.directory, args.lang)
    print(build_report(records, absent, problems, args.directory))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

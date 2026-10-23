#!/usr/bin/env python3
"""Offline tests for the place-corpus verifier.

The corpus itself is built from a crawl that has not run yet, so these tests construct
one from the two committed fixtures — a real notice and a real stub — and then corrupt
it in each way the verifier claims to catch. Every case is a lesson from the building
corpus, which is why it is checked here rather than rediscovered later.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACES = ROOT / "three-ages" / "summarise_places.py"
SCRAPER = ROOT / "three-ages" / "scrape_monument.py"
FIXTURES = ROOT / "three-ages" / "tests" / "fixtures"

# A real notice, and a real stub (an h1 name with nothing else on the page).
NOTICE = ("street-10601002.fr.html", "10601002", "Saint-Gilles", "Rue_Africaine")
STUB = ("street-stub-10700323.fr.html", "10700323", "Anderlecht", "Allee_des_Orpins")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def records(scraper) -> dict[str, dict]:
    """The two fixture records, in the shape the scraper writes."""
    built = {}
    for filename, place_id, city, street in (NOTICE, STUB):
        html = (FIXTURES / filename).read_text(encoding="utf-8")
        record = scraper.build_place_record(
            html, scraper.place_url(place_id, city, street, "fr"), place_id, "fr"
        )
        record["extraction"]["content_hash"] = scraper.content_hash(record)
        built[place_id] = record
    return built


def write_corpus(directory: Path, built: dict[str, dict], absent: list[dict] | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for place_id, record in built.items():
        (directory / f"{place_id}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if absent is not None:
        (directory / "_absent.fr.json").write_text(
            json.dumps(absent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def absent_entry(place_id: str = "99999999") -> dict:
    return {
        "target": place_id,
        "url": f"https://monument.heritage.brussels/fr/X/Y/{place_id}",
        "page_sha256": "0" * 64,
        "reason": "the site served its error page; no notice is published here",
    }


def test_clean_corpus_passes(module, scraper) -> None:
    """A corpus of a real notice, a real stub and one absent street is sound."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "places"
        write_corpus(directory, records(scraper), [absent_entry()])
        loaded, absent, problems = module.load_places(directory, "fr")
        assert problems == [], problems
        assert len(loaded) == 2 and len(absent) == 1
        report = module.build_report(loaded, absent, problems, directory)
        assert "integrity: PASS" in report
        # The three tiers are the point: a page can exist and hold nothing.
        assert "1 with an introduction, 1 stub page(s)" in report, report
        assert "1 with no page at all" in report, report
        assert "pictures referenced: 2" in report, report


def test_each_corruption_is_caught(module, scraper) -> None:
    """Every check earns its place: corrupt one thing and it must be reported."""
    base = records(scraper)
    notice = base[NOTICE[1]]

    def with_change(mutate) -> list[str]:
        built = {place_id: copy.deepcopy(record) for place_id, record in base.items()}
        mutate(built)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "places"
            write_corpus(directory, built, [absent_entry()])
            _loaded, _absent, problems = module.load_places(directory, "fr")
            return problems

    # The navigation label sits inside the same element as the prose, so a parser
    # regression would prepend it to every description.
    def label(built):
        built[NOTICE[1]]["description"]["text"] = (
            "Voir les biens de ce lieu repris à l'inventaire " + built[NOTICE[1]]["description"]["text"]
        )

    assert any("navigation label leaked" in p for p in with_change(label))

    # The same picture listed twice is an extraction error, whatever the filename.
    def duplicate(built):
        images = built[NOTICE[1]]["images"]
        images.append(dict(images[0], filename=images[0]["filename"].upper()))

    assert any("listed twice" in p for p in with_change(duplicate))

    # A shared filename across distinct URLs is tolerated: place galleries are
    # reference-only, and all ten live cases are of this kind.
    def shared_name(built):
        images = built[NOTICE[1]]["images"]
        images.append(dict(images[0], url=images[0]["url"] + "?again=1"))

    assert not any("listed twice" in p or "share the name" in p
                   for p in with_change(shared_name))

    # A picture with no declared size cannot be size-checked at all.
    def undeclared(built):
        built[NOTICE[1]]["images"][0].pop("height")

    assert any("no declared height" in p for p in with_change(undeclared))

    # Identity drift: the URL must end in the id the record claims.
    def wrong_url(built):
        built[NOTICE[1]]["url"] = built[NOTICE[1]]["url"].replace(NOTICE[1], "10601099")

    assert any("url ends in a different id" in p for p in with_change(wrong_url))

    def wrong_kind(built):
        built[NOTICE[1]]["kind"] = "building"

    assert any("kind is" in p for p in with_change(wrong_kind))

    def bad_hash(built):
        built[NOTICE[1]]["extraction"]["content_hash"] = "not-a-digest"

    assert any("content_hash is not a 64-character digest" in p for p in with_change(bad_hash))

    def empty_description(built):
        built[NOTICE[1]]["description"]["text"] = "   "

    assert any("description present but empty" in p for p in with_change(empty_description))


def test_absent_and_present_are_mutually_exclusive(module, scraper) -> None:
    """A place cannot both have a notice and have none."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "places"
        write_corpus(directory, records(scraper), [absent_entry(NOTICE[1])])
        _loaded, _absent, problems = module.load_places(directory, "fr")
        assert any("is absent but also has a record" in p for p in problems), problems


def test_strict_json_and_filename_identity(module, scraper) -> None:
    """Non-standard constants and misfiled records must fail the corpus."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "places"
        write_corpus(directory, records(scraper), [absent_entry()])
        # A NaN must be rejected rather than parsed.
        (directory / "88888888.fr.json").write_text(
            '{"kind": "place", "place_id": "88888888", "url": "x", "description": NaN}',
            encoding="utf-8",
        )
        _loaded, _absent, problems = module.load_places(directory, "fr")
        assert any("not strict JSON" in p for p in problems), problems

        (directory / "88888888.fr.json").unlink()
        # A record filed under a name that is not its id.
        (directory / "77777777.fr.json").write_text(
            json.dumps(dict(records(scraper)[NOTICE[1]])), encoding="utf-8"
        )
        _loaded, _absent, problems = module.load_places(directory, "fr")
        assert any("filename does not match place_id" in p for p in problems), problems


def test_missing_directory_and_journals(module, scraper) -> None:
    """Journals are not records, and a missing directory is reported plainly."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "places"
        write_corpus(directory, records(scraper), [absent_entry()])
        # The journals must not be read as place records.
        (directory / "_failures.fr.json").write_text("[{\"target\": \"1\", \"error\": \"x\"}]", encoding="utf-8")
        loaded, absent, problems = module.load_places(directory, "fr")
        assert len(loaded) == 2 and len(absent) == 1 and problems == [], problems

        capture = io.StringIO()
        with redirect_stdout(capture), redirect_stderr(io.StringIO()):
            assert module.main([str(directory)]) == 0
        assert "integrity: PASS" in capture.getvalue()

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.main([str(Path(tmp) / "absent")]) == 2


def test_encoding_damage_is_caught(module, scraper) -> None:
    """`\ufffd` means bytes were decoded with the wrong charset, so all text is suspect.

    Measured clean across the whole building corpus when this rule was added — 0 records
    carried the replacement character and 100% had correctly-decoded accents — so it costs
    nothing today and would otherwise let mangled introductions through unremarked.
    """
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "places"
        write_corpus(directory, records(scraper), [absent_entry()])
        record = records(scraper)[NOTICE[1]]
        record["name"] = "Rue Caf\ufffd"
        (directory / f"{NOTICE[1]}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
        _loaded, _absent, problems = module.load_places(directory, "fr")
        assert any("encoding damage" in p for p in problems), problems

        # An unusable retrieval time makes the corpus undatable.
        record = records(scraper)[NOTICE[1]]
        record["retrieved_at"] = "sometime"
        (directory / f"{NOTICE[1]}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
        _loaded, _absent, problems = module.load_places(directory, "fr")
        assert any("retrieved_at" in p for p in problems), problems


def main() -> None:
    module = load(PLACES, "summarise_places")
    scraper = load(SCRAPER, "scrape_monument")
    tests = [
        test_clean_corpus_passes,
        test_encoding_damage_is_caught,
        test_each_corruption_is_caught,
        test_absent_and_present_are_mutually_exclusive,
        test_strict_json_and_filename_identity,
        test_missing_directory_and_journals,
    ]
    for test in tests:
        test(module, scraper)
    print(f"Three Ages place-corpus verifier passed ({len(tests)} offline checks)")


if __name__ == "__main__":
    sys.exit(main())

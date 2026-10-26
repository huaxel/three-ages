#!/usr/bin/env python3
"""Offline tests for the Brussels architectural-inventory scraper.

These tests parse committed HTML fixtures, so they never touch the network. They
pin the extraction contract (identity, tags, description, pictures, rights
metadata), the bilingual label mapping, the address-URL trap that makes the
street id look like a building id, and the image-reuse gate: pictures from this
source must not be downloaded without an explicit rights basis.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parent
SCRAPER = ROOT / "three-ages" / "scrape_monument.py"
SUMMARY = ROOT / "three-ages" / "summarise_corpus.py"
FIXTURES = ROOT / "three-ages" / "tests" / "fixtures"

# The fixtures are committed snapshots of the public notice pages.
UNNAMED = ("building-23775.fr.html", "23775", "fr")
NAMED = ("building-30991.fr.html", "30991", "fr")
DUTCH = ("building-23775.nl.html", "23775", "nl")
# Legacy notice: the street is linked as a flat root-relative *.html file.
LEGACY = ("building-37373.fr.html", "37373", "fr")
# Notice whose captions name a copyright holder: "... ULB © urban.brussels, 2022".
CREDITED = ("building-40680.fr.html", "40680", "fr")
# Corner building: two streets with their own links, separated by <br>.
CORNER = ("building-23604.fr.html", "23604", "fr")
# Numberless entry: a bridge whose address heading links a street with no number.
NUMBERLESS = ("building-25074.fr.html", "25074", "fr")
ROBOTS_FIXTURE = FIXTURES / "robots.txt"
# The site answers a missing id with HTTP 200 and this error page.
SOFT_404 = FIXTURES / "soft-404.html"
# A `notice de lieu`: a street page, at the four-segment URL the building parser refuses.
STREET = ("street-10601002.fr.html", "10601002", "fr")
# A real stub: a place page that exists and holds nothing (h1 name only, no prose,
# no pictures, no labelled blocks). Six of twelve sampled pages were like this.
STREET_STUB = ("street-stub-10700323.fr.html", "10700323", "fr")

# The page embeds a hidden strip of neighbouring buildings (#phrise). Those
# pictures belong to other notices and must never be attributed to this one.
NEIGHBOUR_FILENAMES = {
    "10831042_0017_P01.jpg",
    "10831042_0019_P01.jpg",
    "10831042_0021_P01.jpg",
}


def load_scraper():
    spec = importlib.util.spec_from_file_location("scrape_monument", SCRAPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_summary():
    spec = importlib.util.spec_from_file_location("summarise_corpus", SUMMARY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build(module, fixture: tuple[str, str, str]) -> dict:
    filename, building_id, lang = fixture
    html = (FIXTURES / filename).read_text(encoding="utf-8")
    url = module.building_url(building_id, lang)
    return module.build_record(html, url, building_id, lang)


def filenames(record: dict) -> set[str]:
    return {image["filename"] for image in record["images"]}


def test_unnamed_notice(module) -> None:
    record = build(module, UNNAMED)

    assert record["building_id"] == "23775"
    assert record["urban_id"] == "23775"
    assert record["language"] == "fr"
    assert record["identity"] == {
        "name": None,
        "street": "Avenue des Gloires Nationales",
        "house_number": "53",
        "address_url": "https://monument.heritage.brussels/fr/Ganshoren/"
        "Avenue_des_Gloires_Nationales/10831042",
    }
    assert record["city"] == {"name": "Ganshoren", "id": "1083"}
    assert record["coordinates"] == {
        "latitude": 50.866737752527,
        "longitude": 4.3222264028787,
    }

    interests = [tag["value"] for tag in record["tags"] if tag["kind"] == "interest"]
    assert interests == ["Artistique", "Esthétique", "Historique", "Urbanistique"]
    assert record["typologies"] == []
    assert record["styles"] == []
    assert record["research_and_writing"] == ["2016"]

    # Every interest anchors its own rubric text, kept separately from the tag.
    assert all(item["criteria"] for item in record["interests"])

    # This notice genuinely has no free-text Description; the scraper must say so
    # rather than present the generic interest rubric as a building description.
    assert record["description"] is None
    assert record["sources"] is None
    assert any("No free-text Description" in note for note in record["notes"])

    assert record["legal_status"] == {
        "text": "Inscrit à l’inventaire légal le 19 août 2024",
        "date": "2024-08-19",
    }
    assert [item["name"] for item in record["inventories"]] == [
        "Actualisation de l'inventaire d'urgence",
        "Actualisation du projet d'inventaire régional du patrimoine architectural",
        "Actualisation permanente de l'inventaire régional du patrimoine architectural",
    ]
    assert record["inventories"][0]["period"] == "Sint-Lukasarchief - 1993-1994"
    assert record["inventories"][1]["url"] == (
        "https://monument.heritage.brussels/fr/inventories/7"
    )

    # Pictures: exactly one, and never a neighbour from the hidden #phrise strip.
    assert len(record["images"]) == 1
    image = record["images"][0]
    assert image["filename"] == "10831042_0053_P01.jpg"
    assert image["url"] == (
        "https://monument.heritage.brussels/medias/buildings/10831042_0053_P01.jpg"
    )
    assert image["preview_url"] == (
        "https://monument.heritage.brussels/medias/500/buildings/10831042_0053_P01.jpg"
    )
    assert image["caption"] == "Avenue des Gloires Nationales 53, 2014"
    assert (image["width"], image["height"]) == (1642, 1094)
    assert image["is_main"] is True
    assert not filenames(record) & NEIGHBOUR_FILENAMES

    assert len(record["nearby_trees"]) == 4
    assert record["nearby_trees"][0]["label"] == "Platane à feuille d'érable"
    assert record["suggestions"] == []

    # Source metadata must carry the reuse terms, not just a host name.
    assert record["source"]["host"] == "monument.heritage.brussels"
    assert "images" in record["source"]["rights"] or "photos" in record["source"]["rights"]
    assert record["source"]["legal_url"].endswith("/fr/legal/")


def test_named_notice(module) -> None:
    record = build(module, NAMED)

    assert record["identity"]["name"] == "La Balance"
    assert record["identity"]["street"] == "Rue de la Colline"
    assert record["identity"]["house_number"] == "24"
    assert record["city"] == {"name": "Bruxelles Pentagone", "id": "1000"}

    assert record["typologies"] == ["maison unifamiliale ou de rapport (indéterminé)"]
    assert record["styles"] == ["Baroque"]

    description = record["description"]
    assert description is not None
    assert len(description["text"]) > 2000
    # Glossary terms survive as words; their tooltip definitions do not leak.
    assert "pinacle" in description["text"]
    assert "Amortissement" not in description["text"]
    assert "/fr/glossary/191" in description["html"]
    assert "Amortissement" in description["html"]

    sources = record["sources"]
    assert sources is not None and "AVB/TP 8616" in sources["text"]

    # Three pictures, first one flagged as the notice's main view.
    assert len(record["images"]) == 3
    assert [image["is_main"] for image in record["images"]] == [True, False, False]
    assert record["images"][1]["caption"] == 'Rue de la Colline 24. "La Balance", 1981'
    assert all(image["url"].startswith("https://") for image in record["images"])

    contributors = record["contributors"]
    assert [person["name"] for person in contributors] == [
        "INCONNU - ONBEKEND",
        "Pierre Victor JAMAER",
    ]
    assert contributors[1]["roles"] == ["architecte"]
    assert contributors[1]["years"] == ["1890"]

    assert record["legal_status"]["date"] == "1994-03-10"

    titles = [group["title"] for group in record["suggestions"]]
    assert titles == ["Quelques biens du même auteur", "Quelques biens de la même typologie"]
    assert all(len(group["items"]) == 4 for group in record["suggestions"])
    assert record["suggestions"][0]["items"][0]["building_id"] == "10510"

    # Raw labels are preserved so an untranslated field is never silently lost.
    assert "Statut juridique" in record["details"]
    assert record["details"]["Recherches et rédaction"] == "2016"


def test_dutch_notice(module) -> None:
    record = build(module, DUTCH)

    assert record["language"] == "nl"
    assert record["identity"]["street"] == "Landsroemlaan"
    assert record["identity"]["house_number"] == "53"
    assert record["urban_id"] == "23775"

    # The same notice in Dutch maps typed fields through the Dutch labels.
    assert [tag["value"] for tag in record["tags"]] == [
        "Artistiek",
        "Esthetisch",
        "Historisch",
        "Stedenbouwkundig",
    ]
    assert record["legal_status"]["date"] == "2024-08-19"
    assert len(record["inventories"]) == 3
    assert record["inventories"][0]["name"] == "Actualisatie van de Urgentie-Inventaris"
    assert record["images"][0]["filename"] == "10831042_0053_P01.jpg"


def test_legacy_address_variant(module) -> None:
    """Legacy notices link the street as fr.<City>.<Street>.html, not /fr/city/street/id.

    Treating that heading as a building *title* is the failure mode this pins:
    the address must still split into street and house number.
    """
    record = build(module, LEGACY)
    assert record["identity"] == {
        "name": None,
        "street": "Rue d'Arlon",
        "house_number": "40",
        "address_url": "https://monument.heritage.brussels/"
        "fr.Bruxelles_Extension_Est.Rue_d_Arlon.html",
    }
    assert record["city"] == {"name": "Bruxelles Extension Est", "id": "1002"}
    assert "maison bourgeoise" in record["typologies"]
    assert record["styles"] == ["Néoclassicisme"]


def test_image_credit_and_conditions(module) -> None:
    """Captions that name a holder must yield a credit, and the notice's reuse
    conditions must travel with the record instead of being dropped."""
    record = build(module, CREDITED)

    credited = [image for image in record["images"] if image["credit_holders"]]
    assert credited, "the fixture has a © caption"
    assert credited[0]["credit_holders"] == ["urban.brussels"]
    assert credited[0]["rights_hint"] == "conditional-noncommercial"
    assert "ULB © urban.brussels" in credited[0]["caption"]

    rights = record["image_rights"]
    assert rights["conditions_url"] == "https://monument.heritage.brussels/fr/conditions/"
    assert rights["reuse_basis"] == "conditional-noncommercial"
    # The credit formulae are obligations, so they must be recorded verbatim.
    online = " ".join(rights["obligations"]["online"])
    printed = " ".join(rights["obligations"]["printed"])
    assert "© SPRB-DMS" in online
    assert "rubrique liens" in online or "links section" in online
    assert "Monuments & Sites – Bruxelles" in printed
    assert "rue du Progrès 80" in printed
    assert "independently" in rights["obligations"]["third_party"]
    assert rights["images_without_credit"] == len(record["images"]) - len(credited)

    # An absent credit is not a reuse statement, so hints stay null.
    for image in record["images"]:
        if not image["credit_holders"]:
            assert image["rights_hint"] is None

    # Credit parsing is pure, so both branches are pinned directly.
    assert module.extract_credit_holders("") == []
    assert module.extract_credit_holders("Rue X 1, 2015") == []
    assert module.extract_credit_holders("Rue X 1 © KIK-IRPA, 1942") == ["KIK-IRPA"]
    unknown = module.extract_credit_holders("Rue X 1 © KIK-IRPA, 1942")
    assert module.rights_hint_for(unknown) == "third-party-or-unknown"
    assert module.rights_hint_for([]) is None

    # The source block must carry the conditions URL, not just the legal notice.
    source_rights = record["source"]["rights"]
    assert record["source"]["conditions_url"].endswith("/fr/conditions/")
    assert "conditions" in source_rights["photos"]
    assert "non-commercial" in source_rights["photos"]


def test_corner_building_addresses(module) -> None:
    """A corner building lists several street+number pairs and must not bury the
    second street inside the first one's house numbers."""
    record = build(module, CORNER)

    assert record["identity"]["street"] == "Rue de l'Ancien Presbytère"
    assert record["identity"]["house_number"] == "4, 2, 2a"
    assert record["addresses"] == [
        {
            "street": "Rue de l'Ancien Presbytère",
            "house_numbers": "4, 2, 2a",
            "url": "https://monument.heritage.brussels/fr/Ganshoren/"
            "Rue_de_l_Ancien_Presbytere/10831003",
        },
        {
            "street": "Rue François Beeckmans",
            "house_numbers": "54, 52",
            "url": "https://monument.heritage.brussels/fr/Ganshoren/"
            "Rue_Francois_Beeckmans/10831006",
        },
    ]
    # Single-street notices still expose exactly one group.
    assert len(build(module, UNNAMED)["addresses"]) == 1
    assert len(build(module, NAMED)["addresses"]) == 1


def test_robots_policy(module) -> None:
    """The live robots.txt must drive the decisions, with a safe fallback."""
    policy = module.parse_robots(ROBOTS_FIXTURE.read_text(encoding="utf-8"))
    assert policy.crawl_delay == 2.0

    for path in ("/fr/buildings/23775", "/nl/buildings/23775", "/files/a.pdf",
                 "/medias/x.jpg", "/", "/robots.txt"):
        assert policy.allows(path), f"{path} must be allowed"
    for path in ("/jsonapi/node/building", "/_integration/x.js",
                 "/index.php?section=buildings", "/en/buildings/23775"):
        assert not policy.allows(path), f"{path} must be disallowed"

    # Prefix fallback, used when robots.txt cannot be read, is equally strict.
    fallback = module.RobotsPolicy()
    assert fallback.allows("/fr/buildings/23775")
    assert not fallback.allows("/jsonapi")
    assert not fallback.allows("/_integration/x.js")
    assert fallback.crawl_delay >= 2.0

    # The fetcher applies its policy, so an explicitly supplied one takes effect.
    strict = module.RobotsPolicy([(False, module.robots_pattern_regex("/fr/"))])
    try:
        module.validate_url("https://monument.heritage.brussels/fr/buildings/1", strict)
    except module.ScrapeError:
        pass
    else:
        raise AssertionError("a parsed Disallow rule must be enforced")

    # A crawl delay below the floor is never accepted.
    tight = module.parse_robots("User-agent: *\nCrawl-delay: 0\nAllow: /fr/\n")
    assert tight.crawl_delay == module.MIN_CRAWL_DELAY_SECONDS


def test_numberless_entry(module) -> None:
    """A bridge links a street with no house number; the name must still come from
    h1 and the address must not be lost."""
    record = build(module, NUMBERLESS)

    assert record["identity"] == {
        "name": "Pont enjambant le chemin de fer",
        "street": "Rue August De Boeck",
        "house_number": None,
        "address_url": "https://monument.heritage.brussels/fr/Evere/"
        "Rue_August_De_Boeck/11400022",
    }
    assert record["addresses"] == [
        {
            "street": "Rue August De Boeck",
            "house_numbers": None,
            "url": "https://monument.heritage.brussels/fr/Evere/"
            "Rue_August_De_Boeck/11400022",
        }
    ]
    assert record["typologies"] == ["pont", "Patrimoine ferroviaire"]


def test_survey_report(module) -> None:
    """The survey must summarise a sample without touching the network."""
    fixtures = (UNNAMED, NAMED, DUTCH, LEGACY, CREDITED, CORNER, NUMBERLESS)
    records = [build(module, fixture) for fixture in fixtures]
    report = module.survey_report(
        records,
        {"description": 3, "quelques biens du même auteur": 2},
        [{"building_id": "999", "error": "ScrapeError: boom"}],
        sampled=8,
        requests=8,
    )

    assert "sampled 8 notices · parsed 7 · failed 1" in report
    assert "field coverage" in report
    assert "extraction health" in report
    assert "no street" in report
    # The known section titles are not reported as unknown.
    assert "'description'" not in report
    assert "'quelques biens du même auteur'" in report
    assert "image rights hints" in report
    assert "ScrapeError: boom" in report

    # An empty sample must degrade gracefully rather than crash.
    empty = module.survey_report([], {}, [{"building_id": "1", "error": "x"}], 1, 1)
    assert "parsed 0" in empty


def test_soft_404_is_rejected(module) -> None:
    """A missing id must fail loudly, not be stored as an empty record.

    The site returns HTTP 200 for absent notices, so treating the body as a notice
    would write a record with no address, no tags and no pictures, and whose notes
    wrongly claim the notice has no Description section.
    """
    raw = SOFT_404.read_text(encoding="utf-8")
    assert "main-info-wrapper" not in raw
    assert "Error404" in raw  # the real error page, not a synthesised stub

    try:
        module.build_record(raw, module.building_url("15", "fr"), "15", "fr")
    except module.ScrapeError as error:
        assert "not a notice page" in str(error)
    else:
        raise AssertionError("a soft 404 must be rejected")

    # Every committed notice still passes the same guard.
    for fixture in (UNNAMED, NAMED, DUTCH, LEGACY, CREDITED, CORNER, NUMBERLESS):
        assert module.is_notice_page(module.parse_dom((FIXTURES / fixture[0]).read_text(
            encoding="utf-8"
        )))


def test_index_is_a_complete_enumeration(module) -> None:
    """Notify-ids are sparse: gaps in the numeric range are genuinely absent.

    This pins the finding that ``--from-index`` is not missing notices. It uses the
    committed fixtures plus index arithmetic, never the network: in the live index
    the ids span 12..41881 with 15,451 numeric gaps, and every probed gap returned
    the error page rather than a notice.
    """
    assert module.index_ids({"features": [
        {"properties": {"id": "12"}},
        {"properties": {"id": "12"}},   # repeated entrance, deduplicated
        {"properties": {"id": "13"}},
        {"properties": {"id": ""}},     # placeholder, skipped
    ]}) == ["12", "13"]

    ids = module.index_ids_for_city(
        {"features": [
            {"properties": {"id": "1", "city": "1083"}},
            {"properties": {"id": "2", "city": "1000"}},
            {"properties": {"id": "3", "city": "1083"}},
            {"properties": {"id": "3", "city": "1083"}},
        ]},
        "1083",
    )
    assert ids == ["1", "3"]
    assert module.index_city_counts(
        {"features": [{"properties": {"city": "1083"}}, {"properties": {"city": "1000"}}]}
    ) == {"1000": 1, "1083": 1}


def test_rubric_dedup(module) -> None:
    """The repeated interest rubric must be storable once, without changing the
    canonical hash, so toggling --dedupe-rubrics is never mistaken for drift."""
    html = (FIXTURES / NAMED[0]).read_text(encoding="utf-8")
    url = module.building_url(NAMED[1], NAMED[2])

    inline = module.build_record(html, url, NAMED[1], NAMED[2])
    store = module.RubricStore()  # no path, so nothing is written
    shared = module.build_record(html, url, NAMED[1], NAMED[2], store)

    assert all(item["criteria"] for item in inline["interests"])
    assert all("criteria" not in item for item in shared["interests"])
    assert all(item["criteria_ref"] for item in shared["interests"])

    # The pin survives either way, and both modes hash identically.
    assert [i["criteria_sha256"] for i in inline["interests"]] == [
        i["criteria_sha256"] for i in shared["interests"]
    ]
    assert module.content_hash(inline) == module.content_hash(shared)
    assert inline["extraction"]["content_hash"] == shared["extraction"]["content_hash"]

    # Keys are readable, and the store keeps the original label.
    assert module.rubric_key("Esthétique") == "esthetique"
    assert module.rubric_key("Néo-baroque") == "neo-baroque"
    artistique = store.entries["artistique"]
    assert artistique["value"] == "Artistique"
    inline_artistique = next(
        item for item in inline["interests"] if item["value"] == "Artistique"
    )
    assert artistique["criteria"] == inline_artistique["criteria"]
    assert len(artistique["sha256"]) == 64
    assert store.save() is None  # a path-less store writes nothing

    # Re-defining a rubric under the same interest name is reported, not hidden.
    conflicting = module.RubricStore()
    conflicting.record("Artistique", "original prose")
    conflicting.record("Artistique", "rewritten prose")
    assert conflicting.redefined == ["artistique"]

    # Deduplicating genuinely shrinks the record and moves the hash only when the
    # real content moves.
    assert len(json.dumps(shared)) < len(json.dumps(inline))
    shifted = json.loads(json.dumps(inline))
    shifted["interests"][0]["criteria_sha256"] = "0" * 64
    assert module.content_hash(shifted) != module.content_hash(inline)


def test_credits_appear_only_in_captions(module) -> None:
    """Pin the verified negative: notices carry no per-photo rights marker.

    The conditions page names "© Reproduction autorisée sous certaines conditions"
    as a per-photo mention, but it was not found anywhere in notice HTML, not even
    in the print block. So a credit in figcaption/alt is the only signal available,
    and rights_hint must stay a hint.
    """
    for fixture in (NAMED, CREDITED, UNNAMED, CORNER):
        raw = (FIXTURES / fixture[0]).read_text(encoding="utf-8")
        assert "Reproduction autoris" not in raw
        record = build(module, fixture)
        for image in record["images"]:
            if image["credit_holders"]:
                # Any credit found must be visible in the caption, not inferred.
                assert all(h in image["caption"] for h in image["credit_holders"])
                assert image["rights_hint"] in (
                    "conditional-noncommercial",
                    "third-party-or-unknown",
                )
    # A hint is never a clearance: the record states the conditions URL to check.
    record = build(module, CREDITED)
    assert record["image_rights"]["conditions_url"].endswith("/fr/conditions/")
    assert "null" in record["image_rights"]["hint_note"]


def test_corpus_summary(module) -> None:
    """A corpus must be provably intact, and corruption must be caught.

    The store file shares the records' suffix, so a validator that globbed naively
    would report itself as a broken record.
    """
    corpus = load_summary()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        store = module.RubricStore(out / "rubrics.fr.json")
        for fixture in (UNNAMED, NAMED):
            filename, building_id, lang = fixture
            url = module.building_url(building_id, lang)
            record = module.build_record(
                (FIXTURES / filename).read_text(encoding="utf-8"), url, building_id, lang, store
            )
            module.write_record(record, module.record_path(out, building_id, lang))
        store.save()

        records, rubrics, problems = corpus.load_corpus(out, "fr", module.SCHEMA_VERSION, module.building_url)
        assert problems == [], problems
        # The rubric store is not a record, despite matching the glob.
        assert len(records) == 2
        assert len(rubrics) >= 5

        report = corpus.build_report(records, rubrics, problems)
        assert "integrity: PASS" in report
        assert "records: 2" in report
        assert "by municipality" in report
        assert "caption years:" in report, report
        assert "tag frequencies (interests)" in report

        rows = corpus.corpus_rows(records)
        assert len(rows) == 2
        assert {r["building_id"] for r in rows} == {"23775", "30991"}
        assert all("pictures" in r and "url" in r for r in rows)

        # Coverage is reported against the index when one is supplied.
        covered = corpus.build_report(records, rubrics, [], ["23775", "30991", "40404"])
        assert "2/3" in covered and "1 still to fetch" in covered

        # A record must point at the page it came from: nothing else ties it to a notice,
        # and this host has a URL shape that looks like one notice but is another.
        misfiled = out / "7777.fr.json"
        misfiled.write_text(json.dumps({
            **records[0], "building_id": "7777",
            "url": "https://monument.heritage.brussels/fr/Ganshoren/Rue_X/10831042",
        }, ensure_ascii=False), encoding="utf-8")
        _r, _s, misfiled_problems = corpus.load_corpus(
            out, "fr", module.SCHEMA_VERSION, module.building_url)
        assert any("url is" in problem for problem in misfiled_problems), misfiled_problems
        misfiled.unlink()

        # An unusable retrieval time makes the corpus undatable.
        undated = out / "6666.fr.json"
        undated.write_text(json.dumps(
            {**records[0], "building_id": "6666", "retrieved_at": "yesterday"},
            ensure_ascii=False), encoding="utf-8")
        _r, _s, undated_problems = corpus.load_corpus(
            out, "fr", module.SCHEMA_VERSION, module.building_url)
        assert any("retrieved_at" in problem for problem in undated_problems), undated_problems
        undated.unlink()
        records, rubrics, problems = corpus.load_corpus(
            out, "fr", module.SCHEMA_VERSION, module.building_url)

        # Encoding damage is unambiguous, so it is an integrity failure, not a warning.
        damaged = out / "8888.fr.json"
        damaged.write_text(
            # ensure_ascii=False matters: with the default the character is written as a
            # JSON escape, the file stays valid UTF-8, and the rule correctly stays quiet.
            json.dumps({**(records[0] if records else {}), "identity": {"street": "Rue Caf\ufffd"}},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        _records, _rubrics, damaged_problems = corpus.load_corpus(out, "fr", module.SCHEMA_VERSION, module.building_url)
        assert any("encoding damage" in problem for problem in damaged_problems), damaged_problems
        damaged.unlink()
        records, rubrics, problems = corpus.load_corpus(out, "fr", module.SCHEMA_VERSION, module.building_url)

        # A non-strict constant must fail the integrity check, not parse.
        (out / "9999.fr.json").write_text("{'schema_version': NaN}", encoding="utf-8")
        records, rubrics, problems = corpus.load_corpus(out, "fr", module.SCHEMA_VERSION, module.building_url)
        assert problems, "NaN must be rejected"
        assert "not strict JSON" in problems[0]
        assert "integrity: FAIL" in corpus.build_report(records, rubrics, problems)

        # A dangling rubric reference is the failure mode an interrupted run causes.
        (out / "9999.fr.json").unlink()
        victims, rubrics, _ = corpus.load_corpus(out, "fr", module.SCHEMA_VERSION, module.building_url)
        (out / "rubrics.fr.json").write_text('{"rubrics": {}}', encoding="utf-8")
        broken, _, problems = corpus.load_corpus(out, "fr", module.SCHEMA_VERSION, module.building_url)
        assert len(broken) == len(victims)
        assert any("missing from the store" in p for p in problems), problems


class StubFetcher:
    """Serves canned robots.txt text, so policy tests never touch the network."""

    def __init__(self, text: str, delay: float = 2.0) -> None:
        self.text = text
        self.delay = delay
        self.policy = None
        self.calls = 0

    def get_text(self, url: str) -> str:
        self.calls += 1
        return self.text


def test_midrun_robots_recheck(module) -> None:
    """A fifteen-hour crawl must not be governed by its hour-zero policy read.

    The cache path is injected so the test cannot disturb the live cache that a
    running sweep depends on.
    """
    live = ROBOTS_FIXTURE.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()):
        cache = Path(tmp) / "robots.txt"

        # Unchanged policy: keep crawling, and refresh the cache.
        same = StubFetcher(live)
        same.policy = module.RobotsPolicy()
        assert module.recheck_robots(same, "/fr/buildings/1", cache) is False
        assert cache.exists()
        assert same.calls == 1

        # The site withdraws /fr/: stop rather than keep crawling.
        tightened = StubFetcher(live.replace("Allow: /fr/", ""))
        tightened.policy = module.RobotsPolicy()
        assert module.recheck_robots(tightened, "/fr/buildings/1", cache) is True

        # A raised crawl delay slows the run instead of stopping it.
        slower = StubFetcher(live.replace("Crawl-delay: 2", "Crawl-delay: 9"))
        slower.policy = module.RobotsPolicy()
        assert module.recheck_robots(slower, "/fr/buildings/1", cache) is False
        assert slower.delay == 9.0
        assert slower.policy.crawl_delay == 9.0

        # An unreadable robots.txt must not silently stop a long run.
        class Broken(StubFetcher):
            def get_text(self, url: str) -> str:
                raise module.ScrapeError("network down")

        broken = Broken(live)
        broken.policy = module.RobotsPolicy()
        assert module.recheck_robots(broken, "/fr/buildings/1", cache) is False


def test_consecutive_failure_guard(module) -> None:
    """An outage should cost one aborted run, not thousands of failed ids.

    Foreign hosts fail inside parse_target, before any request, so this exercises
    the guard fully offline.
    """
    bad = [f"https://example.com/fr/buildings/{i}" for i in range(10)]

    for limit, expected in ((3, 3), (1, 1), (0, 10)):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = module.main([
                    *bad, "--out", tmp, "--max-consecutive-failures", str(limit),
                    "--no-robots", "--quiet",
                ])
            lines = err.getvalue().splitlines()
            attempts = sum(line.startswith("error:") for line in lines)
            aborted = any(line.startswith("aborting:") for line in lines)
            assert code == 1
            assert attempts == expected, f"limit={limit}: {attempts} attempts"
            assert aborted is (limit > 0)


def test_progress_throughput(module) -> None:
    """A resumed run must not report a rate the crawl delay forbids.

    Numbers come from a real resume: 200 records fetched, 424 skipped, 430 s of
    wall clock. Counting skips as throughput gave 1.45/s and \"eta 4.9h\"; the
    truth was 0.47/s and ~15h.
    """
    total = 26419
    rate, eta = module.throughput(200, 624, total, 430.0)
    assert rate == 200 / 430
    assert rate < 0.5, "2s crawl delay forbids faster than 0.5/s"
    assert 14 < eta / 3600 < 17, f"eta was {eta / 3600:.1f}h"

    # The old formula, for contrast: including free skips inflates the rate.
    inflated = 624 / 430.0
    assert inflated > 1.4
    assert (total - 624) / inflated / 3600 < 5

    # A fresh run has no skips, so both formulae agree.
    rate2, eta2 = module.throughput(100, 100, 200, 200.0)
    assert rate2 == 0.5 and eta2 == 200.0

    # No fetches yet: report nothing rather than dividing by zero.
    assert module.throughput(0, 500, total, 10.0) == (0.0, 0.0)
    assert module.throughput(5, 5, total, 0.0) == (0.0, 0.0)


def test_contributor_year_ranges(module) -> None:
    """The site splits a year range across two spans, so a leading dash is part of
    the year. Treating it as a role corrupted the dates this project exists to
    compare, in 41 of the first 817 records."""
    assert module.merge_year_fields(["1850", "-1875"]) == ["1850-1875"]
    assert module.merge_year_fields(["1898", "-1901"]) == ["1898-1901"]
    assert module.merge_year_fields(["1850", "-1875", "1900", "-1905"]) == [
        "1850-1875", "1900-1905"
    ]
    # A dash with nothing to continue is a stray separator, not a value.
    assert module.merge_year_fields(["-1900"]) == ["1900"]
    assert module.merge_year_fields(["1876"]) == ["1876"]
    assert module.merge_year_fields([]) == []

    # building-37373 carries exactly this split range in the committed fixture.
    record = build(module, LEGACY)
    people = {person["name"]: person for person in record["contributors"]}
    assert people["INCONNU - ONBEKEND"]["years"] == ["1850-1875"]
    assert people["INCONNU - ONBEKEND"]["roles"] == []
    for person in record["contributors"]:
        for role in person["roles"]:
            assert not role.startswith("-"), person
            assert not role[:1].isdigit(), person

    # A plain single year still parses as before.
    named = build(module, NAMED)["contributors"][1]
    assert named["roles"] == ["architecte"] and named["years"] == ["1890"]


def test_truncated_year_range(module) -> None:
    """A truncated range's second half is a date fragment, not a contributor role.

    building-37373 splits a range as 1850 + -1875. Building 31373 emits 1875 + -19,
    and because two digits miss YEAR_FIELD_RE that fragment was filed as a role:
    local/scraped/31373.fr.json carried roles ["-19"] until the corpus check
    flagged it. The value is kept verbatim, never completed into a year the source
    does not state and never split into a role.
    """
    html = (FIXTURES / LEGACY[0]).read_text(encoding="utf-8")
    assert "-1875" in html, "fixture no longer carries the split-range shape"

    truncated = module.build_record(
        html.replace("-1875", "-19"),
        module.building_url(LEGACY[1], LEGACY[2]),
        LEGACY[1],
        LEGACY[2],
    )
    person = {p["name"]: p for p in truncated["contributors"]}["INCONNU - ONBEKEND"]
    assert person["years"] == ["1850-19"], person
    assert person["roles"] == [], person
    assert any("incomplete" in note for note in truncated["notes"]), truncated["notes"]
    # The rule the corpus check uses must agree that this record is now clean.
    assert load_summary().date_like_roles(truncated) == []

    # A complete range still merges exactly as before.
    intact = build(module, LEGACY)
    merged = {p["name"]: p for p in intact["contributors"]}["INCONNU - ONBEKEND"]
    assert merged["years"] == ["1850-1875"] and merged["roles"] == []

    # A dash fragment with no year to continue is not silently promoted into one.
    orphaned = module.build_record(
        html.replace(
            "<span class='art-field'>1850</span><span class='art-field'>-1875</span>",
            "<span class='art-field'>-19</span>",
        ),
        module.building_url(LEGACY[1], LEGACY[2]),
        LEGACY[1],
        LEGACY[2],
    )
    orphan = {p["name"]: p for p in orphaned["contributors"]}["INCONNU - ONBEKEND"]
    assert orphan["years"] == [], orphan
    assert orphan["roles"] == ["-19"], orphan
    assert load_summary().date_like_roles(orphaned) == ["-19"]


def test_coordinate_cross_check(module) -> None:
    """Each record is compared against the publisher's own index, not just itself.

    Every other corpus check proves internal consistency; a record could agree with
    its own hash and still be the wrong building. Measured on the full corpus:
    23,987/26,419 notices put their building within 25 m of where the index puts it,
    2,406 share one identical value 233 km away (the source's placeholder), and the
    remaining 26 are long or multi-number addresses at 25-126 m. Zero unexplained.
    """
    corpus = load_summary()
    placeholder = {"latitude": 49.293381634479, "longitude": 2.3067617893134}
    points = {str(i): [(50.85, 4.35)] for i in (1, 2, 3, 4, 5)}
    # The comparison itself works on bare id/coordinates pairs.
    probe = [
        {"building_id": "1", "coordinates": {"latitude": 50.85, "longitude": 4.35}},
        {"building_id": "2", "coordinates": dict(placeholder)},
        {"building_id": "3", "coordinates": dict(placeholder)},
        # ~18 m away: ordinary variation between the two sources, not a divergence.
        {"building_id": "4", "coordinates": {"latitude": 50.8502, "longitude": 4.3501}},
        # ~60 m: divergent at a 25 m tolerance, but far too close to print as "0 km".
        {"building_id": "5", "coordinates": {"latitude": 50.85054, "longitude": 4.35}},
    ]
    checked, divergent, worst, repeated = corpus.coordinate_divergence(probe, points)
    assert checked == 5 and divergent == 3, (checked, divergent)
    assert repeated == [(2, (49.29338, 2.30676))], repeated
    assert worst and "2" in {row[1] for row in worst}
    assert worst[0][0] > 200_000, "the placeholder is hundreds of km away"

    # A record with no index entry, or no coordinates, is skipped rather than guessed.
    assert corpus.coordinate_divergence(
        [{"building_id": "99", "coordinates": dict(placeholder)}], points
    )[0] == 0
    assert corpus.coordinate_divergence([{"building_id": "1"}], points)[0] == 0

    # The report needs whole records, so build real ones and move their coordinates.
    records = []
    for fixture in (UNNAMED, NAMED, LEGACY):
        filename, building_id, lang = fixture
        records.append(module.build_record(
            (FIXTURES / filename).read_text(encoding="utf-8"),
            module.building_url(building_id, lang), building_id, lang,
        ))
    points = {str(r["building_id"]): [(50.85, 4.35)] for r in records}
    records[0]["coordinates"] = {"latitude": 50.85, "longitude": 4.35}
    records[1]["coordinates"] = dict(placeholder)
    records[2]["coordinates"] = dict(placeholder)

    # It must be reported, and it must not be called an integrity failure: the
    # records are consistent and correctly attributed, the source serves this value,
    # and re-scraping would change nothing.
    report = corpus.build_report(records, {}, [], points=points)
    assert "integrity: PASS" in report
    assert "coordinates vs index: 1/3 within 25 m · 2 divergent" in report, report
    assert "one value recurs across 2 notice(s): 49.29338, 2.30676" in report, report
    # ~226 km from the synthetic index point; bounded rather than hard-coded.
    assert re.search(r"is 2\d\d km from where the index puts it", report), report
    # A sub-kilometre divergence needs a whole record to be reported, since the
    # report reads fields beyond coordinates. ~60 m north of the index point.
    near = corpus.build_report(
        [{**records[0], "coordinates": {"latitude": 50.850543, "longitude": 4.35}}],
        {}, [], points={"23775": [(50.85, 4.35)]},
    )
    assert re.search(r"is 6\d m from where the index puts it", near), near

    # Without an index there is nothing to compare against, and nothing is claimed.
    assert "coordinates vs index" not in corpus.build_report(records, {}, [])

    # End to end through the real entry point: a corpus the source has mis-located
    # still passes, because the records are sound and re-scraping would change
    # nothing. Pinning the exit code is what stops this drifting into the failure
    # path later, where it would make the checker unable to ever gate a real corpus.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "scraped"
        out.mkdir()
        for fixture in (UNNAMED, NAMED):
            filename, building_id, lang = fixture
            record = module.build_record(
                (FIXTURES / filename).read_text(encoding="utf-8"),
                module.building_url(building_id, lang), building_id, lang,
            )
            record["coordinates"] = dict(placeholder)
            module.write_record(record, module.record_path(out, building_id, lang))
        index = Path(tmp) / "monuments.fr.json"
        index.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"properties": {"id": "23775"}, "geometry": {"coordinates": [4.35, 50.85]}},
            {"properties": {"id": "30991"}, "geometry": {"coordinates": [4.35, 50.85]}},
        ]}), encoding="utf-8")
        capture = io.StringIO()
        with redirect_stdout(capture), redirect_stderr(io.StringIO()):
            code = corpus.main([str(out), "--index", str(index)])
        report = capture.getvalue()
        assert code == 0, "a source placeholder must not fail an otherwise sound corpus"
        assert "integrity: PASS" in report, report
        assert "coordinates vs index: 0/2 within 25 m · 2 divergent" in report, report

    # The index reader keeps every entrance of a corner building and flips [lon, lat].
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "monuments.fr.json"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"properties": {"id": "7"}, "geometry": {"coordinates": [4.35, 50.85]}},
            {"properties": {"id": "7"}, "geometry": {"coordinates": [4.36, 50.86]}},
            {"properties": {"id": "8"}, "geometry": {"coordinates": []}},
        ]}), encoding="utf-8")
        corner = corpus.index_points(path)
        assert corner["7"] == [(50.85, 4.35), (50.86, 4.36)], corner
        assert "8" not in corner


def test_coordinate_cross_check_and_summary() -> None:
    module = load_scraper()
    test_coordinate_cross_check(module)


def test_caption_year_coverage(module) -> None:
    """The inventory dates its own photographs in the caption, and that date is the
    axis the corpus exists for: a comparison across eras needs the same building in
    different years. Measured over 26,419 notices: 72,278 of 77,175 pictures dated
    (93.7%), 1807-2026, median 2012, and 8,726 buildings carrying pictures from two
    or more decades.
    """
    corpus = load_summary()
    records = [
        {"building_id": "1", "images": [
            {"caption": "Rue A 12, 1912"},
            {"caption": "Rue A 12, 2011"},
            {"caption": None},
        ]},
        {"building_id": "2", "images": [{"caption": "Rue B 3, 1998"}]},
        {"building_id": "3", "images": [{"caption": "no year in this caption"}]},
    ]
    stats = corpus.caption_years(records)
    assert (stats["dated"], stats["total"]) == (3, 5), stats
    assert (stats["min"], stats["max"], stats["median"]) == (1912, 2011, 1998), stats
    assert stats["multi_decade"] == 1, stats  # only building 1 spans more than one

    # The trailing year is the capture date, so an earlier mention must not win:
    # this is what makes the current-year captions in the real corpus meaningful.
    trailing = corpus.caption_years(
        [{"building_id": "9", "images": [{"caption": "Restored in 1875, photographed 1990"}]}]
    )
    assert trailing["median"] == 1990, trailing

    # An undated corpus claims no span rather than reporting a bogus one.
    undated = corpus.caption_years(
        [{"building_id": "1", "images": [{"caption": "no year"}, {}]}]
    )
    assert undated["dated"] == 0 and "min" not in undated, undated


def test_manifest_rewrite_preserves_the_derivation_record(module) -> None:
    """Two tools write one manifest, and neither may erase the other's section.

    The picture pass rewrites a building's manifest on every resume, and it used to
    drop the ``derived_previews`` section it does not own: 157 real buildings ended
    up with ``preview/`` files that no manifest described, which is exactly the
    state in which a locally derived 500px copy can be mistaken for the publisher's
    own asset.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        module.write_manifest(target, {"schema_version": 2, "images": [{"filename": "a.JPG"}]})
        manifest_path = target / "manifest.json"

        # derive_previews.py records its work on the manifest it finds.
        written = json.loads(manifest_path.read_text(encoding="utf-8"))
        written["derived_previews"] = {
            "derived": True, "tool": "derive_previews.py", "note": "derived", "images": [],
        }
        manifest_path.write_text(json.dumps(written), encoding="utf-8")

        # A later picture-pass rewrite must carry it forward, and still own `images`.
        module.write_manifest(
            target, {"schema_version": 2, "images": [{"filename": "a.JPG"}, {"filename": "b.JPG"}]}
        )
        after = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert after["derived_previews"]["derived"] is True, after
        assert len(after["images"]) == 2, after

        # Nothing to preserve: nothing is invented, and a fresh tree stays fresh.
        fresh = Path(tmp) / "fresh"
        module.write_manifest(fresh, {"schema_version": 2, "images": []})
        assert "derived_previews" not in json.loads(
            (fresh / "manifest.json").read_text(encoding="utf-8")
        )

        # An unreadable manifest is replaced outright rather than blocking a fetch.
        broken = Path(tmp) / "broken"
        broken.mkdir()
        (broken / "manifest.json").write_text("{ not json", encoding="utf-8")
        module.write_manifest(broken, {"schema_version": 2, "images": [{"filename": "c.JPG"}]})
        assert len(json.loads((broken / "manifest.json").read_text(encoding="utf-8"))["images"]) == 1


def test_no_titled_section_is_silently_dropped(module) -> None:
    """Every section the notice titles must reach the record, or the gap is invisible.

    `details` is built *unfiltered* from every `h4.label` on the page — which is what
    lets the corpus-wide count of exactly 8 distinct French labels prove that no
    block label went unmapped, rather than merely suggesting it. Panels come from a
    different element (`h3` + `.wysiwyg`), so the same argument needs the panel
    vocabulary enumerated instead of assumed: across the seven committed fixtures it
    is exactly description, sources and the nearby-trees panel, and each one
    populates a record field. A fourth panel type would be the only remaining place
    prose could hide from a 26,419-notice corpus check, so this fails if one appears.
    """
    panel_fields = {
        "description": "description",
        "sources": "sources",
        "arbres remarquables à proximité": "nearby_trees",
        "opmerkelijke bomen in de nabijheid": "nearby_trees",
    }
    seen: set[str] = set()
    for fixture in (UNNAMED, NAMED, DUTCH, LEGACY, CREDITED, CORNER, NUMBERLESS):
        filename, building_id, lang = fixture
        html = (FIXTURES / filename).read_text(encoding="utf-8")
        panels = module.extract_panels(module.parse_dom(html))
        seen.update(panels)
        unknown = sorted(set(panels) - set(panel_fields))
        assert not unknown, f"{filename}: panel(s) nothing consumes: {unknown}"

        record = module.build_record(
            html, module.building_url(building_id, lang), building_id, lang
        )
        for title, field in panel_fields.items():
            if title not in panels:
                continue
            value = record[field]
            if field == "nearby_trees":
                assert isinstance(value, list), f"{filename}: {title!r} reached no field"
            else:
                assert value is not None, f"{filename}: {title!r} did not reach {field!r}"

    # The vocabulary is closed: nothing in the fixtures is outside it.
    assert seen == set(panel_fields), sorted(seen)

    # And blocks are recorded unfiltered, which is the property the corpus count relies on.
    labels = set()
    for filename, _bid, _lang in (UNNAMED, NAMED, DUTCH, LEGACY, CREDITED, CORNER, NUMBERLESS):
        labels.update(module.extract_detail_blocks(
            module.parse_dom((FIXTURES / filename).read_text(encoding="utf-8"))
        ))
    assert "Statut juridique" in labels and "Juridisch statuut" in labels, sorted(labels)
    assert "Une section qui n'existe pas" not in labels


def test_two_pictures_sharing_a_basename_are_both_kept(module) -> None:
    """The source serves some photographs twice, and both must survive.

    571 notices list the same basename under two URLs — `/medias/buildings/<name>`
    and `/medias/buildings/inv39-99/<name>`. Storing by basename made the second
    fetch overwrite the first, wrote a manifest whose two entries both claimed the
    *prefixed* URL (the merge map is keyed by filename, so the second replaced the
    first's entry), and left the audit a gap that no re-run could close: every pass
    re-fetched the losing picture and the audit reported it missing again.
    """
    base = "11500070_0075_P01.jpg"
    record = build(module, UNNAMED)
    record["images"] = [
        {"url": f"https://monument.heritage.brussels/medias/buildings/{base}",
         "filename": base, "caption": "plain", "width": 1085, "height": 1600},
        {"url": f"https://monument.heritage.brussels/medias/buildings/inv39-99/{base}",
         "filename": base, "caption": "prefixed", "width": 1085, "height": 1600},
    ]

    # Names are a pure function of the stored record, so a resume, a re-run and the
    # audit all agree without any extra state on disk.
    names = module.local_names(record["images"])
    assert names == [base, f"inv39-99__{base}"], names
    assert len(set(names)) == 2
    assert module.local_names(record["images"]) == names
    # Uniqueness is case-insensitive: 68 notices list one name in two extension
    # cases, which is two files here and one file on macOS or Windows.
    case_pair = [
        {"url": "https://monument.heritage.brussels/medias/buildings/a_01.JPG",
         "filename": "a_01.JPG"},
        {"url": "https://monument.heritage.brussels/medias/buildings/a_01.jpg",
         "filename": "a_01.jpg"},
    ]
    case_names = module.local_names(case_pair)
    assert case_names[0] == "a_01.JPG", case_names
    assert case_names[1].lower() != case_names[0].lower(), case_names
    assert len({n.lower() for n in case_names}) == 2, case_names
    # And the third variant of the same basename still gets its own name.
    three = module.local_names(case_pair + [dict(case_pair[0], url=case_pair[0]["url"] + "?v=2")])
    assert len({n.lower() for n in three}) == 3, three
    # A collision with no directory to borrow a prefix from still gets a name.
    assert module.local_name(
        {"filename": "x.jpg", "url": "https://h/p/x.jpg"}, {"x.jpg"}
    ) == "duplicate__x.jpg"
    # A URL is not a filename: a subpath is sanitised to safe characters, and one
    # that sanitises away entirely falls back rather than contributing "..".
    assert module.local_name(
        {"filename": "x.jpg", "url": "https://h/medias/buildings/2021-08/foo:bar baz/x.jpg"},
        {"x.jpg"},
    ) == "2021-08_foo_bar_baz__x.jpg"
    assert module.local_name(
        {"filename": "x.jpg", "url": "https://h/medias/buildings/../../x.jpg"}, {"x.jpg"}
    ) == "duplicate__x.jpg"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        (out / f"{record['building_id']}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        image_dir = Path(tmp) / "inbox"
        argv = ["--images-only", "--out", str(out), "--image-dir", str(image_dir),
                "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0"]
        args = module.build_parser().parse_args(argv)

        fetcher = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(fetcher, args) == 0
        assert fetcher.requests == 2, "both references are fetched"

        building_dir = image_dir / str(record["building_id"])
        manifest = json.loads((building_dir / "manifest.json").read_text(encoding="utf-8"))
        assert [entry["filename"] for entry in manifest["images"]] == names
        assert len({entry["url"] for entry in manifest["images"]}) == 2, "each keeps its URL"
        assert len({entry["sha256"] for entry in manifest["images"]}) == 2, "none overwritten"
        for entry in manifest["images"]:
            assert (building_dir / entry["filename"]).exists(), entry["filename"]

        # The audit can now reach green, and a resume costs nothing.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.verify_image_tree(module.build_parser().parse_args(
                ["--verify-images", "--out", str(out), "--image-dir", str(image_dir)]
            )) == 0
        again = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            module.run_image_pass(again, args)
        assert again.requests == 0, "a collision must not re-fetch forever"


def test_picture_pass_rechecks_robots(module) -> None:
    """A policy read at hour zero must not govern forty-two hours of pictures.

    The text crawl has re-read robots.txt hourly since its first long run. The
    picture pass had no re-check at all, so a publisher raising `Crawl-delay`
    mid-run would have been ignored for the remaining tens of hours — the one
    politeness failure the consecutive-failure guard cannot see, because
    over-fetching produces no errors. `recheck_robots` itself is covered by
    `test_midrun_robots_recheck`; this pins the wiring: the cadence, the stop, and
    that the run resumes cleanly.
    """
    record = build(module, NAMED)
    images = record["images"]

    def corpus(root: Path) -> Path:
        out = root / "out"
        out.mkdir(parents=True)
        (out / f"{record['building_id']}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return out

    with tempfile.TemporaryDirectory() as tmp:
        # Both bypasses: a cadence of 0, and --no-robots. Each needs its own corpus,
        # because a second run over the same one resumes and fetches nothing — the
        # per-picture loop would never be reached, and the bypass would look honoured
        # for the wrong reason.
        calls: list[str] = []
        original = module.recheck_robots
        module.recheck_robots = lambda f, path, cache=None: calls.append(path) or False
        try:
            for name, extra in (
                ("a1", ["--robots-recheck-seconds", "0"]),
                ("a2", ["--robots-recheck-seconds", "1e-9", "--no-robots"]),
            ):
                out = corpus(Path(tmp) / name)
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = module.run_image_pass(PictureFetcher(), module.build_parser().parse_args([
                        "--images-only", "--out", str(out),
                        "--image-dir", str(Path(tmp) / name / "inbox"),
                        "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
                        *extra,
                    ]))
                assert code == 0, name
                # The pictures really were fetched, so the loop did run.
                assert (Path(tmp) / name / "inbox" / str(record["building_id"])
                        / "manifest.json").exists(), name
        finally:
            module.recheck_robots = original
        assert calls == [], calls

    with tempfile.TemporaryDirectory() as tmp:
        # A revoked media path stops the run with the abort code, and no picture of
        # the second building is fetched after the policy changed.
        out = corpus(Path(tmp) / "b")
        seen: list[str] = []
        original = module.recheck_robots
        module.recheck_robots = lambda f, path, cache=None: seen.append(path) or True
        fetcher = PictureFetcher()
        err = io.StringIO()
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = module.run_image_pass(fetcher, module.build_parser().parse_args([
                    "--images-only", "--out", str(out), "--image-dir", str(Path(tmp) / "b" / "inbox"),
                    "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
                    "--robots-recheck-seconds", "1e-9",
                ]))
        finally:
            module.recheck_robots = original
        assert code == module.IMAGE_EXIT_ABORTED == 3, code
        assert len(seen) == 1, seen  # checked the media path it was about to fetch
        assert seen[0].startswith("/medias/buildings/"), seen
        assert "aborting: robots.txt no longer allows" in err.getvalue(), err.getvalue()
        assert fetcher.requests == 0, "nothing may be fetched once the path is disallowed"

    with tempfile.TemporaryDirectory() as tmp:
        # A permitted path with a raised delay just continues; the delay itself is
        # adopted by recheck_robots, which test_midrun_robots_recheck pins.
        out = corpus(Path(tmp) / "c")
        original = module.recheck_robots
        module.recheck_robots = lambda f, path, cache=None: False
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = module.run_image_pass(PictureFetcher(), module.build_parser().parse_args([
                    "--images-only", "--out", str(out), "--image-dir", str(Path(tmp) / "c" / "inbox"),
                    "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
                    "--robots-recheck-seconds", "1e-9",
                ]))
        finally:
            module.recheck_robots = original
        assert code == 0, code
        manifest = json.loads(
            (Path(tmp) / "c" / "inbox" / str(record["building_id"]) / "manifest.json")
            .read_text(encoding="utf-8")
        )
        assert len(manifest["images"]) == len(images)


def png_payload(width: int, height: int) -> bytes:
    """A minimal PNG header: enough for a signature and an IHDR size, no image data."""
    return (
        b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big") + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00" + b"\x00" * 32
    )


def jpeg_payload(width: int, height: int, app0: int = 0) -> bytes:
    """A minimal JPEG: SOF0 carries the frame size, optionally behind padding.

    Padding is split across APP0 segments because a segment length field is two
    bytes, exactly as a real EXIF block is chunked.
    """
    out = b"\xff\xd8"
    remaining = app0
    while remaining > 0:
        chunk = min(remaining, 60000)
        out += b"\xff\xe0" + (2 + chunk).to_bytes(2, "big") + b"\x00" * chunk
        remaining -= chunk
    frame = (
        b"\xff\xc0" + (17).to_bytes(2, "big") + b"\x08"
        + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x03"
        + b"\x01\x11\x00" * 3
    )
    return out + frame + b"\xff\xd9"


def test_image_dimensions_parser(module) -> None:
    """The size has to come from the bytes, in the standard library only.

    The scraper deliberately carries no image library, so the frame header is read
    from the file itself. Measured on the 2,471 real files downloaded first, this
    agreed with the notice's declared size in every case.
    """
    assert module.image_dimensions(jpeg_payload(1085, 1600)) == (1085, 1600)
    assert module.image_dimensions(png_payload(339, 500)) == (339, 500)
    gif = b"GIF89a" + (640).to_bytes(2, "little") + (480).to_bytes(2, "little") + b"\x00" * 8
    assert module.image_dimensions(gif) == (640, 480)
    bmp = b"BM" + b"\x00" * 16 + (300).to_bytes(4, "little") + (200).to_bytes(4, "little")
    assert module.image_dimensions(bmp) == (300, 200)

    # Not a picture, a bare signature, an empty file: all unknown, never a guess.
    assert module.image_dimensions(b"<html>") is None
    assert module.image_dimensions(b"\xff\xd8\xff") is None
    assert module.image_dimensions(b"") is None
    # A frame header behind 80 KiB of EXIF is found only when more is read.
    big = jpeg_payload(1200, 900, app0=80 * 1024)
    assert module.image_dimensions(big[: module.DIMENSION_HEAD_BYTES]) is None
    assert module.image_dimensions(big) == (1200, 900)


def test_audit_checks_the_stored_size(module) -> None:
    """A hash proves a file agrees with its manifest; the size proves it is the picture.

    This is the strongest check the corpus has, and it has to distinguish three
    states: agreeing, disagreeing (a real defect — the file is not what the notice
    names) and unreadable (reported, but *not* a defect, or an unparseable format
    would make a sound corpus look broken forever).
    """

    def stored(tmp: Path, declared: tuple[int, int] | None, payload: bytes) -> tuple[Path, Path]:
        out = tmp / "out"
        out.mkdir(parents=True)
        record = build(module, UNNAMED)
        name = "stimulus.png"
        entry = {
            "url": f"https://monument.heritage.brussels/medias/buildings/{name}",
            "filename": name, "caption": "synthetic",
        }
        if declared is not None:  # None means the notice declared no size at all
            entry["width"], entry["height"] = declared
        record["images"] = [entry]
        module.write_record(record, module.record_path(out, str(record["building_id"]), "fr"))
        image_dir = tmp / "inbox"
        building_dir = image_dir / str(record["building_id"])
        building_dir.mkdir(parents=True)
        (building_dir / name).write_bytes(payload)
        manifest = module.manifest_skeleton(record, module.CONDITIONAL_BASIS)
        manifest["images"] = [{
            "url": record["images"][0]["url"], "filename": name, "variant": "full",
            "format": module.sniff_image_format(payload), "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            # The real writer always records these, and the audit now requires them.
            "rights_hint": None, "credit_holders": [],
        }]
        module.write_manifest(building_dir, manifest)
        return out, image_dir

    def audit(out: Path, image_dir: Path) -> tuple[int, str]:
        capture, err = io.StringIO(), io.StringIO()
        with redirect_stdout(capture), redirect_stderr(err):
            code = module.verify_image_tree(module.build_parser().parse_args(
                ["--verify-images", "--out", str(out), "--image-dir", str(image_dir)]
            ))
        return code, capture.getvalue() + err.getvalue()

    with tempfile.TemporaryDirectory() as tmp:
        out, image_dir = stored(Path(tmp) / "a", (64, 32), png_payload(64, 32))
        code, report = audit(out, image_dir)
        assert code == 0, report
        assert counter(report, "size disagrees with the notice:") == 0, report
        assert counter(report, "size unreadable (not a defect):") == 0, report

    with tempfile.TemporaryDirectory() as tmp:
        # The file is a 64x32 picture; the notice claims 999x999. That is a defect.
        out, image_dir = stored(Path(tmp) / "b", (999, 999), png_payload(64, 32))
        code, report = audit(out, image_dir)
        assert code == 1, report
        assert counter(report, "size disagrees with the notice:") == 1, report
        assert "64x32 but the notice declares 999x999" in report, report
        assert counter(report, "missing/altered despite a manifest:") == 0, report

    with tempfile.TemporaryDirectory() as tmp:
        # Signature-valid but no frame header: unchecked, and still not a defect.
        out, image_dir = stored(Path(tmp) / "c", (64, 32), b"\xff\xd8\xff" + b"\x00" * 64)
        code, report = audit(out, image_dir)
        assert code == 0, report
        assert counter(report, "size unreadable (not a defect):") == 1, report
        assert counter(report, "size disagrees with the notice:") == 0, report
        assert "0 defect(s)" in report, report


    with tempfile.TemporaryDirectory() as tmp:
        # No declared size: the sizes cannot be compared at all, so the audit has to
        # say so rather than let "size disagrees: 0" imply it checked everything.
        out, image_dir = stored(Path(tmp) / "e", None, png_payload(64, 32))
        code, report = audit(out, image_dir)
        assert code == 0, report
        assert counter(report, "no declared size (not size-checked):") == 1, report
        assert counter(report, "size disagrees with the notice:") == 0, report
        assert counter(report, "size unreadable (not a defect):") == 0, report
        assert "0 defect(s)" in report, report

    with tempfile.TemporaryDirectory() as tmp:
        # The ordinary case must not be counted as undeclared.
        out, image_dir = stored(Path(tmp) / "f", (64, 32), png_payload(64, 32))
        code, report = audit(out, image_dir)
        assert code == 0, report
        assert counter(report, "no declared size (not size-checked):") == 0, report

    with tempfile.TemporaryDirectory() as tmp:
        # A frame header past the first 64 KiB of EXIF: the audit must read further
        # rather than report a sound picture as unchecked.
        payload = jpeg_payload(1200, 900, app0=80 * 1024)
        assert len(payload) > module.DIMENSION_HEAD_BYTES
        out, image_dir = stored(Path(tmp) / "d", (1200, 900), payload)
        code, report = audit(out, image_dir)
        assert code == 0, report
        assert counter(report, "size unreadable (not a defect):") == 0, report
        assert counter(report, "size disagrees with the notice:") == 0, report


def test_audit_requires_the_rights_record(module) -> None:
    """A manifest that lists pictures without the terms is a rights defect.

    The permission this corpus is built on is conditional: the pictures may be used
    with the credit and the source link the publisher requires. A tree that verified
    its pixels while shipping images with no record of those terms would be a
    compliance failure the audit could not see. All 1,452 manifests written by the
    time this was added state them, so requiring them costs nothing today.
    """
    complete = {
        "rights_basis": module.CONDITIONAL_BASIS,
        "conditions_url": module.CONDITIONS_URL,
        "obligations": {"online": ["x"], "printed": ["y"], "third_party": "z"},
        "images": [{"filename": "a.JPG", "rights_hint": None, "credit_holders": []}],
    }
    assert module.rights_problems(complete, "1") == []

    for broken, expect in (
        ({**complete, "rights_basis": None}, "states no reuse basis"),
        ({**complete, "conditions_url": None}, "no conditions_url"),
        ({**complete, "obligations": {"online": ["x"]}}, "no printed obligation"),
        ({**complete, "images": [{"filename": "a.JPG"}]}, "no rights_hint"),
        (
            {**complete, "images": [{"filename": "a.JPG", "rights_hint": None}]},
            "no credit_holders",
        ),
    ):
        problems = module.rights_problems(broken, "1")
        assert any(expect in problem for problem in problems), (expect, problems)

    # Another basis is not asked for the conditional obligations: the writer only
    # sets them for the conditional basis, so demanding them would be wrong.
    other = {"rights_basis": "cc-by", "images": [
        {"filename": "a.JPG", "rights_hint": None, "credit_holders": []}]}
    assert module.rights_problems(other, "1") == []

    # And the audit treats a missing rights record as a defect that fails the run.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir(parents=True)
        record = build(module, UNNAMED)
        # One synthetic picture, fully stored, so the rights gap is the ONLY defect:
        # a fixture that is also incomplete would fail the audit for that reason
        # instead, and the assertion would pass without testing the rights check.
        name = "stimulus.png"
        payload = png_payload(64, 32)
        record["images"] = [{
            "url": f"https://monument.heritage.brussels/medias/buildings/{name}",
            "filename": name, "width": 64, "height": 32, "caption": "synthetic",
        }]
        module.write_record(record, module.record_path(out, "23775", "fr"))
        image_dir = Path(tmp) / "inbox"
        building_dir = image_dir / "23775"
        building_dir.mkdir(parents=True)
        (building_dir / name).write_bytes(payload)
        manifest = module.manifest_skeleton(record, module.CONDITIONAL_BASIS)
        manifest["obligations"] = {}
        manifest["conditions_url"] = None
        manifest["images"] = [{
            "url": record["images"][0]["url"], "filename": name, "variant": "full",
            "format": "png", "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "rights_hint": None, "credit_holders": [],
        }]
        module.write_manifest(building_dir, manifest)
        capture, err = io.StringIO(), io.StringIO()
        with redirect_stdout(capture), redirect_stderr(err):
            code = module.verify_image_tree(module.build_parser().parse_args(
                ["--verify-images", "--out", str(out), "--image-dir", str(image_dir)]
            ))
        report = capture.getvalue() + err.getvalue()
        # Only the rights record is wrong: everything else must be clean.
        assert counter(report, "missing/altered despite a manifest:") == 0, report
        assert counter(report, "not downloaded yet:") == 0, report
        assert counter(report, "rights record incomplete:") == 4, report
        assert code == 1, report
        assert "conditional basis with no conditions_url" in report, report
        assert "conditional basis with no printed obligation" in report, report


def test_coordinate_resolution(module) -> None:
    """A notice that mis-states its location must not decide the record's coordinate.

    Measured: **2,406 notices serve one shared placeholder value 233 km from
    Brussels**, while ordinary divergence from the publisher's index is under 126 m
    (long and multi-number buildings). A kilometre separates the two cleanly, and the
    substituted point is recorded with its provenance rather than silently — the
    notice's own value is kept verbatim in `coordinates_notice`.
    """
    # The committed 40680 fixture really does carry that placeholder.
    html = (FIXTURES / CREDITED[0]).read_text(encoding="utf-8")
    brussels = (50.77148067572179, 4.380589481521128)  # where the index puts it
    record = module.build_record(
        html, module.building_url("40680", "fr"), "40680", "fr", None, brussels
    )
    assert record["coordinates"] == {"latitude": brussels[0], "longitude": brussels[1]}
    assert record["coordinates_source"] == "index"
    assert record["coordinates_notice"] == {
        "latitude": 49.293381634479, "longitude": 2.3067617893134}
    # 221 km from the synthetic Uccle point; bounded rather than hard-coded, since the
    # exact figure depends on which index point is used.
    assert any(re.search(r"is 2\d\d km from where", note) for note in record["notes"]), \
        record["notes"]
    # The page's own marker is still what the parser read; nothing is invented.
    assert module.extract_coordinates(html)["longitude"] == 2.3067617893134

    # A notice whose marker agrees is left exactly as it was, and no field is added,
    # which is why the 24,013 already-stored records stay valid unchanged.
    other = (FIXTURES / UNNAMED[0]).read_text(encoding="utf-8")
    notice = module.extract_coordinates(other)
    assert notice is not None
    near = (notice["latitude"] + 0.00005, notice["longitude"] + 0.00005)  # ~7 m away
    plain = module.build_record(
        other, module.building_url("23775", "fr"), "23775", "fr", None, near
    )
    assert plain["coordinates"] == notice
    assert "coordinates_source" not in plain and "coordinates_notice" not in plain

    # No index point at all: the notice decides, as it always did.
    alone = module.build_record(other, module.building_url("23775", "fr"), "23775", "fr")
    assert alone["coordinates"] == notice
    assert "coordinates_source" not in alone

    # A far-away index point substitutes even when the notice looks self-consistent.
    far = module.build_record(
        other, module.building_url("23775", "fr"), "23775", "fr", None,
        (notice["latitude"] + 0.05, notice["longitude"]),
    )
    assert far["coordinates_source"] == "index"
    assert far["coordinates_notice"] == notice

    # A notice with no marker takes the index's point, with nothing to preserve.
    stripped = re.sub(r"L\.marker\(", "L.notmarker(", other)
    assert module.extract_coordinates(stripped) is None
    filled = module.build_record(
        stripped, module.building_url("23775", "fr"), "23775", "fr", None, near
    )
    assert filled["coordinates_source"] == "index"
    assert filled["coordinates_notice"] is None
    assert filled["coordinates"] == {"latitude": near[0], "longitude": near[1]}
    assert any("no map marker" in note for note in filled["notes"]), filled["notes"]


def test_index_points_reader(module) -> None:
    """The index is GeoJSON with one feature per entrance, and [lon, lat] order."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "monuments.fr.json"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"properties": {"id": "7"}, "geometry": {"coordinates": [4.35, 50.85]}},
            {"properties": {"id": "7"}, "geometry": {"coordinates": [4.36, 50.86]}},
            {"properties": {"id": "8"}, "geometry": {"coordinates": []}},
        ]}), encoding="utf-8")
        points = module.index_points_from(path)
        assert points == {"7": (50.85, 4.35)}, points  # first entrance, lat before lon
        # A missing or unreadable cache means no points, not a failed scrape.
        assert module.index_points_from(Path(tmp) / "absent.json") == {}
        broken = Path(tmp) / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        assert module.index_points_from(broken) == {}


def test_place_notice_parser(module) -> None:
    """A `notice de lieu` lives at the URL the building parser refuses as a trap.

    `/<lang>/<city>/<street>/<street-id>` cannot be a building id, so the building
    parser rejects it rather than silently scraping the wrong notice. It is the place
    notice, and it reuses the building page's markup — so the extraction is shared,
    while the entity is not: a place has no address, tags, legal status or
    contributors, and its prose is the street-and-place introduction.
    """
    html = (FIXTURES / STREET[0]).read_text(encoding="utf-8")
    url = "https://monument.heritage.brussels/fr/Saint-Gilles/Rue_Africaine/10601002"
    record = module.build_place_record(html, url, STREET[1], STREET[2])

    assert record["kind"] == "place" and record["place_id"] == "10601002"
    assert record["name"] == "Rue Africaine"
    assert record["municipality"] == "Saint-Gilles"
    assert record["street_slug"] == "Rue_Africaine"

    # The introduction, with the "see the properties" navigation label stripped: it
    # sits inside the same `.wysiwyg`, so leaving it in would begin every place
    # description with a UI string.
    text = record["description"]["text"]
    assert "À cheval sur les communes" in text, text[:120]
    assert "Voir les biens de ce lieu" not in text, text[:120]
    assert len(text) > 1000, len(text)
    assert record["description"]["html"], "the source HTML is kept too"

    assert "Archives des nos ne figurant pas en notice" in record["sources"]["text"]

    # Exactly the gallery, under the *street* media path, and not the suggestions
    # strip, which lists properties on other streets entirely.
    assert [i["filename"] for i in record["images"]] == ["10601002_P01.JPG", "10601002_P02.JPG"]
    assert all("/medias/streets/" in i["url"] for i in record["images"])
    assert record["images"][0]["caption"].startswith("Rue Africaine, vue depuis")
    assert (record["images"][0]["width"], record["images"][0]["height"]) == (1600, 1200)
    assert not any("Avenue_Henri_Jaspar" in i["url"] for i in record["images"])

    assert "Inventaire(s)" in record["details"]
    # The page's own building list is a robots-disallowed route: recorded, not fetched.
    assert record["inventory_link"] == "/index.php?street=10601002&section=buildings&lg=fr"
    assert any("robots.txt disallows" in note for note in record["notes"])

    # A place is not a building, and the record says so by shape as well as by `kind`.
    for absent in ("building_id", "identity", "tags", "interests", "legal_status", "contributors"):
        assert absent not in record, absent

    # The soft-404 guard applies here too: this host answers a missing page with 200.
    for bad in ((FIXTURES / "soft-404.html").read_text(encoding="utf-8"), "<html><body></body></html>"):
        try:
            module.build_place_record(bad, url, STREET[1], STREET[2])
        except module.ScrapeError:
            continue
        raise AssertionError("a page with no notice containers must be refused")


def test_place_targets_and_streets(module) -> None:
    """Places need their city and street; the trap the building mode refuses is theirs.

    The same four-segment URL that `parse_target` rejects as a trap is the place URL,
    which is exactly why the two modes must not share one parser.
    """
    url = "https://monument.heritage.brussels/fr/Saint-Gilles/Rue_Africaine/10601002"
    assert module.parse_place_target(url) == ("10601002", "Saint-Gilles", "Rue_Africaine")
    assert module.parse_place_target("/fr/Saint-Gilles/Rue_Africaine/10601002") == (
        "10601002", "Saint-Gilles", "Rue_Africaine")
    assert module.place_url("10601002", "Saint-Gilles", "Rue_Africaine", "fr") == url

    for bad, why in (
        ("23775", "a bare id cannot name a place"),
        ("/fr/buildings/23775", "wrong path shape"),
        ("https://example.com/fr/A/B/10601002", "foreign host"),
        ("/fr/Saint-Gilles/Rue_Africaine/10601002/9", "five segments is a building"),
    ):
        try:
            module.parse_place_target(bad)
        except module.ScrapeError:
            continue
        raise AssertionError(f"{why}: {bad!r} must be refused")
    # And the building parser still refuses the place form, so the trap has not regressed.
    try:
        module.parse_target(url)
    except module.ScrapeError:
        pass
    else:
        raise AssertionError("the building parser must keep refusing the street URL")

    # Streets come from the building corpus itself: no places index exists.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "scraped"
        out.mkdir(parents=True)
        for fixture in (UNNAMED, NAMED):
            filename, building_id, lang = fixture
            record = module.build_record(
                (FIXTURES / filename).read_text(encoding="utf-8"),
                module.building_url(building_id, lang), building_id, lang,
            )
            module.write_record(record, module.record_path(out, building_id, lang))
        # A second building on the same street must not add a second target: the
        # corpus links one street id from many buildings, which is the whole point of
        # enumerating streets this way. Without this the uniqueness assertion below
        # could not fail, and a lost de-duplication would go unnoticed.
        copy = json.loads(
            module.record_path(out, UNNAMED[1], UNNAMED[2]).read_text(encoding="utf-8")
        )
        copy["building_id"] = "999999"
        module.write_record(copy, out / "999999.fr.json")

        targets = module.street_targets(out, "fr")
        assert targets and all(len(t) == 3 and t[0].isdigit() for t in targets), targets
        ids = [t[0] for t in targets]
        assert len(ids) == len(set(ids)), f"a street must appear once: {ids}"
        # Derive the expectation from the fixtures rather than hard-coding it: these two
        # buildings sit on different streets, and neither is Rue Africaine.
        expected = set()
        for _filename, building_id, lang in (UNNAMED, NAMED):
            record = json.loads(
                module.record_path(out, building_id, lang).read_text(encoding="utf-8")
            )
            for address in record["addresses"]:
                expected.add(str(address["url"]).rstrip("/").rsplit("/", 1)[-1])
        assert set(ids) == expected, (ids, expected)
        assert module.street_targets(Path(tmp) / "absent", "fr") == []


def test_place_scrape_runner(module) -> None:
    """The place corpus is its own stream, and it resumes like the building sweep."""
    html = (FIXTURES / STREET[0]).read_text(encoding="utf-8")

    class ServesPlaces:
        def __init__(self) -> None:
            self.requests = 0
            self.bytes = 0
            self.delay = 2.0
            self.policy = None

        def get_text(self, url: str) -> str:
            self.requests += 1
            self.bytes += len(html)
            return html

    url = "https://monument.heritage.brussels/fr/Saint-Gilles/Rue_Africaine/10601002"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "places"
        argv = ["--places", "--out", str(out), "--places-out", str(out), url,
                "--no-robots", "--progress-every", "0", "--quiet"]
        fixture_fetcher = ServesPlaces()
        with patch.object(module, "Fetcher", return_value=fixture_fetcher) as factory, \
                patch("socket.socket", side_effect=AssertionError("offline test attempted network")), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.main(argv) == 0
        factory.assert_called_once()
        assert fixture_fetcher.requests == 1, "CLI dispatch must use the fixture fetcher"
        written = json.loads((out / "10601002.fr.json").read_text(encoding="utf-8"))
        assert written["kind"] == "place" and written["name"] == "Rue Africaine"
        assert written["extraction"]["content_hash"]
        # Nothing about a place pretends to be a building.
        assert "building_id" not in written and "tags" not in written
        # A place record is not a building record, so it must not land in the
        # building corpus by accident.
        assert list(out.glob("*.json")) == [out / "10601002.fr.json"]

    # Resuming: a second run over the same corpus makes no request at all.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "places"
        args = ["--places", "--out", str(out), "--places-out", str(out), url,
                "--no-robots", "--progress-every", "0", "--quiet"]
        main_args = module.build_parser().parse_args(args)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_place_scrape(ServesPlaces(), main_args) == 0
        again = ServesPlaces()
        resume = module.build_parser().parse_args([*args, "--skip-existing"])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_place_scrape(again, resume) == 0
        assert again.requests == 0, "a resume must fetch nothing"


def test_offline_correction_matches_a_rescrape(module) -> None:
    """The correction must be identical whether it comes from a page or from disk.

    A crawl would derive these fields from the notice; the amendment derives them from
    the value already stored. If the two differed, a corrected record would register as
    upstream drift against its own re-scrape — so this equivalence is what makes doing
    it offline legitimate rather than merely 80 minutes cheaper. It also means the
    amendment needs no crawl at all: its inputs are the record and the local index.
    """
    html = (FIXTURES / CREDITED[0]).read_text(encoding="utf-8")
    url = module.building_url("40680", "fr")
    brussels = (50.77148067572179, 4.380589481521128)
    scraped = module.build_record(html, url, "40680", "fr", None, brussels)
    stored = module.build_record(html, url, "40680", "fr")  # as it would already be
    assert "coordinates_source" not in stored

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "scraped"
        out.mkdir(parents=True)
        module.write_record(stored, module.record_path(out, "40680", "fr"))
        # A record the correction must leave alone.
        untouched = module.build_record(
            (FIXTURES / UNNAMED[0]).read_text(encoding="utf-8"),
            module.building_url("23775", "fr"), "23775", "fr",
        )
        module.write_record(untouched, module.record_path(out, "23775", "fr"))
        before = module.record_path(out, "23775", "fr").read_bytes()

        index = Path(tmp) / "monuments.fr.json"
        index.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"properties": {"id": "40680"},
             "geometry": {"coordinates": [brussels[1], brussels[0]]}},
            {"properties": {"id": "23775"},
             "geometry": {"coordinates": [-4.3222264028787 * -1, 50.866737752527]}},
        ]}), encoding="utf-8")

        # Dry run first: it must change nothing at all.
        args = module.build_parser().parse_args([
            "--amend-coordinates", "--dry-run", "--out", str(out),
            "--index-file", str(index), "--lang", "fr",
        ])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.amend_coordinates(args) == 0
        assert module.record_path(out, "40680", "fr").read_text(encoding="utf-8") == (
            json.dumps(stored, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ), "a dry run must not write"

        args = module.build_parser().parse_args([
            "--amend-coordinates", "--out", str(out), "--index-file", str(index),
            "--lang", "fr",
        ])
        capture = io.StringIO()
        with redirect_stdout(capture), redirect_stderr(io.StringIO()):
            assert module.amend_coordinates(args) == 0
        assert "1 record(s) corrected" in capture.getvalue(), capture.getvalue()

        amended = json.loads(module.record_path(out, "40680", "fr").read_text(encoding="utf-8"))
        for field in ("coordinates", "coordinates_source", "coordinates_notice", "notes"):
            assert amended[field] == scraped[field], field
        assert amended["extraction"]["content_hash"] == scraped["extraction"]["content_hash"]
        # Everything else about the record is left exactly as it was.
        for key in stored:
            if key not in ("coordinates", "coordinates_source", "coordinates_notice",
                           "notes", "extraction"):
                assert amended[key] == stored[key], key
        # And the record that needed nothing was not rewritten.
        assert module.record_path(out, "23775", "fr").read_bytes() == before

        # Re-running finds nothing left to do, and says so distinguishably: after a run
        # the record is idempotent by construction (its corrected coordinate now agrees
        # with the index), so only the *report* can show that a correction is already
        # there — "already right" and "already carrying a correction" are different
        # facts to a reader checking whether an earlier run took effect.
        again = io.StringIO()
        with redirect_stdout(again), redirect_stderr(io.StringIO()):
            assert module.amend_coordinates(args) == 0
        assert "0 record(s) corrected" in again.getvalue(), again.getvalue()
        assert "1 already carrying a correction" in again.getvalue(), again.getvalue()
        assert json.loads(module.record_path(out, "40680", "fr").read_text(encoding="utf-8")) \
            == amended


def test_place_absence_is_a_finding_not_a_failure(module) -> None:
    """Only ~2,241 of the 3,564 streets are published as notices, so absence is normal.

    This host answers a missing id with HTTP 200 *and an error page*, so "there is no
    notice here" and "the request failed" are different facts. Treating the first as the
    second would have put ~1,300 expected absences into the failure journal, made the
    pipeline call a healthy stage broken, and buried any real failure among them.
    """
    soft = (FIXTURES / "soft-404.html").read_text(encoding="utf-8")
    real = (FIXTURES / STREET[0]).read_text(encoding="utf-8")

    # The signal is a type, not a message, so it cannot drift with the wording.
    assert issubclass(module.NotANoticePage, module.ScrapeError)
    for builder, args in (
        (module.build_place_record, (STREET[1], STREET[2])),
        (module.build_record, ("23775", "fr")),
    ):
        try:
            builder(soft, module.building_url("23775", "fr"), *args)
        except module.NotANoticePage:
            continue
        raise AssertionError(f"{builder.__name__} must signal absence distinctly")

    class Mixed:
        """A real notice for one street, the site's error page for another."""

        def __init__(self) -> None:
            self.requests = 0
            self.bytes = 0
            self.delay = 2.0
            self.policy = None

        def get_text(self, url: str) -> str:
            self.requests += 1
            body = real if url.endswith("/10601002") else soft
            self.bytes += len(body)
            return body

    argv = [
        "--places", "--no-robots", "--progress-every", "0", "--quiet",
        "/fr/Saint-Gilles/Rue_Africaine/10601002",
        "/fr/Saint-Gilles/Rue_Inexistante/99999999",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "places"
        args = module.build_parser().parse_args([*argv, "--out", str(out), "--places-out", str(out)])
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            assert module.run_place_scrape(Mixed(), args) == 0, "absence is not a problem"
        final = [line for line in err.getvalue().splitlines() if line.startswith("[FINAL]")]
        assert final and "1 without a published notice" in final[0], final
        assert "1 place(s) written" in final[0], final
        assert not (out / "_failures.fr.json").exists(), "absence must not fill the journal"
        absent = json.loads((out / "_absent.fr.json").read_text(encoding="utf-8"))
        assert [entry["target"] for entry in absent] == ["99999999"], absent
        # The claim is checkable: the hash of what the site actually served is kept.
        assert len(absent[0]["page_sha256"]) == 64
        assert absent[0]["url"].endswith("/99999999")
        assert "no notice is published" in absent[0]["reason"]

        # A resume must not spend crawl time re-confirming a remembered absence.
        again = Mixed()
        resume = module.build_parser().parse_args(
            [*argv, "--out", str(out), "--places-out", str(out), "--skip-existing"]
        )
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_place_scrape(again, resume) == 0
        assert again.requests == 0, "a remembered absence must not be re-fetched"

    # A genuine fetch failure is still a failure: the distinction must cut both ways.
    class Fails:
        def __init__(self) -> None:
            self.requests = 0
            self.bytes = 0
            self.delay = 2.0
            self.policy = None

        def get_text(self, url: str) -> str:
            raise module.ScrapeError(f"{url} returned HTTP 503")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "places"
        args = module.build_parser().parse_args([*argv, "--out", str(out), "--places-out", str(out)])
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            assert module.run_place_scrape(Fails(), args) == 1
        assert "2 failed" in err.getvalue(), err.getvalue()
        assert not (out / "_absent.fr.json").exists()


def test_place_stub_pages_are_counted_apart(module) -> None:
    """A place page can exist with nothing on it, and the run must say so.

    Measured across a deterministic spread of twelve real place pages (one per
    municipality): **six carried an introduction and six were an `h1` name only** — no
    prose, no pictures, no labelled blocks. A `[FINAL]` line reporting only pages
    written would have claimed 12 and hidden that half of them contained nothing.
    """
    real = (FIXTURES / STREET[0]).read_text(encoding="utf-8")
    stub = (FIXTURES / STREET_STUB[0]).read_text(encoding="utf-8")
    # A synthetic stub was tried first and was wrong: truncating the real page kept
    # its gallery, because the pictures precede the description. The real stub is
    # captured instead, and it is shaped differently from any guess.
    assert "Allée des Orpins" in stub

    class Serves:
        def __init__(self) -> None:
            self.requests = 0
            self.bytes = 0
            self.delay = 2.0
            self.policy = None

        def get_text(self, url: str) -> str:
            self.requests += 1
            body = real if url.endswith("/10601002") else stub
            self.bytes += len(body)
            return body

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "places"
        args = module.build_parser().parse_args([
            "--places", "--no-robots", "--progress-every", "0", "--quiet",
            "--out", str(out), "--places-out", str(out),
            "/fr/Saint-Gilles/Rue_Africaine/10601002",
            "/fr/Anderlecht/Allee_des_Orpins/10700323",
        ])
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            assert module.run_place_scrape(Serves(), args) == 0
        final = [line for line in err.getvalue().splitlines() if line.startswith("[FINAL]")]
        assert final and "2 place(s) written (1 carrying an introduction)" in final[0], final
        # The stub is written, not dropped: a missing introduction is a fact about the
        # source, and the record has to say so rather than look like a parse failure.
        stub_record = json.loads((out / "10700323.fr.json").read_text(encoding="utf-8"))
        assert stub_record["kind"] == "place"
        assert stub_record["name"] == "Allée des Orpins"
        assert stub_record["description"] is None
        assert stub_record["images"] == []
        assert any("no written notice" in note for note in stub_record["notes"]), stub_record["notes"]
        full = json.loads((out / "10601002.fr.json").read_text(encoding="utf-8"))
        assert full["description"] and len(full["description"]["text"]) > 1000


def test_picture_progress_reports_pace_and_eta(module) -> None:
    """The log is a detached run's only observability, so it must not mislead.

    The pace used to be `fetched / whole-run elapsed`, so a resume — which begins by
    hashing what is already stored — reported **0.00/s for its first minutes** and
    understated the true rate for hours after. There was no ETA and no denominator
    either, so "12 image(s)" said nothing about how far through the run was.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir(parents=True)
        for filename, building_id in (("building-23775.fr.html", "23775"),
                                     ("building-30991.fr.html", "30991")):
            record = build(module, (filename, building_id, "fr"))
            module.write_record(record, module.record_path(out, building_id, "fr"))
        image_dir = Path(tmp) / "inbox"
        args = module.build_parser().parse_args([
            "--images-only", "--out", str(out), "--image-dir", str(image_dir),
            "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "1",
        ])

        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            assert module.run_image_pass(PictureFetcher(), args) == 0
        lines = err.getvalue().splitlines()
        plan = [line for line in lines if line.startswith("plan:")]
        assert plan and "4 picture(s) to fetch of 4 named across 2 record(s); 0 already stored" in plan[0], plan
        progress = [line for line in lines if re.match(r"^\[\d+/", line)]
        assert progress, lines
        assert re.search(r"\d+/4 image\(s\)", progress[-1]), progress[-1]
        assert "eta" in progress[-1] and "verified" in progress[-1], progress[-1]

        # The resume is the case that used to report a false 0.00/s.
        err = io.StringIO()
        second = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            assert module.run_image_pass(second, args) == 0
        assert second.requests == 0, "a resume fetches nothing"
        lines = err.getvalue().splitlines()
        plan = [line for line in lines if line.startswith("plan:")]
        assert "0 picture(s) to fetch of 4 named" in plan[0], plan
        progress = [line for line in lines if re.match(r"^\[\d+/", line)]
        assert progress and "verifying" in progress[-1], progress[-1]
        assert "verified 2" in progress[-1], progress[-1]
        assert "0.00/s" not in err.getvalue(), "a resume must not report a false pace"


def test_one_record_id_for_both_kinds(module) -> None:
    """A place record is filed under `place_id`; every image path must accept that.

    The picture pass already coped, through a filename-stem fallback, while
    `download_images` required a building id outright and would have raised on a place
    record. One helper now serves both, so the two kinds cannot drift apart again.
    """
    assert module.record_id({"building_id": "23775"}) == "23775"
    assert module.record_id({"place_id": "10601002"}) == "10601002"
    assert module.record_id({"place_id": "10601002"}, "ignored") == "10601002"
    assert module.record_id({}, "stem") == "stem"
    try:
        module.record_id({})
    except module.ScrapeError:
        pass
    else:
        raise AssertionError("a record with no id must be refused")

    # And the inline download path now works on a place record, not just a building one.
    html = (FIXTURES / STREET[0]).read_text(encoding="utf-8")
    url = "https://monument.heritage.brussels/fr/Saint-Gilles/Rue_Africaine/10601002"
    place = module.build_place_record(html, url, STREET[1], STREET[2])
    with tempfile.TemporaryDirectory() as tmp:
        manifest = module.download_images(
            PictureFetcher(), place, module.CONDITIONAL_BASIS, Path(tmp) / "places"
        )
        assert (Path(tmp) / "places" / STREET[1] / "manifest.json").exists()
        assert len(manifest["images"]) == len(place["images"])
        assert all("/medias/streets/" in entry["url"] for entry in manifest["images"])
        # The rights record travels with it, as for buildings.
        assert manifest["rights_basis"] == module.CONDITIONAL_BASIS
        assert any("SPRB-DMS" in duty for duty in manifest["obligations"]["online"])


def test_final_status_line(module) -> None:
    """A detached run's log must state its outcome: a finished run and a crashed
    one otherwise look identical, both simply stopping after the last progress
    line. Foreign hosts fail before any request, so this runs offline."""
    with tempfile.TemporaryDirectory() as tmp:
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = module.main([
                "https://example.com/fr/buildings/1", "--out", tmp,
                "--no-robots", "--max-consecutive-failures", "1", "--quiet",
            ])
        lines = [line for line in err.getvalue().splitlines() if line]
        assert code == 1
        assert lines[-1].startswith("[FINAL] aborted early"), lines[-1]
        assert "1 failed" in lines[-1]



def test_content_hash_contract(module) -> None:
    """The content hash must ignore run noise but catch real notice changes.

    The server randomises the related-notices widget on every request, so hashing
    it would report drift on every re-scrape and make `--fail-on-change` useless.
    """
    record = build(module, NAMED)
    baseline = record["extraction"]["content_hash"]
    assert len(baseline) == 64
    assert record["schema_version"] == module.SCHEMA_VERSION

    # Randomised widget, run metadata and static config must not move the hash.
    for field in ("suggestions", "retrieved_at", "source"):
        mutated = json.loads(json.dumps(record))
        mutated[field] = "deliberately different"
        assert module.content_hash(mutated) == baseline, f"{field} must not be hashed"

    # Real extracted content must move it.
    for field, value in (
        ("description", None),
        ("tags", []),
        ("images", []),
        ("legal_status", None),
    ):
        mutated = json.loads(json.dumps(record))
        mutated[field] = value
        assert module.content_hash(mutated) != baseline, f"{field} must be hashed"

    # The record names what it left out, so a consumer can verify the claim.
    assert "suggestions" in record["extraction"]["non_canonical_fields"]
    assert record["extraction"]["page_hash"] != baseline
    assert record["extraction"]["scraper"] == "scrape_monument.py"


def test_records_are_strict_json(module) -> None:
    for fixture in (UNNAMED, NAMED, DUTCH, LEGACY, CREDITED, CORNER, NUMBERLESS):
        payload = json.dumps(build(module, fixture), allow_nan=False)
        assert json.loads(payload)["schema_version"] == module.SCHEMA_VERSION


def test_target_parsing(module) -> None:
    assert module.parse_target("23775") == "23775"
    assert module.parse_target("/fr/buildings/30991") == "30991"
    assert module.parse_target("https://monument.heritage.brussels/fr/buildings/12") == "12"
    assert module.parse_target("/nl/buildings/30991") == "30991"
    # A 4-part address URL ends in the building id.
    assert module.parse_target("/fr/Bruxelles_Pentagone/Grand-Place/26/31141") == "31141"

    # A 3-part address URL ends in the *street* id, so it must not be accepted.
    try:
        module.parse_target("/fr/Ganshoren/Avenue_des_Gloires_Nationales/10831042")
    except module.ScrapeError as error:
        assert "street" in str(error)
    else:
        raise AssertionError("a 3-part street URL must not be read as a building id")

    try:
        module.parse_target("https://example.com/fr/buildings/1")
    except module.ScrapeError:
        pass
    else:
        raise AssertionError("foreign hosts must be refused")


def test_url_and_delay_policy(module) -> None:
    module.validate_url("https://monument.heritage.brussels/fr/buildings/23775")
    module.validate_url("https://monument.heritage.brussels/medias/monuments.fr.json")

    for url in (
        "http://monument.heritage.brussels/fr/buildings/23775",
        "https://example.com/fr/buildings/23775",
        # robots.txt disallows everything but /fr/, /nl/ and /medias/.
        "https://monument.heritage.brussels/jsonapi/node/building",
        "https://monument.heritage.brussels/index.php?section=buildings",
    ):
        try:
            module.validate_url(url)
        except module.ScrapeError:
            continue
        raise AssertionError(f"{url} must be refused")

    # robots.txt sets Crawl-delay: 2 and the scraper never goes below 1s.
    assert module.CRAWL_DELAY_SECONDS >= 2.0
    assert module.Fetcher(delay=0.01).delay >= module.MIN_CRAWL_DELAY_SECONDS


def test_non_ascii_source_urls_are_encoded(module) -> None:
    # A diaeresis in a street slug reached http.client raw and crashed the
    # place scrape (2026-10-20). Encoding is idempotent, so quoted URLs pass
    # through and only the path and query are touched.
    raw = module.place_url("42", "Schaerbeek", "Rue_Joséphine", "fr")
    encoded = module.encode_url(raw)
    assert "Joséphine" not in encoded
    encoded.encode("ascii")
    assert module.encode_url(encoded) == encoded
    assert module.encode_url("https://monument.heritage.brussels/fr/buildings/23775") == \
        "https://monument.heritage.brussels/fr/buildings/23775"


def test_image_download_gate(module) -> None:
    """Pictures must not be fetched without an explicit reuse basis."""
    # The inventory's conditional permission is an accepted basis, but naming it
    # brings obligations, so it is never the default.
    assert module.CONDITIONAL_BASIS in module.ALLOWED_RIGHTS_BASIS

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"

        for argv, label in (
            (["23775", "--download-images", "--out", str(out)], "missing basis"),
            (
                ["23775", "--download-images", "--rights-basis", "fair-use", "--out", str(out)],
                "unelaborated fair use",
            ),
        ):
            # The refusal is the point; keep its explanation out of the gate log.
            # --no-robots keeps this genuinely offline: reading the policy would
            # otherwise fetch robots.txt whenever local/ has no cached copy, which
            # is every fresh clone and every CI run.
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = module.main([*argv, "--no-robots"])
            assert code == 2, f"{label} must be refused before any request"
            assert not out.exists(), f"{label} must not write output"

        # No targets means no output, and above all no silent network work.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.main(["--out", str(out)]) == 2
        assert not out.exists()


def test_image_pass_gate(module) -> None:
    """--images-only must not reach the network without an explicit reuse basis."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        for argv, label in (
            (["--images-only", "--out", str(out)], "missing basis"),
            (
                ["--images-only", "--out", str(out), "--rights-basis", "fair-use"],
                "unelaborated fair use",
            ),
        ):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = module.main([*argv, "--no-robots"])
            assert code == 2, label
            assert not out.exists(), f"{label} must not write output"


class PictureFetcher:
    """Serves canned image bytes, so the picture pass never touches the network."""

    def __init__(self) -> None:
        self.requests = 0
        self.bytes = 0
        self.served: list[str] = []

    def get(self, url: str, max_bytes: int = 0) -> tuple[bytes, str]:
        self.requests += 1
        self.served.append(url)
        # A real JPEG header: the downloader inspects the bytes rather than the
        # Content-Type, because this source answers a miss with a page.
        body = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + url.encode("utf-8") + b"\xff\xd9"
        self.bytes += len(body)
        return body, "image/jpeg"


def test_image_pass_downloads_and_resumes(module) -> None:
    """Pictures come from stored records, and a resume re-fetches only what is missing.

    The pass exists so a 21-hour picture crawl never has to replay the 15-hour text
    crawl, and so one unloadable photo cannot cost a building its labels.
    """
    record = build(module, NAMED)
    images = record["images"]
    assert len(images) > 1, "fixture must carry several pictures for this check"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        (out / f"{record['building_id']}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Side files share the record suffix and must never be read as buildings.
        (out / "rubrics.fr.json").write_text("{}", encoding="utf-8")
        (out / "_failures.fr.json").write_text("[]", encoding="utf-8")
        image_dir = Path(tmp) / "inbox"
        args = module.build_parser().parse_args([
            "--images-only", "--out", str(out), "--image-dir", str(image_dir),
            "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
        ])

        fetcher = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(fetcher, args) == 0
        assert fetcher.requests == len(images)
        assert sorted(fetcher.served) == sorted(str(image["url"]) for image in images)

        building_dir = image_dir / str(record["building_id"])
        manifest = json.loads((building_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["rights_basis"] == module.CONDITIONAL_BASIS
        assert manifest["conditions_url"] == module.CONDITIONS_URL
        # The obligations travel with the pixels: compliance must stay checkable.
        assert any("SPRB-DMS" in duty for duty in manifest["obligations"]["online"])
        assert manifest["source_page"] == record["url"]
        assert [entry["filename"] for entry in manifest["images"]] == [
            image["filename"] for image in images
        ]
        assert [entry["url"] for entry in manifest["images"]] == [
            str(image["url"]) for image in images
        ]
        for entry in manifest["images"]:
            path = building_dir / entry["filename"]
            assert path.exists()
            assert entry["variant"] == "full"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]

        # Already complete: a resume must cost no request at all.
        again = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(again, args) == 0
        assert again.requests == 0

        # A truncated picture is not "already downloaded".
        victim = building_dir / manifest["images"][0]["filename"]
        victim.write_bytes(victim.read_bytes()[:1])
        repair = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(repair, args) == 0
        assert repair.requests == 1
        assert hashlib.sha256(victim.read_bytes()).hexdigest() == manifest["images"][0]["sha256"]

        # Neither is a same-size edit: the hash, not only the size, decides.
        data = bytearray(victim.read_bytes())
        data[len(data) // 2] ^= 0xFF
        victim.write_bytes(bytes(data))
        edited = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(edited, args) == 0
        assert edited.requests == 1
        assert hashlib.sha256(victim.read_bytes()).hexdigest() == manifest["images"][0]["sha256"]

        # A missing picture is re-fetched on its own, not the whole building.
        second = building_dir / manifest["images"][-1]["filename"]
        second.unlink()
        restore = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(restore, args) == 0
        assert restore.requests == 1
        assert restore.served == [str(images[-1]["url"])]

        # Switching to the 500px thumbnails re-fetches them: the stored original is
        # the wrong variant, not an up-to-date file.
        preview_args = module.build_parser().parse_args([
            "--images-only", "--out", str(out), "--image-dir", str(image_dir),
            "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
            "--image-size", "preview",
        ])
        previews = PictureFetcher()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(previews, preview_args) == 0
        assert previews.requests == len(images)
        assert previews.served == [str(image["preview_url"]) for image in images]
        got = json.loads((building_dir / "manifest.json").read_text(encoding="utf-8"))
        assert {entry["variant"] for entry in got["images"]} == {"preview"}


def test_image_pass_isolation(module) -> None:
    """A record's labels survive a picture that will not load.

    The picture pass is separate from the text crawl exactly so this holds: the
    notice file is read, never rewritten, and the failure is journalled per picture.
    """
    record = build(module, NAMED)
    images = record["images"]
    assert len(images) > 1, "fixture must carry several pictures for this check"

    class PartlyBroken(PictureFetcher):
        def get(self, url: str, max_bytes: int = 0) -> tuple[bytes, str]:
            if url == str(images[0]["url"]):
                self.requests += 1
                raise module.ScrapeError(f"{url} returned HTTP 500")
            return super().get(url, max_bytes)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        record_path = out / f"{record['building_id']}.fr.json"
        original = json.dumps(record, ensure_ascii=False, indent=2)
        record_path.write_text(original, encoding="utf-8")
        image_dir = Path(tmp) / "inbox"
        args = module.build_parser().parse_args([
            "--images-only", "--out", str(out), "--image-dir", str(image_dir),
            "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
        ])

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(PartlyBroken(), args) == 1

        journal = json.loads((out / "_image_failures.fr.json").read_text(encoding="utf-8"))
        assert [entry["url"] for entry in journal] == [str(images[0]["url"])]
        assert journal[0]["target"] == str(record["building_id"])
        # The other pictures still landed, and the notice file is untouched.
        building_dir = image_dir / str(record["building_id"])
        manifest = json.loads((building_dir / "manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["images"]) == len(images) - 1
        assert record_path.read_text(encoding="utf-8") == original


def counter(report: str, label: str) -> int:
    """Read a labelled number out of a plan or audit report.

    Asserting on the literal padding would break every time a label is reworded,
    and the number is the claim being tested, not the column width. The first
    integer after the label is the value, whatever suffix follows it.
    """
    for line in report.splitlines():
        if line.startswith(label):
            match = re.search(r"\d+", line[len(label):])
            if match:
                return int(match.group())
    raise AssertionError(f"{label!r} not found in report:\n{report}")


def test_image_plan_makes_no_request(module) -> None:
    """The plan has to describe a day-and-a-half crawl without starting one.

    A picture pass over the whole inventory costs ~37 h and ~25 GB, so the
    decision to start it should rest on counts measured from the stored corpus
    instead of an estimate made from whatever slice happened to be fetched first.
    """
    record = build(module, NAMED)
    images = record["images"]

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        (out / f"{record['building_id']}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        image_dir = Path(tmp) / "inbox"
        argv = [
            "--images-only", "--dry-run", "--out", str(out),
            "--image-dir", str(image_dir), "--rights-basis", module.CONDITIONAL_BASIS,
            "--no-robots", "--quiet",
        ]

        out_text = io.StringIO()
        with redirect_stdout(out_text), redirect_stderr(io.StringIO()):
            assert module.main(argv) == 0
        report = out_text.getvalue()
        assert counter(report, "to fetch:") == len(images), report
        assert "no requests made" in report, report
        assert not image_dir.exists(), "a plan must not create the picture tree"

        # After a real pass the same plan reports nothing left to do.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(PictureFetcher(), module.build_parser().parse_args([
                "--images-only", "--out", str(out), "--image-dir", str(image_dir),
                "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
            ])) == 0
        out_text = io.StringIO()
        with redirect_stdout(out_text), redirect_stderr(io.StringIO()):
            assert module.main(argv) == 0
        assert counter(out_text.getvalue(), "already stored:") == len(images)
        assert counter(out_text.getvalue(), "to fetch:") == 0


def test_download_refuses_what_is_not_a_picture(module) -> None:
    """A media request that answers with a page must not become a .JPG.

    This source answers a missing notice with HTTP 200 and an error page, so a
    status code proves nothing. The same reply on a media URL used to be written
    to disk, hashed into the manifest, and then confirmed by every later check as
    "stored and matching" — an archive that audits as clean while holding pages.
    """
    record = build(module, NAMED)
    images = record["images"]

    class ServesHtml(PictureFetcher):
        def get(self, url: str, max_bytes: int = 0) -> tuple[bytes, str]:
            self.requests += 1
            self.served.append(url)
            return b"<!DOCTYPE html><html><body>Not found</body></html>", "text/html"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        (out / f"{record['building_id']}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        image_dir = Path(tmp) / "inbox"
        args = module.build_parser().parse_args([
            "--images-only", "--out", str(out), "--image-dir", str(image_dir),
            "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
        ])
        fetcher = ServesHtml()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(fetcher, args) == 1

        # Every picture was attempted, none was stored, and each is journalled with
        # the reason, so the next run retries exactly them.
        assert fetcher.requests == len(images)
        building_dir = image_dir / str(record["building_id"])
        for image in images:
            assert not (building_dir / image["filename"]).exists(), image["filename"]
        assert not (building_dir / "manifest.json").exists(), "an empty manifest misstates"
        journal = json.loads((out / "_image_failures.fr.json").read_text(encoding="utf-8"))
        assert len(journal) == len(images)
        assert "did not return a picture" in journal[0]["error"]

    # Known formats pass, anything else does not.
    assert module.sniff_image_format(b"\xff\xd8\xff\xe0rest") == "jpeg"
    assert module.sniff_image_format(b"\x89PNG\r\n\x1a\n") == "png"
    assert module.sniff_image_format(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert module.sniff_image_format(b"<!DOCTYPE html>") is None
    assert module.sniff_image_format(b"") is None


def test_audit_catches_a_mislabelled_file(module) -> None:
    """An HTML file pinned by its own hash must still be reported as not a picture.

    Manifest agreement is not enough: a file can match its recorded hash and size
    exactly and still be the wrong kind of file, which is what a download written
    before the signature check leaves behind.
    """
    record = build(module, NAMED)
    images = record["images"]

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        (out / f"{record['building_id']}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        image_dir = Path(tmp) / "inbox"
        building_dir = image_dir / str(record["building_id"])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.run_image_pass(PictureFetcher(), module.build_parser().parse_args([
                "--images-only", "--out", str(out), "--image-dir", str(image_dir),
                "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
            ])) == 0

        # Replace a picture with a page and re-pin the manifest so hashes agree.
        victim = building_dir / images[0]["filename"]
        page = b"<!DOCTYPE html><html>error</html>"
        victim.write_bytes(page)
        manifest_path = building_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["images"][0]["bytes"] = len(page)
        manifest["images"][0]["sha256"] = hashlib.sha256(page).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        capture, err = io.StringIO(), io.StringIO()
        with redirect_stdout(capture), redirect_stderr(err):
            code = module.main([
                "--verify-images", "--out", str(out), "--image-dir", str(image_dir)
            ])
        report = capture.getvalue() + err.getvalue()
        assert code == 1
        assert counter(report, "not actually a picture:") == 1, report
        assert "stored bytes are not a picture" in report, report
        # The hash agrees, so this must not also be reported as missing.
        assert counter(report, "missing/altered despite a manifest:") == 0, report


def test_picture_pass_stops_when_the_source_goes_away(module) -> None:
    """An outage must cost one aborted run, not the rest of a 43-hour crawl.

    The text crawl has guarded against this since the first long run; the picture
    pass did not, so a source that stopped answering at hour 20 would have spent
    the remaining twenty hours writing a failure against every picture left. The
    limit is per picture rather than per notice, so it has to be far higher than
    the crawl's ten: a notice names ~2.9 pictures, and a single building with
    broken files is not an outage.
    """
    records = [build(module, NAMED), build(module, LEGACY)]
    total_pictures = sum(len(r["images"]) for r in records)
    assert total_pictures > 4, total_pictures

    class Dead(PictureFetcher):
        def get(self, url: str, max_bytes: int = 0) -> tuple[bytes, str]:
            self.requests += 1
            self.served.append(url)
            raise module.ScrapeError(f"{url} returned HTTP 503")

    def make_corpus(root: Path) -> Path:
        out = root / "out"
        out.mkdir()
        for record in records:
            (out / f"{record['building_id']}.fr.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return out

    def run(out: Path, image_dir: Path, limit: int, fetcher) -> tuple[int, str]:
        args = module.build_parser().parse_args([
            "--images-only", "--out", str(out), "--image-dir", str(image_dir),
            "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
            "--max-consecutive-image-failures", str(limit),
        ])
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = module.run_image_pass(fetcher, args)
        return code, err.getvalue()

    with tempfile.TemporaryDirectory() as tmp:
        out = make_corpus(Path(tmp))
        image_dir = Path(tmp) / "inbox"
        dead = Dead()
        code, err = run(out, image_dir, 2, dead)
        # Its own exit code, so the pipeline can tell an outage from a few bad files.
        assert code == module.IMAGE_EXIT_ABORTED == 3, code
        assert "aborting: 2 consecutive picture failure(s)" in err, err
        # It stopped after the limit instead of walking the whole corpus.
        assert dead.requests == 2, f"{dead.requests} requests for a limit of 2"
        journal = json.loads((out / "_image_failures.fr.json").read_text(encoding="utf-8"))
        assert len(journal) == 2
        assert all("503" in entry["error"] for entry in journal)

        # A picture that loads proves the source is answering, so a cluster of
        # broken files can never accumulate into an abort: fail, succeed, fail, fail.
        with tempfile.TemporaryDirectory() as tmp2:
            out2 = make_corpus(Path(tmp2))

            class Flaky(PictureFetcher):
                def get(self, url: str, max_bytes: int = 0) -> tuple[bytes, str]:
                    # Alternate: succeed, fail, succeed, fail...
                    if len(self.served) % 2 == 1:
                        self.requests += 1
                        self.served.append(url)
                        raise module.ScrapeError(f"{url} returned HTTP 503")
                    return super().get(url, max_bytes)

            flaky = Flaky()
            code, err = run(out2, Path(tmp2) / "inbox", 2, flaky)
            assert "aborting:" not in err, err
            assert code == 1, "failures are still reported, just not fatal to the run"
            assert code != module.IMAGE_EXIT_ABORTED, "a broken-file cluster is not an outage"
            assert "finished with problems" in err, err
            assert flaky.requests == total_pictures, "every picture was still attempted"

        # A limit of 0 disables the guard entirely.
        with tempfile.TemporaryDirectory() as tmp3:
            out3 = make_corpus(Path(tmp3))
            dead0 = Dead()
            code, err = run(out3, Path(tmp3) / "inbox", 0, dead0)
            assert "aborting:" not in err, err
            assert dead0.requests == total_pictures, dead0.requests


def test_manifest_writes_are_atomic(module) -> None:
    """A kill during a write must leave a whole file, not half of one.

    The picture pass has already been interrupted twice by hand, and a torn
    manifest reads as corruption rather than as work still to do — for 26,000
    manifests over 43 hours, that has to be impossible by construction rather than
    by luck. Checking only the happy path would not prove it, so the write is made
    to fail part-way and the previous file has to survive.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "manifest.json"
        target.write_text('{"old": true}\n', encoding="utf-8")
        module.write_json_atomic(target, {"new": True, "images": []})
        assert json.loads(target.read_text(encoding="utf-8"))["new"] is True
        # No debris, and no window in which a reader could see a partial file.
        assert list(Path(tmp).iterdir()) == [target], list(Path(tmp).iterdir())

        # Now fail the write part-way: the old file must still be the whole truth.
        real_write_text = Path.write_text

        def failing_write(self, data, *args, **kwargs):
            real_write_text(self, data[:5], *args, **kwargs)  # a torn prefix
            raise OSError("no space left on device")

        target.write_text('{"old": true}\n', encoding="utf-8")
        Path.write_text = failing_write
        try:
            try:
                module.write_json_atomic(target, {"new": True})
            except OSError:
                pass
            else:
                raise AssertionError("a failed write must propagate, not be swallowed")
        finally:
            Path.write_text = real_write_text

        assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
        assert list(Path(tmp).iterdir()) == [target], "a .part file survived the failure"

        record = build(module, UNNAMED)
        written = module.write_record(record, Path(tmp) / "nested" / "23775.fr.json")
        assert json.loads(written.read_text(encoding="utf-8"))["building_id"] == "23775"
        assert not list((Path(tmp) / "nested").glob("*.part")), "a .part file survived"


def test_verify_images_separates_missing_from_broken(module) -> None:
    """A 37-hour download needs an audit that can tell 'not yet' from 'wrong'.

    Run before the pictures exist, every notice is legitimately absent; that is not
    the same finding as a file that is on disk but altered, unrecorded or orphaned,
    and reporting the first as the second would make the audit useless exactly when
    it is first run.
    """
    record = build(module, NAMED)
    images = record["images"]

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        (out / f"{record['building_id']}.fr.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        image_dir = Path(tmp) / "inbox"
        argv = ["--verify-images", "--out", str(out), "--image-dir", str(image_dir)]
        building_dir = image_dir / str(record["building_id"])

        def audit() -> tuple[int, str]:
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = module.main(argv)
            # The report is on stdout and the [FINAL] line on stderr, by the
            # convention every long run in this repository follows.
            return code, out.getvalue() + err.getvalue()

        # Nothing downloaded: incomplete, but no defect to report.
        code, report = audit()
        assert code == 1
        assert counter(report, "not downloaded yet:") == len(images), report
        assert counter(report, "missing/altered despite a manifest:") == 0, report
        assert "orphan folders / files:               0 / 0" in report, report

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            module.run_image_pass(PictureFetcher(), module.build_parser().parse_args([
                "--images-only", "--out", str(out), "--image-dir", str(image_dir),
                "--rights-basis", module.CONDITIONAL_BASIS, "--progress-every", "0",
            ]))
        code, report = audit()
        assert code == 0, report
        assert counter(report, "stored and matching:") == len(images), report
        assert "0 defect(s)" in report, report

        # An altered file is a defect, not a download that has not happened.
        victim = building_dir / images[0]["filename"]
        original = victim.read_bytes()
        victim.write_bytes(original[:1])
        code, report = audit()
        assert code == 1
        assert f"{images[0]['filename']}: missing, altered or not recorded" in report, report
        assert counter(report, "missing/altered despite a manifest:") == 1, report
        assert counter(report, "not downloaded yet:") == 0, report
        # The headline count must not overstate: one picture is not matching.
        assert counter(report, "stored and matching:") == len(images) - 1, report
        victim.write_bytes(original)

        # A file nobody recorded, and a folder for a building nobody stored.
        (building_dir / "unexpected.JPG").write_bytes(b"x")
        orphan = image_dir / "999999"
        orphan.mkdir()
        (orphan / "stray.JPG").write_bytes(b"x")
        code, report = audit()
        assert code == 1
        assert "not recorded in its manifest" in report, report
        assert "999999/: 1 downloaded file(s) no stored notice names" in report, report
        (building_dir / "unexpected.JPG").unlink()
        (orphan / "stray.JPG").unlink()

        # A manifest entry the notice no longer names is stale, not current.
        manifest_path = building_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["images"].append({
            "filename": "gone.JPG", "url": "https://monument.heritage.brussels/medias/buildings/gone.JPG",
            "bytes": 1, "sha256": "0" * 64, "variant": "full",
        })
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        code, report = audit()
        assert code == 1
        assert "gone.JPG: recorded but no longer named by the notice" in report, report
        assert counter(report, "stale manifest entries:") == 1, report


def main() -> None:
    module = load_scraper()
    tests = [
        test_unnamed_notice,
        test_named_notice,
        test_dutch_notice,
        test_legacy_address_variant,
        test_image_credit_and_conditions,
        test_corner_building_addresses,
        test_numberless_entry,
        test_robots_policy,
        test_midrun_robots_recheck,
        test_consecutive_failure_guard,
        test_survey_report,
        test_progress_throughput,
        test_contributor_year_ranges,
        test_truncated_year_range,
        test_image_dimensions_parser,
        test_coordinate_resolution,
        test_offline_correction_matches_a_rescrape,
        test_place_notice_parser,
        test_place_targets_and_streets,
        test_place_scrape_runner,
        test_place_absence_is_a_finding_not_a_failure,
        test_place_stub_pages_are_counted_apart,
        test_picture_progress_reports_pace_and_eta,
        test_one_record_id_for_both_kinds,
        test_index_points_reader,
        test_audit_checks_the_stored_size,
        test_audit_requires_the_rights_record,
        test_final_status_line,
        test_soft_404_is_rejected,
        test_index_is_a_complete_enumeration,
        test_rubric_dedup,
        test_corpus_summary,
        test_caption_year_coverage,
        test_no_titled_section_is_silently_dropped,
        test_manifest_rewrite_preserves_the_derivation_record,
        test_two_pictures_sharing_a_basename_are_both_kept,
        test_coordinate_cross_check,
        test_credits_appear_only_in_captions,
        test_content_hash_contract,
        test_records_are_strict_json,
        test_target_parsing,
        test_url_and_delay_policy,
        test_image_download_gate,
        test_image_pass_gate,
        test_image_pass_downloads_and_resumes,
        test_image_pass_isolation,
        test_image_plan_makes_no_request,
        test_download_refuses_what_is_not_a_picture,
        test_audit_catches_a_mislabelled_file,
        test_picture_pass_stops_when_the_source_goes_away,
        test_picture_pass_rechecks_robots,
        test_manifest_writes_are_atomic,
        test_verify_images_separates_missing_from_broken,
        test_non_ascii_source_urls_are_encoded,
    ]
    for test in tests:
        test(module)
    print(f"Three Ages inventory scraper passed ({len(tests)} offline checks)")


if __name__ == "__main__":
    sys.exit(main())

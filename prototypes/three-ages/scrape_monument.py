#!/usr/bin/env python3
"""Scrape pictures, tags and descriptions from the Brussels architectural inventory.

The inventory (monument.heritage.brussels) publishes one server-rendered HTML
page per building at ``/<lang>/buildings/<id>``. There is no public JSON API:
``/jsonapi`` and ``?_format=json`` both fall back to the same HTML page. The
page carries every field we want, so this scraper parses the HTML with the
standard library only and adds no dependency.

What it collects
----------------
identity      name, street, house number, municipality, coordinates
details       every ``h4.label`` / ``.list-content`` pair, keyed by its raw
              label, so unknown or untranslated fields are never dropped
tags          interests (``Artistique``, ``Esthétique``, ...), typologies and
              styles, both as typed tags and as named fields
descriptions  the ``Description`` and ``Sources`` panels, as plain text (with
              glossary tooltips removed) and as source HTML
pictures      every gallery figure: full-resolution URL, preview URL, caption,
              pixel size and file name

Politeness and rights
---------------------
``robots.txt`` allows ``/fr/``, ``/nl/`` and ``/medias/`` with ``Crawl-delay: 2``,
and this scraper honours that delay, an explicit User-Agent and a response size
cap. Only ``monument.heritage.brussels`` is ever requested.

Two traps to know about before extending this file:

* the site answers a missing id with **HTTP 200** and an error page, so a status
  code proves nothing (``is_notice_page`` guards this);
* ``/fr/buildings/<id>/pdf`` also returns HTTP 200 and a real notice page, but it
  **ignores the id** and serves the same unrelated street notice for every
  building. The fiche's print rendering is the ``d-print-block`` markup inside the
  ordinary notice page, not a separate document.

The site's legal notice permits quoting or reusing the *texts* with explicit
mention of the source. Illustrations are more nuanced than "no reuse":
`/fr/conditions/` grants a **conditional, non-commercial** permission to
reproduce photographs taken by DPC/Ministry agents, subject to stated credit
formulae, and states that copyright in the depicted buildings and artworks must
be cleared separately. Because this repository is public, pictures are recorded
as references only. ``--download-images`` therefore refuses to run without an
explicit ``--rights-basis`` and writes exclusively under the gitignored
``local/`` directory, next to the obligations that basis implies.

Usage
-----
    python3 prototypes/three-ages/scrape_monument.py 23775
    python3 prototypes/three-ages/scrape_monument.py 23775 30991 --combined /tmp/all.json
    python3 prototypes/three-ages/scrape_monument.py 30991 --lang nl
    python3 prototypes/three-ages/scrape_monument.py --index
    python3 prototypes/three-ages/scrape_monument.py --from-index --limit 5
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import signal
import statistics
import sys
import time
import unicodedata
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]

SOURCE_HOST = "monument.heritage.brussels"
BASE_URL = f"https://{SOURCE_HOST}"
ALLOWED_HOSTS = frozenset({SOURCE_HOST})
LEGAL_URL = f"{BASE_URL}/fr/legal/"
CONDITIONS_URL = f"{BASE_URL}/fr/conditions/"
INDEX_URL = f"{BASE_URL}/medias/monuments.fr.json"

USER_AGENT = "final-work-three-ages/1.0 (inventory scraper; +https://monument.heritage.brussels/fr/legal/)"
SCRAPER_NAME = "scrape_monument.py"
# Bump when the emitted record shape changes, so stored records stay comparable.
SCHEMA_VERSION = 2
# Fields excluded from the content hash: run metadata, static source config, and
# the related-notices widget, which the server randomises on every request (so it
# is real data but not a stable property of the notice).
NON_CANONICAL_FIELDS = ("retrieved_at", "extraction", "source", "suggestions")

ROBOTS_URL = f"{BASE_URL}/robots.txt"
# Fallback used only when robots.txt cannot be read; it mirrors the live file.
DEFAULT_ALLOWED_PREFIXES = ("/fr/", "/nl/", "/files/", "/medias/")
DEFAULT_CRAWL_DELAY = 2.0
MIN_CRAWL_DELAY_SECONDS = 1.0
CRAWL_DELAY_SECONDS = 2.0  # default; refined from robots.txt at run time
MIN_CRAWL_DELAY_SECONDS = 1.0
MAX_RESPONSE_BYTES = 40 * 1024 * 1024
MAX_IMAGE_BYTES = 25 * 1024 * 1024
# Pictures never enter version control: the inventory's permission is conditional
# and non-commercial, so the pixels stay in the gitignored local/ tree.
DEFAULT_IMAGE_ROOT = REPO_ROOT / "local" / "monument-inbox"
# Galleries expose each picture twice: the original and the ~500px thumbnail the
# page itself displays. The original is the archive-safe default; the thumbnail
# costs roughly a sixth of the disk for review and model work.
IMAGE_VARIANTS = ("full", "preview")
# A response is only a picture if its own bytes say so. This source answers a
# missing notice with HTTP 200 and an error page, so a status code proves nothing;
# the same failure on a media request would write that page into a .JPG, hash it
# into the manifest, and let the audit report a corrupt file as "stored and
# matching". The signature is checked instead of the Content-Type header, because
# the bytes cannot disagree with themselves.
IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
)

# Mirrors the accepted reuse bases in prototypes/three-ages/ingest_local_images.py,
# plus the inventory's own conditional permission. Choosing
# "conditional-noncommercial" means accepting the obligations recorded in
# SOURCE_METADATA["rights"]["obligations"], which are written into the manifest.
CONDITIONAL_BASIS = "conditional-noncommercial"
# Persist the shared rubric store this often. The default is every record: the
# write is a few KB and a full run lasts hours, while records already reference
# these keys, so a missing store would leave them dangling.
RUBRIC_SAVE_EVERY = 1


def install_sigterm_handler() -> None:
    """Make SIGTERM unwind like an exception so finally blocks still run.

    ``timeout``, ``kill`` and shutdowns send SIGTERM, which by default terminates
    Python without running ``finally``; that would drop the rubric store and the
    failure journal for a run that had been going for hours.
    """

    def handler(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"received signal {signum}")

    try:
        signal.signal(signal.SIGTERM, handler)
    except (ValueError, AttributeError, OSError):
        pass  # not the main thread, or not a POSIX platform
ALLOWED_RIGHTS_BASIS = frozenset(
    {
        "explicit-licence",
        "cc0",
        "cc-by",
        "cc-by-sa",
        "public-domain",
        "written-permission",
        "personal-capture",
        CONDITIONAL_BASIS,
    }
)

SOURCE_METADATA = {
    "name": "Inventaire du patrimoine architectural (Brussels architectural inventory)",
    "publisher": "urban.brussels — Direction du Patrimoine culturel (DPC)",
    "host": SOURCE_HOST,
    "legal_url": LEGAL_URL,
    "conditions_url": CONDITIONS_URL,
    "robots": f"Crawl-delay: 2 ({BASE_URL}/robots.txt)",
    "rights": {
        "text": (
            "Quotation and reuse of information are permitted with explicit mention "
            "of the source."
        ),
        "photos": (
            "Photographs taken by DPC/Ministry agents may be reproduced in other "
            "non-commercial publications under the conditions stated at "
            f"{CONDITIONS_URL}; the permission covers the photographers' copyright "
            "only, and rights in the depicted buildings and artworks must be cleared "
            "separately with their holders."
        ),
        "reuse_basis": "conditional-noncommercial",
        "obligations": {
            "online": [
                "Display the credit « © SPRB-DMS » next to every image used.",
                "Add a link to monument.heritage.brussels to the site's links section.",
            ],
            "printed": [
                "Send one copy to Centre de Documentation de BDU, Service Public "
                "Régional de Bruxelles, rue du Progrès 80, boîte 1, 1030 Bruxelles.",
                "Print « © Monuments & Sites – Bruxelles » in the caption of every "
                "image used.",
                "Where the publication has a photo-credit section, give the full "
                "institution name « Direction des Monuments et des Sites – Service "
                "Public Régional de Bruxelles ».",
            ],
            "third_party": (
                "Clear rights in the depicted buildings and artworks independently."
            ),
        },
        "policy": (
            "This scraper records image references, captions and credit holders only. "
            "Pixels are downloaded only with an explicit --rights-basis, and only "
            "under the gitignored local/."
        ),
    },
}

# Label translations. Anything missing here still lands in "details" verbatim.
FIELD_LABELS = {
    "legal_status": ("statut juridique", "juridisch statuut"),
    "inventories": ("inventaire(s)", "inventaris(sen)"),
    "interests": (
        "ce bien présente l’(es) intérêt(s) suivant(s)",
        "ce bien présente l'(es) intérêt(s) suivant(s)",
        "dit (deze) goed(eren) bezit(ten) de volgende waarde(n)",
    ),
    "typologies": ("typologie(s)", "typologie(ën)"),
    "styles": ("styles", "stijlen"),
    "contributors": ("intervenant(s)", "ontwerper(s)"),
    "research": ("recherches et rédaction", "onderzoek en redactie"),
    "urban_id": ("id",),
}

SECTION_TITLES = {
    "description": ("description", "beschrijving"),
    "sources": ("sources", "bronnen"),
}

# Fallback container classes: <div class="object-info description"> / "... source".
PANEL_CONTAINER_CLASSES = {"description": "description", "sources": "source"}

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "oktober": 10,
}

DATE_RE = re.compile(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\b")
COORD_RE = re.compile(r"L\.marker\(\s*\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]")

# The notice's own map marker is normally the building's point — measured within 25 m
# of the publisher's index in 23,987 of 26,419 records — but for **2,406 notices the
# page serves one shared placeholder value, 233 km from Brussels**. Measured
# divergence is either under 126 m (long and multi-number buildings, whose entrance
# differs from their centroid) or about 233 km, so a kilometre separates the two
# cleanly: beyond it the notice is not stating this building's location at all.
COORDINATE_SUBSTITUTION_METRES = 1000.0


def metres_apart(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance in metres, exact enough at city scale.

    `summarise_corpus.py` carries the same formula because it is standalone too; both
    are used to compare the notice with the publisher's own index.
    """
    dx = (lon1 - lon2) * math.cos(math.radians((lat1 + lat2) / 2)) * 111320.0
    dy = (lat1 - lat2) * 110540.0
    return math.hypot(dx, dy)


def resolve_coordinates(
    notice: dict[str, float] | None, index_point: tuple[float, float] | None = None
) -> tuple[dict[str, float] | None, str | None, dict[str, float] | None]:
    """Where the building is, and where that answer came from.

    Takes the notice's *own* value rather than the page, so the same decision serves
    both a live scrape and an offline amendment of records already on disk — the
    correction is a pure function of (notice value, index point), which is what makes
    the two routes produce identical records.

    Returns (coordinates, source, notice_value). *source* is None when the notice's own
    marker was used, which is the ordinary case and why the field is only written on a
    substitution — the 24,013 records already stored stay valid as they are. It is
    "index" when the index supplied the point, either because the notice contradicted
    it or because the notice had none, and then the notice's own value is returned so
    the record can keep it rather than lose it.
    """
    if not index_point:
        return notice, None, None
    latitude, longitude = index_point
    from_index = {"latitude": latitude, "longitude": longitude}
    if notice is None:
        return from_index, "index", None
    if (
        metres_apart(notice["latitude"], notice["longitude"], latitude, longitude)
        > COORDINATE_SUBSTITUTION_METRES
    ):
        return from_index, "index", notice
    return notice, None, None


def coordinate_note(
    coordinates: dict[str, float], notice_value: dict[str, float] | None
) -> str:
    """Why the record's coordinates are not the notice's own, in words.

    Built in one place so a live scrape and an offline amendment write byte-identical
    notes — otherwise the two would register as drift against each other.
    """
    if notice_value is None:
        return (
            "The notice carried no map marker, so the publisher's index supplied "
            "the coordinates; coordinates_source records that."
        )
    kilometres = metres_apart(
        notice_value["latitude"], notice_value["longitude"],
        coordinates["latitude"], coordinates["longitude"],
    ) / 1000
    return (
        "The notice's map marker "
        f"({notice_value['latitude']:.6f}, {notice_value['longitude']:.6f}) "
        f"is {kilometres:.0f} km from where the publisher's index places this "
        "building, so the index's point is used; the notice's own value is kept "
        "verbatim in coordinates_notice."
    )
STREET_HREF_RE = re.compile(r"^/(?:fr|nl)/[^/]+/[^/]+/\d+(?:/\d+)?$")
BUILDING_HREF_RE = re.compile(r"^/(?:fr|nl)/buildings/(\d+)$")
# Legacy notices link their street as a flat root-relative file, e.g.
# fr.Bruxelles_Extension_Est.Rue_d_Arlon.html (it still resolves via a 301).
LEGACY_STREET_HREF_RE = re.compile(r"^(?:[a-z]{2}\.)?[\w-]+(?:\.[\w-]+)+\.html?$", re.I)
# An address heading always ends in its house number; a building title does not.
HOUSE_NUMBER_RE = re.compile(r"^\s*\d")
# Captions carry the copyright holder for the photos that state one, e.g.
# "Rue du Bourdon 351, ULB © urban.brussels, 2022".
# Contributor year ranges arrive split across two art-field spans, e.g.
# <span>1850</span><span>-1875</span>, so a leading dash is part of the year.
YEAR_FIELD_RE = re.compile(r"-?\d{3,4}")
# A split range's second span can itself be truncated by the source: building
# 31373 emits <span>1875</span><span>-19</span>. Two digits are too few to stand
# as a year, so the bare form misses YEAR_FIELD_RE, but the fragment still
# belongs to the date and not to the role the contributor held.
YEAR_CONTINUATION_RE = re.compile(r"-\d{1,4}")
CREDIT_RE = re.compile(r"(?:\(c\)|©)\s*([^,;()]+)")
# Credit holder used on photos taken by urban.brussels / DPC agents.
DPC_CREDIT_HOLDERS = ("urban.brussels", "sprb-dms", "monuments & sites", "dms")

VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
     "param", "source", "track", "wbr"}
)
BLOCK_TAGS = frozenset(
    {"address", "blockquote", "div", "dl", "dt", "dd", "figcaption", "figure",
     "h1", "h2", "h3", "h4", "h5", "h6", "li", "ol", "p", "section", "table",
     "tbody", "td", "tfoot", "th", "thead", "tr", "ul"}
)

VALID_LANGS = ("fr", "nl")


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #
def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def rubric_key(value: str) -> str:
    """Stable ASCII slug for an interest name, usable as a JSON key.

    Accents are folded rather than dropped so ``Esthétique`` becomes
    ``esthetique`` instead of ``esth-tique``. The store also keeps the original
    name, so folding never loses the label itself.
    """
    folded = unicodedata.normalize("NFKD", value)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")


class RubricStore:
    """Shared pool for the interest rubric text, which repeats on every notice.

    The rubric is identical for a given interest across notices (verified by hash),
    so inlining it costs ~20% of every record. This store holds each rubric once so
    records can reference it instead. The store path is only written by ``save``, so
    tests can exercise the behaviour without touching the filesystem.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.entries: dict[str, dict[str, str]] = {}
        self.redefined: list[str] = []
        if path is not None and path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.entries = payload.get("rubrics", {})

    def record(self, value: str, criteria: str) -> str:
        """Add a rubric and return its reference key."""
        key = rubric_key(value)
        digest = sha256_hex(criteria.encode("utf-8"))
        existing = self.entries.get(key)
        if existing and existing.get("sha256") != digest:
            # The same interest name carrying different prose means the source
            # changed its rubric; surface it rather than silently overwriting.
            self.redefined.append(key)
        self.entries[key] = {"value": value, "criteria": criteria, "sha256": digest}
        return key

    def save(self) -> Path | None:
        if self.path is None:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "conditions": (
                "Interest rubric text is generic catalogue prose that repeats verbatim "
                "across notices; records reference it by key and pin its sha256."
            ),
            "rubrics": dict(sorted(self.entries.items())),
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.path


def content_hash(record: dict[str, object]) -> str:
    """Hash the canonical notice content, so a re-scrape can detect drift.

    ``retrieved_at`` changes every run, ``source`` is static configuration, and
    ``suggestions`` is randomised by the server, so all three are excluded;
    everything else is hashed in canonical form.
    """
    core = {
        key: value for key, value in record.items() if key not in NON_CANONICAL_FIELDS
    }
    # Hash the interest rubric by digest rather than by shape, so inline text and a
    # store reference produce the same hash and toggling --dedupe-rubrics does not
    # look like drift. A changed rubric still moves the hash, via its sha256.
    interests = core.get("interests")
    if isinstance(interests, list):
        core["interests"] = [
            {"value": item.get("value"), "criteria_sha256": item.get("criteria_sha256")}
            for item in interests
            if isinstance(item, dict)
        ]
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_hex(blob.encode("utf-8"))


class ScrapeError(RuntimeError):
    """Raised for anything the operator needs to fix."""


class NotANoticePage(ScrapeError):
    """The site answered with its error page instead of a notice.

    A distinct type because it is not a fetch failure: this host answers a missing
    id with HTTP 200 plus an error page, so "no notice exists here" and "the request
    did not work" are different facts. The place crawl depends on that difference —
    only about 2,241 of the 3,564 streets it visits are published as notices — and
    counting the rest as failures would drown any real failure in expected absences.
    """


class RobotsPolicy:
    """Allowed paths and crawl delay, parsed from robots.txt or defaulted.

    ``rules`` holds ``(allow, regex)`` pairs ordered most-specific-first, so the
    first match wins exactly as crawlers are expected to resolve them.
    """

    def __init__(self, rules=(), crawl_delay=DEFAULT_CRAWL_DELAY,
                 allowed_prefixes=DEFAULT_ALLOWED_PREFIXES) -> None:
        self.rules = list(rules)
        self.crawl_delay = crawl_delay
        self.allowed_prefixes = tuple(allowed_prefixes)

    def allows(self, path: str) -> bool:
        # robots.txt itself is always retrievable, whatever the rules say.
        if path == "/robots.txt":
            return True
        for allow, regex in self.rules:
            if regex.match(path):
                return allow
        if self.rules:
            return True  # no rule matched, so the path is not disallowed
        return path.startswith(self.allowed_prefixes)


def robots_pattern_regex(pattern: str) -> re.Pattern[str]:
    body = ""
    for char in pattern:
        if char == "*":
            body += ".*"
        elif char == "$":
            body += "$"
        else:
            body += re.escape(char)
    return re.compile("^" + body)


def parse_robots(text: str) -> RobotsPolicy:
    """Parse the ``User-agent: *`` group of a robots.txt document."""
    collected: list[tuple[bool, str]] = []
    delay: float | None = None
    agents: list[str] = []
    group_started = False
    applies = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            # A new User-agent line after directives starts the next group.
            if group_started:
                agents = []
                group_started = False
            agents.append(value.lower())
            applies = any(agent == "*" for agent in agents)
            continue

        if not applies:
            continue
        group_started = True
        if field == "disallow" and value:
            collected.append((False, value))
        elif field == "allow" and value:
            collected.append((True, value))
        elif field == "crawl-delay":
            try:
                delay = float(value)
            except ValueError:
                continue

    ordered = sorted(
        ((allow, robots_pattern_regex(pattern), len(pattern))
         for allow, pattern in collected),
        key=lambda item: -item[2],
    )
    policy = RobotsPolicy([(allow, regex) for allow, regex, _ in ordered])
    if delay is not None:
        policy.crawl_delay = max(delay, MIN_CRAWL_DELAY_SECONDS)
    return policy


def validate_url(url: str, policy: RobotsPolicy | None = None) -> None:
    active = policy or RobotsPolicy()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ScrapeError(f"refusing unexpected URL: {url}")
    if not active.allows(parsed.path):
        raise ScrapeError(
            f"robots.txt on {SOURCE_HOST} disallows {parsed.path}: {url}"
        )


class Fetcher:
    """Throttled, size-capped HTTP client for a single allowed host."""

    def __init__(self, delay: float = CRAWL_DELAY_SECONDS, timeout: float = 60.0,
                 retries: int = 3, policy: RobotsPolicy | None = None) -> None:
        self.delay = max(delay, MIN_CRAWL_DELAY_SECONDS) if delay else CRAWL_DELAY_SECONDS
        self.timeout = timeout
        self.retries = retries
        self.policy = policy or RobotsPolicy()
        self.requests = 0
        self.bytes = 0
        self._last_request = 0.0

    def _throttle(self) -> None:
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, max_bytes: int = MAX_RESPONSE_BYTES) -> tuple[bytes, str]:
        validate_url(url, self.policy)
        url = encode_url(url)
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._throttle()
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html,application/json,image/*;q=0.8,*/*;q=0.5",
                        "Accept-Language": "fr, nl;q=0.9, en;q=0.5",
                    },
                )
                with urlopen(request, timeout=self.timeout) as response:
                    self._last_request = time.monotonic()
                    body = response.read(max_bytes + 1)
                    content_type = response.headers.get("Content-Type", "")
                self.requests += 1
                self.bytes += len(body)
                if len(body) > max_bytes:
                    raise ScrapeError(f"{url} exceeds the {max_bytes:,} byte cap")
                return body, content_type
            except HTTPError as error:
                last_error = error
                if error.code not in (429, 500, 502, 503, 504):
                    raise ScrapeError(f"{url} returned HTTP {error.code}") from error
                # Honour the server's own pacing hint when it sends one.
                retry_after = error.headers.get("Retry-After") if error.headers else None
                if retry_after and retry_after.strip().isdigit():
                    time.sleep(min(float(retry_after), 60.0))
                else:
                    time.sleep(min(2 ** attempt * self.delay, 30.0))
            except (URLError, TimeoutError) as error:
                last_error = error
                time.sleep(min(2 ** attempt * self.delay, 30.0))
        raise ScrapeError(f"{url} failed after {self.retries} attempts: {last_error}")

    def get_text(self, url: str) -> str:
        body, content_type = self.get(url)
        charset = "utf-8"
        match = re.search(r"charset=([\w-]+)", content_type or "")
        if match:
            charset = match.group(1)
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            return body.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# minimal tolerant DOM
# --------------------------------------------------------------------------- #
class Element:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict[str, str], parent: Element | None = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[Element | str] = []
        self.parent = parent

    @property
    def classes(self) -> frozenset[str]:
        return frozenset(filter(None, (self.attrs.get("class") or "").split()))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.tag} {dict(self.attrs)}>"


class DomBuilder(HTMLParser):
    """Builds a tree, tolerating the inventory's unclosed <p> and <div> tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#document", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = Element(tag, {k: (v or "") for k, v in attrs}, self._stack[-1])
        self._stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self._stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = Element(tag, {k: (v or "") for k, v in attrs}, self._stack[-1])
        self._stack[-1].children.append(element)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def parse_dom(html_text: str) -> Element:
    builder = DomBuilder()
    builder.feed(html_text)
    builder.close()
    return builder.root


def iter_elements(node: Element):
    for child in node.children:
        if isinstance(child, Element):
            yield child
            yield from iter_elements(child)


def matches(element: Element, tag: str | None, classes, attrs) -> bool:
    if tag and element.tag != tag:
        return False
    if classes:
        required = (classes,) if isinstance(classes, str) else classes
        if not all(name in element.classes for name in required):
            return False
    if attrs and any(element.attrs.get(key) != value for key, value in attrs.items()):
        return False
    return True


def find_all(node: Element, tag: str | None = None, classes=None, attrs=None):
    for element in iter_elements(node):
        if matches(element, tag, classes, attrs):
            yield element


def find(node: Element | None, tag: str | None = None, classes=None, attrs=None):
    if node is None:
        return None
    return next(find_all(node, tag, classes, attrs), None)


def first_child(node: Element | None, tag: str | None = None, classes=None):
    if node is None:
        return None
    for child in node.children:
        if isinstance(child, Element) and matches(child, tag, classes, None):
            return child
    return None


def next_element_sibling(element: Element) -> Element | None:
    parent = element.parent
    if parent is None:
        return None
    seen = False
    for child in parent.children:
        if child is element:
            seen = True
            continue
        if seen and isinstance(child, Element):
            return child
    return None


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #
def collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()


def is_glossary_tooltip(element: Element) -> bool:
    """True for the <span> holding a glossary definition inside <a class='info'>."""
    parent = element.parent
    return (
        element.tag == "span"
        and parent is not None
        and parent.tag == "a"
        and "info" in parent.classes
    )


def plain_text(node: Element, skip=is_glossary_tooltip) -> str:
    """Whitespace-collapsed text of a subtree."""
    parts: list[str] = []

    def walk(current: Element) -> None:
        for child in current.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag in ("script", "style"):
                continue
            elif skip and skip(child):
                continue
            else:
                walk(child)

    walk(node)
    return collapse("".join(parts))


def direct_text(element: Element) -> str:
    """Text held directly by an element, ignoring nested elements.

    Interest anchors are ``<a class='info'>Artistique<span>criteria</span></a>``,
    so the tag is the anchor's own text.
    """
    return collapse("".join(c for c in element.children if isinstance(c, str)))


def block_text(node: Element, skip=is_glossary_tooltip) -> str:
    """Text of a subtree with block breaks preserved as newlines."""
    parts: list[str] = []

    def walk(current: Element) -> None:
        for child in current.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag in ("script", "style"):
                continue
            elif skip and skip(child):
                continue
            elif child.tag == "br":
                parts.append("\n")
            elif child.tag in BLOCK_TAGS:
                parts.append("\n")
                walk(child)
                parts.append("\n")
            else:
                walk(child)

    walk(node)

    lines = []
    for line in "".join(parts).split("\n"):
        cleaned = re.sub(r"[ \t]+", " ", line.replace("\u00a0", " ")).strip()
        if not cleaned and lines and not lines[-1]:
            continue
        lines.append(cleaned)
    return "\n".join(lines).strip()


def serialize(node: Element) -> str:
    """Render a subtree back to HTML for provenance."""
    if not isinstance(node, Element):
        return escape(str(node))

    def render(element: Element) -> str:
        attrs = "".join(
            f' {key}="{escape(value, quote=True)}"' for key, value in element.attrs.items()
        )
        if element.tag in VOID_TAGS:
            return f"<{element.tag}{attrs}>"
        inner = "".join(
            render(child) if isinstance(child, Element) else escape(child)
            for child in element.children
        )
        return f"<{element.tag}{attrs}>{inner}</{element.tag}>"

    return render(node)


# --------------------------------------------------------------------------- #
# field extraction
# --------------------------------------------------------------------------- #
def normalise_label(label: str) -> str:
    return collapse(label).lower().rstrip(":")


def label_key(label: str) -> str | None:
    normalised = normalise_label(label)
    for key, candidates in FIELD_LABELS.items():
        if normalised in candidates:
            return key
    return None


def extract_detail_blocks(root: Element) -> dict[str, Element]:
    """Map every ``h4.label`` to its ``.list-content`` node."""
    blocks: dict[str, Element] = {}
    for container in find_all(root, tag="div", classes="single-list"):
        heading = find(container, tag="h4", classes="label")
        if heading is None:
            continue
        label = plain_text(heading)
        if not label:
            continue
        content = find(container, tag="div", classes="list-content")
        if content is None:
            content = next_element_sibling(heading)
        if content is not None and label not in blocks:
            blocks[label] = content
    return blocks


def extract_panels(root: Element) -> dict[str, Element]:
    """Map section titles (Description, Sources, ...) to their wysiwyg node."""
    panels: dict[str, Element] = {}
    for heading in find_all(root, tag="h3"):
        title = normalise_label(plain_text(heading))
        if not title:
            continue
        node = next_element_sibling(heading)
        hops = 0
        while node is not None and "wysiwyg" not in node.classes and hops < 3:
            node = next_element_sibling(node)
            hops += 1
        if node is None or "wysiwyg" not in node.classes:
            continue
        panels.setdefault(title, node)
    return panels


def panel_for(panels: dict[str, Element], key: str, root: Element) -> Element | None:
    for title in SECTION_TITLES[key]:
        if title in panels:
            return panels[title]
    # Fallback: the container class (object-info description / object-info source).
    container = PANEL_CONTAINER_CLASSES.get(key, key)
    return find(root, tag="div", classes=("object-info", container))


def extract_addresses(heading: Element) -> list[dict[str, str | None]]:
    """Split a heading into one group per street.

    Corner buildings list several street+number pairs separated by ``<br>``, each
    with its own street link (this is also why the site's index carries multiple
    features for one building). Collapsing them into a single ``house_number``
    string would bury the second street inside the first one's numbers.
    """
    groups: list[dict[str, str | None]] = []
    current: dict[str, str | None] | None = None

    def add_text(text: str) -> None:
        nonlocal current
        if current is None:
            current = {"street": None, "house_numbers": text, "url": None}
            groups.append(current)
        else:
            current["house_numbers"] = f"{current['house_numbers']} {text}".strip()

    for child in heading.children:
        if isinstance(child, str):
            text = collapse(child)
            if text:
                add_text(text)
        elif child.tag == "br":
            if current is not None and current["house_numbers"]:
                current = None
        elif child.tag == "a":
            href = child.attrs.get("href", "")
            current = {
                "street": plain_text(child),
                "house_numbers": "",
                "url": urljoin(BASE_URL, href) if href else None,
            }
            groups.append(current)
        else:
            nested = collapse(plain_text(child))
            if nested:
                add_text(nested)

    return [
        {
            "street": group["street"],
            "house_numbers": group["house_numbers"] or None,
            "url": group["url"],
        }
        for group in groups
        if group["street"] or group["house_numbers"]
    ]


def is_address_heading(heading: Element) -> bool:
    """True when a heading is the street + house number, not the building name.

    Four notice shapes exist. An unnamed building puts the address in ``h1``; a
    titled building puts the name in ``h1`` and the address in ``h3``; legacy
    notices link the street as a flat ``*.html`` file; and numberless entries such
    as bridges or public spaces link a street with no house number at all. So a
    heading is an address when its link is street-shaped and is either followed by
    a house number, or followed by nothing.
    """
    groups = extract_addresses(heading)
    if not groups or not groups[0]["street"]:
        return False
    anchor = find(heading, tag="a")
    if anchor is None:
        return False
    href = anchor.attrs.get("href", "")
    canonical = bool(STREET_HREF_RE.match(href) or LEGACY_STREET_HREF_RE.match(href))

    numbers = str(groups[0]["house_numbers"] or "").strip()
    if numbers:
        # A number confirms the address even when the link is only root-relative.
        return bool(HOUSE_NUMBER_RE.match(numbers)) and (canonical or href.startswith("/"))
    # With no number, only a canonical street link is convincing: a title that
    # merely links somewhere on the site must not be read as an address.
    return canonical


def first_address_heading(scope: Element) -> Element | None:
    for candidate in find_all(scope, tag="h1"):
        if is_address_heading(candidate):
            return candidate
    for candidate in find_all(scope, tag="h3"):
        if is_address_heading(candidate):
            return candidate
    return None


def extract_identity(
    root: Element,
) -> tuple[dict[str, str | None], list[dict[str, str | None]]]:
    wrapper = find(root, tag="div", classes="main-info-wrapper")
    name = None
    heading: Element | None = None

    if wrapper is not None:
        h1 = first_child(wrapper, tag="h1")
        if h1 is not None and is_address_heading(h1):
            heading = h1
        else:
            name = plain_text(h1) if h1 is not None else None
            heading = first_address_heading(wrapper)

    if heading is None:
        heading = first_address_heading(root)

    addresses = extract_addresses(heading) if heading is not None else []
    primary = next((group for group in addresses if group["street"]), None)
    if primary is None and addresses:
        primary = addresses[0]

    identity = {
        "name": name,
        "street": primary["street"] if primary else None,
        "house_number": ((primary["house_numbers"] or None) if primary else None),
        "address_url": primary["url"] if primary else None,
    }
    return identity, addresses


def extract_city(root: Element) -> dict[str, str | None]:
    wrapper = find(root, tag="div", classes="location-wrapper")
    anchor = find(wrapper, tag="a") if wrapper is not None else None
    if anchor is None:
        return {"name": None, "id": None}
    href = anchor.attrs.get("href", "")
    match = re.search(r"/city/(\d+)", href)
    return {"name": plain_text(anchor), "id": match.group(1) if match else None}


def extract_coordinates(html_text: str) -> dict[str, float] | None:
    match = COORD_RE.search(html_text)
    if not match:
        return None
    return {"latitude": float(match.group(1)), "longitude": float(match.group(2))}


def extract_interests(node: Element) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in find_all(node, tag="a"):
        value = direct_text(anchor)
        if not value or value in seen:
            continue
        criteria = " ".join(
            collapse(plain_text(span))
            for span in find_all(anchor, tag="span")
            if "info" not in span.classes
        )
        seen.add(value)
        results.append({"value": value, "criteria": criteria or None})
    if not results:
        # No anchors: fall back to the list items / lines of the block.
        for line in block_text(node).split("\n"):
            if line and line not in seen:
                seen.add(line)
                results.append({"value": line, "criteria": None})
    return results


def extract_lines(node: Element) -> list[str]:
    return [line for line in block_text(node).split("\n") if line]


def extract_inventories(node: Element) -> list[dict[str, str | None]]:
    items = []
    for item in find_all(node, tag="li"):
        anchor = find(item, tag="a")
        name = plain_text(anchor) if anchor is not None else None
        if not name:
            continue
        href = anchor.attrs.get("href", "")
        full = plain_text(item)
        period = full[len(name):].strip(" ()") if full.startswith(name) else full
        items.append(
            {
                "name": name,
                "period": period or None,
                "url": urljoin(BASE_URL, href) if href else None,
            }
        )
    return items


def merge_year_fields(tokens: list[str]) -> list[str]:
    """Rejoin a split year range: ['1850', '-1875'] -> ['1850-1875'].

    The site emits ranges as two spans, so a bare leading dash is a continuation,
    not a value. A dash with nothing to continue is dropped as a stray separator.
    """
    merged: list[str] = []
    for token in tokens:
        if token.startswith("-"):
            if merged:
                merged[-1] = f"{merged[-1]}{token}"
            else:
                merged.append(token.lstrip("-"))
        else:
            merged.append(token)
    return merged


def extract_contributors(node: Element) -> list[dict[str, list[str] | str | None]]:
    entries: list[dict[str, list[str] | str | None]] = []
    current: dict[str, list[str] | str | None] | None = None
    for element in iter_elements(node):
        if element.tag == "a":
            current = {
                "name": plain_text(element),
                "url": urljoin(BASE_URL, element.attrs.get("href", "")) or None,
                "roles": [],
                "years": [],
            }
            entries.append(current)
        elif element.tag == "span" and "art-field" in element.classes and current is not None:
            value = plain_text(element)
            if not value:
                continue
            if YEAR_FIELD_RE.fullmatch(value):
                current["years"].append(value)
            elif YEAR_CONTINUATION_RE.fullmatch(value) and current["years"]:
                # A continuation only continues something: without a year already
                # read, a bare dash fragment is still not a year and stays visible
                # in the roles for the corpus check to flag.
                current["years"].append(value)
            else:
                current["roles"].append(value)
    for entry in entries:
        entry["years"] = merge_year_fields(entry["years"])  # type: ignore[arg-type]
    return entries


def extract_legal_status(node: Element) -> dict[str, str | None]:
    text = block_text(node).replace("\n", " ")
    text = collapse(text)
    date_iso = None
    match = DATE_RE.search(text)
    if match:
        day, month_name, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month:
            date_iso = f"{int(year):04d}-{month:02d}-{int(day):02d}"
    return {"text": text or None, "date": date_iso}


def extract_credit_holders(caption: str) -> list[str]:
    """Copyright holders named in a caption, e.g. "... © urban.brussels, 2022"."""
    holders = []
    for match in CREDIT_RE.finditer(caption or ""):
        holder = collapse(match.group(1)).strip(" .")
        if holder and holder not in holders:
            holders.append(holder)
    return holders


def rights_hint_for(holders: list[str]) -> str | None:
    """A hint only: an absent credit states nothing, so eligibility stays unknown.

    ``/fr/conditions/`` covers photographs taken by DPC/Ministry agents, which the
    notice credits as ``© urban.brussels``. That is evidence of the holder, not a
    determination of reuse eligibility, so the value is labelled a hint and every
    consumer still has to check the conditions page.

    The phrase the conditions page names as the per-photo marker, "© Reproduction
    autorisée sous certaines conditions", was not found anywhere in sampled notice
    HTML, including the print block: a credit in ``figcaption``/``alt`` is the only
    per-photo rights signal the notices carry. So a positive hint means "a
    DPC-related holder is named", never "this photo is cleared".
    """
    if not holders:
        return None
    lowered = [holder.lower() for holder in holders]
    if any(any(known in holder for known in DPC_CREDIT_HOLDERS) for holder in lowered):
        return "conditional-noncommercial"
    return "third-party-or-unknown"


def extract_images(root: Element, page_url: str) -> list[dict[str, object]]:
    gallery = find(root, tag="div", classes="my-gallery")
    if gallery is None:
        return []
    images: list[dict[str, object]] = []
    seen: set[str] = set()
    for figure in find_all(gallery, tag="figure"):
        if figure.attrs.get("itemprop") != "associatedMedia":
            continue
        anchor = None
        for candidate in find_all(figure, tag="a"):
            if candidate.attrs.get("itemprop") == "contentUrl":
                anchor = candidate
                break
        url = anchor.attrs.get("href") if anchor is not None else None
        if not url or url in seen:
            continue
        seen.add(url)

        image = find(figure, tag="img")
        caption_node = find(figure, tag="figcaption")
        preview = image.attrs.get("src") if image is not None else None
        caption = plain_text(caption_node) if caption_node is not None else (
            collapse(image.attrs.get("alt", "")) if image is not None else ""
        )

        width = height = None
        size = anchor.attrs.get("data-size", "") if anchor is not None else ""
        if re.fullmatch(r"\d+x\d+", size or ""):
            width, height = (int(part) for part in size.split("x"))

        images.append(
            {
                "url": urljoin(page_url, url),
                "preview_url": urljoin(page_url, preview) if preview else None,
                "caption": caption or None,
                "credit_holders": extract_credit_holders(caption),
                "rights_hint": rights_hint_for(extract_credit_holders(caption)),
                "width": width,
                "height": height,
                "filename": Path(urlparse(url).path).name,
            }
        )

    for index, image in enumerate(images):
        image["is_main"] = index == 0
    return images


def extract_related(root: Element, page_url: str) -> list[dict[str, object]]:
    """Parse the "Quelques biens du même auteur" style suggestion strips."""
    suggestions = None
    for element in find_all(root, tag="div"):
        if element.attrs.get("id") == "suggestions":
            suggestions = element
            break
    if suggestions is None:
        return []

    groups: list[dict[str, object]] = []
    for heading in find_all(suggestions, tag="h3"):
        title = plain_text(heading)
        if not title:
            continue
        node = next_element_sibling(heading)
        hops = 0
        while node is not None and "mini-thumbnail-wrapper" not in node.classes and hops < 3:
            node = next_element_sibling(node)
            hops += 1
        if node is None or "mini-thumbnail-wrapper" not in node.classes:
            continue

        entries = []
        for anchor in find_all(node, tag="a"):
            href = anchor.attrs.get("href", "")
            match = BUILDING_HREF_RE.match(href)
            if not match:
                continue
            image = find(anchor, tag="img")
            entries.append(
                {
                    "building_id": match.group(1),
                    "url": urljoin(page_url, href),
                    "preview_url": urljoin(page_url, image.attrs.get("src", ""))
                    if image is not None and image.attrs.get("src")
                    else None,
                    "label": collapse(image.attrs.get("alt", "")) if image is not None else None,
                }
            )
        if entries:
            groups.append({"title": title, "items": entries})
    return groups


def extract_list_items(node: Element, page_url: str) -> list[dict[str, object]]:
    """Parse tree / related-building strips inside a wysiwyg panel."""
    items = []
    for block in find_all(node, tag="div", classes="arborescence_results"):
        anchor = find(block, tag="a")
        bold = find(block, tag="b")
        address = find(block, tag="div", classes="address")
        image = find(block, tag="img")
        href = anchor.attrs.get("href", "") if anchor is not None else ""
        items.append(
            {
                "label": plain_text(bold) if bold is not None else plain_text(anchor),
                "url": urljoin(page_url, href) if href else None,
                "address": extract_lines(address) if address is not None else [],
                "preview_url": urljoin(page_url, image.attrs.get("src", ""))
                if image is not None and image.attrs.get("src")
                else None,
            }
        )
    return items


# --------------------------------------------------------------------------- #
# record assembly
# --------------------------------------------------------------------------- #
def is_notice_page(root: Element) -> bool:
    """True only for a real notice page.

    The site answers a missing id with **HTTP 200** and an error page, so a status
    code cannot be trusted. Without this guard a bad id would be written as an
    empty record whose notes even claim the notice has no Description section,
    which is worse than failing.
    """
    return (
        find(root, tag="div", classes="main-info-wrapper") is not None
        or find(root, tag="div", classes="object-info") is not None
    )


def panel_text(node: Element | None, skip=None) -> dict[str, str] | None:
    """A panel as both text and source HTML, or None when it holds nothing."""
    if node is None:
        return None
    text = block_text(node, skip) if skip is not None else block_text(node)
    return {"text": text, "html": serialize(node)} if text else None


def is_view_more(element: Element) -> bool:
    """The "see the properties of this place" link the place pages carry.

    It is navigation, not prose, and it sits inside the same `.wysiwyg` as the street
    introduction — so leaving it in would make every place description begin with a UI
    label. Its target is `/index.php?street=…&section=buildings`, a route robots.txt
    disallows, so the place record keeps the link as a reference and never follows it.
    """
    return "view-more" in element.classes


def place_skip(element: Element) -> bool:
    return is_glossary_tooltip(element) or is_view_more(element)


def amend_coordinates(args) -> int:
    """Apply the index correction to records already on disk, without a crawl.

    The correction is a pure function of the stored record and the local index, so a
    re-scrape would produce the same three fields — `test_offline_correction_matches_a_rescrape`
    demonstrates that rather than asserting it. Doing it here costs no requests, and it
    avoids the delete-then-refetch that `--fail-on-change` would otherwise force, which
    would silently absorb any upstream rewrite for exactly the records being rewritten.
    Drift detection is a whole-corpus question, not one a 2,406-record subset can answer.
    """
    points = index_points_from(args.index_file)
    if not points:
        print(f"no index points at {args.index_file}: nothing to correct", file=sys.stderr)
        return 2
    amended: list[tuple[str, float]] = []
    already = unchanged = failed = 0
    for path in stored_record_paths(args.out, args.lang):
        record, error = load_stored_record(path)
        if error or record is None:
            failed += 1
            continue
        building_id = record_id(record, path.name.split(".")[0])
        if "coordinates_source" in record:
            already += 1
            continue
        notice = record.get("coordinates")
        coordinates, source, notice_value = resolve_coordinates(notice, points.get(building_id))
        if source is None or coordinates is None:
            unchanged += 1
            continue
        record["coordinates"] = coordinates
        record["coordinates_source"] = source
        record["coordinates_notice"] = notice_value
        notes = list(record.get("notes") or [])
        notes.append(coordinate_note(coordinates, notice_value))
        record["notes"] = notes
        extraction = dict(record.get("extraction") or {})
        extraction["content_hash"] = content_hash(record)
        record["extraction"] = extraction
        distance = metres_apart(
            notice["latitude"], notice["longitude"],
            coordinates["latitude"], coordinates["longitude"],
        )
        amended.append((building_id, distance))
        if not args.dry_run:
            write_json_atomic(path, record)
    amended.sort(key=lambda item: -item[1])
    print(
        f"{len(amended)} record(s) corrected, {unchanged} already right, "
        f"{already} already carrying a correction, {failed} unreadable"
        + (" (dry run: nothing written)" if args.dry_run else "")
    )
    for building_id, distance in amended[:5]:
        print(f"   {building_id}: moved {distance / 1000:.0f} km from the notice's placeholder")
    if amended:
        print(
            "note: drift detection is unaffected and remains a whole-corpus question; "
            "these records were corrected from data already on disk."
        )
    return 1 if failed else 0


def build_place_record(
    html_text: str, url: str, place_id: str, lang: str
) -> dict[str, object]:
    """Parse a `notice de lieu`: a street, square or avenue.

    Place notices live at `/<lang>/<city>/<street>/<street-id>` — the four-segment URL
    the building parser refuses as a trap, because it cannot be a building id. They
    reuse the building page's markup (`object-info` containers, `h4.label` blocks, the
    same gallery), so the extraction is shared, but the *entity* is different: a place
    has no address, tags, legal status or contributors, and its prose is the
    street-and-place introduction rather than a building description. It is kept in a
    separate corpus so the two streams cannot be confused.
    """
    root = parse_dom(html_text)
    if not is_notice_page(root):
        raise NotANoticePage(f"{url} is not a notice page (missing id, or a soft 404)")

    heading = find(root, tag="h1")
    name = plain_text(heading, place_skip) if heading is not None else ""
    sections = extract_panels(root)
    blocks = extract_detail_blocks(root)
    inventory_link = next(
        (
            anchor.attrs.get("href")
            for anchor in find_all(root, tag="a")
            if is_view_more(anchor) and anchor.attrs.get("href")
        ),
        None,
    )
    images = extract_images(root, url)
    details = {label: block_text(node, place_skip) for label, node in blocks.items()}

    notes: list[str] = [
        "This is a notice de lieu (a street, square or avenue), not a building notice: "
        "it carries the place introduction rather than a building description."
    ]
    if not (panel_text(panel_for(sections, "description", root), place_skip) or {}).get("text"):
        notes.append(
            "No free-text introduction on this page; the place has no written notice "
            "even though it has a page."
        )
    if inventory_link:
        notes.append(
            "The page links its own buildings through "
            f"{inventory_link} — a route robots.txt disallows, so the link is recorded "
            "for reference and deliberately not fetched."
        )

    record: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "place",
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "language": lang,
        "place_id": place_id,
        "url": url,
        "source": dict(SOURCE_METADATA, url=url),
        "name": name or None,
        "municipality": unquote_path_segment(url, 1),
        "street_slug": unquote_path_segment(url, 2),
        "inventory_link": inventory_link,
        "description": panel_text(panel_for(sections, "description", root), place_skip),
        "sources": panel_text(panel_for(sections, "sources", root), place_skip),
        "images": images,
        "details": details,
        "notes": notes,
    }
    record["image_rights"] = {
        "conditions_url": CONDITIONS_URL,
        "reuse_basis": SOURCE_METADATA["rights"]["reuse_basis"],
        "obligations": SOURCE_METADATA["rights"]["obligations"],
        "images_without_credit": len(images) - len(
            [i for i in images if i.get("credit_holders")]
        ),
    }
    record["extraction"] = {
        "scraper": SCRAPER_NAME,
        "schema_version": SCHEMA_VERSION,
        "page_bytes": len(html_text.encode("utf-8")),
        "page_hash": sha256_hex(html_text.encode("utf-8")),
    }
    return record


def unquote_path_segment(url: str, index: int) -> str | None:
    """A URL path segment as the site wrote it, unquoted (city name, street slug)."""
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if len(parts) <= index:
        return None
    return unquote(parts[index])


def encode_url(url: str) -> str:
    """Percent-encode a source URL whose path carries raw non-ASCII.

    Street slugs arrive here as the site wrote them in its own address links,
    unquoted -- so a u with diaeresis in a Schaerbeek slug reaches http.client
    raw and the request fails encoding as ASCII (place scrape, 2026-10-20).
    Idempotent: % stays safe, so already-quoted URLs pass through unchanged.
    """
    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        quote(parts.path, safe="/%"),
        quote(parts.query, safe="=&%"),
        parts.fragment,
    ))


def place_url(place_id: str, city: str, street: str, lang: str) -> str:
    return f"{BASE_URL}/{lang}/{city}/{street}/{place_id}"


def parse_place_target(target: str) -> tuple[str, str, str]:
    """Resolve a CLI target to (place_id, city, street).

    A bare id cannot name a place: the address URL carries the city and the street slug
    as well, so the four-segment form is required. The *building* parser keeps refusing
    that same form as a trap, which is what stops the two modes from silently scraping
    each other's notices.
    """
    value = target.strip()
    if "://" not in value:
        value = urljoin(BASE_URL, value if value.startswith("/") else f"/{value}")
    parsed = urlparse(value)
    if parsed.hostname != SOURCE_HOST:
        raise ScrapeError(f"unexpected host in target: {target}")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 4 or not parts[3].isdigit():
        raise ScrapeError(
            f"cannot derive a place from {target!r}: a place URL is "
            "/<lang>/<city>/<street>/<street-id>, and a bare id cannot name a place"
        )
    return parts[3], parts[1], parts[2]


def street_targets(building_out: Path, lang: str) -> list[tuple[str, str, str]]:
    """Every street the stored building notices link, as place targets.

    A building notice carries its address as `/…/<city>/<street>/<street-id>`, so the
    building corpus already enumerates the streets its buildings sit on — 3,564 of
    them. There is no places index to enumerate instead: `/medias/places.fr.json` and
    `/medias/lieux.fr.json` are real 404s, and `/fr/places/`, `/fr/streets/` and
    `/fr/lieux/` all serve the same generic page.
    """
    found: dict[str, tuple[str, str, str]] = {}
    for path in stored_record_paths(building_out, lang):
        record, error = load_stored_record(path)
        if error or record is None:
            continue
        for address in record.get("addresses") or []:
            if not isinstance(address, dict):
                continue
            parts = [
                part for part in urlparse(str(address.get("url") or "")).path.strip("/").split("/")
                if part
            ]
            if len(parts) == 4 and parts[3].isdigit():
                found.setdefault(parts[3], (parts[3], parts[1], parts[2]))
    return sorted(found.values(), key=lambda item: (item[1], item[2], item[0]))


def run_place_scrape(fetcher: Fetcher, args) -> int:
    """Scrape `notices de lieu` into a corpus of their own.

    Same conventions as the building sweep — robots re-checked as it runs, resumable,
    atomic writes, a failure journal and a `[FINAL]` line — because it is the same kind
    of long crawl against the same host. A place needs its city and street in the URL,
    so targets are the four-segment address form rather than bare ids.
    """
    targets = [parse_place_target(target) for target in args.targets]
    if args.from_streets is not None:
        discovered = street_targets(args.from_streets, args.lang)
        print(f"{len(discovered)} street(s) referenced by {args.from_streets}", file=sys.stderr)
        targets += discovered
    unique: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for place_id, city, street in targets:
        if place_id not in seen:
            seen.add(place_id)
            unique.append((place_id, city, street))
    if args.limit is not None:
        unique = unique[: args.limit]
    if not unique:
        print("no places to scrape: pass a place URL or --from-streets DIR", file=sys.stderr)
        return 2

    out = args.places_out
    absent_path = out / f"_absent.{args.lang}.json"
    # Streets the site has no notice for are counted once and remembered, so a resume
    # does not spend crawl time re-confirming ~1,300 expected absences.
    known_absent: dict[str, dict] = {}
    if absent_path.exists():
        try:
            for entry in json.loads(absent_path.read_text(encoding="utf-8")):
                if isinstance(entry, dict) and entry.get("target"):
                    known_absent[str(entry["target"])] = entry
        except (OSError, json.JSONDecodeError, TypeError):
            known_absent = {}

    failures: list[dict[str, str]] = []
    absent: list[dict[str, str]] = []
    written = skipped = drifted = 0
    with_intro = 0
    started = time.monotonic()
    last_robots_check = started
    interrupted = False
    try:
        for index, (place_id, city, street) in enumerate(unique, start=1):
            url = place_url(place_id, city, street, args.lang)
            path = out / f"{place_id}.{args.lang}.json"
            if args.skip_existing and (path.exists() or place_id in known_absent):
                skipped += 1
                continue
            try:
                if (
                    args.robots_recheck_seconds
                    and not args.no_robots
                    and time.monotonic() - last_robots_check >= args.robots_recheck_seconds
                ):
                    last_robots_check = time.monotonic()
                    if recheck_robots(fetcher, urlparse(url).path, args.robots_cache):
                        print("stopping: robots.txt no longer allows this path", file=sys.stderr)
                        break
                html_text = fetcher.get_text(url)
                record = build_place_record(html_text, url, place_id, args.lang)
                record["extraction"]["content_hash"] = content_hash(record)  # type: ignore[index]
                if args.fail_on_change and path.exists():
                    stored = json.loads(path.read_text(encoding="utf-8"))
                    if stored.get("extraction", {}).get("content_hash") != (
                        record["extraction"]["content_hash"]  # type: ignore[index]
                    ):
                        drifted += 1
                        print(
                            f"changed: {place_id}: {url} no longer matches the stored "
                            f"record (kept {path.name}, wrote nothing)",
                            file=sys.stderr, flush=True,
                        )
                        continue
                write_json_atomic(path, record)
                written += 1
                # A page can exist with nothing on it: measured on a spread of
                # twelve real place pages, half carried an introduction and half were
                # an h1 name only. Counting the two apart keeps the run honest about
                # what it obtained rather than how many pages it wrote.
                if record.get("description"):
                    with_intro += 1
                if not args.quiet:
                    print(f"{place_id} · {record['name']} · "
                          f"{len(record['description']['text']) if record['description'] else 0} chars"
                          f" · pics {len(record['images'])}")  # type: ignore[index]
            except NotANoticePage:
                # Expected, not broken: the publisher has no notice page for this street.
                # Recorded with the hash of what the site actually served, so the claim
                # stays checkable, and skipped on a resume so re-runs stay cheap.
                absent.append({
                    "target": place_id,
                    "url": url,
                    "page_sha256": sha256_hex(html_text.encode("utf-8")),
                    "reason": "the site served its error page; no notice is published here",
                })
                if not args.quiet:
                    print(f"{place_id} · no notice published for this street")
            except (ScrapeError, json.JSONDecodeError, OSError) as error:
                failures.append({"target": place_id, "error": str(error)[:200]})
                print(f"error: {place_id}: {error}", file=sys.stderr, flush=True)
            if args.progress_every and index % args.progress_every == 0:
                elapsed = max(time.monotonic() - started, 0.001)
                print(
                    f"[{index}/{len(unique)}] {place_id} · {written} written · "
                    f"{written / elapsed:.2f}/s · {len(failures)} failed",
                    file=sys.stderr, flush=True,
                )
    except KeyboardInterrupt:
        interrupted = True
        print("interrupted: rerun with --skip-existing to resume", file=sys.stderr, flush=True)
    finally:
        if failures:
            out.mkdir(parents=True, exist_ok=True)
            write_json_atomic(out / f"_failures.{args.lang}.json", failures)
        if absent:
            out.mkdir(parents=True, exist_ok=True)
            merged = dict(known_absent)
            merged.update({entry["target"]: entry for entry in absent})
            write_json_atomic(absent_path, [merged[k] for k in sorted(merged)])

    if not args.quiet:
        print(f"{fetcher.requests} request(s), {fetcher.bytes / 1024:.0f} KiB")
    sys.stdout.flush()
    outcome = "interrupted" if interrupted else (
        f"finished with problems ({len(failures)} failed)" if failures or drifted else "complete"
    )
    print(
        f"[FINAL] {outcome}: {written} place(s) written "
        f"({with_intro} carrying an introduction), {skipped} skipped, "
        f"{len(absent)} without a published notice, {len(failures)} failed, "
        f"{drifted} changed, of {len(unique)} target(s)",
        file=sys.stderr, flush=True,
    )
    return 1 if failures or drifted else 0


def build_record(
    html_text: str,
    url: str,
    building_id: str,
    lang: str,
    rubric_store: RubricStore | None = None,
    index_point: tuple[float, float] | None = None,
) -> dict[str, object]:
    root = parse_dom(html_text)
    if not is_notice_page(root):
        raise NotANoticePage(f"{url} is not a notice page (missing id, or a soft 404)")
    blocks = extract_detail_blocks(root)
    named: dict[str, Element] = {}
    for label, node in blocks.items():
        key = label_key(label)
        if key and key not in named:
            named[key] = node

    sections = extract_panels(root)
    identity, addresses = extract_identity(root)
    city = extract_city(root)

    interests = extract_interests(named["interests"]) if "interests" in named else []
    for item in interests:
        criteria = item.get("criteria") or ""
        item["criteria_sha256"] = sha256_hex(criteria.encode("utf-8")) if criteria else None
        if rubric_store is not None:
            # Keep the flag and the pin, drop the prose that the store already holds.
            item["criteria_ref"] = rubric_store.record(str(item["value"]), criteria)
            item.pop("criteria", None)
    typologies = extract_lines(named["typologies"]) if "typologies" in named else []
    styles = extract_lines(named["styles"]) if "styles" in named else []
    contributors = (
        extract_contributors(named["contributors"]) if "contributors" in named else []
    )
    inventories = extract_inventories(named["inventories"]) if "inventories" in named else []
    legal_status = (
        extract_legal_status(named["legal_status"]) if "legal_status" in named else None
    )
    research = extract_lines(named["research"]) if "research" in named else []

    urban_id = building_id
    if "urban_id" in named:
        match = re.search(r"(\d+)", plain_text(named["urban_id"]))
        if match:
            urban_id = match.group(1)

    description_node = panel_for(sections, "description", root)
    sources_node = panel_for(sections, "sources", root)

    tags = [{"kind": "interest", "value": item["value"]} for item in interests]
    tags += [{"kind": "typology", "value": value} for value in typologies]
    tags += [{"kind": "style", "value": value} for value in styles]

    nearby_tree_titles = (
        "arbres remarquables à proximité",
        "opmerkelijke bomen in de nabijheid",
    )
    nearby_trees: list[dict[str, object]] = []
    for title in nearby_tree_titles:
        if title in sections:
            nearby_trees = extract_list_items(sections[title], url)
            break

    images = extract_images(root, url)
    credited = [
        {"filename": image["filename"], "credit_holders": image["credit_holders"]}
        for image in images
        if image["credit_holders"]
    ]
    image_rights = {
        "conditions_url": CONDITIONS_URL,
        "reuse_basis": SOURCE_METADATA["rights"]["reuse_basis"],
        "obligations": SOURCE_METADATA["rights"]["obligations"],
        "credited_images": credited,
        "images_without_credit": len(images) - len(credited),
        "hint_note": (
            "An absent credit states nothing about reuse, so rights_hint stays null."
        ),
    }

    notes: list[str] = []
    if description_node is None:
        notes.append(
            "No free-text Description section on this page; the interest criteria "
            "texts come from the generic catalogue rubric and are not building-specific."
        )
    if not interests and not typologies and not styles:
        notes.append("No interest, typology or style tags found.")
    incomplete_ranges = [
        f"{person['name']}: {year}"
        for person in contributors
        for year in person.get("years", [])
        if "-" in str(year) and not re.fullmatch(r"\d{3,4}-\d{3,4}", str(year))
    ]
    if incomplete_ranges:
        notes.append(
            "The source's contributor date range is incomplete "
            f"({'; '.join(incomplete_ranges)}); recorded verbatim rather than "
            "completed or split into a year and a role."
        )

    coordinates, coordinates_source, coordinates_notice = resolve_coordinates(
        extract_coordinates(html_text), index_point
    )
    if coordinates_source == "index" and coordinates is not None:
        notes.append(coordinate_note(coordinates, coordinates_notice))

    record: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "language": lang,
        "building_id": building_id,
        "urban_id": urban_id,
        "url": url,
        "source": dict(SOURCE_METADATA, url=url),
        "identity": identity,
        "addresses": addresses,
        "city": city,
        "coordinates": coordinates,
        "tags": tags,
        "interests": interests,
        "typologies": typologies,
        "styles": styles,
        "inventories": inventories,
        "legal_status": legal_status,
        "contributors": contributors,
        "research_and_writing": research,
        "description": panel_text(description_node),
        "sources": panel_text(sources_node),
        "images": images,
        "image_rights": image_rights,
        "nearby_trees": nearby_trees,
        "suggestions": extract_related(root, url),
        "details": {label: block_text(node) for label, node in blocks.items()},
        "notes": notes,
    }
    if coordinates_source:
        record["coordinates_source"] = coordinates_source
        record["coordinates_notice"] = coordinates_notice
    record["extraction"] = {
        "scraper": SCRAPER_NAME,
        "schema_version": SCHEMA_VERSION,
        "page_bytes": len(html_text.encode("utf-8")),
        "page_hash": sha256_hex(html_text.encode("utf-8")),
        "non_canonical_fields": list(NON_CANONICAL_FIELDS),
    }
    record["extraction"]["content_hash"] = content_hash(record)
    return record


# --------------------------------------------------------------------------- #
# targets, images and output
# --------------------------------------------------------------------------- #
def parse_target(target: str) -> str:
    """Resolve a CLI target to a building id."""
    value = target.strip()
    if re.fullmatch(r"\d+", value):
        return value
    if "://" not in value:
        value = urljoin(BASE_URL, value if value.startswith("/") else f"/{value}")
    parsed = urlparse(value)
    if parsed.hostname != SOURCE_HOST:
        raise ScrapeError(f"unexpected host in target: {target}")
    direct = BUILDING_HREF_RE.match(parsed.path)
    if direct:
        return direct.group(1)
    if re.fullmatch(r"/(?:fr|nl)/buildings/\d+", parsed.path):
        return parsed.path.rsplit("/", 1)[1]
    if STREET_HREF_RE.match(parsed.path) and len(parsed.path.strip("/").split("/")) == 5:
        return parsed.path.rsplit("/", 1)[1]
    raise ScrapeError(
        f"cannot derive a building id from {target!r}: use an id, "
        f"/<lang>/buildings/<id>, or the 4-part address URL. A 3-part address URL "
        f"(/<lang>/<city>/<street>/<street-id>) points at the street, not the building."
    )


def building_url(building_id: str, lang: str) -> str:
    return f"{BASE_URL}/{lang}/buildings/{building_id}"


def image_root_for(image_root: Path | None) -> Path:
    return image_root if image_root is not None else DEFAULT_IMAGE_ROOT


def record_id(record: dict[str, object], fallback: str | None = None) -> str:
    """The id a record is filed under: `building_id`, or `place_id` for a place.

    One helper rather than a `record["building_id"]` at each site: the picture pass
    already served both kinds through a filename-stem fallback, while `download_images`
    still required a building id outright and would have raised on a place record.
    """
    value = record.get("building_id") or record.get("place_id") or fallback
    if not value:
        raise ScrapeError("record carries neither a building_id nor a place_id")
    return str(value)


def manifest_skeleton(record: dict[str, object], rights_basis: str) -> dict[str, object]:
    """Manifest header for one building, before any picture is fetched.

    The manifest states the basis and, for the inventory's conditional
    permission, the exact obligations that basis carries, so compliance stays
    checkable after the fact rather than living only in the operator's memory.
    """
    conditional = rights_basis == CONDITIONAL_BASIS
    return {
        "schema_version": SCHEMA_VERSION,
        "rights_basis": rights_basis,
        "conditions_url": CONDITIONS_URL if conditional else None,
        "obligations": SOURCE_METADATA["rights"]["obligations"] if conditional else None,
        "source_page": record["url"],
        "retrieved_at": record["retrieved_at"],
        "images": [],
    }


def write_json_atomic(path: Path, payload: object) -> None:
    """Write JSON so an interruption can never leave a half-written file behind.

    A 43-hour run does get interrupted — by the outage guard, by SIGTERM, by a
    reboot — and a torn manifest or record would read as corruption rather than as
    work still to do. Writing beside the target and renaming makes the visible file
    either the old one or the new one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_manifest(target_dir: Path, manifest: dict[str, object]) -> Path:
    """Write a building's manifest, leaving the other tool's section untouched.

    Two tools write this one file: the picture pass owns ``images`` and
    ``derive_previews.py`` owns ``derived_previews``. The pass rewrites a manifest on
    every resume, and it used to drop the section it does not own — 157 real
    buildings ended up with ``preview/`` files that no manifest described, which is
    precisely the state in which a locally derived 500px copy can pass for the
    publisher's own asset. Carrying the section forward keeps that label.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"
    if "derived_previews" not in manifest:
        previous, _ = load_stored_record(manifest_path)
        if isinstance(previous, dict) and "derived_previews" in previous:
            manifest["derived_previews"] = previous["derived_previews"]
    write_json_atomic(manifest_path, manifest)
    return manifest_path


def image_variant_url(image: dict[str, object], variant: str) -> str:
    """The URL for the requested size, falling back to the original."""
    if variant == "preview" and image.get("preview_url"):
        return str(image["preview_url"])
    return str(image["url"])


def sniff_image_format(head: bytes) -> str | None:
    """The picture format these bytes actually are, or None if they are not one."""
    for signature, name in IMAGE_SIGNATURES:
        if head.startswith(signature):
            return name
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def local_name(image: dict[str, object], taken: set[str]) -> str:
    """Local filename for one picture, unique within its notice.

    The source's basename is not a key. Some photographs are served twice, at
    ``/medias/buildings/<name>`` and ``/medias/buildings/inv39-99/<name>`` — 571
    notices list both forms — and storing by basename made the second fetch overwrite
    the first, left the manifest with two entries claiming the *same* URL (the merge
    map is keyed by filename, so the second overwrote the first's entry), and made
    the audit report a gap no re-run could ever close.

    Only a colliding picture is renamed, prefixed with its own directory segment. A
    uniform subdirectory-aware scheme was rejected after measuring: 42,232 of 77,175
    URLs carry a subdirectory, so renaming by URL would also rename 103 files already
    stored and orphan them. Collision-only keeps every existing file valid.

    Collisions are judged case-insensitively, because 68 notices list the same name
    twice differing only in extension case (`10005050_0019_P01.JPG` beside
    `..._01.jpg`). Those are two files here and **one file on macOS or Windows**, so a
    corpus copied to either would silently lose a picture. `taken` therefore holds
    lowercased keys; the returned names keep the source's own casing.
    """
    filename = str(image["filename"])
    if filename.lower() not in taken:
        return filename
    # Borrow a directory segment from the URL, but only from the media path this
    # source actually uses, and only characters safe in a filename: a URL that does
    # not carry one falls back to a neutral prefix rather than contributing host or
    # scheme text to a local path.
    marker = "/medias/buildings/"
    url = str(image.get("url", ""))
    subpath = ""
    if marker in url:
        rest = url.split(marker, 1)[1]
        if "/" in rest:
            subpath = rest.rsplit("/", 1)[0]
    prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", subpath).strip("._-")
    candidate = f"{prefix}__{filename}" if prefix else f"duplicate__{filename}"
    stem, dot, suffix = candidate.rpartition(".")
    unique, counter = candidate, 2
    while unique.lower() in taken:
        unique = f"{stem}__{counter}.{suffix}" if dot else f"{candidate}__{counter}"
        counter += 1
    return unique


def local_names(images: list[dict[str, object]]) -> list[str]:
    """The local filename for every picture of one notice, in the notice's order.

    A pure function of the stored record, so a resume, a re-run and the audit all
    agree on what a picture is called without any extra state on disk. Keys are
    lowercased so uniqueness holds on case-insensitive filesystems too.
    """
    taken: set[str] = set()
    names: list[str] = []
    for image in images:
        name = local_name(image, taken)
        taken.add(name.lower())
        names.append(name)
    return names


def download_image(
    fetcher: Fetcher, image: dict[str, object], target_dir: Path, variant: str = "full",
    name: str | None = None,
) -> dict[str, object]:
    """Fetch one picture and return its manifest entry."""
    url = image_variant_url(image, variant)
    # The name is derived from the source URL, so it cannot escape target_dir.
    filename = name or str(image["filename"])
    if Path(filename).name != filename or not filename:
        raise ScrapeError(f"refusing unsafe image filename {filename!r} for {url}")
    body, content_type = fetcher.get(url, max_bytes=MAX_IMAGE_BYTES)
    image_format = sniff_image_format(body[:16])
    if image_format is None:
        # Refusing beats storing it: a mislabelled file would be pinned by its own
        # hash and every later check would confirm it.
        raise ScrapeError(
            f"{url} did not return a picture ({len(body)} bytes, Content-Type "
            f"{content_type or 'unknown'}); not storing it as {filename}"
        )
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / filename).write_bytes(body)
    return {
        "url": url,
        "filename": filename,
        "variant": variant,
        "format": image_format,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "caption": image.get("caption"),
        "credit_holders": image.get("credit_holders"),
        "rights_hint": image.get("rights_hint"),
    }


def download_images(
    fetcher: Fetcher, record: dict[str, object], rights_basis: str,
    image_root: Path | None = None, variant: str = "full",
) -> dict[str, object]:
    """Fetch every notice picture into the gitignored local/ tree, with a manifest."""
    if rights_basis not in ALLOWED_RIGHTS_BASIS:
        allowed = ", ".join(sorted(ALLOWED_RIGHTS_BASIS))
        raise ScrapeError(f"rights basis {rights_basis!r} is not accepted; use one of: {allowed}")

    building_id = record_id(record)
    target_dir = image_root_for(image_root) / building_id
    images = [image for image in record.get("images", []) if isinstance(image, dict)]
    manifest = manifest_skeleton(record, rights_basis)
    manifest["images"] = [
        download_image(fetcher, image, target_dir, variant, name)
        for image, name in zip(images, local_names(images))
    ]
    write_manifest(target_dir, manifest)
    return manifest


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def stored_images(record: dict[str, object], stored_manifest: dict[str, object] | None) -> dict[str, dict]:
    """Manifest entries from a previous run, keyed by filename."""
    entries = (stored_manifest or {}).get("images") or []
    return {
        str(entry["filename"]): entry
        for entry in entries  # type: ignore[union-attr]
        if isinstance(entry, dict) and entry.get("filename")
    }


def image_is_stored(
    image: dict[str, object], stored: dict[str, dict], target_dir: Path, variant: str = "full",
    name: str | None = None,
) -> bool:
    """True when this picture is already on disk and still matches its hash.

    A resume must not re-download 15 GB of pictures to find out what it already
    has, but it also must not accept a truncated or edited file as done, so the
    cheap size check comes first and the hash decides.
    """
    filename = name or str(image.get("filename"))
    entry = stored.get(filename)
    if not entry or entry.get("url") != image_variant_url(image, variant):
        return False
    path = target_dir / filename
    try:
        if path.stat().st_size != entry.get("bytes"):
            return False
    except OSError:
        return False
    recorded = entry.get("sha256")
    return not recorded or sha256_file(path) == recorded


def pending_images(
    record: dict[str, object], stored_manifest: dict[str, object] | None, target_dir: Path,
    variant: str = "full",
) -> list[tuple[dict[str, object], str]]:
    """Pictures named by the notice that are not stored correctly, with their names."""
    stored = stored_images(record, stored_manifest)
    images = [image for image in record.get("images", []) if isinstance(image, dict)]
    return [
        (image, name)
        for image, name in zip(images, local_names(images))
        if not image_is_stored(image, stored, target_dir, variant, name)
    ]


def stored_record_paths(out_dir: Path, lang: str) -> list[Path]:
    """Notice records in an output directory, newest runs' side files excluded.

    ``rubrics.<lang>.json`` and ``_failures.<lang>.json`` share the record suffix
    but are not building records.
    """
    side_files = {f"rubrics.{lang}.json"}
    return sorted(
        path
        for path in out_dir.glob(f"*.{lang}.json")
        if path.name not in side_files and not path.name.startswith("_")
    )


def load_stored_record(path: Path) -> tuple[dict | None, str | None]:
    """Read one stored notice, returning (record, error)."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, str(error)[:200]
    if not isinstance(record, dict):
        return None, "top level is not an object"
    return record, None


# Measured on real downloads from this source: five originals returned 0.24-0.26
# bytes per pixel (1085x1600 -> ~400 KiB). Used only to label a planning estimate.
MEASURED_BYTES_PER_PIXEL = 0.25


def named_images(record: dict) -> list[dict]:
    """The pictures a notice names, as a list of manifest-shaped dicts."""
    return [image for image in record.get("images") or [] if isinstance(image, dict)]


# Picture failures arrive in two shapes: a broken file here and there, and a
# sustained outage that would otherwise spend the rest of a 43-hour crawl
# recording a failure against every picture still to come. A notice names ~2.9
# pictures, so 50 consecutive failures is about seventeen buildings in a row where
# nothing worked at all — an outage, not bad data — which is why the picture pass
# needs a much higher limit than the text crawl's one-failure-per-notice ten.
DEFAULT_IMAGE_FAILURE_LIMIT = 50

# Exit codes for the picture pass, because the pipeline has to tell an outage from
# a handful of broken files: an outage must not be followed by deriving previews
# from a picture set that is about to be resumed, which is also when a human is
# most likely to restart the pass while those previews are being written.
IMAGE_EXIT_ABORTED = 3


def image_plan(
    out_dir: Path, lang: str, image_root: Path, variant: str, limit: int | None = None
) -> dict[str, object]:
    """Count what a picture pass would fetch, reading every record but no page.

    Shared by the zero-request `--dry-run` plan and by the pass itself, so the pass can
    state how many pictures it is working through. Without that it can only report a
    rate from a run whose first minutes are spent hashing what is already stored, which
    reads as 0.00/s in the log that is a detached run's only observability. Files already
    on disk count as stored, so this also describes a resume.
    """
    paths = stored_record_paths(out_dir, lang)
    if limit is not None:
        paths = paths[:limit]
    records = with_pictures = named = stored = 0
    pixels = 0
    unreadable: list[str] = []
    for path in paths:
        record, error = load_stored_record(path)
        if error or record is None:
            unreadable.append(f"{path.name}: {error}")
            continue
        records += 1
        images = named_images(record)
        if not images:
            continue
        with_pictures += 1
        named += len(images)
        building_id = record_id(record, path.name.split(".")[0])
        target_dir = image_root / building_id
        manifest_path = target_dir / "manifest.json"
        stored_manifest: dict[str, object] | None = None
        if manifest_path.exists():
            stored_manifest, _ = load_stored_record(manifest_path)
        pending = pending_images(record, stored_manifest, target_dir, variant)
        stored += len(images) - len(pending)
        for image, _name in pending:
            width, height = image.get("width"), image.get("height")
            if isinstance(width, int) and isinstance(height, int):
                pixels += width * height
    return {
        "paths": len(paths),
        "records": records,
        "with_pictures": with_pictures,
        "named": named,
        "stored": stored,
        "to_fetch": named - stored,
        "pixels": pixels,
        "unreadable": unreadable,
    }


def report_image_plan(args) -> int:
    """Print the measured plan, without making one request."""
    image_root = image_root_for(args.image_dir)
    if not stored_record_paths(args.out, args.lang):
        print(f"no stored {args.lang} records under {args.out}", file=sys.stderr)
        return 2
    plan = image_plan(args.out, args.lang, image_root, args.image_size, args.limit)
    records = plan["records"]
    with_pictures = plan["with_pictures"]
    named = plan["named"]
    stored = plan["stored"]
    pixels = plan["pixels"]
    unreadable = plan["unreadable"]
    to_fetch = plan["to_fetch"]
    lines = [
        f"plan for {image_root} ({args.image_size} variant)",
        f"records examined:   {records}",
        f"records with pics:  {with_pictures}",
        f"pictures named:     {named}",
        f"already stored:     {stored}",
        f"to fetch:           {to_fetch}",
        f"crawl time at 2 s:  {to_fetch * 2 / 3600:.1f} h",
    ]
    if pixels:
        estimate = pixels * MEASURED_BYTES_PER_PIXEL
        lines.append(
            f"to fetch is {pixels / 1e9:.1f} Gpx; ~{estimate / 1e9:.1f} GB at the "
            f"measured {MEASURED_BYTES_PER_PIXEL} B/px (estimate, not a promise)"
        )
    if unreadable:
        lines.append(f"unreadable records: {len(unreadable)}")
        lines.extend(f"  ! {problem}" for problem in unreadable[:10])
    lines.append("no requests made (--dry-run)")
    print("\n".join(lines))
    return 1 if unreadable else 0


# JPEG needs its marker chain walked; PNG, GIF and BMP state the size in a fixed
# header. 64 KiB is the usual case, but 5 of the first 2,471 real files keep their
# frame header behind a 69-73 KiB EXIF thumbnail, so the read is extended only when
# the size is still unknown. A format the parser cannot read is reported as
# *unchecked*, never as wrong.
DIMENSION_HEAD_BYTES = 1 << 16
DIMENSION_HEAD_LIMIT = 1 << 18


def _jpeg_dimensions(head: bytes) -> tuple[int, int] | None:
    """Walk the JPEG marker chain to the start-of-frame segment."""
    index = 2
    while index + 9 < len(head):
        if head[index] != 0xFF:
            index += 1
            continue
        marker = head[index + 1]
        if marker == 0xDA:  # start of scan: any frame header would already be behind us
            return None
        if marker in (0x01,) or 0xD0 <= marker <= 0xD8:
            index += 2
            continue
        length = int.from_bytes(head[index + 2:index + 4], "big")
        if length < 2:
            return None
        # SOF0-3, SOF5-7, SOF9-11, SOF13-15 carry the frame size.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(head[index + 5:index + 7], "big")
            width = int.from_bytes(head[index + 7:index + 9], "big")
            return (width, height) if width and height else None
        index += 2 + length
    return None


def image_dimensions(head: bytes) -> tuple[int, int] | None:
    """The pixel size these bytes are, or None when it cannot be read from them.

    None means *unchecked*, never *wrong*: the check exists to prove a stored file is
    the picture its notice names, and a format it cannot parse must not silently
    become a defect. Measured on the 2,471 real files downloaded first, the declared
    size matched the file in 2,471 of 2,471 cases.
    frames header is walked past; a format or a frame header beyond that is reported as
    unchecked, never as wrong.
    """
    if head.startswith(b"\xff\xd8\xff"):
        return _jpeg_dimensions(head)
    if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
        width = int.from_bytes(head[16:20], "big")
        height = int.from_bytes(head[20:24], "big")
        return (width, height) if width and height else None
    if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
        width = int.from_bytes(head[6:8], "little")
        height = int.from_bytes(head[8:10], "little")
        return (width, height) if width and height else None
    if head.startswith(b"BM") and len(head) >= 26:
        width = int.from_bytes(head[18:22], "little", signed=True)
        height = int.from_bytes(head[22:26], "little", signed=True)
        return (abs(width), abs(height)) if width and height else None
    return None


def rights_problems(manifest: dict, building_id: str) -> list[str]:
    """What a manifest fails to state about reusing the pictures it lists.

    This corpus is conditionally non-commercial: the pixels may be used only with the
    credit and the source link the publisher's conditions require, so a manifest that
    lists pictures without stating those obligations is a **rights defect**, not a
    formatting one — the audit would otherwise confirm a tree that ships images with
    no record of the terms that permit them. Every one of the 1,452 manifests written
    by the time this was added states them, which is what lets the audit require it.

    Only the conditional basis carries obligations, so a manifest on another basis is
    not asked for them; that mirrors the writer in `manifest_skeleton`.
    """
    problems: list[str] = []
    basis = manifest.get("rights_basis")
    if not basis:
        problems.append(f"{building_id}: manifest states no reuse basis")
    elif basis == CONDITIONAL_BASIS:
        if not manifest.get("conditions_url"):
            problems.append(f"{building_id}: conditional basis with no conditions_url")
        obligations = manifest.get("obligations") or {}
        for key in ("online", "printed", "third_party"):
            if not obligations.get(key):
                problems.append(f"{building_id}: conditional basis with no {key} obligation")
    for entry in manifest.get("images") or []:
        if not isinstance(entry, dict):
            continue
        for key in ("rights_hint", "credit_holders"):
            if key not in entry:
                problems.append(f"{building_id}/{entry.get('filename')}: no {key}")
    return problems


def verify_image_tree(args) -> int:
    """Prove the picture tree matches the notices that reference it.

    Thirty-seven hours of downloading cannot be checked by eye, and a resume that
    reports "0 fetched" only proves the code was satisfied by its own manifest,
    not that the files on disk are the right ones. This walks both sides: every
    picture a notice names must be present, unchanged and recorded, and every file
    present must be one a notice expects. Either direction of mismatch is a gap.
    """
    image_root = image_root_for(args.image_dir)
    paths = stored_record_paths(args.out, args.lang)
    if not paths:
        print(f"no stored {args.lang} records under {args.out}", file=sys.stderr)
        return 2
    if not image_root.is_dir():
        # Not an error: before a picture pass this is simply nothing downloaded
        # yet, and reporting the counts is more useful than bailing out with a
        # message that looks like a wrong argument.
        print(f"note: no picture tree at {image_root} yet", file=sys.stderr)

    named = stored = with_pictures = 0
    not_downloaded = incomplete = corrupt = stale = not_pictures = 0
    mis_sized = sizes_unchecked = sizes_undeclared = rights_incomplete = 0
    buildings_not_downloaded = 0
    gaps: list[str] = []
    expected: dict[str, set[str]] = {}
    declared: dict[str, dict[str, tuple[int, int] | None]] = {}
    for path in paths:
        record, error = load_stored_record(path)
        if error or record is None:
            gaps.append(f"{path.name}: unreadable record ({error})")
            continue
        images = named_images(record)
        if not images:
            continue
        with_pictures += 1
        named += len(images)
        building_id = record_id(record, path.name.split(".")[0])
        expected[building_id] = set(local_names(images))
        declared[building_id] = {
            name: ((image.get("width"), image.get("height"))
                   if isinstance(image.get("width"), int) and isinstance(image.get("height"), int)
                   else None)
            for image, name in zip(images, local_names(images))
        }
        target_dir = image_root / building_id
        manifest_path = target_dir / "manifest.json"
        if not manifest_path.exists():
            # Expected before and during a picture pass; distinct from a defect.
            not_downloaded += len(images)
            buildings_not_downloaded += 1
            continue
        manifest, manifest_error = load_stored_record(manifest_path)
        if manifest is None:
            corrupt += len(images)
            gaps.append(f"{building_id}: unreadable manifest ({manifest_error})")
            continue
        rights_gaps = rights_problems(manifest, building_id)
        if rights_gaps:
            rights_incomplete += len(rights_gaps)
            gaps.extend(rights_gaps)
        missing = pending_images(record, manifest, target_dir, args.image_size)
        stored += len(images) - len(missing)
        incomplete += len(missing)
        for _image, name in missing:
            gaps.append(f"{building_id}/{name}: missing, altered or not recorded")
        for name in stored_images(record, manifest):
            if name not in expected[building_id]:
                stale += 1
                gaps.append(f"{building_id}/{name}: recorded but no longer named by the notice")
        # A file whose hash and size agree can still be the wrong kind of file, if it
        # was written before the downloader checked signatures.
        missing_names = {name for _image, name in missing}
        for name in sorted(expected[building_id]):
            path = target_dir / name
            if name in missing_names or not path.exists():
                continue
            try:
                with path.open("rb") as handle:
                    head = handle.read(DIMENSION_HEAD_BYTES)
            except OSError as error:
                gaps.append(f"{building_id}/{name}: unreadable ({error})")
                continue
            if sniff_image_format(head) is None:
                not_pictures += 1
                gaps.append(f"{building_id}/{name}: stored bytes are not a picture")
                continue
            # The strongest check available: a hash only proves the file agrees with
            # its own manifest entry, while the size proves it is the picture the
            # notice names.
            size = declared.get(building_id, {}).get(name)
            if not size:
                # No declared size means the size cannot be checked at all. Counting it
                # keeps "size disagrees: 0" honest: without this the audit could not
                # tell "checked everything" from "checked the ones that had a size".
                # It is not a defect — if the source stopped emitting data-size, a
                # correctly parsed record would have none, and failing would make the
                # audit un-greenable. All 77,175 references had one when this was added.
                sizes_undeclared += 1
                continue
            actual = image_dimensions(head)
            if actual is None:
                # Only read further when the answer is still unknown, so the common
                # case stays at one 64 KiB read per file.
                try:
                    with path.open("rb") as handle:
                        head = handle.read(DIMENSION_HEAD_LIMIT)
                except OSError as error:
                    gaps.append(f"{building_id}/{name}: unreadable ({error})")
                    continue
                actual = image_dimensions(head)
            if actual is None:
                sizes_unchecked += 1
            elif actual != size:
                mis_sized += 1
                gaps.append(
                    f"{building_id}/{name}: {actual[0]}x{actual[1]} but the notice "
                    f"declares {size[0]}x{size[1]}"
                )

    # The other direction: anything on disk that no stored notice accounts for.
    orphan_dirs = orphan_files = 0
    for directory in sorted(image_root.iterdir()) if image_root.is_dir() else []:
        if not directory.is_dir():
            orphan_files += 1
            gaps.append(f"{directory.name}: loose file in the picture tree")
            continue
        if directory.name not in expected:
            orphans = [e.name for e in directory.iterdir() if e.is_file()]
            if orphans:
                orphan_dirs += 1
                gaps.append(
                    f"{directory.name}/: {len(orphans)} downloaded file(s) no stored "
                    "notice names"
                )
            continue
        for entry in directory.iterdir():
            if entry.is_dir():
                continue  # preview/ holds derived copies, checked by derive_previews.py
            if entry.name == "manifest.json" or entry.name in expected[directory.name]:
                continue
            orphan_files += 1
            gaps.append(f"{directory.name}/{entry.name}: not recorded in its manifest")

    defects = (incomplete + corrupt + stale + not_pictures + mis_sized + rights_incomplete
               + orphan_dirs + orphan_files)
    print(
        f"pictures named by {with_pictures} building(s): {named}\n"
        f"stored and matching:                  {stored}\n"
        f"not downloaded yet:                   {not_downloaded}"
        + (f" across {buildings_not_downloaded} building(s)" if not_downloaded else "")
        + f"\nmissing/altered despite a manifest:  {incomplete}"
        f"\nnot actually a picture:               {not_pictures}"
        f"\nsize disagrees with the notice:        {mis_sized}"
        f"\nsize unreadable (not a defect):        {sizes_unchecked}"
        f"\nno declared size (not size-checked):   {sizes_undeclared}"
        f"\nrights record incomplete:             {rights_incomplete}"
        f"\nunreadable manifests:                 {corrupt}"
        f"\nstale manifest entries:               {stale}"
        f"\norphan folders / files:               {orphan_dirs} / {orphan_files}"
    )
    if gaps:
        for gap in gaps[:25]:
            print(f"  ! {gap}")
        if len(gaps) > 25:
            print(f"  ... and {len(gaps) - 25} more")
    sys.stdout.flush()
    complete = not_downloaded == 0 and defects == 0
    print(
        f"[FINAL] {'complete' if complete else 'incomplete'}: {stored}/{named} picture(s) "
        f"stored and matching, {not_downloaded} not downloaded, {defects} defect(s)",
        file=sys.stderr,
        flush=True,
    )
    return 0 if complete else 1


def run_image_pass(fetcher: Fetcher, args) -> int:
    """Download pictures for notices already scraped, without re-fetching pages.

    Kept separate from the text crawl on purpose: a notice page fetch and an
    image fetch fail for different reasons, at very different volumes (one page
    against one picture each), and a picture that will not load must not cost the
    building its labels and description.
    """
    rights_basis = args.rights_basis
    if rights_basis not in ALLOWED_RIGHTS_BASIS:
        allowed = ", ".join(sorted(ALLOWED_RIGHTS_BASIS))
        print(
            "refusing --images-only: this source does not grant bulk image reuse.\n"
            f"Pass --rights-basis with one of: {allowed}",
            file=sys.stderr,
        )
        return 2

    image_root = image_root_for(args.image_dir)
    variant = args.image_size
    paths = stored_record_paths(args.out, args.lang)
    if args.limit is not None:
        paths = paths[: args.limit]
    if not paths:
        print(f"no stored {args.lang} records under {args.out}", file=sys.stderr)
        return 2

    failures: list[dict[str, str]] = []
    fetched = records = buildings_with_images = 0
    verified = 0
    bytes_total = 0
    consecutive = 0
    aborted = False
    abort_reason = ""
    started = time.monotonic()
    fetch_started: float | None = None
    last_robots_check = started
    interrupted = False
    # Count the work up front, reading records but no page, so every progress line
    # can state the denominator and a real ETA rather than a pace diluted by the
    # opening minutes of hashing what is already stored.
    plan = image_plan(args.out, args.lang, image_root, variant, args.limit)
    planned = int(plan["to_fetch"])  # type: ignore[call-overload]
    print(
        f"plan: {planned} picture(s) to fetch of {plan['named']} named across "
        f"{plan['with_pictures']} record(s); {plan['stored']} already stored",
        file=sys.stderr, flush=True,
    )
    try:
        for path in paths:
            records += 1
            record, error = load_stored_record(path)
            if error or record is None:
                failures.append({"target": path.name, "error": error or "unreadable"})
                continue
            building_id = record_id(record, path.name.split(".")[0])
            target_dir = image_root / building_id
            manifest_path = target_dir / "manifest.json"
            stored: dict[str, object] | None = None
            if manifest_path.exists():
                try:
                    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    stored = None  # unreadable: treat every picture as missing

            images = record.get("images") or []
            if not images:
                continue
            buildings_with_images += 1
            pending = pending_images(record, stored, target_dir, variant)

            fresh: dict[str, dict] = {}
            for image, name in pending:
                # A policy read at hour zero must not govern forty-two hours of
                # pictures. The text crawl re-reads robots.txt hourly for the same
                # reason; here it also covers what the failure guard cannot see at
                # all — the publisher *raising* the crawl delay, which produces no
                # errors while the run quietly keeps over-fetching.
                if (
                    args.robots_recheck_seconds
                    and not args.no_robots
                    and time.monotonic() - last_robots_check >= args.robots_recheck_seconds
                ):
                    last_robots_check = time.monotonic()
                    sample = urlparse(image_variant_url(image, variant)).path or "/medias/"
                    if recheck_robots(fetcher, sample, args.robots_cache):
                        aborted = True
                        abort_reason = f"robots.txt no longer allows {sample}"
                        break
                try:
                    entry = download_image(fetcher, image, target_dir, variant, name)
                except (ScrapeError, OSError) as error:
                    # One dead picture must not abandon the other twenty-five, and
                    # it has no manifest entry, so the next run retries exactly it.
                    failures.append(
                        {
                            "target": building_id,
                            "url": image_variant_url(image, variant),
                            "error": str(error)[:200],
                        }
                    )
                    consecutive += 1
                    if (
                        args.max_consecutive_image_failures
                        and consecutive >= args.max_consecutive_image_failures
                    ):
                        aborted = True
                        abort_reason = f"{consecutive} consecutive picture failure(s)"
                        break
                    continue
                fresh[str(entry["filename"])] = entry
                if fetch_started is None:
                    fetch_started = time.monotonic()
                fetched += 1
                bytes_total += int(entry["bytes"])  # type: ignore[arg-type]
                # A picture that loaded is proof the source is answering again, so
                # a cluster of broken files can never accumulate into an abort.
                consecutive = 0

            # Merge: keep every picture the notice still names, preferring the one
            # just written, so the manifest stays complete across partial passes.
            # Keyed by local name, which is what keeps two pictures that share a
            # source basename as two entries with their own URL and hash.
            if not pending:
                verified += 1
            done = stored_images(record, stored)
            entries = []
            for name in local_names(images):
                entry = fresh.get(name) or done.get(name)
                if entry:
                    entries.append(entry)

            # Publish a manifest only once something is actually stored: an empty
            # manifest for a building whose notice names pictures would read as
            # "this building has none".
            if entries:
                manifest = manifest_skeleton(record, rights_basis)
                manifest["images"] = entries
                write_manifest(target_dir, manifest)

            if args.progress_every and records % args.progress_every == 0:
                # Pace comes from the fetch window, not the whole run: a resume begins
                # by hashing what is already stored, so fetched/elapsed reads 0.00/s
                # for the first minutes and understates the rate for hours after.
                if fetch_started is None:
                    pace = "verifying"
                else:
                    rate = fetched / max(time.monotonic() - fetch_started, 0.001)
                    left = max(planned - fetched, 0)
                    pace = f"{rate:.2f}/s eta {left / rate / 3600:.1f}h"
                print(
                    f"[{records}/{len(paths)}] {building_id} · {fetched}/{planned} image(s) · "
                    f"verified {verified} · {pace} · {len(failures)} failed",
                    file=sys.stderr,
                    flush=True,
                )
            if aborted:
                # Stop rather than grind: an outage — or a policy change — should cost
                # one aborted run, not the twenty hours that remained when it started.
                print(
                    f"aborting: {abort_reason}"
                    + (f" (last: {failures[-1]['error']})" if failures else "")
                    + "; rerun --images-only to resume where this stopped.",
                    file=sys.stderr,
                    flush=True,
                )
                break
    except KeyboardInterrupt:
        interrupted = True
        print(
            "interrupted: manifests for finished buildings are already written; "
            "rerun --images-only to resume",
            file=sys.stderr,
            flush=True,
        )
    finally:
        if failures:
            args.out.mkdir(parents=True, exist_ok=True)
            write_json_atomic(args.out / f"_image_failures.{args.lang}.json", failures)

    print(
        f"{fetcher.requests} request(s), {bytes_total / 1024:.0f} KiB stored "
        f"under {image_root}"
    )
    sys.stdout.flush()
    if interrupted:
        outcome = "interrupted"
    elif aborted:
        outcome = f"aborted early ({abort_reason})"
    elif failures:
        outcome = f"finished with problems ({len(failures)} failed)"
    else:
        outcome = "complete"
    print(
        f"[FINAL] {outcome}: {fetched} {args.image_size} image(s) fetched for "
        f"{buildings_with_images} building(s) with pictures, "
        f"{records} record(s) examined, {len(failures)} failed",
        file=sys.stderr,
        flush=True,
    )
    if aborted:
        return IMAGE_EXIT_ABORTED
    return 1 if failures else 0


def summarise(record: dict[str, object]) -> str:
    identity = record["identity"]  # type: ignore[index]
    address = " ".join(
        part for part in (identity.get("street"), identity.get("house_number")) if part
    )
    city = record["city"]  # type: ignore[index]
    lines = [
        f"{record['building_id']} · {address or '(no address)'}"
        + (f", {city['name']}" if city and city.get("name") else ""),
        f"  name:  {identity.get('name') or '(unnamed)'}",
        f"  tags:  {', '.join(t['value'] for t in record['tags']) or '(none)'}",  # type: ignore[index]
        f"  desc:  {len((record['description'] or {}).get('text', ''))} chars",  # type: ignore[union-attr]
        f"  pics:  {len(record['images'])}",  # type: ignore[arg-type]
    ]
    for note in record.get("notes", []):  # type: ignore[union-attr]
        lines.append(f"  note:  {note}")
    return "\n".join(lines)


def record_path(out_dir: Path, building_id: str, lang: str) -> Path:
    return out_dir / f"{building_id}.{lang}.json"


def write_record(record: dict[str, object], path: Path) -> Path:
    write_json_atomic(path, record)
    return path


def survey_report(
    records: list[dict[str, object]],
    titles: dict[str, int],
    errors: list[dict[str, str]],
    sampled: int,
    requests: int,
) -> str:
    """Describe how well extraction holds up on a sample of real notices.

    Kept pure so the report can be tested against committed fixtures instead of
    the network.
    """
    total = len(records)
    lines = [f"sampled {sampled} notices · parsed {total} · failed {len(errors)}"]
    if not total:
        lines.append(f"errors: {errors}")
        return "\n".join(lines)

    checks: dict[str, object] = {
        "description": lambda r: r["description"] is not None,
        "sources": lambda r: r["sources"] is not None,
        "name (titled bldg)": lambda r: bool(r["identity"]["name"]),
        "house_number": lambda r: bool(r["identity"]["house_number"]),
        "multi-street address": lambda r: len(r["addresses"]) > 1,
        "coordinates": lambda r: r["coordinates"] is not None,
        "legal_status": lambda r: r["legal_status"] is not None,
        "legal_status date": lambda r: bool((r["legal_status"] or {}).get("date")),
        "interests": lambda r: bool(r["interests"]),
        "typologies": lambda r: bool(r["typologies"]),
        "styles": lambda r: bool(r["styles"]),
        "contributors": lambda r: bool(r["contributors"]),
        "inventories": lambda r: bool(r["inventories"]),
        "images": lambda r: bool(r["images"]),
        "image credits": lambda r: any(i["credit_holders"] for i in r["images"]),
        "suggestions": lambda r: bool(r["suggestions"]),
        "nearby_trees": lambda r: bool(r["nearby_trees"]),
    }
    lines.append("\nfield coverage")
    for label, test in checks.items():
        hits = sum(1 for r in records if test(r))  # type: ignore[operator]
        lines.append(f"  {label:21} {hits:3}/{total} {100 * hits / total:5.1f}%")

    street = [r["building_id"] for r in records if not r["identity"]["street"]]
    city = [r["building_id"] for r in records if not r["city"]["name"]]
    images = [r["building_id"] for r in records if not r["images"]]
    mismatch = [r["building_id"] for r in records if r["urban_id"] != r["building_id"]]
    details = [r["building_id"] for r in records if not r["details"]]
    tags = [r["building_id"] for r in records if not r["tags"]]
    captions = [
        r["building_id"] for r in records if any(not i["caption"] for i in r["images"])
    ]
    sizes = [r["building_id"] for r in records
             if any(i["width"] is None for i in r["images"])]
    lines.append("\nextraction health")
    for label, bad in (
        ("no street", street),
        ("no city", city),
        ("no images", images),
        ("urban_id mismatch", mismatch),
        ("empty details", details),
        ("no tags at all", tags),
        ("caption missing", captions),
        ("size missing", sizes),
    ):
        shown = ", ".join(bad[:6]) + ("..." if len(bad) > 6 else "")
        lines.append(f"  {label:21} {len(bad):3}  {shown}")

    unmapped: collections.Counter[str] = collections.Counter()
    for record in records:
        for label in record["details"]:  # type: ignore[union-attr]
            if label_key(label) is None:
                unmapped[label] += 1
    lines.append(f"\nunmapped h4 labels: {len(unmapped)} distinct")
    for label, count in unmapped.most_common(12):
        lines.append(f"  {count:3}x {label!r}")

    known = set()
    for group in SECTION_TITLES.values():
        known |= set(group)
    known |= {"arbres remarquables à proximité", "opmerkelijke bomen in de nabijheid"}
    unseen = {title: count for title, count in titles.items() if title not in known}
    lines.append(f"\nh3 titles outside the known set: {len(unseen)} distinct")
    for title, count in sorted(unseen.items(), key=lambda kv: -kv[1])[:12]:
        lines.append(f"  {count:3}x {title!r}")

    journal = [len(json.dumps(r, ensure_ascii=False)) for r in records]
    rubric = sum(len(i["criteria"] or "") for r in records for i in r["interests"])
    payload = sum(journal) or 1
    described = [len((r["description"] or {}).get("text", "")) for r in records]
    lines.append(
        f"\nrecord size: median {statistics.median(journal):,.0f} B "
        f"max {max(journal):,} B · total {payload / 1024:,.0f} KiB"
    )
    lines.append(
        f"interest rubric: {rubric / 1024:,.0f} KiB = {100 * rubric / payload:.0f}% of payload"
    )
    lines.append(
        f"description chars: median {statistics.median(described):,.0f} max {max(described):,}"
    )
    counts = collections.Counter(len(r["images"]) for r in records)
    lines.append(f"images per notice: {counts.most_common(8)}")
    hints = collections.Counter(
        str(i["rights_hint"]) for r in records for i in r["images"]
    )
    lines.append(f"image rights hints: {hints.most_common()}")
    lines.append(f"\nrequests: {requests} · errors: {errors}")
    return "\n".join(lines)


def run_survey(fetcher: Fetcher, args: argparse.Namespace) -> int:
    """Sample notices across the index and report extraction health."""
    payload = load_index(fetcher, args.lang)
    ids = index_ids_for_city(payload, args.city) if args.city else index_ids(payload)
    size = args.limit or 40
    stride = max(1, len(ids) // size)
    sample = ids[::stride][:size]

    records: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    titles: collections.Counter[str] = collections.Counter()

    for building_id in sample:
        url = building_url(building_id, args.lang)
        try:
            html_text = fetcher.get_text(url)
        except (ScrapeError, OSError) as error:
            errors.append({"building_id": building_id, "error": str(error)[:120]})
            continue
        try:
            records.append(build_record(html_text, url, building_id, args.lang))
        except Exception as error:  # noqa: BLE001 - the survey reports every failure
            errors.append(
                {
                    "building_id": building_id,
                    "error": f"{type(error).__name__}: {error}"[:120],
                }
            )
        root = parse_dom(html_text)
        for heading in find_all(root, tag="h3"):
            title = normalise_label(plain_text(heading))
            if title:
                titles[title] += 1

    print(survey_report(records, dict(titles), errors, len(sample), fetcher.requests))
    return 1 if errors else 0


def throughput(written: int, done: int, total: int, elapsed: float) -> tuple[float, float]:
    """Return (records/second, seconds remaining), counting only real fetches.

    Skipped records cost no time, so deriving the rate from ``done`` makes a resumed
    run look several times faster than the crawl delay permits and reports a wildly
    optimistic ETA: on a real resume, 200 fetches plus 424 skips looked like 1.45/s
    and \"eta 4.9h\" when the truth was 0.47/s and ~15h.
    """
    rate = written / elapsed if elapsed > 0 and written else 0.0
    eta = (total - done) / rate if rate else 0.0
    return rate, eta


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape pictures, tags and descriptions from monument.heritage.brussels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("targets", nargs="*", metavar="TARGET",
                        help="building id, /<lang>/buildings/<id>, or full URL")
    parser.add_argument("--lang", choices=VALID_LANGS, default="fr",
                        help="site language to scrape (default: fr)")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "scraped",
                        help="directory for per-building JSON (default: data/scraped)")
    parser.add_argument("--combined", type=Path, default=None,
                        help="also write every record into one JSON array")
    parser.add_argument("--index", action="store_true",
                        help="fetch the full building index and report its size")
    parser.add_argument("--survey", action="store_true",
                        help="sample notices and report extraction coverage and health")
    parser.add_argument("--from-index", action="store_true",
                        help="scrape ids from the cached index instead of TARGETs")
    parser.add_argument("--progress-every", type=int, default=100,
                        help="log progress every N written records to stderr (0 disables)")
    parser.add_argument("--max-consecutive-failures", type=int, default=10,
                        help="abort after this many consecutive failures, so an outage "
                             "does not burn through the remaining ids (0 disables)")
    parser.add_argument("--robots-recheck-seconds", type=float, default=3600.0,
                        help="re-read robots.txt this often during a long run (0 disables)")
    parser.add_argument("--robots-cache", type=Path, default=None,
                        help="where to cache robots.txt (default: local/monument-index); "
                             "injectable so a test cannot overwrite the real cache")
    parser.add_argument("--amend-coordinates", action="store_true",
                        help="correct stored records whose coordinates the notice states "
                             "wrongly, from the cached index and without a crawl")
    parser.add_argument("--places", action="store_true",
                        help="scrape notices de lieu (streets, squares, avenues) instead "
                             "of building notices; targets are the 4-segment address URL")
    parser.add_argument("--places-out", type=Path, default=REPO_ROOT / "local" / "scraped-places",
                        help="output directory for --places (default: local/scraped-places)")
    parser.add_argument("--from-streets", type=Path, default=None,
                        help="with --places: enumerate place targets from a building "
                             "corpus, which already links every street its buildings sit on")
    parser.add_argument("--index-file", type=Path,
                        default=REPO_ROOT / "local" / "monument-index" / "monuments.fr.json",
                        help="cached index used to resolve coordinates the notice states "
                             "wrongly; a missing file simply means the notice is trusted")
    parser.add_argument("--city", default=None,
                        help="with --from-index, restrict to a municipality code (see --list-cities)")
    parser.add_argument("--list-cities", action="store_true",
                        help="list municipalities in the index with their building counts")
    parser.add_argument("--no-robots", action="store_true",
                        help="skip reading robots.txt and use the built-in conservative policy")
    parser.add_argument("--limit", type=int, default=None,
                        help="maximum number of buildings in --from-index or --images-only mode")
    parser.add_argument("--offset", type=int, default=0,
                        help="skip the first N index entries in --from-index mode")
    parser.add_argument("--download-images", action="store_true",
                        help="download image files under local/ (needs --rights-basis)")
    parser.add_argument("--images-only", action="store_true",
                        help="download pictures for records already stored in --out, "
                             "without re-fetching notice pages (needs --rights-basis); "
                             "resumes from the per-building manifests")
    parser.add_argument("--dry-run", action="store_true",
                        help="with --images-only or --amend-coordinates: report what "
                             "would happen, and make no change")
    parser.add_argument("--verify-images", action="store_true",
                        help="check the picture tree against the stored records and "
                             "exit non-zero on any gap (missing, altered or orphan file)")
    parser.add_argument("--max-consecutive-image-failures", type=int,
                        default=DEFAULT_IMAGE_FAILURE_LIMIT,
                        help="with --images-only: stop after this many consecutive picture "
                             "failures, so a source outage does not spend the rest of a "
                             "43-hour crawl recording failures (0 disables, default: "
                             f"{DEFAULT_IMAGE_FAILURE_LIMIT})")
    parser.add_argument("--image-size", choices=IMAGE_VARIANTS, default="full",
                        help="with --download-images / --images-only: fetch the original "
                             "(default) or the ~500px thumbnail the page displays")
    parser.add_argument("--image-dir", type=Path, default=None,
                        help="where --download-images / --images-only store pictures "
                             f"(default: {DEFAULT_IMAGE_ROOT})")
    parser.add_argument("--rights-basis", default=None,
                        help="explicit reuse basis required by --download-images")
    parser.add_argument("--skip-existing", action="store_true",
                        help="skip ids whose output file already exists (resume a bulk run)")
    parser.add_argument("--fail-on-change", action="store_true",
                        help="refuse to overwrite a stored record whose content hash changed")
    parser.add_argument("--dedupe-rubrics", action="store_true",
                        help="store the repeated interest rubric once in <out>/rubrics.<lang>.json")
    parser.add_argument("--sleep", type=float, default=CRAWL_DELAY_SECONDS,
                        help=f"seconds between requests (default: {CRAWL_DELAY_SECONDS})")
    parser.add_argument("--timeout", type=float, default=60.0, help="request timeout in seconds")
    parser.add_argument("--quiet", action="store_true", help="suppress the per-building summary")
    return parser


def load_robots_policy(
    fetcher: Fetcher, force: bool = False, cache: Path | None = None
) -> RobotsPolicy:
    """Read the site's own robots.txt so the scrape follows the live policy.

    Falls back to a conservative default when the file cannot be read, and never
    lowers the effective crawl delay below the configured floor. ``force`` re-reads
    the live file instead of the cache, which a long run does periodically: a
    policy read once at hour zero should not govern fifteen hours of crawling.
    """
    target = cache or (REPO_ROOT / "local" / "monument-index" / "robots.txt")
    try:
        if target.exists() and not force:
            text = target.read_text(encoding="utf-8")
        else:
            text = fetcher.get_text(ROBOTS_URL)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        policy = parse_robots(text)
    except (ScrapeError, OSError) as error:
        print(f"warning: using default robots policy ({error})", file=sys.stderr)
        return RobotsPolicy()
    if not policy.rules:
        policy.allowed_prefixes = DEFAULT_ALLOWED_PREFIXES
    return policy


def recheck_robots(
    fetcher: Fetcher, sample_path: str, cache: Path | None = None
) -> bool:
    """Re-read robots.txt mid-run; return True when crawling must stop."""
    policy = load_robots_policy(fetcher, force=True, cache=cache)
    if not policy.allows(sample_path):
        print(
            f"stopping: robots.txt no longer allows {sample_path}; "
            "resume only once the site permits it again",
            file=sys.stderr,
            flush=True,
        )
        return True
    if policy.crawl_delay > fetcher.delay:
        print(
            f"robots.txt now asks for Crawl-delay {policy.crawl_delay}; slowing down",
            file=sys.stderr,
            flush=True,
        )
        fetcher.delay = policy.crawl_delay
    fetcher.policy = policy
    return False


def index_points_from(path: Path) -> dict[str, tuple[float, float]]:
    """The publisher's own point per building id, read from the cached index.

    Read-only on purpose: a single-target scrape must stay one request, so a missing
    cache leaves the notice's own marker as the only source rather than triggering a
    fetch. `--index` is what creates the cache. Only the first point for an id is
    kept; the index carries one feature per entrance, and for corner buildings they
    are metres apart.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    points: dict[str, tuple[float, float]] = {}
    for feature in payload.get("features") or []:
        properties = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        building_id = str(properties.get("id", "")).strip()
        if building_id and len(coordinates) == 2 and building_id not in points:
            points[building_id] = (float(coordinates[1]), float(coordinates[0]))
    return points


def load_index(fetcher: Fetcher, lang: str) -> dict[str, object]:
    """Fetch (once) the site's own building index. Cached under gitignored local/."""
    cache = REPO_ROOT / "local" / "monument-index" / f"monuments.{lang}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    url = INDEX_URL if lang == "fr" else f"{BASE_URL}/medias/monuments.{lang}.json"
    payload = json.loads(fetcher.get_text(url))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def index_city_counts(payload: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for feature in payload.get("features", []):  # type: ignore[union-attr]
        code = str(feature.get("properties", {}).get("city", "")).strip()
        if code:
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def index_ids_for_city(payload: dict[str, object], city: str) -> list[str]:
    """Unique building ids whose index entry carries this municipality code."""
    wanted = city.strip()
    ids: list[str] = []
    seen: set[str] = set()
    for feature in payload.get("features", []):  # type: ignore[union-attr]
        properties = feature.get("properties", {})
        if str(properties.get("city", "")).strip() != wanted:
            continue
        value = str(properties.get("id", "")).strip()
        if value and value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def index_ids(payload: dict[str, object]) -> list[str]:
    """Unique building ids in document order.

    The index carries one feature per entrance, so a corner building appears
    several times. Deduplicating avoids re-fetching the same notice.
    """
    ids: list[str] = []
    seen: set[str] = set()
    for feature in payload.get("features", []):  # type: ignore[union-attr]
        value = str(feature.get("properties", {}).get("id", "")).strip()
        if value and value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    install_sigterm_handler()
    fetcher = Fetcher(delay=args.sleep, timeout=args.timeout)
    if not args.no_robots:
        # Follow the live policy rather than a copy of it, and never crawl faster
        # than the site asks for.
        fetcher.policy = load_robots_policy(fetcher, cache=args.robots_cache)
        fetcher.delay = max(fetcher.delay, fetcher.policy.crawl_delay)

    wants_images = args.download_images or args.images_only
    if wants_images and args.rights_basis not in ALLOWED_RIGHTS_BASIS:
        allowed = ", ".join(sorted(ALLOWED_RIGHTS_BASIS))
        print(
            "refusing --download-images: this source does not grant bulk image reuse.\n"
            f"Pass --rights-basis with one of: {allowed}",
            file=sys.stderr,
        )
        return 2

    if wants_images and args.rights_basis == CONDITIONAL_BASIS:
        # Asserting this basis means accepting the site's stated obligations.
        obligations = SOURCE_METADATA["rights"]["obligations"]
        print(
            f"Using the conditional non-commercial basis ({CONDITIONS_URL}).",
            file=sys.stderr,
        )
        for duty in obligations["online"] + obligations["printed"]:
            print(f"  obligation: {duty}", file=sys.stderr)
        print(f"  obligation: {obligations['third_party']}", file=sys.stderr)

    if args.survey:
        return run_survey(fetcher, args)

    if args.amend_coordinates:
        return amend_coordinates(args)

    if args.places:
        return run_place_scrape(fetcher, args)

    if args.verify_images:
        # Local only: this reads the notice records and the picture tree, and makes
        # no request, so it is safe to run beside a crawl or after one.
        return verify_image_tree(args)

    if args.images_only:
        if args.dry_run:
            return report_image_plan(args)
        return run_image_pass(fetcher, args)

    if args.index or args.list_cities:
        payload = load_index(fetcher, args.lang)
        if args.list_cities:
            counts = index_city_counts(payload)
            print(f"{len(counts)} municipality codes in the {args.lang} index")
            for code, count in counts.items():
                print(f"  {code}  {count:5} feature(s)")
            return 0
        features = payload.get("features", [])
        ids = index_ids(payload)
        print(
            f"{len(ids)} unique buildings in the {args.lang} index "
            f"({len(features)} features)"  # type: ignore[arg-type]
        )
        if ids:
            print(f"first ids: {', '.join(ids[:10])}")
        return 0

    targets = list(args.targets)
    index_points: dict[str, tuple[float, float]] = {}
    if not args.index_file.exists():
        print(
            f"note: no cached index at {args.index_file}, so coordinates come from the "
            "notice alone (and its placeholder cannot be detected)",
            file=sys.stderr,
        )
    else:
        index_points = index_points_from(args.index_file)
    if args.from_index:
        payload = load_index(fetcher, args.lang)
        if args.city:
            ids = index_ids_for_city(payload, args.city)
            if not ids:
                print(f"no buildings for municipality code {args.city!r}", file=sys.stderr)
                return 2
        else:
            ids = index_ids(payload)
        targets = ids[args.offset:]
        if args.limit is not None:
            targets = targets[: args.limit]
    if not targets:
        build_parser().print_help()
        return 2

    # Only --combined needs every record in memory; a full-catalogue run would
    # otherwise hold ~26k records (hundreds of MB) until the end.
    collect = args.combined is not None
    records: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    drifted: list[str] = []
    skipped = written = 0
    consecutive_failures = 0
    aborted = False
    interrupted = False
    started = time.monotonic()
    last_robots_check = started
    total = len(targets)
    rubrics = (
        RubricStore(args.out / f"rubrics.{args.lang}.json")
        if args.dedupe_rubrics
        else None
    )
    try:
        for target in targets:
            try:
                building_id = parse_target(target)
                url = building_url(building_id, args.lang)
                path = record_path(args.out, building_id, args.lang)
                if args.skip_existing and path.exists():
                    skipped += 1
                    continue

                # A fifteen-hour crawl must not be governed by the policy snapshot
                # taken at hour zero.
                if (
                    args.robots_recheck_seconds
                    and not args.no_robots
                    and time.monotonic() - last_robots_check >= args.robots_recheck_seconds
                ):
                    last_robots_check = time.monotonic()
                    if recheck_robots(fetcher, f"/{args.lang}/buildings/{building_id}"):
                        aborted = True
                        break

                html_text = fetcher.get_text(url)
                record = build_record(
                    html_text, url, building_id, args.lang, rubrics,
                    index_points.get(building_id),
                )

                if args.fail_on_change and path.exists():
                    stored = json.loads(path.read_text(encoding="utf-8"))
                    if stored.get("extraction", {}).get("content_hash") != (
                        record["extraction"]["content_hash"]  # type: ignore[index]
                    ):
                        # Keep the stored record and the notice as they were: a silent
                        # upstream rewrite must surface, not overwrite reviewed evidence.
                        drifted.append(building_id)
                        print(
                            f"changed: {building_id}: {url} no longer matches the stored "
                            f"record (kept {path.name}, wrote nothing)",
                            file=sys.stderr,
                            flush=True,
                        )
                        continue

                if args.download_images:
                    record["downloaded_images"] = download_images(
                        fetcher, record, args.rights_basis, args.image_dir, args.image_size
                    )
                write_record(record, path)
                written += 1
                consecutive_failures = 0
                if collect:
                    records.append(record)
                if not args.quiet:
                    print(summarise(record))
                    print(f"  wrote: {path}")
            except (ScrapeError, json.JSONDecodeError, OSError) as error:
                failures.append({"target": str(target), "error": str(error)[:200]})
                consecutive_failures += 1
                print(f"error: {target}: {error}", file=sys.stderr, flush=True)
                if (
                    args.max_consecutive_failures
                    and consecutive_failures >= args.max_consecutive_failures
                ):
                    # An outage should cost one aborted run, not thousands of
                    # wrongly-failed ids; --skip-existing resumes cleanly later.
                    print(
                        f"aborting: {consecutive_failures} consecutive failure(s) "
                        f"(last: {error}); rerun with --skip-existing to resume",
                        file=sys.stderr,
                        flush=True,
                    )
                    aborted = True
                    break

            # Persist the rubric store as we go: one run over the whole catalogue
            # lasts hours, and records already reference these rubrics.
            if rubrics is not None and written and written % RUBRIC_SAVE_EVERY == 0:
                rubrics.save()
            if args.progress_every and written and written % args.progress_every == 0:
                elapsed = max(time.monotonic() - started, 0.001)
                done = written + skipped
                rate, eta = throughput(written, done, total, elapsed)
                print(
                    f"[{done}/{total}] {building_id} · {written} fetched · "
                    f"{rate:.2f}/s · eta {eta / 3600:.1f}h · "
                    f"{len(failures)} failed · {len(drifted)} changed",
                    file=sys.stderr,
                    flush=True,
                )
    except KeyboardInterrupt:
        interrupted = True
        print(
            "interrupted: progress and rubric store saved; "
            "rerun with --skip-existing to resume",
            file=sys.stderr,
            flush=True,
        )
    finally:
        # An interrupted long run must still leave a usable store and failure list.
        if rubrics is not None and written:
            rubrics.save()
        if failures:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"_failures.{args.lang}.json").write_text(
                json.dumps(failures, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    if args.combined is not None and records:
        args.combined.parent.mkdir(parents=True, exist_ok=True)
        args.combined.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"wrote {len(records)} record(s) to {args.combined}")

    if rubrics is not None and written:
        store_path = rubrics.save()
        if not args.quiet and store_path is not None:
            print(
                f"{len(rubrics.entries)} shared rubric(s) in {store_path}"
                + (
                    f" ({len(rubrics.redefined)} redefined since the last run)"
                    if rubrics.redefined
                    else ""
                )
            )
        for key in rubrics.redefined:
            print(
                f"warning: rubric {key!r} differs from the stored text; "
                "the source may have edited its catalogue rubric",
                file=sys.stderr,
            )

    if not args.quiet:
        print(
            f"{fetcher.requests} request(s), {fetcher.bytes / 1024:.0f} KiB"
            + (f", {skipped} skipped, {len(drifted)} changed" if skipped or drifted else "")
        )

    # A detached run's log is its only observability, so its terminal state has to
    # be stated. Without this a finished run and a crashed one look identical:
    # both simply stop after the last progress line. Flush stdout first: it is
    # block-buffered when redirected, so otherwise the summary lands after this.
    sys.stdout.flush()
    if interrupted:
        outcome = "interrupted"
    elif aborted:
        outcome = "aborted early"
    elif failures or drifted:
        outcome = f"finished with problems ({len(failures)} failed, {len(drifted)} changed)"
    else:
        outcome = "complete"
    print(
        f"[FINAL] {outcome}: {written} written, {skipped} skipped, "
        f"{len(failures)} failed, {len(drifted)} changed, of {total} target(s)",
        file=sys.stderr,
        flush=True,
    )
    return 1 if failures or drifted or aborted else 0


if __name__ == "__main__":
    sys.exit(main())

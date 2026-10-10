# Three Ages prototype

A dependency-free browser explorer backed by source-linked Grand Place records, imagery and provenance-safe human review exports. Offline image processing requires Pillow.

## Setup and complete validation

From the repository root:

```bash
python3 -m pip install -r prototypes/requirements.txt
scripts/validate-prototypes.sh
```

The gate regenerates all derived artifacts, verifies completed-review preservation, provenance-change refusal, no-partial-write behavior and explicit reset behavior in isolated copies, validates snapshot invariants, compiles Python, exercises the browser UI, strictly parses JSON and runs `git diff --check`. CI runs `--check-clean` on Python 3.10 and 3.13 to reject stale, missing or version-dependent artifacts.

## Run locally

```bash
cd prototypes
python3 -m http.server 8000
```

Open <http://localhost:8000/three-ages/>.

To validate only committed snapshot invariants:

```bash
cd prototypes
python3 validate_snapshots.py
```

## Regenerate review artifacts

```bash
python3 prototypes/three-ages/generate_structural_crops.py
python3 prototypes/three-ages/export_pilot.py
```

The crop generator projects each building coordinate into shared WMS bounds, applies the same 160-pixel box to all four epochs and records stable pixel hashes. These crops are review aids, not structural observations.

The exporter produces building, facade-image, structural-comparison and register-semantics worksheets. It preserves completed human fields only while exact source provenance matches. Completed rows require reviewer, ISO-8601 date and `low`, `medium` or `high` confidence. Register decisions use one controlled value:

- `accept proxy for MVP`
- `retain as reconstruction evidence`
- `reject source mapping`

Completed rows compile to the corresponding `three-ages-*-reviews.json` artifact and appear beside evidence in the explorer. Regeneration refuses changed or removed assets, crop pixels, identity notes, source semantics or comparisons without modifying any output. Use `--reset-reviews` only to deliberately clear all three review worksheets.

## Refresh source data

Refresh the City of Brussels Grand Place snapshot and live-check its catalogue licence, publisher and attributions:

```bash
python3 prototypes/fetch_open_data.py
```

Refresh the Irismonument (Brussels architectural heritage inventory) WFS layer — the multi-era label pool for the training corpus (see `docs/facade-style-vocabulary.md`):

```bash
python3 prototypes/fetch_irismonument.py
```

The WFS layer exposes the inventory's own style, build-year, typology, architect, location and first-image fields (~40,900 records). Metadata is CC0 per the BruGIS layer page; the `FIRSTIMAGE` photos on monument.heritage.brussels are © KIK-IRPA/urban.brussels and are not downloaded until their licence is verified (see the training-licence task).

The Irismonument selector currently stores up to ten examples per class (`sample`), not every candidate in each class. BALaT acceptance requires an exact street + whole-house-number match, `rights_consent_status=free`, the photo page's own title matching the address, and a visible CC BY 4.0 badge. Per-photo capture date, represented detail, credit and checksum are recorded. Run a smoke-sized pass or the full bounded selector sample with a separate provenance output:

```bash
python3 prototypes/fetch_balat_photos.py --selection prototypes/three-ages/data/irismonument-case-selection.json --limit-per-class 1 --output /tmp/balat-validation.json
python3 prototypes/fetch_balat_photos.py --selection prototypes/three-ages/data/irismonument-case-selection.json --offset-per-class 0 --limit-per-class 10 --output /tmp/balat-selector-sample.json
python3 prototypes/fetch_balat_photos.py --selection prototypes/three-ages/data/irismonument-case-selection.json --sample-field additional_sample --output /tmp/balat-selector-second-sample.json
```

The report includes per-class matches/downloads, unique buildings/photos, and catalogue view-scope counts. The default command remains the six-case identity-validation pilot. Unmatched candidates stay visible in provenance and must not enter the training set. The full candidate pool has not yet been exported from the selector, so even all ten stored samples per class are not a full-corpus acquisition run.

Curate openly licensed Commons facade photos (Wikidata-address join, style-category sweep, WLM filename join) into the same gated flow. Agent-accepted rows only; review fields start blank:

```bash
python3 prototypes/build_commons_provenance.py
python3 prototypes/three-ages/export_commons_review.py
```

This stages `three-ages/data/commons-photo-provenance.json` (match records with per-file licence, ShareAlike flag, artist credit and SHA-256), 800px previews under `three-ages/data/historical/commons/`, and the `commons-photo-review.csv` worksheet (one row per photo) compiling to `commons-photo-reviews.json`. Join hygiene: strip photo dates and parenthetical counters from filenames before number matching, and never substring-match street names. Unviewed candidates stay out of the repo until they pass the visual identity gate.

Label the verified photos (one row per unique photo) with the signed-off vocabulary term:

```bash
python3 prototypes/three-ages/export_balat_review.py
```

This writes `three-ages/data/balat-photo-review.csv` (provenance columns plus blank `facade_label`, observation, reviewer and confidence fields) and compiles completed rows to `three-ages/data/balat-photo-reviews.json`. Regeneration preserves existing reviews and refuses to attach a review after its photo provenance changed. Wide street-level sweeps confirmed the remaining misses are genuine absences (BALaT holds no exact-address photo for those buildings), not query failures.

Before any training export, prepare blind independent worksheets for the pilot and scaled photo sources, create the standalone ZIP with `build_independent_review_bundle.py`, and import its returned copy with `import_independent_review_bundle.py --bundle <zip>`. Then generate adjudication sheets after both reviewers finish:

```bash
python3 prototypes/three-ages/export_independent_review.py
python3 prototypes/three-ages/compare_independent_reviews.py --channel balat
python3 prototypes/three-ages/compare_independent_reviews.py --channel commons
```

Record agreement, rationale, disposition, adjudicator, date, resolved facade label and post-adjudication confidence in each photo adjudication CSV. The training exporter now requires distinct primary and independent reviewers plus a complete, current disposition; non-comparable cases, unresolved labels, non-vocabulary labels, non-CC-BY licences (including SPRB-agent photos), or missing checksums are excluded and listed. The resolved label and confidence—not provisional primary values—are exported. Publishing model weights is outside the EHB non-commercial education framing — review before publishing any trained artifact (see `docs/irismonument-image-licence.md`).

Refresh checksum-pinned imagery:

```bash
python3 prototypes/three-ages/download_bruciel_1935_preview.py
python3 prototypes/three-ages/download_bruciel_1971_preview.py
python3 prototypes/three-ages/download_bruciel_preview.py
python3 prototypes/three-ages/download_urbisgrid_preview.py
python3 prototypes/three-ages/download_kik_previews.py
python3 prototypes/three-ages/download_commons_previews.py
python3 prototypes/three-ages/download_british_library_preview.py
```

The downloaders verify source-specific metadata, rights statements and expected SHA-256 before replacing evidence. A changed checksum requires source inspection and a deliberate provenance update.

## Current evidence

The prototype contains:

- 34 City of Brussels Grand Place records under catalogue CC BY 4.0 terms;
- six curated source-linked cases;
- six explicit register-date proxies with source semantics and comparison state;
- aligned 1930–1935, 1971, 1996 and 2022 area-level ortho previews;
- twenty-four deterministic building-centred structural crops;
- twelve KIK-IRPA facade previews under CC BY 4.0 (five 1941–1942, plus 1890, four 1969 and one 1984);
- an exact-case 1878 British Library engraving and 2011 Wikimedia Commons photograph for La Balance;
- separate image, structural and register review channels.

Historical source access is demonstrated; identity confirmation, visible-change interpretation and reviewed labels remain human tasks. Source-specific terms and credits are authoritative in [`three-ages/data/source-inventory.json`](three-ages/data/source-inventory.json).

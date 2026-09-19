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

The crop generator projects each building coordinate into shared WMS bounds, applies the same 160-pixel box to all three epochs and records stable pixel hashes. These crops are review aids, not structural observations.

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

Refresh checksum-pinned imagery:

```bash
python3 prototypes/three-ages/download_bruciel_1935_preview.py
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
- aligned 1930–1935, 1996 and 2022 area-level ortho previews;
- eighteen deterministic building-centred structural crops;
- five 1941–1942 KIK-IRPA facade previews under CC BY 4.0;
- an exact-case 1878 British Library engraving and 2011 Wikimedia Commons photograph for La Balance;
- separate image, structural and register review channels.

Historical source access is demonstrated; identity confirmation, visible-change interpretation and reviewed labels remain human tasks. Source-specific terms and credits are authoritative in [`three-ages/data/source-inventory.json`](three-ages/data/source-inventory.json).

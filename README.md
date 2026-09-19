# Three Ages of a Brussels Building

An evidence-led prototype for comparing a building's register/source dates, facade evidence and structural imagery without collapsing disagreement into one “true” construction year.

The repository contains a 34-building City of Brussels Grand Place snapshot and six curated pilot cases. It keeps official descriptions, reconstruction-date proxies, historical imagery, aligned structural crops and human review decisions as separate, source-linked evidence.

## Repository map

- [`prototypes/three-ages/`](prototypes/three-ages/) — browser explorer, source data, images, review worksheets and generators
- [`docs/three-ages-annotation-spec.md`](docs/three-ages-annotation-spec.md) — evidence and review schema
- [`docs/three-ages-demo-script.md`](docs/three-ages-demo-script.md) — five-minute review flow
- [`docs/three-ages-source-access.md`](docs/three-ages-source-access.md) — source, licence and access status
- [`docs/prototype-review.md`](docs/prototype-review.md) — current evidence assessment
- [`docs/prototype-next-iteration.md`](docs/prototype-next-iteration.md) — curated-MVP definition of done

## Setup

Requirements: Python 3.10+, Node.js 22+ and Pillow.

```bash
python3 -m pip install -r prototypes/requirements.txt
scripts/validate-prototypes.sh
```

The gate regenerates structural crops and exports, validates source and review provenance, tests preservation/refusal/reset behavior in isolated copies, compiles Python, exercises the browser UI, strictly parses JSON and checks artifact permissions. CI runs the same gate with `--check-clean` on Python 3.10 and 3.13.

## Run locally

```bash
cd prototypes
python3 -m http.server 8000
```

Open <http://localhost:8000/three-ages/>.

See [`prototypes/README.md`](prototypes/README.md) for refresh, export and review commands.

## Evidence boundary

This is a source-grounded evidence prototype, not a completed building chronology. Register years remain explicitly typed proxies until reviewed; source imagery is not itself an annotation; aligned crops are review aids rather than structural-change findings.

## Licensing

Source-specific reuse terms and required credits are recorded in [`prototypes/three-ages/data/source-inventory.json`](prototypes/three-ages/data/source-inventory.json) and displayed in the interface. No repository-wide software or documentation licence has been declared; do not infer one asset's terms apply to another.

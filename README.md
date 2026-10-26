# Three Ages of a Brussels Building

An evidence-led prototype for comparing a building's register/source dates, facade evidence and structural imagery without collapsing disagreement into one “true” construction year.

The repository contains a 34-building City of Brussels Grand Place snapshot and six curated pilot cases. It keeps official descriptions, reconstruction-date proxies, historical imagery, aligned structural crops and human review decisions as separate, source-linked evidence.

## Repository map

- [`prototypes/three-ages/`](prototypes/three-ages/) — browser explorer, source data, images, review worksheets and generators
- [`ocaml/`](ocaml/) — experimental OCaml/Bonsai evidence-review slice using the same JSON artifacts
- [`prototypes/three-ages/training/README.md`](prototypes/three-ages/training/README.md) — ML data isolation, byte-pinned features, development evaluation and human review workflow
- [`docs/three-ages-annotation-spec.md`](docs/three-ages-annotation-spec.md) — evidence and review schema
- [`docs/three-ages-demo-script.md`](docs/three-ages-demo-script.md) — five-minute review flow
- [`docs/three-ages-source-access.md`](docs/three-ages-source-access.md) — source, licence and access status
- [`scripts/monument-corpus-pipeline.sh`](scripts/monument-corpus-pipeline.sh) — unattended scrape of the whole architectural inventory (26,419 notices) plus its verifiers
- [`docs/prototype-review.md`](docs/prototype-review.md) — current evidence assessment
- [`docs/prototype-next-iteration.md`](docs/prototype-next-iteration.md) — curated-MVP definition of done
- [`docs/three-ages-review-packet.md`](docs/three-ages-review-packet.md) — human review checklist and controlled decisions

## Setup

Requirements: Python 3.10+, Node.js 22+, opam and an OCaml 5.2 toolchain.

```bash
python3 -m pip install -r prototypes/requirements.txt
opam switch create . 5.2.1 --yes
eval "$(opam env --switch=.)"
opam install ./ocaml/three_ages.opam --deps-only --yes
npm ci --prefix ocaml
scripts/validate-prototypes.sh
scripts/validate-bonsai.sh
```

If the project-local opam switch already exists, skip `opam switch create` and
run the remaining commands.

The prototype gate regenerates structural crops and exports, validates source and review provenance, tests preservation/refusal/reset behavior in isolated copies, compiles Python, exercises the browser UI, strictly parses JSON and checks artifact permissions. The Bonsai gate builds the JavaScript bundle and tests draft contracts, review decoding, case-switch isolation and download attribution. CI runs the prototype gate with `--check-clean` on Python 3.10 and 3.13 and runs the Bonsai gate on OCaml 5.2 and Node.js 22.

The optional synthetic ML contract gate is `scripts/validate-ml.sh` in an
environment with PyTorch, NumPy and scikit-learn. It needs no corpus, model
weights or GPU and also runs in CI. See the ML workflow above for actual data
and feature-generation prerequisites.

## Run locally

```bash
cd prototypes
python3 -m http.server 8000 --bind 127.0.0.1
```

Open <http://localhost:8000/three-ages/>.

For remote review over Tailscale, start the server on the Tailscale interface:

```bash
bash scripts/serve-tailscale.sh
```

It prints the Tailscale URLs for the explorer and review workbench. It selects an available ephemeral port by default; set `PORT=8080` or `TAILSCALE_IP=100.x.y.z` when needed. This does not configure `tailscale serve`; it binds the local server only to the selected Tailscale address.

See [`prototypes/README.md`](prototypes/README.md) for refresh, export and review commands.

## Evidence boundary

This is a source-grounded evidence prototype, not a completed building chronology. Register years remain explicitly typed proxies until reviewed; source imagery is not itself an annotation; aligned crops are review aids rather than structural-change findings.

## Licensing

Source-specific reuse terms and required credits are recorded in [`prototypes/three-ages/data/source-inventory.json`](prototypes/three-ages/data/source-inventory.json) and displayed in the interface. No repository-wide software or documentation licence has been declared; do not infer one asset's terms apply to another.

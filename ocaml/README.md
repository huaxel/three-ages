# Three Ages — OCaml/Bonsai slice

This is the first vertical slice of the Three Ages explorer. It deliberately
keeps the existing Python acquisition/export pipeline and models the review UI
in OCaml/Bonsai.

## Local setup

The repository uses a project-local opam switch. From the repository root:

```bash
opam switch create . 5.2.1 --yes
eval $(opam env --switch=.)
opam install ./ocaml/three_ages.opam --deps-only --yes
npm ci --prefix ocaml
```

Build and serve the release-optimized browser bundle:

```bash
./ocaml/run.sh
```

The validation gate also runs draft and review-decoding contract tests plus a
Bonsai VDOM interaction test covering draft edits, active-case re-clicks, case
switches and download attribution.

Open <http://localhost:8000/ocaml/index.html>. Set `PORT=8080` to use another port.

## Current boundary

The build embeds and decodes `prototypes/three-ages/data/three-ages-pilot.json`
with Yojson and joins identity labels from the canonical Grand Place building
snapshot, so the case list remains source-driven.
The screen now also renders aligned structural crop epochs as review aids and
includes a local reactive draft facade-review form with evidence-asset and
confidence controls. The draft is intentionally not persisted; `draft.ml`
defines the completeness and JSON boundary, and complete source-and-asset
specific drafts expose a client-side JSON download link
without mutating source artifacts.
Python-generated CSV/JSON review artifacts remain the source of truth. Completed reviewer rows are decoded and
displayed when present. The JavaScript explorer remains the reference until
feature parity is established.

### Scope gap: this slice renders the curated pilot only

The slice embeds `three-ages-pilot.json` and renders each case's own `image_evidence`, so it
displays **12 of the 67 images** the review worksheet contains, across the 6 curated pilot
cases. It does not embed `three-ages-image-cases.json`, `facade-image-commons.json` or
`facade-units.json`.

The JavaScript explorer was widened to read the generated `three-ages-image-cases.json` and
now reaches all 27 facade units. This slice has not been widened, deliberately: the opam
switch in the working tree is unusable, so a change here could not be built or tested. Reach
parity by embedding `three-ages-image-cases.json`, iterating its cases instead of
`image_evidence`, and rendering buildings that carry images but no register claim — the same
change the explorer required.

`prototypes/test_bonsai_data_contract.py` runs in the fast Python gate and fails if a data
change drops or renames a field this slice reads, so the separate OCaml build cannot be
broken silently.

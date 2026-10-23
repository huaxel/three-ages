# OCaml/Bonsai boundary

The migration is deliberately incremental:

```text
Python acquisition/image tooling
        │
        │ committed JSON review artifacts
        ▼
OCaml model + Yojson decoder
        │
        ▼
Bonsai reactive evidence-review UI
        │
        │ browser bundle via Dune's js_of_ocaml mode
        ▼
HTML/CSS and existing image assets
```

## What OCaml owns

- `Claim_status` and `Draft_confidence` variants;
- evidence and structural-crop records;
- decoding the canonical pilot, building identities and compiled review JSON;
- selected-case state and the local draft-review interaction;
- rendering explicit pending/proxy/source-description/documented-proxy/reviewed boundaries;
- case-switch and draft-download behavior covered through Bonsai VDOM tests.

## What Python continues to own

- public-data acquisition and source snapshots;
- image downloads and structural crop generation;
- provenance checks and review CSV preservation;
- compiled review JSON exports.

This boundary keeps the language experiment focused on domain modeling and
reactive UI design instead of rewriting reliable data-ingestion code. Local
draft edits are intentionally not persisted yet: the existing review exporter
remains the authority until a future Bonsai form is designed to preserve the
same provenance and reset contracts.

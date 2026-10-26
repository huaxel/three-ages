# Evidence behind the reported numbers

## Validity notice — 2026-10-25

Historical retrieval reports have shared-image split leakage and image-level
intervals that ignore grouping. They remain evidence of the experiments run,
not clean generalisation claims. `shared-image-audit-20261025.json` records the
full corpus audit summary and a zero-cross-split verification of separately
quarantined manifests. No clean retraining or new holdout evaluation is included.
See [the validity update](../../../../docs/three-ages-finetune-pilot-result.md).

Small, human-readable report files. No images, no caches, no checkpoints — those
stay in `local/training/` and are ignored.

| file | what it is |
|---|---|
| `drawing-grouped-development-20261025.json` | fresh byte-pinned frozen drawing/source-proxy CV, train+val only; grouped metrics, all age slices and OOF integrity checks |
| `drawing-development-protocol-20261025.json` | fixed development protocol pinned before scoring; not a locked test protocol |
| `sequence-metadata-coverage-20261025.json` | metadata-only availability: no native sequence fields in 41,046 cached image records; UNKNOWN coverage, not sequence isolation |
| `capture-era-scope-audit-20261025.json` | metadata-only proof that historical dating scores included drawing-flagged rows |
| `report_test_final_v2.json` | test split, random-order checkpoint (hashed inputs, 95% CIs) |
| `report_test_hardneg.json` | test split, validation-selected hard-negative checkpoint |
| `pilot-*__report.json` | one training run each: config, data hashes, both validation arms |
| `report_neighbour_control.json` | near-neighbour control with the computed chance floor |
| `report_neighbour_epochs.json` | same control, epoch 1 vs epoch 2 |
| `report_neighbour_hardneg.json` | same control for the hard-negative seeds |
| `report_curated_slice.json` | out-of-source check on KIK-IRPA/IDPS/Commons previews |
| `report_drawing_*` / `report_capture_era_*` | the linear probes for frozen, random-order and the recommended checkpoint |

`../verify_documented_numbers.py` asserts every headline figure in
`docs/three-ages-finetune-pilot-result.md` against these files and runs as part of
`scripts/validate-prototypes.sh`, so the document cannot drift from its evidence
without the gate failing.

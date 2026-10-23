# Evidence behind the reported numbers

Small, human-readable report files. No images, no caches, no checkpoints — those
stay in `local/training/` and are ignored.

| file | what it is |
|---|---|
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

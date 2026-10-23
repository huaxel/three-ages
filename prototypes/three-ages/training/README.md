# Fine-tuning code (artifacts live in local/training)

This directory holds the **tracked** code; the manifests, feature caches,
checkpoints, run directories and logs it works on live in `local/training/`,
which stays gitignored (pixels and multi-GB artifacts never enter the repository,
and `prototypes/test_local_ingest.py` enforces that). Pass `--run-dir` under
`local/training/` as the examples below do.

Several near-identical reports accumulated while the pilot was corrected, so read
this before quoting a number. The narrative lives in
[`docs/three-ages-finetune-pilot-result.md`](../../docs/three-ages-finetune-pilot-result.md).

## Current — quote these

| artifact | what it is |
|---|---|
| `report_test_hardneg.json` | **The test-split result for the selected (hard-negative) checkpoint.** Hashed inputs, 95% CIs. |
| `report_test_final_v2.json` | Test result for the earlier random-order checkpoint; kept for the comparison. |
| `report_neighbour_control.json` | Neighbour control: train rows excluded, per-query chance computed. |
| `report_neighbour_epochs.json` | Same control, epoch 1 vs epoch 2. |
| `report_curated_slice.json` | Out-of-source check on KIK-IRPA/IDPS/Commons previews (n=72). |
| `report_drawing_frozen_venv.json`, `report_capture_era_frozen_venv.json` | Frozen probe baselines in the **same toolchain** as the tuned runs. |
| `report_drawing_tuned.json`, `report_capture_era_tuned.json` | Tuned probes. Compare against the `_frozen_venv` files, not `_full`. |
| `embeddings_refresh2e.npz` | Caches for the **default** checkpoint: hard negatives, 2 epochs, fresh pairs per epoch. Also `mapillary_embeddings_hard42.npz` for the cross-pole arm. |
| `embeddings_frozen_venv.npz`, `embeddings_hard42.npz` | Frozen baseline and the one-epoch hard-negative checkpoint (`--index hard1`). |
| `embeddings_tuned_seed42.npz`, `mapillary_embeddings_tuned_seed42.npz` | Caches for the earlier random-order checkpoint. |

## Superseded — kept for history, do not quote

| artifact | why |
|---|---|
| `report_test_final.json` | Mixed toolchains and no provenance; replaced by `_v2` with identical numbers. |
| `report_neighbour_control_v1_alltrain.json` | Its gallery included train rows and it had no chance floor. |
| `embeddings.npz`, `mapillary_embeddings.npz` | Built with system Python; a **different torchvision resize path** than the ROCm venv, so they differ by up to 0.013/component from venv-built vectors. Still the reference for "what the frozen project shipped", not for comparisons against tuned runs. |
| `report_drawing_full.json`, `report_capture_era_full.json`, `report_style*.json`, `report_retrieval*.json` | Pre-fine-tuning measurements from the old cache; fine for the frozen story, not comparable to the venv tables. |

## Runs

- `pilot-20261022-232106/` — **the checkpoint to use** (seed 42, epoch 1).
- `pilot-seed7-20261023-002018/` — reproducibility seed.
- `pilot-epoch2-20261023-105251/` — second epoch from the seed-42 checkpoint; kept because the negative result is the point.
- `pilot-hard3-*` and `pilot-hard-seed7-*` — **best validation results** (visual hard negatives, one epoch each, seeds 42 and 7).
- `pilot-hard-epoch2-*` — second epoch on hard negatives; **rejects** the "easy negatives caused saturation" explanation.
- `pilot-refresh2e-*` — two epochs drawing a **fresh pair sample each epoch**; the collapse disappears, so the cause was repeating fixed pairs.
- `pilot-hardneg-*`, `pilot-hard2-*` — abandoned attempts: location-grouped batches made negatives easier (measured), and the first hard-batch builder skipped pairs (coverage bug, caught by a unit test).
- `resume-smoke-*`, `pilot-smoke-*` — plumbing checks, not results.

Each run holds `report.json` (hashes, config, both validation arms),
`progress.json`, `checkpoint.pt`, and `summary.md` where the sumraiser ran.

## Commands

```bash
~/.venvs/rocm/bin/python prototypes/three-ages/training/train_local_pilot.py --run-dir <new dir>      # one epoch
python3 prototypes/three-ages/training/run_pilot_job.py <new dir> --seed 7                            # with 2h watchdog
python3 prototypes/three-ages/training/run_pilot_job.py <new dir> --negatives hard --seed 7           # one epoch
python3 prototypes/three-ages/training/run_pilot_job.py <new dir> --negatives hard --epochs 2 --refresh-pairs  # best so far
python3 prototypes/three-ages/training/run_pilot_job.py <new dir> --resume <ckpt>                     # continue
python3 prototypes/three-ages/training/summarise_pilot.py <run dir>                                   # refuses incomplete runs
python3 prototypes/three-ages/training/eval_test_once.py                                              # test split; refuses overwrite
python3 prototypes/three-ages/training/eval_neighbour_control.py                                      # neighbour control
python3 prototypes/three-ages/training/eval_curated_slice.py                                          # out-of-source check
python3 prototypes/three-ages/training/three_ages.py --building <id> --cross-era                      # default = best checkpoint
python3 prototypes/three-ages/training/three_ages.py --building <id> --cross-era --index frozen       # or hard1 / random1
python3 prototypes/three-ages/training/test_three_ages.py                                             # 7 utility invariants
~/.venvs/rocm/bin/python prototypes/three-ages/training/test_local_pilot.py                           # 7 offline checks
```

Two catches learned the hard way: always set `HF_HUB_OFFLINE=1` so weights come
from `/mnt/ai_models` instead of the Hub, and never mix caches from different
`toolchain=` values in one comparison.

## Provenance checks already performed

Every cache quoted above was verified against the canonical builder rather than
trusted, because two of them predate the `toolchain=` field:

| cache | check | result |
|---|---|---|
| `embeddings.npz` (frozen) | system-Python re-encode, 120 ids | 0.0 |
| `embeddings_frozen_venv.npz` | built by `build_embeddings.py`, field recorded | — |
| `embeddings_tuned_seed42.npz` | venv `--checkpoint` re-encode, 25 ids | 0.0 |
| `mapillary_embeddings.npz` (frozen) | venv re-encode, 25 ids | 2e-6 |
| `mapillary_embeddings_tuned_seed42.npz` | venv `--checkpoint` re-encode, 25 ids | 0.0 |

So every number in the summary tables traces to the same build, and to the
checkpoint named there.

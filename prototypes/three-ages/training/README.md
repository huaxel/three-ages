# Fine-tuning code (artifacts live in local/training)

This directory holds the **tracked** code; the manifests, feature caches,
checkpoints, run directories and logs it works on live in `local/training/`,
which stays gitignored (pixels and multi-GB artifacts never enter the repository,
and `prototypes/test_local_ingest.py` enforces that). Pass `--run-dir` under
`local/training/` as the examples below do.

Several near-identical reports accumulated while the pilot was corrected, so read
this before quoting a number. The narrative lives in
[`docs/three-ages-finetune-pilot-result.md`](../../../docs/three-ages-finetune-pilot-result.md).

## Validity and safe workflow — 2026-10-25

Historical retrieval numbers below have exact-image split leakage; they are
exploratory, not clean generalisation estimates. See the
[validity update](../../../docs/three-ages-finetune-pilot-result.md).
The old test cohort is spent. Do not tune against it or silently overwrite reports.

1. Audit bytes/source IDs and write **new** manifests (never replace originals):
   ```bash
   python3 prototypes/three-ages/training/data_integrity.py --out-dir local/training/image-isolated-NEW
   ```
   This quarantines all copies of cross-split shared source IDs/exact bytes.
   It does not detect near-duplicates or validate building identity. Training and
   evaluation recompute exact-image isolation; they refuse the old leaking inputs.
2. Prepare a human identity audit of actual sampled training pairs:
   ```bash
   python3 prototypes/three-ages/training/prepare_pair_audit.py --out-dir local/training/pair-audit-NEW
   ```
   Open `index.html`; record correct/ambiguous/incorrect identity and reviewer
   evidence in `reviews.csv`. Metadata pins input/sampler hashes and seeds.
   The default audits the original seed-42 training distribution, not hypothetical
   clean training. Pass cleaned `--publisher-manifest`/`--mapillary-manifest` to
   audit a future distribution. No automatic identity judgement is made.
3. Any clean retraining must start **fresh**, explicitly selecting the new
   manifests with `train_local_pilot.py --publisher-manifest ...
   --mapillary-manifest ...`. Old checkpoints lack matching isolated-manifest
   provenance and cannot be resumed as clean runs. Retraining has not been run.
4. Use development validation for selection. `train_probe.py` defaults to
   `--eval-split val`, requires non-existing `--out`, and enforces applicability
   for construction labels via mandatory `--image-reviews`; a building-wide
   depicts flag is no longer sufficient. The dating head now accepts only explicitly
   photo-flagged dated rows; historical mixed-media scores are not photo-only baselines. Supply `--image-root` for non-default image stores.
5. Freeze a new evaluation cohort before confirmation. `eval_test_once.py`
   requires `--acknowledge-spent-test` for exploratory legacy-cohort reuse,
   verified training-manifest provenance and checkpoint-matched caches with
   identical recorded toolchains. It reports paired grouped differences, not
   image-independent Wilson claims. Filtering old evaluation inputs alone does
   not make contaminated checkpoints clean.

Prepared local artifacts: `image-isolated-20261025/` (quarantined manifests and
full audit), `pair-audit-20261025/` (40 unreviewed actual training pairs), and
`frozen-isolated-20261025/batch64/` (completed byte-pinned frozen cache and
development-only drawing report).
The compact audit summary is in `evidence/shared-image-audit-20261025.json`.
Human identity review, per-image applicability, new holdout selection and clean
retraining remain open; existing images, reviews and weights were not changed.

## Near-image and acquisition diagnostics

`near_image_audit.py` is a **read-only diagnostic**, not an identity classifier,
training gate or automatic deduplicator. It writes a NEW `audit.json` and
`fingerprints.csv`, separating exact raw decoder RGB arrays (the current encoder's
conversion semantics), EXIF-normalized RGBA arrays, and cross-split dHash review
candidates. Pixel equivalence is decoder/build-specific; Pillow/codecs and source
hashes are recorded. Reconfirm actual encoder preprocessing/toolchain before
using these groups as model dependencies. Perceptual collisions are not proof
of duplicates or common building identity; crops/rotations/edits may be missed.

A bounded smoke check, **not an incidence estimate**:

```bash
python3 prototypes/three-ages/training/near_image_audit.py \
  --publisher-manifest local/training/image-isolated-20261025/manifest.csv \
  --mapillary-manifest local/training/image-isolated-20261025/mapillary_manifest.csv \
  --limit-per-pole 20 --out-dir local/training/near-image-smoke-NEW
```

Omit `--limit-per-pole` only for an intentional full supplied-manifest scan;
large image collections can take substantial CPU/I/O time. Decode/byte/pixel
failures, multi-frame inputs, low-information exclusions, comparison budgets,
and retained-candidate truncation are explicit. `--max-bucket-visits` bounds
search work; `--max-candidates` limits retained pairs, not the number searched.
A completed eligible-hash search never establishes overall image isolation.
No groups are merged, images removed, splits reassigned or labels manufactured.

Capture sequences require **native IDs**, not shared photographers, timestamps
or nearby locations. Future cached `sequence_id` or `sequence`/`sequence.id`
evidence is preserved by the Mapillary builder; missing evidence stays blank.
Generate a new CSV from an existing cache, never replace pinned manifests:

```bash
mkdir -p local/training/sequence-source-NEW
python3 prototypes/three-ages/training/build_mapillary_manifest.py \
  --out local/training/sequence-source-NEW/mapillary.csv
python3 prototypes/three-ages/training/sequence_metadata.py \
  --manifest local/training/sequence-source-NEW/mapillary.csv \
  --out local/training/sequence-source-NEW/coverage.json
```

The metadata-only CLI decodes no images. Reports distinguish directly observed
row/unique-source coverage from memberships propagated through identical native
image IDs; input rows are never backfilled. Conflicting IDs refuse. Shared
sequences represent acquisition dependence, **not building identity**. `UNKNOWN`
or `PARTIAL` coverage and an empty observed-overlap list are not isolation proof.

The 2026-10-25 cache survey found **0 native sequence fields in 41,046 image
records across 8,726 cached metadata files** (6,119 buildings have frames).
All 37,605 unique native image IDs therefore lack sequence evidence. New derived
CSV rows match every legacy field; the original manifest remains unchanged.
Compact pins/counts: [`sequence-metadata-coverage-20261025.json`](evidence/sequence-metadata-coverage-20261025.json).
Native acquisition metadata remains missing; these tools cannot recover it by
inference. A real 40-image smoke run decoded all selected images and emitted one
unreviewed perceptual candidate, not a verified duplicate or population rate.
Its local output is `local/training/near-image-smoke-20261025/`. A full near-image
scan and candidate review remain pending; no learned-model inference occurred.

## Grouped development cross-validation

`train_probe.py --grouped-cv 5` evaluates a frozen-representation head using only
train/validation rows. Deterministic folds keep buildings and exact-image-linked
buildings together; each fold fits its own scaler, logistic head and dummy.
Reports pin inputs and include fold membership/support, out-of-fold predictions,
building-macro metrics, confusion matrices and capture-era diagnostics. Missing
classes remain visible. Too few groups or single-class training folds refuse
before fitting. These are exploratory development estimates, not independent
replications or a new test cohort; no generalisation CI is fabricated from
correlated fold fits.

CV refuses project-tuned caches: their encoder has already seen the nominally
fold-held-out training buildings. It also requires aligned per-image
`image_sha256` metadata, verified against current files. **Old caches cannot be
made verifiable by attaching hashes now**; re-encode through the canonical
builder, which hashes the same bytes it decodes. The declared historical
`17387/11500227_0192_P04.jpg` cache/file gap is recorded and excluded before hashing;
other eligible cache gaps refuse. Example, in an ML environment:

```bash
python3 prototypes/three-ages/build_embeddings.py \
  --manifest local/training/image-isolated-20261025/manifest.csv \
  --out local/training/embeddings_frozen_byte_pinned.npz
python3 prototypes/three-ages/train_probe.py --head drawing --grouped-cv 5 \
  --manifest local/training/image-isolated-20261025/manifest.csv \
  --embeddings local/training/embeddings_frozen_byte_pinned.npz \
  --out local/training/drawing_grouped_development.json
```

Add `--device cuda` to encoding only when the configured ML environment supports
it. The subsequent frozen follow-up completed **76,999 byte-pinned vectors** at
`local/training/frozen-isolated-20261025/batch64/embeddings.npz`, omitting only the
declared unreadable image. All bytes were verified against disk; a seeded
100-vector sample reproduced the previous frozen reference exactly. A pre-pinned
five-fold drawing development run scored 69,376 train/val images: building-macro
98.71% versus a 93.50% majority dummy, zero test rows. This is source-flag agreement,
not reviewed visual accuracy; older-media slice agreement is only 83–85%.
Class imbalance hides worse failures: modern drawing-proxy recall is just 12/49
(24.49%), and pre-1900 photo-proxy recall 134/324 (41.36%). Do not deploy this
source-proxy head as an automatic photo/drawing filter. Future CV and ordinary
probe reports include per-class support, precision and recall for every slice.
See the results document and `evidence/drawing-grouped-development-20261025.json`.
No encoder weights were trained, and no construction-era result was scored. Construction CV additionally needs source construction labels and explicit
image-level eligibility via `--image-reviews`; no building-wide flag or historical
export silently becomes image truth.

## Image-level construction applicability

A source construction label describes a building, not every photograph stored
under its ID. Prepare a new worksheet from the existing reviewed building labels:

```bash
python3 prototypes/three-ages/training/construction_image_reviews.py prepare \
  --manifest local/training/image-isolated-20261025/manifest.csv \
  --reviewed-labels local/training/reviewed_construction_eras.csv \
  --image-root local/monument-inbox \
  --out-dir local/training/construction-image-reviews-NEW
```

Use `--building-ids ID ...` for a bounded subset; this does not request or authorise
an expanded human-label campaign. `contact-sheet.html` links source photographs
and shows the construction label/phase/evidence, explicitly distinguishing the
building-label reviewer from the image reviewer. Edit only reviewer fields in
`reviews.csv`. Every decision starts blank. Controlled decisions are `applicable`,
`wrong_subject`, `predecessor`, `interior_or_detail`, `not_visually_inferable`, and
`unknown`. Only explicit applicable images with observation/reviewer/ISO date/
confidence may inherit source truth. All others—including missing rows—stay out.
Metadata pins the prepared cohort, source files, actual image bytes, era and phase;
changed sources, duplicate/extra rows and tampering refuse instead of transferring
reviews. This is human attestation, not authenticated identity or licence proof.

Both ordinary construction validation and grouped CV now require
`--reviewed-labels ... --image-reviews REVIEW_DIRECTORY`, plus byte-pinned
embeddings matching the photographs that were actually reviewed. The building
`depicts_building` value cannot bypass this gate. Source-label loading may ignore
that interim flag only because the stronger image-level contract is mandatory.

The prepared existing cohort is
`local/training/construction-image-reviews-20261025/`: **1,195 photographs across
59 already-labelled buildings, 0 applicable image reviews**. Its source labels
were preserved. This is a blank review inventory, not 1,195 newly authorised
review tasks or evidence that those images depict the labelled volume.

## Validate returned human identity audits

```bash
python3 prototypes/three-ages/training/validate_pair_audit.py \
  --audit-dir local/training/pair-audit-20261025 \
  --out local/training/pair-audit-returned-validation.json
```

Optional `--reviews`, `--sample`, manifest and root overrides support returned
copies and other pinned cohorts. Validation reconstructs the exact sample,
checks manifest/sampler/byte hashes and immutable pair fields, rejects changed,
missing/duplicate/extra IDs and incomplete review rows, and exclusively creates
a new report. Inputs/reviews are never edited. Pending samples report counts and
coverage with `cleanliness=null`; a fully reviewed sample reports the correct
fraction with sampled-component uncertainty where possible. This is pair-weighted
for one seed's capped training population, not corpus-wide or building-uniform
cleanliness. Source hashes are not authenticated attestations of reviewer honesty.
No reviews are inferred and no training/quarantine is triggered.

The existing prepared audit was validated as **0/40 reviewed**; its report is
`local/training/pair-audit-20261025/pending-validation.json`. Human identity and
per-image applicability review remain open.

## Offline browser review workbenches

The prepared audits now have interactive pages (new review decisions start blank):

- `local/training/pair-audit-20261025/browser-review.html` — 40 identity pairs;
- `local/training/construction-image-reviews-20261025/browser-review.html` —
  1,195 image-applicability cases from the existing 59 source-labelled buildings.

Open as a file, or serve the repository root locally with
`python3 -m http.server 8000 --bind 127.0.0.1` and open the corresponding
`http://127.0.0.1:8000/local/training/.../browser-review.html`. Do not expose the
repository/private images on a public interface. No server is started by the
builder. Source pictures are referenced, not copied or uploaded to an external service.

Use previous/next or the case selector; hide completed cases when useful. For
identity pairs, `correct` means the views support the assigned building identity;
choose `ambiguous` when the evidence is insufficient, not a forced match. For
construction images, only an explicit `applicable` review may inherit the source
campaign; wrong-subject/predecessor/detail/uninferable/unknown views stay out.
Enter your own reviewer name, decision, evidence/observation and confidence.
Explicit Save + next may fill today's date/name, never a decision or confidence;
without a decision it creates no phantom review metadata.

Draft history is scoped to this page, cohort and exact baseline CSV hash.
Autosave uses exclusive browser Web Locks and refuses stale writes from another
tab rather than erasing saved work. Without coordinated storage, new drafts are
memory-only and the page warns you to download JSON backups. Web Locks normally
require localhost or HTTPS; plain-HTTP remote/Tailscale pages may use this
memory-only fallback. Pending/failed saves warn before leaving. Recovery errors preserve the original stored text, with a
separate recovery download; JSON export retains new in-memory drafts. Changed
sources/baselines, duplicate/unknown/immutable fields and conflicting backup
imports refuse atomically. Importing somebody else's backup is not an independent
review. Use a new blank review page/cohort or a separate browser profile for an
independent reviewer, not somebody else's restored drafts. No old browser history
is automatically purged.

Existing source-review fields are read-only. Partial new drafts can be backed up
as JSON, but CSV export refuses incomplete new reviews. Completed CSV includes all
canonical rows/immutable fields; quotes, newlines and Unicode are preserved.
Formula-looking cells are deliberately not rewritten: inspect CSV as text or
import **all columns as text**, without spreadsheet formula interpretation.

To build another NEW page from a pinned cohort:

```bash
python3 prototypes/three-ages/training/build_review_workbench.py --kind pair \
  --audit-dir local/training/pair-audit-20261025 \
  --out local/training/pair-audit-20261025/browser-review-NEW.html
```

Use `--kind construction` and explicitly pass the source
`--publisher-manifest local/training/image-isolated-20261025/manifest.csv` for the
construction cohort. Manifest/root/label overrides support other pinned inputs.
The builder validates source pins and image bytes, escapes embedded data, checks
root confinement and exclusively creates the output. It never overwrites a page,
worksheet, label, image or model.

Stage a downloaded CSV into a NEW validated cohort, never over the originals:

```bash
python3 prototypes/three-ages/training/stage_review_workbench.py --kind pair \
  --audit-dir local/training/pair-audit-20261025 --reviews DOWNLOADED.csv \
  --out-dir local/training/pair-audit-reviewed-NEW
python3 prototypes/three-ages/training/stage_review_workbench.py --kind construction \
  --audit-dir local/training/construction-image-reviews-20261025 \
  --publisher-manifest local/training/image-isolated-20261025/manifest.csv \
  --reviews DOWNLOADED.csv --out-dir local/training/construction-reviewed-NEW
```

Staging applies the existing canonical validators and refuses changes/removals
to source-owned reviews, including work entered after an old page was generated.
It copies pinned metadata plus returned CSV into the new directory and records
validation; it does not fit a model or approve truth/licensing/training. For
construction, only the deliberately staged directory should later be passed as
`--image-reviews`. Rebuilding a page from it keeps the staged reviews read-only.
Both actual source audits remain entirely blank; no human decisions were supplied
by the software implementation.

Verification: Node model/DOM regressions and Python -> JS CSV -> canonical-validator
round trips run in the prototype gate. Optional real Firefox smoke uses a temporary
profile, synthetic PNGs and a loopback-only fixture server:
`python3 prototypes/test_review_workbench_firefox.py`. It checks HTTP/file images,
refresh recovery, two-tab stale-write refusal and exports without touching a real
browser profile, review file or model. No third-party browser-test package is needed.

## Historical reports — reproduce with these caveats

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

- `pilot-20261022-232106/` — historical random-order checkpoint (seed 42, epoch 1); not image-isolated.
- `pilot-seed7-20261023-002018/` — reproducibility seed.
- `pilot-epoch2-20261023-105251/` — second epoch from the seed-42 checkpoint; kept because the negative result is the point.
- `pilot-hard3-*` and `pilot-hard-seed7-*` — **best validation results** (visual hard negatives, one epoch each, seeds 42 and 7).
- `pilot-hard-epoch2-*` — second epoch on hard negatives; **rejects** the "easy negatives caused saturation" explanation.
- `pilot-refresh2e-*` — two epochs drawing a **fresh pair sample each epoch**; the collapse disappears, so the cause was repeating fixed pairs. This is the checkpoint to use for retrieval (`--index tuned`); the frozen caches stay better for the drawing and dating probes, as the results document shows.
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

## Reproducing from a clean checkout

Nothing under `local/` is committed, so the scripts fail fast with
`FileNotFoundError: ... local/training/manifest.csv` until the corpus exists.
Order matters:

1. **Crawl the corpus** (network, ~40 h for the full publisher set):
   `scripts/monument-corpus-pipeline.sh` writes `local/scraped/`,
   `local/monument-inbox/` and the place records. Part of that run also builds
   `local/training/manifest.csv`.
2. **Present-day pole** (optional, needed for cross-pole numbers):
   acquire/cache frames in `local/mapillary-inbox/` first, then run
   `build_mapillary_manifest.py --out NEW.csv`. The original local acquisition
   helper (`fetch_mapillary.py`) is not tracked here; a clean checkout alone
   cannot reproduce that download step. The tracked builder does not fetch
   missing sequence IDs and refuses existing output files/symlinks.
3. **Feature caches**: `prototypes/three-ages/build_embeddings.py` (frozen) or
   the same script with `--checkpoint` (tuned). Budget ~10 min per 77k images on
   the GPU here, and set `HF_HUB_OFFLINE=1` so weights come from the local model
   mount instead of the Hub.
4. **Train**: `train_local_pilot.py --run-dir local/training/run-X`, optionally
   `--negatives hard --epochs 2 --refresh-pairs` (the validation-chosen setup).
5. **Evaluate**: `eval_test_once.py` (test, once), `eval_neighbour_control.py`,
   `eval_curated_slice.py`.

Requirements: torch + torchvision + open_clip_torch (see
`prototypes/requirements-ml.txt`); the two offline test suites need only numpy
and torch, which is why they pass in a bare checkout:

```bash
~/.venvs/rocm/bin/python prototypes/three-ages/training/test_local_pilot.py   # 9 checks
~/.venvs/rocm/bin/python prototypes/three-ages/training/test_three_ages.py    # 7 checks
```

A venv is recommended rather than required: on this machine the system Python has
a CUDA build of torch that cannot see the AMD GPU, while `~/.venvs/rocm` has the
ROCm build.

## Script contract

Corpus/model artifacts default under gitignored `local/`; explicit output
paths remain the caller's responsibility. Keep large artifacts out of tracked
paths. The new diagnostics exclusively create outputs, never replace sources:

| script | reads | writes |
|---|---|---|
| `build_mapillary_manifest.py` | `local/mapillary-inbox/` metadata | new `--out` CSV, including explicit/blank `sequence_id` |
| `sequence_metadata.py` | Mapillary CSV | new `--out` JSON, no image decoding |
| `near_image_audit.py` | both manifests/image roots | new `--out-dir` fingerprints and diagnostic JSON |
| `build_taskb_queue.py` | `local/scraped/`, manifests | `local/training/taskb_queue.csv` |
| `extract_notice_evidence.py` | `local/scraped/`, the queue | the queue, plus excerpts, years, `suggested_era` and a rebuild flag |
| `make_label_audit_sheet.py` | manifests, both image roots | `local/training/label-audit.html` (defaults to train split, no drawings) |
| `build_colab_pack.py` | manifests, image roots | `local/training/colab-pack/` |
| `build_tuned_embeddings.py` | manifests, image roots, `--checkpoint` | `--out` (default under `local/training/`) |
| `verify_baseline_reproduction.py` | manifests, caches | `--out` directory |

Scripts that need an output path require it explicitly (`--out`), so a typo
fails with a usage error instead of silently launching a ten-minute GPU encode.

Reproducibility spot checks, both rerun on this machine: the Mapillary manifest
builder regenerates all 41,046 rows with identical IDs and legacy field values;
the new schema adds `sequence_id` (blank for the current cache). The task-B queue
builder regenerates the same 60 buildings.

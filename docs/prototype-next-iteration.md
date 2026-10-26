# Prototype next iteration

The current explorer is ready for review as an **evidence-shaped prototype**, not a finished building chronology.

## Three Ages

**Question tested:** can a building record show separate register, facade and structural evidence without collapsing uncertainty into one date?

**Now demonstrated:**

- 34 real Grand Place source records;
- six source-linked pilot cases;
- explicit separation between source description and image-derived annotation;
- a visible annotation protocol and next-step evidence notes;
- four aligned area-level structural epochs (1930–1935, 1971, 1996 and 2022);
- public dataset provenance links.

**Definition of done for a curated MVP:**

- obtain permission for at least two historical image epochs (source access complete for the curated pilot: aligned BruCiel 1930–1935, 1971 and 1996 CC0 orthos plus the 2022 open-data ortho are committed; five cases have 1941–1942 KIK-IRPA facade previews under CC BY 4.0, Joseph et Anne adds 1969 and 1984 epochs, an 1890 west-side ensemble view awaits identity confirmation, and Le Cornet, Le Cygne, L'Ange and Le Pigeon each add a 1969 Van de Walle facade view — so every case now has at least two historical epochs. La Balance has an exact-case 1878 British Library engraving with no known copyright restrictions and a 2011 Wikimedia Commons photograph under CC BY-SA 3.0. Exact capture-year interpretation and visible-change review remain pending);
- add an official register-year source for each pilot case (progress: all six source claims now expose their actual date semantics and City-history comparison in a provenance-safe register worksheet. The reviewer must choose whether each date is an acceptable MVP proxy, reconstruction evidence only, or a rejected mapping);
- annotate facade period and structural change with source, epoch, rationale and reviewer (progress: seventeen facade rows and six case-level structural-comparison rows now have separate provenance-safe worksheets and compiled JSON outputs; twenty-four aligned building-centred crops make the four structural epochs reviewable, while observations and reviewer metadata remain pending);
- record inter-annotator disagreement before assigning confidence;
- publish the image licence and a reproducible annotation export.

## Model-training goal (recorded 2026-10-09)

The curated corpus has a second purpose beyond the explorer: its reviewed evidence is the seed for training an architectural-recognition model. Decisions recorded with the project owner on 2026-10-09:

- **Targets, sequenced:** facade style/period recognition first, then structural-change detection across the aligned epochs, reusing the same provenance-safe pipeline.
- **Data strategy:** scale the reviewed case corpus before any training run; the six-case pilot proves the labeling methodology and is not a training set.
- **Label vocabulary:** reuse the style terms already used by the City dataset and heritage inventory (for example Baroque, Classical French), agreed with a reviewer as the annotation spec requires.

The curated-MVP boundary below still holds: no automated city-wide classification is attempted before the evidence is reviewed and the corpus is scaled.

## Review backlog — 2026-10-25

Findings from the repository and ML/data review. Counts below describe the local
artifacts inspected on this date; preserve that snapshot context when comparing
later runs. Status reflects implementation, not a claim of scientific validation.

### Implementation progress — 2026-10-25

| Item | Status and remaining work |
|---|---|
| Shared-image leakage | **Safeguards implemented; clean retrieval retraining/confirmation pending.** Full byte/source audit found 1,232 cross-split groups / 2,691 rows. Separate quarantined manifests contain 77,000 publisher + 38,527 Mapillary rows; a second complete audit found zero exact-image cross-split groups. Originals/weights unchanged. Near-duplicate/sequence dependence remains open. |
| Cross-pole identity | **Review and return-validation implemented; human audit pending.** `local/training/pair-audit-20261025/index.html` and `reviews.csv` contain 40 reproducibly sampled actual seed-42 training pairs. The validator reconstructs the sample, checks hashes/immutable fields and refuses malformed reviews. The actual sample validated as 0/40 reviewed, with no cleanliness estimate. |
| Construction applicability | **Image-level gate implemented; human review pending.** Both ordinary and CV construction evaluation require explicit applicable image reviews pinned to source bytes/era/phase, plus matching byte-bound features; building-wide depicts flags cannot bypass the gate. A blank inventory covers 1,195 photos of the existing 59 reviewed buildings; 0 are currently eligible. Drawings, missing/unknown/wrong-subject/predecessor/detail/uninferable views stay out. Source labels and missing phases remain human decisions. |
| Independent construction evaluation | **Development tooling and frozen features complete; construction confirmation pending.** Grouped train+val CV keeps linked buildings together and refits scaler/head/dummy per fold. Fresh byte-pinned frozen features are verified; development-only drawing/source-proxy CV completed on 69,376 images with zero test rows. Construction CV still needs actual image reviews (currently 0 eligible) and a newly frozen independently reviewed confirmation cohort. No annotation batch or holdout was invented. |
| Uncertainty/claims | **Implementation complete; clean estimates pending.** Deterministic paired shared-image/building-group bootstrap wired into retrieval evaluation; duplicate query copies excluded from ranking and eligibility. Caches require matching backbone/checkpoint/toolchain metadata; tuned probes require isolated-training checkpoint provenance. Historical claims qualified, not silently recomputed. |
| Reviewed queue preservation | **Fixed and regression-tested.** Missing reviewed IDs refuse before output mutation; human columns and preservation counts retained. |
| Workbench navigation | **Fixed and regression-tested.** Identity-based save, arrows, sidebar and hide-decided navigation cover wraparound/final rows. |
| Offline scraper gate | **Fixed.** CLI dispatch uses a fixture fetcher with a socket guard; full prototype gate passes. |

New canonical tooling: `training/data_integrity.py` (new-output quarantine),
`training/pair_sampling.py` (shared sampler), `training/prepare_pair_audit.py`
(actual-pair human review preparation), and `scripts/validate-ml.sh` (synthetic
CPU tests, also wired into CI). The legacy tuned-cache entrypoint now forwards
to the canonical builder with manifest selection and provenance metadata.
The compact pinned audit is
[`shared-image-audit-20261025.json`](../prototypes/three-ages/training/evidence/shared-image-audit-20261025.json).
Independent read-only review found provenance/duplicate-metric bypasses; those
were fixed and covered by synthetic regressions. Browser/CLI applicability now
defaults to unknown, and legacy session import cannot manufacture `yes`; existing
human fields remain untouched. No encoder training or spent-test predictions
were made; the later frozen development run below is explicitly exploratory.

Checks run: full `scripts/validate-prototypes.sh` passed; synthetic CPU
`scripts/validate-ml.sh` passed (22 ML tests); `git diff --check` passed.
Continuation checks: full prototype gate passed again; the expanded synthetic
CPU ML gate passed **28 tests**, including fold isolation, fold-local scaling,
spent-test exclusion, historical missing-file handling, changed/unverifiable
cache refusal, and canonical byte-fingerprint encoding. Audit-return validation
adds 17 standard-library fixture tests to the prototype gate. Independent
read-only review identified the missing-file/cache-byte gaps; both were fixed.
At that safeguard-only stage, no corpus CV or re-encoding was run. Old caches
must be re-encoded, not retrofitted
with current-file hashes. Details/commands live in the
[training README](../prototypes/three-ages/training/README.md).

`validate-bonsai.sh` was attempted but blocked by a relocated opam switch whose
compiler configuration still points at a missing previous checkout. No OCaml
files changed and the switch was not modified. Hosted CI has not been run here.

### Further continuation — image eligibility and label scope

`training/construction_image_reviews.py` now prepares provenance-pinned
image-level worksheets/contact sheets, supports bounded building subsets, and
validates returned decisions. Prepared inventory:
`local/training/construction-image-reviews-20261025/` (59 existing buildings,
1,195 photos, all image decisions blank). This does not authorise expanded
reviewer hours or imply image identity. Construction CLI requires this stronger
gate in both evaluation modes; positive building-wide flags are insufficient.

The photo-dating head now excludes drawing/unknown media. A metadata-only audit
of the original dated test denominator found 767 drawing-flag rows among 7,143;
historical scores are therefore caption-era, not photo-only dating scores.
Drawing flags and caption dates remain weak proxies; report semantics now say so
for every head. Pinned counts live in
[`capture-era-scope-audit-20261025.json`](../prototypes/three-ages/training/evidence/capture-era-scope-audit-20261025.json).
No new test predictions were made for that correction.

Checks for this continuation: 16 standard-library image-review tests and the
expanded **30-test synthetic CPU ML gate** passed. Independent read-only review
caught a non-CV stale-feature bypass; shared byte verification now covers both
construction modes and the regression uses a fresh image review with stale
cached pixels.

### Completed frozen development run

Frozen inference (not encoder training) completed successfully under a 40-minute
deadline, using existing offline weights. New local artifact:
`local/training/frozen-isolated-20261025/batch64/embeddings.npz` — 76,999 vectors,
all byte hashes checked, finite/unit-normalised, one declared unreadable image
omitted, kernel taint zero. A seeded 100-vector sample reproduced the previous
same-toolchain frozen reference exactly. Lifecycle logs, launch source snapshots,
cache verification, and the protocol pinned before scoring are retained beside it.

The single fixed five-fold drawing development run used 69,376 train/val images,
23,734 buildings and 23,601 dependency groups, **zero test rows**. Building-macro
source-flag agreement: **98.71% vs 93.50% dummy**; image-weighted: 97.61% vs 90.25%.
Older-media slice macro agreement is only 83–85%; these are weak caption-keyword
targets, not human visual truth or architectural dating. Independent review exposed
class imbalance: modern drawing-proxy recall is just 12/49 (24.49%), while
pre-1900 photo-proxy recall is 134/324 (41.36%). Do not use this head as an
automatic filter. All future ordinary/CV reports now expose per-class support,
precision and recall; the completed run's diagnostics were derived from saved
confusions without fitting again. OOF membership, group
isolation, fold-majority predictions, confusion and macro scores were recomputed
from saved outcomes without fitting another model. No hyperparameter selection,
construction scoring or fine-tuned retrieval evaluation occurred. A real-data
construction CLI check correctly refused the all-blank image reviews before
fitting and created no report.

Tracked compact results/protocol are in `training/evidence/`; all seven age slices
and scientific limitations are reported in the ML results document. The gate now
traces 69 headline evidence checks, including both classes' slice recalls and
minority support/recovered counts. Construction remains genuinely blocked on
per-image reviews; both prepared human audits remain unreviewed.

### Software-only continuation — browser review usability

The owner chose **software work only**, not human labelling or provisional AI
judgements. Added offline browser workbenches for both already-prepared cohorts:

- `local/training/pair-audit-20261025/browser-review.html` (40 pairs);
- `local/training/construction-image-reviews-20261025/browser-review.html`
  (1,195 photographs).

`training/build_review_workbench.py` validates pinned inputs/bytes and creates a
NEW escaped, self-contained page. Navigation is keyed by immutable IDs; source
reviews are read-only; new decisions/confidence stay blank. Partial drafts have
JSON backup/import; completed canonical CSV round-trips through the existing
validators. Draft storage is isolated by page, cohort and baseline revision.
Independent review caught concurrent-tab loss: exclusive Web Locks plus in-lock
stale-write refusal now protect saved work. Without safe coordination, drafts
remain memory-only with backup/unload warnings. Raw failed-recovery data has a
separate download; neither old history nor source files are overwritten.

`training/stage_review_workbench.py` validates downloaded CSV into a NEW cohort,
refusing changed/removed source-owned review fields, stale provenance and
malformed returns. Staging is not training approval and never modifies originals.
Commands and CSV/text-import cautions are in the training README.

Verified: **20 Node model/DOM tests**, **10 Python builder/stager round-trip tests**,
and **1 real isolated headless Firefox scenario** covering HTTP/file images,
refresh recovery, genuine two-tab conflict refusal, inert source text and CSV
validation. The ordinary prototype gate includes Node/Python coverage; Firefox
is optional and needs no browser-test package. No real user browser profile or
review data was used. Both actual audits remain **0/40** and **0/1,195** decided.

### Software-only continuation — near-image/acquisition diagnostics

Added `training/near_image_audit.py` and `training/sequence_metadata.py`:
new-output, read-only diagnostics separating raw RGB/display RGBA equivalence,
perceptual review candidates and explicit native capture-sequence metadata.
Decoder provenance, source pins, low-information/error exclusions and search/
output budgets are visible; no automatic merges, quarantine, split changes or
semantic labels. Native-source joins retain acquisition overlap when one copy
has missing sequence metadata, without inflating observed coverage or editing
source rows. Growing image inputs are hard-bounded during reads.

The Mapillary builder preserves future native sequence IDs, rejects malformed/
duplicate image identities and refuses existing output paths. Typed manifests
retain `sequence_id`. Metadata-only inspection found **0 sequence fields in all
41,046 cached image records** (8,726 metadata files; 37,605 unique native image
IDs). Thus sequence coverage is **UNKNOWN**, not a zero-leakage result. A new
local CSV reproduces every legacy field; originals stay pinned and unchanged.
Counts/hashes: [`sequence-metadata-coverage-20261025.json`](../prototypes/three-ages/training/evidence/sequence-metadata-coverage-20261025.json).

A bounded real smoke run decoded 40/40 selected images and emitted one
**unreviewed perceptual candidate**, not a verified duplicate or incidence rate.
This is not a full-corpus scan or a learned-model evaluation. Full near-image
inspection, candidate review and actual native acquisition metadata remain open;
no human review decisions were added. Commands/limitations are in the training
README. **30 diagnostic regressions (17 sequence, 13 near-image), the full
prototype gate, and all 30 synthetic CPU ML tests passed.** Independent read-only
review found the partial-source and byte-budget defects above; both were fixed,
regression-tested and re-reviewed with no important remaining findings. No full
image scan, corpus-model training/scoring, new review decisions or commits.

### P0 — Repair shared-image leakage across ML splits

- **Evidence:** `training/train_local_pilot.py::check_splits` checks building IDs,
  but a Mapillary image can be assigned to several buildings. Reproducing the
  seed-42 sampler yielded the documented 78,343 pairs (17,925 cross-era and
  60,418 cross-pole). Sampled training frames share source image IDs with 479
  validation queries and 501/4,421 test queries (11.3%). Three inspected
  train/test frame pairs had identical SHA-256 hashes.
- **Work:** audit source IDs and image hashes across both poles; group connected
  buildings sharing images into one split, or exclude overlapping images before
  training/evaluation. Investigate near-duplicates and shared acquisition
  sequences separately. Publisher shared filenames require byte/source checks,
  not automatic deduplication.
- **Done:** automated split assertions reject shared source images/pixels;
  regression fixtures cover one frame assigned to multiple buildings; a pinned
  overlap report and clean evaluation quantify the effect. Do not assume the
  bias direction or reuse contaminated results as clean generalisation evidence.

### P1 — Audit cross-pole identity assignments

- **Evidence:** the fine-tuning report explicitly lacks a trustworthy estimate
  of whether Mapillary frames depict their assigned buildings. Shared frames
  also raise the possibility of conflicting identity supervision.
- **Work:** human-review a reproducibly sampled set of actual training pairs,
  using `training/make_label_audit_sheet.py`; record correct, ambiguous and
  incorrect identity, sampling scope, reviewer and evidence. Include publisher
  views rather than assuming catalogue membership guarantees visible identity.
- **Done:** report measured agreement/error with uncertainty and exclusions;
  quarantine incorrect/ambiguous pairs under an explicit policy and measure
  the resulting dataset coverage. Never use embedding similarity as ground truth.

### P1 — Make construction labels applicable to individual images

- **Evidence:** `epoch_data.py::with_reviewed_labels` joins a building's label to
  every image. It does not filter drawings, interiors, predecessor structures
  or unrelated ensemble views. The reviewed-label CSV omits `depicts_building`;
  24/59 labelled queue rows had that field blank and 22 lacked phase years.
- **Work:** separate historical construction truth from image applicability;
  carry reviewed applicability through export and training, with explicit
  unknown/not-visually-inferable states. Review missing phases and ambiguous
  construction campaigns; do not mechanically infer missing human decisions.
- **Done:** non-applicable and unreviewed applicability cases cannot silently
  become positive image labels; tests cover drawings, unrelated views and
  predecessors; report retained buildings/images and exclusions by class.

### P1 — Establish a genuinely independent construction-era evaluation

- **Evidence:** `report_construction_n59.json` reports 19.2% exact-era and 66.3%
  within-one-era accuracy on 193 images from only seven test buildings. Batch
  checks at n=42/56/59 reuse overlapping test populations: they are exploratory
  learning-curve observations, not three independent replications.
- **Work:** use grouped cross-validation on development buildings; report
  building-macro metrics, class support/confusion, appropriate baseline results
  and capture-era slices. Define a new locked evaluation cohort and primary
  metrics before further selection, respecting reviewer-time approval boundaries.
- **Done:** development and final evaluation roles are explicit; no tuning on
  the locked cohort; results include independent building counts and uncertainty.
  Construction prediction/disentanglement remains unproven until supported.

### P1 — Correct uncertainty estimates and scope of ML claims

- **Evidence:** `training/stats.py` and `training/eval_test_once.py` use
  image-level Wilson intervals despite within-building dependence and shared
  images. Non-overlapping intervals alone do not justify the report's strong
  sampling-noise claim. The original retrieval test population was also inspected
  for more than one checkpoint; construction checks repeatedly reuse test data.
- **Work:** compute paired bootstrap differences at building or shared-image
  group level; report image-weighted and group-macro performance. Reconcile
  result documents with actual checkpoint selection, repeated evaluations,
  leakage findings, and the absence of demonstrated out-of-source improvement.
- **Done:** reproducible grouped intervals accompany effect sizes; exploratory
  results are distinguished from locked confirmation; avoid claims that probe
  degradation proves disentanglement or that repeated checks are replications.

### P1 — Prevent regeneration from deleting reviewed queue rows

- **Evidence:** `training/extract_notice_evidence.py` carries edits from `--out`
  but writes only IDs in `--queue`. With distinct inputs, a reviewed ID absent
  from the new queue was deleted while reporting `reviewed_rows_preserved: 1`.
- **Work:** refuse removal of reviewed IDs or retain them explicitly; report
  actual preservation counts and validate before replacing the destination.
- **Done:** a regression test with an omitted reviewed ID proves no human work
  is lost and refusal leaves the original file unchanged.

### P2 — Fix task-B workbench navigation after saving

- **Evidence:** `taskb_review.html::saveNext` increments position before
  `renderList` removes the decided row. With default “hide decided”, saving A
  in `[A, B, C]` opens C instead of B; reproduced using the actual JavaScript.
- **Work:** navigate by stable building identity or account for filtering before
  advancing; inspect sidebar, arrow and previous/next navigation for the same issue.
- **Done:** browser tests cover hide-decided on/off, sidebar selection, wraparound
  and the final row without skipping or assigning drafts to the wrong building.

### P2 — Restore the offline scraper test and complete the gate

- **Evidence:** `prototypes/test_monument_scraper.py::test_place_scrape_runner`
  defines `ServesPlaces` but invokes `module.main(argv)` without injecting it;
  `main` constructs a real `Fetcher`. `scripts/validate-prototypes.sh --check-clean`
  failed at this assertion during review; later gate checks did not run.
- **Work:** inject the fixture fetcher and enforce no network access in offline
  tests; retain coverage of the CLI dispatch path.
- **Done:** the test passes without network and the full project gate completes
  with a clean working tree. Report any remaining failures separately.

### Recommended execution order

Repair split leakage and audit identity/applicability before further model tuning.
Then freeze the evaluation protocol and rerun the relevant comparisons on clean
artifacts. Queue-preservation and offline-test fixes can proceed independently;
workbench navigation should be fixed before further annotation sessions.

Code paths under `training/` above are relative to
`prototypes/three-ages/`. Related sources:
[ML results](three-ages-finetune-pilot-result.md),
[construction-label campaign](three-ages-task-b-label-campaign.md), and
[training plan](training-plan.md).

## Decision boundary

Do not add more interface features until the curated-MVP evidence has been reviewed. The next work is human confirmation of identity mappings, register semantics, facade observations and structural comparisons.

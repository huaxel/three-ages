# Fine-tuning result: cross-condition contrastive pilot

Date 2026-10-22/23. Machine: Framework Desktop, AMD Ryzen AI Max (Strix Halo),
Radeon 8060S (gfx1151), kernel 7.3.0-4-cachyos, torch 2.14.1+rocm7.2 in
`~/.venvs/rocm`. Runs live under `local/` (gitignored); this document records
the method, numbers and limits. **Revised after an adversarial audit** — see
"Corrections" at the end for what changed and why.

## The question

Frozen CLIP (ViT-B-32/laion2b_s34b_b79k) detects photographs, not buildings.
Measured with the metric used throughout this document, frozen retrieval found
the same building across capture eras in **0.64%** of eligible test queries and
1.36% of validation queries (cross-pole: 0.93% / 1.36%). Does contrastive
fine-tuning on cross-condition positives fix that?

## Method

Two training pair types, train-split buildings only, photo-only (i.e. not
flagged as drawings):

- **cross-era publisher**: same building, different caption-derived capture era;
- **cross-pole**: Mapillary present-day frame + publisher picture, same building.

78,343 pairs (17,925 cross-era / 60,418 cross-pole), sampled boundedly from all
eligible frames and capped per building so prolific facades cannot dominate.
Loss is symmetric InfoNCE over a **building-equality mask**, not a diagonal: two
views of the same building in one batch are positives for each other, never
false negatives. Vision encoder only, FP32, AdamW lr 3e-6, batch 16, one epoch,
4,897 steps, ~1,920 s, peak 2.27 GiB.

Splits are **building-level and consistent across both poles**, so no image of a
validation or test building can appear in training, and test queries only ever
have held-out mates.

Evaluation:

- publisher leg: validation (or, once, test) queries against the **full**
  77,171-image publisher gallery; test images act only as fixed distractors and
  are scored only as queries in the test evaluation; self-match excluded;
  cross-era rate on the fair denominator (queries that have a cross-era mate);
- cross-pole leg: Mapillary frame → same publisher gallery.

## Results — held-out validation, two seeds

| leg | metric | frozen | seed 42 | seed 7 |
|---|---|---:|---:|---:|
| publisher | top5 | 31.24% | 33.51% | 34.10% |
| publisher | cross-era top5 (fair) | 0.87% | **3.80%** | **3.80%** |
| cross-pole | top5 | 1.36% | **4.68%** | **3.96%** |
| cross-pole | cross-era top5 | 0.00% | 0.68% | 0.72% |

Cross-era publisher retrieval improves **4.4×**; cross-pole **2.9–3.4×**.

Both seeds report exactly 148 cross-era hits on the same 3,895 eligible
queries — but **only 84 of those 148 queries are shared** (union 212). The equal
totals are a coincidence of counts, not the same hits; the seeds genuinely
differ.

## One honest test-split evaluation

Run once after the pilot was fixed on validation, via
`local/training/eval_test_once.py`. Both arms use caches built by the **same
toolchain** in this venv, and the report records SHA-256 of every input plus the
checkpoint, so the numbers can be attributed to specific weights.

| leg | metric | frozen | tuned | ratio |
|---|---|---:|---:|---:|
| publisher | top5 | 31.98% | 34.91% | 1.09× |
| publisher | cross-era top5 (fair) | 0.64%<br>[0.43–0.94] | **4.58%**<br>[3.97–5.28] | 7.2× |
| cross-pole | top5 | 0.93%<br>[0.68–1.26] | **4.21%**<br>[3.65–4.84] | 4.5× |
| cross-pole | cross-era top5 | 0.02% | 1.33% | 58× |

Brackets are 95% Wilson intervals (25/3,933 → 180/3,933 cross-era hits;
41/4,421 → 186/4,421 cross-pole). The intervals do not overlap: the gain is not
sampling noise. This is a deterministic recomputation from hashed artifacts, not
a second look — no model was chosen using these numbers.

## Forgetting check on the existing probes

Linear probes retrained on tuned embeddings; both frozen columns come from the
same 77,171-row caches, and the tuned delta is quoted against the
**same-toolchain** column:

| probe | frozen (cache) | frozen (same toolchain) | tuned | delta vs same-toolchain |
|---|---:|---:|---:|---:|
| drawing detection | 97.79% | 97.77% | 97.68% | −0.09 pp |
| capture-era top1 | 90.30% | 90.40% | 88.70% | −1.70 pp |
| capture-era within-one-era | 99.13% | 99.13% | 98.91% | −0.22 pp |

The drawn-vs-photo gate is intact. Photo dating gives up 1.70 pp (7,143 test
rows, ~121 flips) while cross-era retrieval gains 3.94 pp on the test leg and
2.93 pp on validation. This is the shape expected if the encoder leans less on
photographic medium — but a probe accuracy drop is **not** evidence of
disentanglement, only of changed representation.

Note the probes train on 69,502 (drawing) and 65,043 (era-known) rows, not the
full 77,171 embedded rows; the caches have 77,171 entries.

### Toolchain caution (measured)

Embedding caches are only comparable **within one torchvision build**. Encoding
the frozen weights with system Python reproduces the stored cache bit-exactly
(max abs diff 0.0); encoding the same weights in the ROCm venv differs by up to
0.013 per component. Same weights, different resize path. `build_embeddings.py`
now records `toolchain=` in every cache, and the forgetting table above exists
precisely to separate training from toolchain.

Two caches in the test table predate that field, so their provenance was
**checked rather than read**: re-encoding slices in this venv reproduces the
Mapillary frozen cache to 2e-6 and the tuned publisher cache to exactly 0.0.
All four test-table caches therefore come from the same build, which is what the
table assumes.

## Does the tuned encoder identify buildings, or just cluster similar facades?

Control: buildings whose centres fall in the same 0.0003° grid cell (~33 m
N–S × ~21 m E–W at this latitude — a street-block proxy, not an exact radius).
3,344 validation queries whose building has a neighbour. Galleries exclude
**train** rows for both arms, since the tuned encoder saw those images and the
frozen one did not.

| measurement | frozen | tuned | chance |
|---|---:|---:|---:|
| full gallery (15,333 held-out images): top-1 same building | 14.44% | 17.17% | — |
| full gallery: top-1 a *different* building in the same cell | 2.72% | 3.14% | — |
| cluster-only gallery: top-1 same building | 80.17% | **82.90%** | 79.07% |
| above chance, normalised | 0.052 | **0.183** | — |

Chance is computed per query, not assumed: the probability of landing on the
correct building equals that building's share of the candidate images, which
averages 79.07% because clusters are small (usually two buildings) and the
query building usually owns most of its cluster's images.

What this supports: among near-identical neighbours the tuned encoder picks the
right building 2.73 pp more often than frozen, and sits ~3.5× further above
chance. That is a real, paired improvement on the hardest local comparison
available without reviewed facade labels.

What it does **not** support: "not just style clustering". The same artifact
shows top-1 neighbour confusion *rising* (2.72% → 3.14%) while same-building
accuracy rose less, which is exactly what weighting street-level appearance
predicts. With a 79% chance floor and a 17% cluster error rate, the honest
claim is narrow: better discrimination among neighbours, not a demonstrated
shift from style to identity.

## Out-of-source check: does it transfer to a different archive?

Everything above scores the two sources the model trained on. The curated
Grand-Place pilot holds 72 previews from KIK-IRPA / IDPS / Commons — different
photographers, different scans, 1878–2026 — covering 27 facade units, 20 of them
across multiple years. Ranking those 72 against each other:

| metric (top-5, n=72) | frozen | tuned | chance |
|---|---:|---:|---:|
| same facade unit | 52.8% | 52.8% | 12.8% |
| same unit, different year | 26.4% | 26.4% | 8.6% |

The headline is a non-result, and reporting it as one matters: the percentages are
*identical*, but the hit sets are not — 38 hits in each arm sharing only 32
queries, with top-1 at 22/72 vs 23/72. At n=72 the difference is inside noise.

So on an archive the encoder has never seen, fine-tuning neither helps nor hurts
measurably, and both arms sit far above chance. What this supports is narrow but
worth having: the tuned encoder **does not collapse out of source**. It does not
show an out-of-source gain, and this slice is far easier than the corpus
benchmark (27 famous units, several images per unit sharing viewpoint and year),
so its absolute numbers are not comparable to the tables above.

## Does more training help? (no — measured)

Continued the seed-42 run for a second epoch from its checkpoint (optimiser
state restored, same pairs, same lr). Training loss fell 1.301 → 0.459, but
validation did not follow:

| validation | frozen | epoch 1 | epoch 2 |
|---|---:|---:|---:|
| publisher top5 | 31.24% | **33.51%** | 28.45% |
| publisher cross-era top5 (fair) | 0.87% | **3.80%** | 3.77% |
| cross-pole top5 | 1.36% | **4.68%** | 4.25% |
| cross-pole cross-era top5 | 0.00% | 0.68% | **0.99%** |
| neighbour control, cluster-only top-1 (chance 79.07%) | 80.17% | 82.90% | 83.38% |
| neighbour control, full-gallery top-1 | 14.44% | **17.17%** | 14.32% |

The extra epoch buys lower pair loss and essentially nothing else: cluster-
restricted accuracy creeps up 0.5 pp, while full-gallery top-1 falls below the
frozen baseline. So one epoch is the right stopping point at this learning rate.
Further gains would need a different regime (lower lr, larger batch, harder
negatives), not more steps. Note that falling training loss is not evidence of
learning anything generalisable — that trap is what this measurement exists to
catch.

## Reproducing

```bash
~/.venvs/rocm/bin/python local/training/train_local_pilot.py --run-dir local/training/pilot-X
# bounded variant with a 2h watchdog and lifecycle record:
python3 local/training/run_pilot_job.py local/training/pilot-X --seed 7
# continue training from a checkpoint:
python3 local/training/run_pilot_job.py local/training/pilot-X --resume <ckpt>
# summary (refuses incomplete runs):
python3 local/training/summarise_pilot.py local/training/pilot-X
```

Frozen-baseline re-encoding check:
`local/training/verify_baseline_reproduction.py`.

The tuned encoder is usable by the project itself:

```bash
# frozen weights (default behaviour unchanged)
python3 prototypes/three-ages/build_embeddings.py --out local/training/embeddings.npz
# tuned weights, on the GPU, with toolchain + checkpoint provenance recorded
~/.venvs/rocm/bin/python prototypes/three-ages/build_embeddings.py \
  --device cuda --checkpoint local/training/pilot-20261022-232106/checkpoint.pt \
  --out local/training/embeddings_tuned_seed42.npz
```

Verified: encoding 120 images through `--checkpoint` reproduces the pilot's tuned
cache bit-exactly (max abs diff 0.0), and the default frozen path reproduces the
original cache bit-exactly under system Python.

## Verification summary

- Building-level split consistency across both poles, asserted at train and at
  evaluation time.
- Pipeline equivalence: frozen weights through the pilot's own path reproduce the
  cached baseline within 0.05 pp, ~45× smaller than the measured deltas.
- Independent read-only reviews: pre-launch (three findings fixed) and
  post-hoc adversarial audit of these numbers (six defects fixed, see below).
- 7 offline CPU tests (`local/training/test_local_pilot.py`); kernel taint 0
  through every run.
- Out-of-source check on a third archive (KIK-IRPA/IDPS/Commons): no collapse,
  no measurable gain either way (`report_curated_slice.json`).
- Equal totals that looked like duplicate runs were checked twice — cross-seed
  (148 hits, 84 shared) and cross-arm on the curated slice (38 hits, 32 shared).
  Both are coincidences of counts, not duplicated work.

## Corrections (post-audit)

The audit found and this revision fixes:

1. **Chance floor was wrong and uncomputed.** The earlier text derived 40.5%
   from `1/mean-cluster-size`, which is arithmetically wrong (1/2.71 = 37.0%)
   and conceptually wrong for an argmax over candidate *images*. Chance is now
   computed per query (79.07%) and the "essentially at chance" claim for frozen
   is retracted — frozen is also above chance.
2. **Control gallery leaked train rows.** The cluster-only gallery had included
   images the tuned encoder trained on. Both arms now see held-out images only.
3. **"Within 33 m" was not what the code measured.** The cell is 0.0003° on both
   axes, i.e. ~33 m N–S × ~21 m E–W.
4. **Test evaluation lacked provenance** and mixed toolchains. Both arms now use
   same-toolchain caches, and the report records input and checkpoint hashes.
   Two caches predate the `toolchain=` field, so their provenance was verified by
   re-encoding slices (2e-6 and 0.0) instead of trusted.
5. **Epoch-2 reporting was selective** — it quoted only the cluster-restricted
   metric that looked flat and omitted the full-gallery regression now shown.
6. **Stale and unsupported numbers**: "1.9%" (no artifact supports it; this
   document uses the measured 0.64%), "same 77,171 rows" for the probes
   (69,502 / 65,043 rows), a limits sentence still claiming the test split was
   untouched after it had been spent, and a 3.9 pp figure quoted from the test
   leg while sitting next to a validation probe delta.

## Next steps, in order of value

1. Facade-level positives/negatives (same building, same facade): the only way
   to test disentanglement rather than assume it. Needs the label campaign.
2. A different training regime if more is wanted: lower lr or larger batch with
   harder negatives, judged on validation — never on the spent test split.
3. Wire the tuned encoder into the corpus embedding path so downstream probes
   and retrieval share one feature set (the `--checkpoint` flag exists; the
   corpus-wide run is unstarted).

## Using it

`local/training/three_ages.py` is the encoder made usable — give it a building or
a photograph and it ranks the corpus by similarity:

```bash
python3 local/training/three_ages.py --building 37300 --topk 5 --cross-era
python3 local/training/three_ages.py --image local/monument-inbox/13130/10401112_0049_P01.JPG --cross-era
python3 local/training/three_ages.py --building 37300 --cross-era --index frozen   # before/after
```

`--cross-era` restricts hits to a different capture era; `--index frozen` runs the
same query on the untuned encoder, which is the clearest way to see what the
fine-tune bought. Matches are model **candidates**, not verified identifications —
the catalogue stays the authority, and external images are reported as
identity-unknown rather than guessed.

A concrete case (`13130/10401112_0049_P01.JPG`, 1990–2009):

| | top-1 cross-era hit |
|---|---|
| tuned | `13130/10401112_0049_W01.jpg` (1900–1929), score 0.701 — same building |
| frozen | unrelated building, score 0.428 — same building absent from top-3 |

Verified invariants: the query never appears in its own results, a corpus image
resolves its real metadata, external images are flagged unknown, and
`--topk`/`--json` shapes hold. The tool also reproduces the evaluation exactly —
counting cross-era hits across the whole corpus gives 148 validation queries,
the same figure the seed analysis reports.

Regression coverage for the utility lives in `local/training/test_three_ages.py`
(7 offline tests, no index or model). The tests were mutation-checked: putting
back the original "zip queries against the gallery rows" defect makes two of them
fail, so they are not decorative. One caught a defect in the tests themselves —
the first fixture used `rows[0]` as its query, which hid the bug entirely; the
replacement queries a building that is not the first row.

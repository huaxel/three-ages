# Research focus

**Primary question:** can reviewers reproducibly distinguish visible facade evidence from documented construction phases, while identifying images that cannot support a building-specific claim?

This is a prerequisite for the approved facade-first modelling programme, not a change to its targets.

## What this means

- **Documentary date:** which event does the source date?
- **Visible style:** what architectural language is observable in this image?
- **Fabric/phase:** which surviving component belongs to which campaign?
- **Observed change:** what changed between two dated observations?

These are separate claims. A Baroque-looking facade can contain nineteenth-century replacement fabric; stable aerial appearance cannot establish structural continuity.

## Active gate

Validate the meaning of existing reviews before expanding labels or fitting a model against reviewed visual-style targets:

1. Audit the already-populated facade rows as a diagnostic, not a corpus error rate.
2. Obtain blind independent judgments without showing existing labels or source-style suggestions.
3. Report valid-label yield, agreement/abstention, remaining unit/class support, and reviewer time.
4. Revise the protocol before scaling if identity or label semantics remain inconsistent.

No new tuning, repeated construction-era scoring, or corpus expansion is authorised by this focus document. The existing Stage 1 entry thresholds in `training-plan.md` remain unchanged.

## Measured baseline — 2026-10-26

The facade audit reports 17/77 populated review rows, of which **6 are uncontradicted valid labels and 11 carry a style alongside a context-only / no-annotation observation**. Valid-label class support is baroque 4 images across 2 units, classical french 2 images across 1 unit, renaissance-inspired 0. Held-out style evaluation remains infeasible; the deficit is now semantic, not just numerical.

## Zero-human-hours probe — 2026-10-26

The exploratory 12-family probe fit weak catalogue tags (61,743 train images) and evaluated validation buildings only: building-macro exact match 0.50, micro-F1 0.51; neoclassical F1 0.69, eclectic 0.63, and baroque F1 0.245 (167 validation images). These are metadata-reproduction scores, not visual-style accuracy. On the six valid pilot rows with toolchain-calibrated encodings (max absolute difference 5e-07 vs cache), it predicted baroque for 2/4 baroque examples, no family for the 1878 engraving, and baroque for both classical-French examples. Correction: the 12-family head has no dedicated Louis XIV class; its helper routes unseen terms to a generic `other` class, trained on only 106 images tagged Mauresque, Néo-égyptien, or Néo-byzantin. The owner-approved vocabulary already includes Louis XIV, so this is a model-target mismatch—not a vocabulary decision still needed. Reports: `local/training/style_weak_val_20261026.json`, `local/training/style_clean_spotcheck_20261026.json` (gitignored).

## Owner-crosswalk taxonomy probe — 2026-10-26

Added `style_taxonomy` to `prototypes/three-ages/train_probe.py`, applying the existing owner-agreed Irismonument crosswalk rather than the exploratory 12-family aliases. The mapping has 16 source-tag categories; exact matching covers 40/43 raw manifest terms (85,122 of 85,330 style-tag occurrences). The three unmapped terms—Gothique, Néo-byzantin and Régence—account for 208 occurrences. The probe excludes 2,234 styled rows with no positive mapped period/style target (including descriptor-only terms) instead of turning them into all-negative training examples. Current byte-pinned cache verification ran before fitting.

On 52,123 train images and 6,557 validation images from 16,514 and 2,029 buildings respectively, the fixed linear probe scored micro-F1 0.549 and building-macro exact match 0.496 against weak catalogue tags. Baroque F1 was 0.283 (62 validation images); baroque_classical was 0.065 (22 images); eclecticism 0.677 and neoclassical 0.729. Do not compare these directly with the earlier 12-family scores: the label definitions and eligible rows differ. These remain proxy-reproduction metrics, not human visual-style evaluation, and do not satisfy Stage 1's independent-label threshold.

Important residual mismatch: the source crosswalk is not the full image-review vocabulary. It has no dedicated Louis XIV or Baroque-with-Renaissance-elements output; its 16 categories are source-derived labels, not direct predictions for every approved facade class. No new human reviews or Colab runtime were used. Report: `local/training/style_taxonomy_val_20261026_v3.json` (gitignored; includes input SHA-256 provenance).

## Blind review handoff audit — 2026-10-26

The existing `three-ages-independent-image-review.csv` is not a valid blind handoff: all 17 `facade_observation`, `reviewer`, and `reviewed_at` values exactly match the primary worksheet; the independent `facade_label` fields are blank. The generic bundle builder would have exposed those copied primary annotations, so it now refuses to package any worksheet with prefilled review answers. The original worksheets were left untouched.

Added `prototypes/three-ages/build_blind_facade_style_packet.py` and prepared `local/training/blind-style-review-20261026/blind-facade-style-review.zip` for a second look at the 17 already-labeled images. The reviewer-facing CSV/gallery use anonymous IDs, blank answers, and metadata-stripped PNGs with pixel-identical decoded content; no source URLs, names, dates, primary labels, or observations are shown in the review surface. Per-image licence/credit details are in a separate after-review file; the primary answer key is outside the ZIP at `local/training/blind-style-review-20261026/answer-key.json` and must not be shared.

This is a small paired consistency check, not a representative sample or model evaluation. It has not been reviewed yet, creates no new training labels, and does not satisfy the independent-label threshold. The packet includes 15 CC BY 4.0 images, one marked no known copyright restrictions, and one CC BY-SA 3.0 image; the packet preserves per-image attribution.

## Cluster-then-name — 2026-10-26

30 MiniBatchKMeans clusters (seed 42) over the 76,999 frozen embeddings; contact sheet at `local/training/clusters-20261026/index.html` (90 representatives, all files local). Weak catalogue-Baroque images concentrate in clusters 13/28/21/4, all dominated by Néoclassicisme/Éclectisme labels — the teaching contradicts the seeing, which explains baroque F1 0.245 better than any model tweak. All clusters are ~0 drawing share. Do not use these clusters to decide that Louis XIV is visually inseparable: the head and clustering targets are weak source metadata, while the approved visual vocabulary has a finer, different label space. A valid separability claim needs independently reviewed examples in that class.

## Out-of-source visual-neighbour search — 2026-10-26

Added reproducible `prototypes/three-ages/training/search_visual_neighbours.py`. It embeds the six populated, non-contradicted pilot rows with frozen CLIP and searches only the byte-pinned training-split gallery, keeps one best image per building, removes exact-byte query matches and all gallery records within 200m of any Grand Place pilot building. The real run searched **60,538 images / 20,805 buildings**; excluded 1,205 nearby images, found zero exact query duplicates and zero cache-byte mismatches. Output/contact sheet (gitignored): `local/training/historical-neighbors-repro-v3-20261026/`.

This is evidence-finding, not a performance estimate. It retrieved visually similar but temporally later inventory photos: the 1942, 1952 and 1969 queries each had 4–5/5 neighbours captioned 1960–1989; the 1878 engraving's five neighbours were all 1900–1929. The weak catalogue styles of the top five were mixed and rarely matched the reviewed label exactly (the two classical-French queries returned neoclassical twice for one query, zero for the other; Baroque queries returned Rococo once and no Baroque for the rest). Thus frozen visual search can propose cross-source analogues without hand labels, but neither catalogue style nor capture-year metadata turns those neighbours into historical construction ages. Same-building vicinity and exact duplicates were excluded; unverified foundation-model pretraining overlap and non-exact near-duplicates remain limitations.

## Explicitly deferred

- Construction-era prediction as a supervised head: later hypothesis, blocked on image-level applicability.
- Cross-era/cross-pole retrieval as a research claim: supporting evidence-finding tool only until clean confirmation exists.
- Structural-change learning: remains Stage 2, blocked on completed structural interpretations with independent agreement.

## Stop rules

- Stop annotation at the pre-approved reviewer-time cap; unfinished work is a feasibility result.
- No forced adjudication or model fitting against reviewed visual-style targets while semantic contradictions remain. Weak catalogue-tag probes are diagnostics only, not Stage 1 style recognition.
- Without an independent reviewer, report a consistency audit, not independent validation.
- Preserve completed conservative register decisions; do not reopen them to manufacture stronger claims.

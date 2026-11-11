# Independent annotation handoff

For a reviewer-ready checklist, use the [independent annotation packet](independent-annotation-review-packet.md).

### Minimal blind facade-style re-review

The generic pilot independent worksheet currently contains 17 observation/reviewer/date fields copied exactly from the primary worksheet; it is not an independent review. The generic bundle builder now refuses any prefilled review answers. Do not share the old independent worksheet or build the generic bundle from it.

To prepare a source-blind consistency check of the 17 existing style-labelled images, run:

```sh
python3 prototypes/three-ages/build_blind_facade_style_packet.py
```

Share only `local/training/blind-style-review-20261026/blind-facade-style-review.zip`. Keep the adjacent `answer-key.json` private. The ZIP presents anonymous image IDs, blank review fields and metadata-stripped, pixel-preserving images; required attribution is separated into a file marked for after review. This checks only the existing small annotated set; it is not a representative sample or model evaluation. After return, preserve the returned ZIP, compare its `review.csv` to the private answer key, record agreement/abstention and reviewer time, and do not use it for training without the normal adjudication gate.

The generic pilot image worksheet cannot currently be used for a full blind bundle: its 17 observation/reviewer/date fields are copied from primary review, and regeneration preserves those values. The bundle builder refuses this state. Do not clear or overwrite those worksheets to force a bundle; use the focused style-only packet above for the current check. A future full bundle needs clean blank review worksheets in a separate, provenance-preserving staging area.

Other blind second-review worksheets cover the six-case pilot, case-level structural comparisons and scaled photo sources:

- `prototypes/three-ages/data/three-ages-independent-image-review.csv`
- `prototypes/three-ages/data/three-ages-independent-structural-review.csv`
- `prototypes/three-ages/data/balat-independent-photo-review.csv`
- `prototypes/three-ages/data/commons-independent-photo-review.csv`

Regenerate them with:

```sh
python3 prototypes/three-ages/export_independent_review.py
python3 prototypes/three-ages/build_independent_review_bundle.py
```

Import a reviewer-returned ZIP with `python3 prototypes/three-ages/import_independent_review_bundle.py --bundle <zip>`. It verifies the evidence files and local provenance, and only copies annotation fields; it never extracts archive paths to disk.

When creating an independent worksheet for the first time, the exporter copies evidence provenance but omits primary identity notes, labels, observations, reviewer, date, confidence, and review status. On regeneration it preserves existing independent fields; it does not clear or repair contaminated values. A changed evidence key or provenance causes a refusal rather than silently reattaching a review. Inspect the resulting review columns before sharing, and use the bundle builder's blank-answer guard.

## Required review steps

1. Assign a reviewer other than the primary annotator. Record that person's name and ISO date in the appropriate independent worksheet.
2. Enter identity verdict and facade label/observation independently for image rows. For structural rows, record the independent comparison across the pinned epochs/crops. Use `uncertain` or explain when evidence is insufficient; do not infer structural continuity from facade similarity.
3. After the independent pass is complete, compare each independent row with the primary worksheet. Record agreement, partial agreement, or disagreement and a rationale in the project review record before adjudication.
4. Once both annotations are complete, generate paired adjudication worksheets with `python3 prototypes/three-ages/compare_independent_reviews.py`. It refuses incomplete annotations or identical reviewer names. Record `agreement` (`agree`, `partial`, `disagree`, or `not-comparable`), rationale, disposition, adjudicator and date in the resulting adjudication CSVs. For photo channels, also record `resolved_facade_label`. Regeneration preserves dispositions but refuses to attach them if either annotation changes.
5. Preserve both annotations and the disposition. Do not replace disagreement with a consensus label or assign final confidence until the disposition is documented. For photo training rows, record the post-adjudication `resolved_confidence` (`low`, `medium`, or `high`) with the resolved label.
6. The training manifest consumes only BALaT/Commons photo adjudications with two distinct annotators and a resolved vocabulary label. The pilot image/structural adjudication sheets do not promote photo rows into that manifest.

The generator and its regression test are included in `scripts/validate-prototypes.sh`. The manual second annotation and comparison remain required; automation cannot satisfy independence.

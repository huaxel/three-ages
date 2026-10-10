# Independent annotation handoff

For a reviewer-ready checklist, use the [independent annotation packet](independent-annotation-review-packet.md).

Blind second-review worksheets cover the six-case pilot, case-level structural comparisons and scaled photo sources:

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

The export copies evidence provenance but omits the primary annotator's identity notes, labels, observations, reviewer, date, confidence, and review status. The second reviewer should work from these files without first consulting the primary review worksheets. Independent fields are preserved on regeneration; a changed evidence key or provenance causes a refusal rather than silently reattaching a review.

## Required review steps

1. Assign a reviewer other than the primary annotator. Record that person's name and ISO date in the appropriate independent worksheet.
2. Enter identity verdict and facade label/observation independently for image rows. For structural rows, record the independent comparison across the pinned epochs/crops. Use `uncertain` or explain when evidence is insufficient; do not infer structural continuity from facade similarity.
3. After the independent pass is complete, compare each independent row with the primary worksheet. Record agreement, partial agreement, or disagreement and a rationale in the project review record before adjudication.
4. Once both annotations are complete, generate paired adjudication worksheets with `python3 prototypes/three-ages/compare_independent_reviews.py`. It refuses incomplete annotations or identical reviewer names. Record `agreement` (`agree`, `partial`, `disagree`, or `not-comparable`), rationale, disposition, adjudicator and date in the resulting adjudication CSVs. For photo channels, also record `resolved_facade_label`. Regeneration preserves dispositions but refuses to attach them if either annotation changes.
5. Preserve both annotations and the disposition. Do not replace disagreement with a consensus label or assign final confidence until the disposition is documented. For photo training rows, record the post-adjudication `resolved_confidence` (`low`, `medium`, or `high`) with the resolved label.
6. The training manifest consumes only BALaT/Commons photo adjudications with two distinct annotators and a resolved vocabulary label. The pilot image/structural adjudication sheets do not promote photo rows into that manifest.

The generator and its regression test are included in `scripts/validate-prototypes.sh`. The manual second annotation and comparison remain required; automation cannot satisfy independence.

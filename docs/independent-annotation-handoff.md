# Independent annotation handoff

For a reviewer-ready checklist, use the [independent annotation packet](independent-annotation-review-packet.md).

The pilot now has blind second-review worksheets for image-level facade review and case-level structural comparison:

- `prototypes/three-ages/data/three-ages-independent-image-review.csv`
- `prototypes/three-ages/data/three-ages-independent-structural-review.csv`

Regenerate them with:

```sh
python3 prototypes/three-ages/export_independent_review.py
```

The export copies evidence provenance but omits the primary annotator's identity notes, labels, observations, reviewer, date, confidence, and review status. The second reviewer should work from these files without first consulting the primary review worksheets. Independent fields are preserved on regeneration; a changed evidence key or provenance causes a refusal rather than silently reattaching a review.

## Required review steps

1. Assign a reviewer other than the primary annotator. Record that person's name and ISO date in the appropriate independent worksheet.
2. Enter identity verdict and facade label/observation independently for image rows. For structural rows, record the independent comparison across the pinned epochs/crops. Use `uncertain` or explain when evidence is insufficient; do not infer structural continuity from facade similarity.
3. After the independent pass is complete, compare each independent row with the primary worksheet. Record agreement, partial agreement, or disagreement and a rationale in the project review record before adjudication.
4. Once both annotations are complete, generate paired adjudication worksheets with `python3 prototypes/three-ages/compare_independent_reviews.py`. It refuses incomplete annotations or identical reviewer names. Record `agreement` (`agree`, `partial`, `disagree`, or `not-comparable`), rationale, disposition, adjudicator and date in the resulting `three-ages-*-adjudication.csv` files. Regeneration preserves dispositions but refuses to attach them if either annotation changes.
5. Preserve both annotations and the disposition. Do not replace disagreement with a consensus label or assign final confidence until the disposition is documented.
6. The independent worksheets are review inputs only. They are not consumed by the training manifest and do not themselves promote any photo or label into training data.

The generator and its regression test are included in `scripts/validate-prototypes.sh`. The manual second annotation and comparison remain required; automation cannot satisfy independence.

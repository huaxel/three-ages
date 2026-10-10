# Three Ages independent annotation packet

**Purpose:** Obtain an independent annotation before confidence or training decisions. This packet is for a reviewer who has not seen the primary review worksheets. It does not contain the primary annotations.

## Materials

To create a self-contained archive that excludes primary-review files, run:

```sh
python3 prototypes/three-ages/build_independent_review_bundle.py
```

This writes `/tmp/three-ages-independent-review.zip` (override with `--output`). It contains all four pilot/scaled independent worksheets, referenced evidence images, an offline `gallery.html`, a README and SHA-256 manifest. Extract the ZIP and open `gallery.html` for visual review. The ZIP builder rejects unexpected worksheet columns rather than risk including hidden primary labels.

- Pilot facade/photo worksheet: [`three-ages-independent-image-review.csv`](../prototypes/three-ages/data/three-ages-independent-image-review.csv) — 14 evidence rows across six cases.
- Pilot structural worksheet: [`three-ages-independent-structural-review.csv`](../prototypes/three-ages/data/three-ages-independent-structural-review.csv) — six case-level comparisons across aligned epochs.
- Scaled photo worksheets: [`balat-independent-photo-review.csv`](../prototypes/three-ages/data/balat-independent-photo-review.csv) and [`commons-independent-photo-review.csv`](../prototypes/three-ages/data/commons-independent-photo-review.csv).
- Annotation rules and regeneration behavior: [`independent-annotation-handoff.md`](independent-annotation-handoff.md).

Image paths are relative to `prototypes/three-ages/`; open each `preview` path in the image worksheet. Structural crop paths are likewise under that directory and listed in `case_crop_previews`. Use the supplied source links, dates, checksums, licences and credits as evidence context. Do not inspect the primary review worksheet until your independent pass is complete.

## Reviewer instructions

1. Work independently. Do not copy labels or observations from another review.
2. For every image/photo row, fill `identity_verdict`, `facade_label`, `facade_observation`, `reviewer` and ISO `reviewed_at`. Use explicit uncertainty (such as `uncertain` or `not-visible`) rather than guessing. Use the project's agreed controlled vocabulary in `docs/facade-style-vocabulary.md` for positive labels; keep uncertainty explicit.
3. For every structural row, record the observed building-volume change or state that the imagery is insufficient; fill `reviewer` and ISO `reviewed_at`. Facade similarity alone does not establish structural continuity.
4. Keep the evidence and annotation separate: a catalogued identity is not automatically a visually confirmed match; a reconstruction date is not a visual structural label.
5. Return both CSVs without changing evidence/provenance columns.

## After the independent pass

From the repository root, regenerate the handoff (it preserves review fields and rejects changed evidence):

```sh
python3 prototypes/three-ages/export_independent_review.py
```

Then generate the paired adjudication worksheets:

```sh
python3 prototypes/three-ages/compare_independent_reviews.py
```

The second command only succeeds when the primary and independent annotations are complete and name different reviewers. In the resulting adjudication CSVs, complete the agreement category, rationale, disposition, adjudicator and date; for photo channels, also set `resolved_facade_label` and post-adjudication `resolved_confidence` (`low`, `medium`, or `high`). Preserve both annotations. The BALaT and Commons photo adjudications are required by the training-manifest gate; the pilot worksheets are not. Do not use adjudication output itself as a training manifest.

**Gate:** These files are review inputs, not approved training data. No new confidence assignment or training run should rely on them until disagreement and disposition are recorded. The scripts do not simulate or replace a human second reviewer.

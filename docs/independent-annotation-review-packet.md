# Three Ages independent annotation packet

**Purpose:** Obtain an independent annotation before confidence or training decisions. This packet is for a reviewer who has not seen the primary review worksheets. It does not contain the primary annotations.

## Materials

- Facade/photo worksheet: [`prototypes/three-ages/data/three-ages-independent-image-review.csv`](../prototypes/three-ages/data/three-ages-independent-image-review.csv) — 14 licensed evidence rows across six cases.
- Structural worksheet: [`prototypes/three-ages/data/three-ages-independent-structural-review.csv`](../prototypes/three-ages/data/three-ages-independent-structural-review.csv) — six case-level comparisons using aligned 1930–1935, 1971, 1996 and 2022 crops.
- Annotation rules and regeneration behavior: [`independent-annotation-handoff.md`](independent-annotation-handoff.md).

Image paths are relative to `prototypes/three-ages/`; open each `preview` path in the image worksheet. Structural crop paths are likewise under that directory and listed in `case_crop_previews`. Use the supplied source links, dates, checksums, licences and credits as evidence context. Do not inspect the primary review worksheet until your independent pass is complete.

## Reviewer instructions

1. Work independently. Do not copy labels or observations from another review.
2. For every image row, fill `identity_verdict`, `facade_label`, `facade_observation`, `reviewer` and ISO `reviewed_at`. Use explicit uncertainty (such as `uncertain` or `not-visible`) rather than guessing.
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

The second command only succeeds when the primary and independent annotations are complete and name different reviewers. In the resulting `three-ages-image-adjudication.csv` and `three-ages-structural-adjudication.csv`, complete the agreement category, rationale, disposition, adjudicator and date. Preserve both annotations. Do not use adjudication output as a training manifest.

**Gate:** These files are review inputs, not approved training data. No new confidence assignment or training run should rely on them until disagreement and disposition are recorded. The scripts do not simulate or replace a human second reviewer.

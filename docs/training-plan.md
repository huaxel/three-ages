# Training plan: facade recognition first, then change detection

Owner decision 2026-10-09: sequence both targets. Stage 1 trains facade
style/period recognition on the scaled BALaT corpus; Stage 2 trains
structural-change detection on the aligned four-epoch crops, reusing the
provenance pipeline. The six-case pilot serves only as eval/testbed until
scale exists. No training run starts before the blockers below clear.

## Readiness status (2026-10-09)

| Blocker | Status |
|---|---|
| Scaled corpus | PARTIAL: 41 verified CC BY 4.0 photos, 10 of 19 classes; 9 modern-era classes have zero BALaT holdings (genuine absences, not query failures) |
| Agreed vocabulary | DONE: `docs/facade-style-vocabulary.md` (owner sign-off) |
| Licence matrix | DONE: `docs/irismonument-image-licence.md`; manifest enforces CC BY 4.0 only |
| Independent-annotation check | OPEN: `balat-photo-review.csv` has 41 rows, 0 reviewed; second annotation required before confidence (TODO-65a73811) |

## Stage 1 — facade style/period classifier

- **Data**: `data/balat-training-manifest.json` (image + SHA-256, vocabulary
  label, epoch, provenance, reviewer, licence, train/eval split).
- **Splits**: building-grouped by heritage fiche (already in the manifest;
  one group never straddles train/eval). Pilot cases stay in eval only.
- **Model**: transfer learning from an ImageNet-pretrained vision backbone
  (linear probe first; fine-tune only with enough labels). Rationale: 41
  images cannot train a backbone from scratch; the corpus must grow first.
- **Entry threshold (APPROVED by owner 2026-10-09)**: every target class
  has ≥ 20 independently-agreed labels spanning ≥ 5 buildings and ≥ 2 capture
  decades before the first training run. Current corpus meets this for zero
  classes — do not train yet.
- **Eval protocol**: per-class precision/recall on the held-out building
  groups; report the confusion pairs (e.g. Baroque vs Baroque-with-classical
  features); pilot six cases as a fixed qualitative testbed with reviewer
  commentary, not a metric.
- **Reproducibility**: manifest pins image SHA-256, label, reviewer and
  split; retraining from the same manifest commit reproduces the dataset
  exactly. Model weights inherit CC BY 4.0 attribution duties and the
  EHB non-commercial framing — review before publishing any artifact.

## Stage 2 — structural change detection

- **Data**: aligned 1930–1935 / 1971 / 1996 / 2022 structural crops plus the
  reviewed structural interpretations (TODO-c1cf830f, in progress).
- **Model**: change classifier over co-registered crop pairs/quadruples
  (Siamese or differencing baseline first); labels are the reviewed
  visible-change annotations, not raw pixel diffs.
- **Blocked by**: completed structural interpretations with independent
  agreement, then the same split-safety and licence treatment as Stage 1.
- **Not started**: no architecture selection until Stage 1 data exists.

## What would change this plan

- BALaT coverage of the 9 missing classes (unlikely; holdings probed empty),
  alternate CC-licensed modern-era sources, or an owner decision to train a
  reduced 10-class Stage 1 once per-class thresholds are met.

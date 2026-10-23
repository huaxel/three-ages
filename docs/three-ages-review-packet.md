# Three Ages — human review packet

This packet is the next milestone for the prototype. Do not add interface features until these review decisions are recorded.

A generated briefing that walks the whole queue unit by unit is in
[`three-ages-review-briefing.md`](three-ages-review-briefing.md). It is derived from the
committed evidence, lists every reviewable image, and opens with the identity gate, the
shared-facade units and the recorded source conflicts. Regenerate it with
`prototypes/three-ages/generate_review_briefing.py`; the validation gate checks it stays current.

## Review order

1. Confirm the La Balance identity crosswalk before interpreting either image.
2. Review the six register claims.
3. Review the seventy-two historical-image rows covering all twenty-seven facade units.
4. Review the six aligned structural comparisons.
5. Repeat a subset with a second reviewer and record disagreements. Each reviewer should enter their name and use **Export review session** to produce an independent `three-ages-review-session.json`; do not overwrite the first reviewer's worksheet.

## Controlled values

### Register decision

Choose exactly one:

- `accept proxy for MVP` — usable as a dated proxy with its semantics preserved.
- `retain as reconstruction evidence` — useful context, but not an age claim.
- `reject source mapping` — identity or source relationship is not acceptable.

### Facade style

Choose one controlled primary style from the image; do not copy the source-described style as if it were a visual judgment:

- `baroque`
- `classical french`
- `renaissance-inspired`
- `mixed` — multiple distinct historical styles visible across registers or features.
- `other` — a visible primary style outside the initial vocabulary.
- `uncertain` — visible facade features do not clearly indicate a style.
- `not assessable` — image angle, resolution, or detail is insufficient to assess style.

### Confidence

Choose `low`, `medium`, or `high`. Confidence applies to the review decision, not to the source's authority.

## La Balance identity gate

Source `024` is **gated**. Before any image for `024` can be reviewed, resolve the crosswalk in the register worksheet's `identity_gate` column by selecting one of:

- `confirmed` — all four records describe the same building and facade.
- `confirmed with qualification` — the same building, with a stated difference (for example a side facade versus the square facade).
- `not confirmed` — the records do not describe the same building.

Record the basis for your decision in `identity_gate_note`. Resolving the gate without a recorded rationale is refused by the exporter, and an unresolved gate must not carry one.

A gate disagreement is a hard stop, not a note. If one reviewer confirms the crosswalk and records image
reviews, and another reviewer rejects it (`not confirmed`), the exporter refuses to compile those image reviews
until the crosswalk is reconciled: style labels must not survive for a building whose identity is contested.
The comparison report names the disagreement; reconcile it before exporting.

`pending` is the default and `not applicable` applies to buildings without cross-source identity evidence. `export_pilot.py` refuses to record image reviews for a gated building while the gate is `pending` or `not confirmed`, and `validate_snapshots.py` rejects a worksheet in that state. The gate therefore travels with the exported review data instead of living in a comment.

Compare:

- City open data: `The Weighing Scales`, Grand-Place 24, record `024`.
- Brussels heritage inventory: La Balance, Rue de la Colline 24, record `30991`.
- British Library: Maison de la Balance, rue de la Colline, 1878 engraving.
- Wikimedia Commons: Maison de la Balance, Grand-Place, monument id `2043-0177/0`.

## Review checklist

### Register semantics — `three-ages-register-review.csv`

Rows: `005`, `009`, `022`, `023`, `024`, `026`.

For each row, verify the linked source, compare the reported date with the City history, choose a controlled decision, and enter reviewer/date/confidence.

### Historical images — `three-ages-image-review.csv`

Rows: 77 covering all 27 facade units, at least two views each. Every one of them is reachable in the workbench and displayable in the explorer (`index.html`); both read the generated `three-ages-image-cases.json` rather than a hand-listed subset. Seventeen are the curated-pilot assets (`005`, `009`, `022`, `023`, `024`, `026`); three are supplement views (`004`, `006`, `011`); the remaining 57 are Commons candidates listed in `facade-image-commons.json`.

Use `facade-style-candidates.csv` to work through them; it pairs every asset with its building, source URL, licence, credit and source-described style text. The Commons candidates carry the raw City facade description as their weak label, which is source text and not a visual judgment.

The review workbench defaults to **Blind visual review**, hiding source-written observations and style text while annotating. Keep this enabled for independent visual labels; provenance remains in the exported row. Do not consult source descriptions until after recording the visual judgment. If you disable blinding to research provenance, record that as a non-blind review rather than treating it as an independent visual annotation.

Describe only visible, source-grounded facade observations in `facade_observation` and select one controlled primary `facade_style` when making a facade observation. The source-described style remains separate. Structural-only reviews may leave the style blank. The supplemental buildings `004`, `006`, and `011` are image-only review cases; they have no register or structural review rows. Do not infer a construction date from style alone. For La Balance, explicitly distinguish an engraving from a photograph, and resolve the identity gate first.

### Structural comparisons — `three-ages-structural-review.csv`

Rows: `005`, `009`, `022`, `023`, `024`, `026`.

Compare the identical 160px crops for 1930–1935, 1996, and 2022. Record visible changes or limitations, and distinguish `no visible change`, `possible change`, `visible change`, and `not interpretable` in the observation. Do not call a change structural when the orthophoto resolution or alignment cannot support it.

## Second-review handoff

The session JSON export is a separate reviewer submission. Compare two session files with:

```bash
python3 scripts/compare-review-sessions.py first-reviewer.json second-reviewer.json
```

Preserve both observations, and record the disagreement in the canonical worksheet's observation field before exporting the final CSV. To apply one session to a copy of a worksheet:

```bash
python3 scripts/apply-review-session.py \
  --type register \
  reviewer-session.json \
  prototypes/three-ages/data/three-ages-register-review.csv \
  /tmp/register-review-reviewed.csv
```

The tool never modifies the input worksheet and refuses provenance mismatches. Repeat with `--type image` and `--type structural` as needed. The session export includes a provenance fingerprint; reject a submission if its fingerprint no longer matches the current source row.

## Completion check

Run the validation gates after editing worksheets:

```bash
scripts/validate-prototypes.sh
scripts/validate-bonsai.sh
```

The exporter preserves completed annotations only while their source provenance remains unchanged. If provenance changes, stop and resolve the review rather than using `--reset-reviews`.

## Success criterion

The curated MVP is ready for a product decision when the identity gate is resolved, all rows have complete review metadata, and at least one subset has an independent second review with disagreement recorded.

**Reviewing 77 images does not by itself make this an evaluation set.** The source-described weak labels are
not separable by style at unit level — one `renaissance-inspired` unit, three `classical french`, ten units with
no source style term at all (see [Dataset viability at unit level](three-ages-annotation-spec.md#dataset-viability-at-unit-level)).
Reviewer labels are what would make the vocabulary usable, and a three-class evaluation needs enough independent
units per class, not enough images per class.

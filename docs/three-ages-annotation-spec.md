# Three Ages — annotation specification

This is the working protocol for turning the six-record source-linked pilot into a defensible curated MVP.

## Scope

The MVP is a manually reviewed case set of six to ten Brussels buildings. It does not attempt city-wide automated classification.

Each case keeps three claims separate:

1. **Register age:** an official construction or registration year from an approved source.
2. **Facade evidence:** a description or visual annotation of the visible facade period.
3. **Structural evidence:** an evidence-backed statement about the underlying building volume or major reconstruction.

A reconstruction date in a public history text is a **documented proxy**, not a structural-age label.

## Case schema

Each building record should contain:

```text
case_id
source_record_id
name
address
coordinates
register_claim
facade_claim
structural_claim
evidence[]
review_status
```

Each claim should contain:

```text
value or date range
claim_type: source_text | visual_annotation | image_comparison
status: pending | proxy | reviewed
confidence: unassigned | low | medium | high
rationale
reviewer
reviewed_at
```

Each evidence item should contain:

```text
evidence_id
claim_type
asset_uri
asset_epoch
preview_sha256
source_owner
licence_or_permission
observation
supports_or_contradicts
annotator
reviewer
notes
```

## Annotation rules

### Register age

- Prefer an official register or permit source over a derived year in narrative text.
- Preserve the original field name and source URL.
- If the source reports a reconstruction rather than a register year, store it as historical evidence, not as the register claim.
- A Wikidata inception claim referenced to the Brussels heritage register record (via the Heritage API `srcountry=be-bru` identifier) may be stored as a `proxy` register claim, but only with the full source chain: QID, claim URL, heritage identifier, and the city-history comparison in the note. Record agreement or disagreement explicitly; disagreement blocks any confidence assignment until review.

### Facade evidence

- Start with the source-described style as a separate text field.
- Use a controlled style vocabulary only after a reviewer agrees to it.
- Record visible features and evidence, not just a style label.
- Allow `uncertain`, `mixed`, and `not-visible` outcomes.

### Structural evidence

- Require at least two image epochs or an equivalent permitted archival source before assigning a reviewed structural claim.
- Distinguish facade replacement, rear-volume change, interior reconstruction and complete rebuilding.
- A stable facade does not prove a stable structure.
- A changed facade does not prove that the underlying volume changed.

## Review workflow

1. Select a source-linked building from the pilot.
2. Verify identity, address and coordinates.
3. Attach the register source, record its actual date semantics and compare it explicitly with the City history.
4. Attach permitted historical image assets and record their epochs and licence.
5. Annotate facade observations without inferring structure.
6. Compare the identical building-centred 1930–1935, 1996 and 2022 crop boxes for structural change. The red centre marker locates the source coordinate; it does not define a building footprint.
7. Have a second reviewer inspect the evidence and disagreement notes.
8. Record facade-source observations in `three-ages-image-review.csv` and the case-level aerial comparison in `three-ages-structural-review.csv`. In `three-ages-register-review.csv`, choose `accept proxy for MVP`, `retain as reconstruction evidence`, or `reject source mapping` and explain the semantics decision. Every completed row requires reviewer, ISO-8601 review date and `low`, `medium` or `high` confidence.
9. Regenerate with `export_pilot.py`; it preserves completed fields only while the full asset, comparison or register provenance matches, refuses to silently move or discard a review, and compiles completed rows to the corresponding `three-ages-*-reviews.json` artifact for the explorer.
10. Verify the explorer displays each reviewed observation or decision beside the correct source claim, with reviewer, date and confidence; unresolved fields remain pending. Use `--reset-reviews` only when all three sets of reviewer data should deliberately be cleared.

## MVP acceptance criteria

- [ ] Six to ten buildings have verified identity and source links.
- [ ] Each building has an approved register-year source or an explicit pending status.
- [ ] Each building has at least two permitted image epochs or a documented reason why not.
- [ ] Facade and structural claims are stored separately.
- [ ] Every non-pending claim has evidence, rationale, annotator and reviewer fields.
- [ ] Disagreements and uncertainty remain visible in the explorer.
- [ ] Image permissions and reuse conditions are documented.
- [ ] The building export and three review worksheets can reproduce every displayed claim and decision.

## Current pilot status

The six current cases have source-described facade text and documented reconstruction proxies. They intentionally have no final confidence labels.

Image epochs: the pilot commits three aligned ortho extracts for the pilot area — BruCiel 1930–1935 and 1996 under CC0, plus urbisgrid 2022 (open data; CC0 per the Ortho info page, CC-BY per the INSPIRE record) — and five KIK-IRPA BALaT facade photographs from 1941–1942 under CC BY 4.0 for Grand-Place 6, 9, 21-22, 23 and 26-27. Maison de la Balance has an exact-case 1878 British Library engraving marked no known copyright restrictions and a 2011 Wikimedia Commons photograph under CC BY-SA 3.0. Each case-level preview stores its source URL, image URL, epoch, credit, SHA-256 checksum and explicit no-annotation status. The 1944 BruCiel WMS is retired, but the verified 1930–1935 layer now supplies the missing historical structural/aerial source; its mixed capture window and any visible changes require reviewer interpretation.

Register status: three cases (The Swan, Joseph and Anne, The Angel) carry `proxy` register years sourced from Wikidata inception claims referenced to Brussels heritage register records; the other three carry direct heritage-inventory reconstruction dates. Each now stores `date_semantics` and a structured City-history comparison. The Swan (1698) agrees; Joseph and Anne (1695) is compatible with “reconstruction after 1695”; The Angel preserves the 1695-versus-1697 disagreement. All six remain unreviewed until a controlled decision is recorded in the register worksheet.

Three provenance-safe worksheets are ready. `three-ages-image-review.csv` contains seven facade-asset rows. `three-ages-structural-review.csv` binds six case rows to the complete 1930–1935/1996/2022 evidence set, crop geometry and pixel hashes. `three-ages-register-review.csv` binds six semantics decisions to each source claim, source note and City comparison. Completed rows compile to the JSON artifacts displayed by the explorer, and the exporter refuses preservation after provenance changes. The next blockers are reviewer confirmation of the La Balance crosswalk (City and Commons use Grand-Place labels; heritage and the British Library use Rue de la Colline), completion of the six structural comparisons and completion of the six register decisions.

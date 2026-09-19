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
3. Attach the register source and record the register claim.
4. Attach permitted historical image assets and record their epochs and licence.
5. Annotate facade observations without inferring structure.
6. Compare image epochs for structural change.
7. Have a second reviewer inspect the evidence and disagreement notes.
8. Assign confidence only after review.
9. Export the case with all evidence and unresolved fields preserved.

## MVP acceptance criteria

- [ ] Six to ten buildings have verified identity and source links.
- [ ] Each building has an approved register-year source or an explicit pending status.
- [ ] Each building has at least two permitted image epochs or a documented reason why not.
- [ ] Facade and structural claims are stored separately.
- [ ] Every non-pending claim has evidence, rationale, annotator and reviewer fields.
- [ ] Disagreements and uncertainty remain visible in the explorer.
- [ ] Image permissions and reuse conditions are documented.
- [ ] The exported dataset can reproduce every displayed claim.

## Current pilot status

The six current cases have source-described facade text and documented reconstruction proxies. They intentionally have no final confidence labels.

Image epochs: the pilot now commits two legally reusable modern ortho extracts for the pilot area — BruCiel 1996 (CC0) and urbisgrid 2022 (open data; CC0 per the Ortho info page, CC-BY per the INSPIRE record). They are displayed as source previews only and are not yet attached as evidence to individual cases. The analytical blocker remains the historical epoch (1940s): the 1944 BruCiel WMS is retired, and permitted archival photographs are pending the archives request.

Register status: three cases (The Swan, Joseph and Anne, The Angel) carry `proxy` register years sourced from Wikidata inception claims referenced to Brussels heritage register records, with the city-history comparison recorded in each note. The Swan (1698) agrees with the city text; Joseph and Anne (1695) is consistent with "reconstruction after 1695"; The Angel shows a recorded inter-source disagreement (Wikidata 1695 vs city text 1697) and must not receive confidence until reviewed. The Horn, The Weighing Scales and The Pigeon now carry direct Brussels architectural heritage inventory reconstruction-date proxies (1697, 1704 and 1697), with source URLs and the distinction from an original-construction year recorded in each note. All six remain unreviewed.

The next blockers are access to permitted 1940s-era imagery and confirmation that the six proxy dates satisfy the intended register-year semantics.

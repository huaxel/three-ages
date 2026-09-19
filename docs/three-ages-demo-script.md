# Three Ages — stakeholder demo script

## Goal

Use the prototype to test whether an evidence-led building-history explorer is useful before requesting image access or creating more labels.

## Five-minute flow

1. **State the question**
   > Can a Brussels building record show separate register, facade and structural evidence without collapsing uncertainty into one date?

2. **Set the boundary**
   Explain that the pilot contains six real Grand Place source records. The source text is real; register dates are explicitly labelled proxies (three Wikidata/heritage-linked and three official architectural-inventory reconstruction dates). Five cases include licensed 1941–1942 KIK-IRPA facade previews. La Balance has an exact-case 1878 British Library engraving and a 2011 Commons photograph, but image-derived annotations are intentionally not final until reviewed.

3. **Select a case**
   Open a case such as Joseph and Anne or The Angel. Point out why it was selected: the history text describes an earlier reconstruction and a later facade rebuild.

4. **Read the three evidence cards**
   - Register/source date: three cases show Wikidata inception claims referenced to heritage records, while three show direct heritage-inventory reconstruction dates. Open “Register semantics review” to show the actual source semantics, structured City comparison and pending controlled decision; the displayed year remains a proxy until review.
   - Image previews: five cases show KIK-IRPA source previews with 1941–1942 epochs and CC BY 4.0 credit; La Balance shows an 1878 British Library engraving with no known copyright restrictions and a 2011 Commons photograph under CC BY-SA 3.0. The previews are not annotations, and the engraving-versus-photograph difference must remain explicit.
   - Facade evidence: source-described style, not a dated visual classification.
   - Structural evidence: documented reconstruction proxy, not an aerial-image conclusion.

5. **Inspect the evidence trail**
   Show the source history, facade description, next annotation step, dataset endpoint, building export, facade-image worksheet, structural-comparison worksheet and register-semantics worksheet. Then show the three aligned ortho previews (BruCiel 1930–1935 and 1996 under CC0; 2022 open data), the three building-centred crops for the selected case and all seven case-level facade previews with per-asset rights and credit. Explain that the same 160 px crop box is applied to every structural epoch and the red ring marks the source coordinate rather than a building footprint. Use 1930–1935 versus 2022 as structural context without asserting a change. For La Balance, compare the 1878 and 2011 views and open the four-source identity crosswalk: City uses `Grand-Place 24`; the heritage inventory uses `Rue de la Colline 24`; the British Library caption says `rue de la Colline`; Commons says `Grand-Place` and supplies monument id `2043-0177/0`. Emphasise that the explorer only displays annotations after complete reviewer metadata passes the provenance checks.

6. **Close with the feasibility decision**
   Ask whether the stakeholder accepts the City-to-heritage identity mapping for La Balance, whether its 1878 engraving/2011 photograph pair is sufficient for facade review, and whether the 1930–1935/2022 ortho comparison is sufficient for structural review. Then use the register worksheet’s controlled choices—accept as an MVP proxy, retain as reconstruction evidence, or reject the mapping—to capture the intended semantics explicitly.

## Questions to capture

- What heritage or planning decision would this explorer support?
- Which building changes matter: facade replacement, rear-volume change, interior reconstruction or complete rebuilding?
- Which image sources are sufficient for review? (three aligned ortho epochs and seven case-level facade previews are secured; La Balance has an 1878/2011 facade pair, and 1930–1935/2022 supplies historical-to-modern structural context)
- What evidence is sufficient to call a structural claim reviewed?
- Who can perform a second review of annotations?
- Is a six-to-ten-building curated MVP valuable without city-wide automation?

## Success signal

The demo succeeds if the stakeholder accepts the separation between source text, visual annotation and structural evidence, and can identify an approved image source or reviewer. If they require automatic city-wide classification before accepting a curated pilot, revisit the scope before implementation.

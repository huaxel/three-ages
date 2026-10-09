# Facade style vocabulary

**Status:** draft for reviewer sign-off (annotation-spec requirement: image-derived style labels use a controlled vocabulary only after a reviewer agrees to it).

**Owner decisions (2026-10-09):** reuse the style terms already used by the sources (City dataset, heritage inventory) rather than a custom or external taxonomy; the vocabulary serves the model-training goal (facade style/period recognition first) recorded in `prototype-next-iteration.md`.

**Primary source:** City of Brussels Grand Place snapshot, committed at `prototypes/three-ages/data/grand-place-buildings.json` (34 records; 32 with facade text), catalogue CC BY 4.0. Every record carries its own `source_url`. **Corroborating source:** Brussels architectural heritage inventory (monument.heritage.brussels), consulted 2026-10-09 for the six pilot cases.

## Label semantics (read before labeling)

- A style term describes the visible facade's architectural language. It is **not** a construction date; date semantics stay in the register channel (`three-ages-register-review.csv`).
- Several visible facades are 19th-century reconstructions or restorations of 1697-era fronts, per the heritage inventory: Le Cornet restored 1899–1902, Le Cygne 1903–1904, Joseph et Anne reconstructed 1896–1897, L'Ange reconstructed 1896–1897, Le Pigeon restored 1906–1908. When known, record the fabric epoch alongside the style term (for example `Baroque (fabric: 1896–1897 reconstruction of a 1697 design)`). A model trained on these images sees restored fabric; do not present labels as evidence of unaltered 17th-century material.
- Source-described style and image-derived style stay separate fields, per `docs/three-ages-annotation-spec.md`.

## Style terms

| Term | Definition (as used by the sources) | Source usage |
|---|---|---|
| **Baroque** | Ornate post-1695 reconstruction fronts: curved/dramatic gables (scroll or "prow" forms), layered orders, sculptural emblem programs. | City: 11 records, incl. pilot 005, 022, 023, 024. Heritage agrees for Le Cornet ("façade baroque", rococo-précoces elements), Joseph et Anne ("ordonnance de type baroque tardif"), L'Ange ("style baroque tardif"), La Balance (three-storey Baroque facade). |
| **Baroque with classical features** | Baroque front whose organization is classical: giant order, antique-style pediment, balanced composition. | City: 010 Brewers House, 025 Golden Boat ("baroque style with classical features/appearance"). |
| **Louis XIV (French classical)** | Restrained, monumental front in the French classical manner. Heritage term adopted as the primary label (2026-10-09); the City wording "classical French style" is recorded beside it. | Heritage: "de style Louis XIV" ([40020](https://monument.heritage.brussels/fr/buildings/40020)). City: 009 The Swan. |
| **Antique (classical orders)** | Fronts composed of registers with antique/classical orders and pediment, without a named baroque element. | City: 001 King of Spain ("3 antique orders"), 004 She-Wolf ("pediment in the antique style"). |
| **Mixed: Antique registers + Baroque gable** | Both terms appear for one front; record as `mixed` with both components. | City: 002 Wheelbarrow, 003 Sack. |
| **Baroque with Renaissance elements** | Baroque front integrating Renaissance composition (overlapping registers, arched windows, serlienne/Venetian window). Heritage term adopted as the primary label (2026-10-09); the City wording "still inspired by the Renaissance" is recorded beside it. | Heritage: "façade baroque … intégrant harmonieusement des éléments Renaissance" ([31141](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/26/31141)). City: 026 Le Pigeon. |

## Non-style and uncertainty classes

- **no on-square facade** — 014 (built inside a block; no square front to recognize).
- **undescribed** — 007 City Hall, 028 King's House (no facade text in the City snapshot).
- **style not named in source** — the source describes composition/materials without a style word (015–020 Dukes-of-Brabant ensemble with giant order and mansard roof; 008, 030–034). These need reviewer/heritage terms before becoming positive training labels.
- **uncertain / mixed / not-visible** — annotation-spec outcomes for image-derived labels.

## Pilot-case crosswalk (City term vs heritage term)

| Case | City term | Heritage term | State |
|---|---|---|---|
| 005 The Horn (Le Cornet) | Baroque | Façade baroque, elements rococo précoces ([31123](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/6/31123)) | agree |
| 009 The Swan (Le Cygne) | classical French style | Style Louis XIV ([40020](https://monument.heritage.brussels/fr/buildings/40020)) | resolved 2026-10-09: heritage term **Louis XIV** adopted as the label; City wording kept beside it |
| 022 Joseph and Anne | Baroque (gable in two registers of baroque style) | Ordonnance de type baroque tardif ([31138](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/21/31138)) | agree (late-Baroque qualifier noted) |
| 023 The Angel (L'Ange) | Baroque (baroque gable) | Style baroque tardif ([31139](https://monument.heritage.brussels/fr/buildings/31139)) | agree (late-Baroque qualifier noted) |
| 024 The Weighing Scales (La Balance) | Baroque façade, 3 overlapping orders | Baroque facade, caryatids/balcony ([30991](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Colline/24/30991)) | agree |
| 026 The Pigeon (Le Pigeon) | still inspired by the Renaissance | Façade baroque under pignon à consoles renversées integrating Renaissance elements ([31141](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/26/31141)) | resolved 2026-10-09: heritage term **Baroque with Renaissance elements** adopted as the label; City wording kept beside it |

## Full 34-record mapping (source-derived, City dataset)

| ID | Name | Label | Style-bearing evidence (City facade text) | |
|---|---|---|---|---|
| 001 | The King of Spain | Antique (classical orders) | …composed of 3 registers with 3 antique orders; balustrade and roof dome… | |
| 002 | The Wheelbarrow | Mixed: Antique registers + Baroque gable | …ue style, and finished with a baroque gable… | |
| 003 | The Sack | Mixed: Antique registers + Baroque gable | …rs in the Antique style and a baroque gable… | |
| 004 | The She-Wolf | Antique (classical orders) | …pediment in the antique style… | |
| 005 | The Horn | Baroque | Façade in a striking Baroque style, with concave lateral spans and a highly elaborate crowning… | **pilot** |
| 006 | The Fox | Baroque | …finished with a baroque gable… | |
| 007 | City Hall | undescribed | — | |
| 008 | The Star | style not named in source | …giant order spanning 2 levels, scrolled gable… | |
| 009 | The Swan | Louis XIV (City: classical French) | …in the classical French style, topped by a domed roof… | **pilot** |
| 010 | The Brewers House (The Golden Tree) | Baroque with classical features | Monumental façade in baroque style with classical features… | |
| 011 | The Rose | Baroque | …divided into 3 registers, with baroque gable… | |
| 012 | Mount Tabor | Baroque | …very sober lower section and baroque gable… | |
| 013 | The King of Bavaria | Baroque | …finished with a large baroque gable… | |
| 014 | The Dukes of Brabant - Fortune | no on-square facade | House without a façade, as it was built inside a block of houses… | |
| 015 | The Dukes of Brabant - the Hermitage | style not named in source | …giant order spanning the two upper floors, monumental cornice and balustrade in front of the mansard roof… | |
| 016 | The Dukes of Brabant - Fortune | style not named in source | (same ensemble text as 015) | |
| 017 | The Dukes of Brabant - The Windmill | style not named in source | (same ensemble text as 015; pediment modified 1770, Dewez) | |
| 018 | The Dukes of Brabant - the Tin Pot | style not named in source | (same ensemble text as 015; pediment modified 1770, Dewez) | |
| 019 | The Dukes of Brabant - The Hill | style not named in source | (same ensemble text as 015) | |
| 020 | The Dukes of Brabant - the Purse | style not named in source | (same ensemble text as 015) | |
| 021 | The Stag | Baroque | …finished with a gable in the baroque style… | |
| 022 | Joseph and Anne | Baroque | …gable in two registers of baroque style… | **pilot** |
| 023 | The Angel | Baroque | …disproportionate giant order on 3 levels instead of 2, baroque gable… | **pilot** |
| 024 | The Weighing Scales | Baroque | Baroque façade with an original elevation, adorned with 3 overlapping orders… | **pilot** |
| 025 | The Golden Boat | Baroque with classical features | Monumental façade in baroque style with a classical appearance… | |
| 026 | The Pigeon | Baroque with Renaissance elements (City: Renaissance-inspired) | Façade still inspired by the Renaissance… Venetian window… | **pilot** |
| 027 | The Arms of the Duchy of Brabant | Baroque | …restrained gable in the baroque spirit… | |
| 028 | The King's House | undescribed | — | |
| 029 | The Helm | Baroque | …gable with inverted consoles in the Baroque style… | |
| 030 | The Peacock | style not named in source | Modest façade in plastered and painted masonry… | |
| 031 | The Little Fox | style not named in source | …restrained façade in painted and coated brick, hipped roof… | |
| 032 | The Oak | style not named in source | …restrained façade in painted and coated brick, hipped roof… | |
| 033 | Saint Barbara | style not named in source | Narrow façade with a very restrained elevation, finished with a scroll gable… | |
| 034 | The House of the Donkey | style not named in source | Façade with 3 registers with orders and original gable finished with a curved pediment… | |

Positive style classes available today: Baroque (11), Baroque with classical features (2), Antique (2), Mixed (2), Louis XIV (1), Baroque with Renaissance elements (1). Twelve records carry composition-only descriptions, two are undescribed, one has no on-square facade. **This confirms the scale-first decision: the current corpus cannot train a recognizer from scratch, and none of the modern-era classes below has a single label yet.**

## Modern-era terms (agreed 2026-10-09; for corpus scaling beyond the Grand Place)

Owner decision 2026-10-09: the vocabulary covers the modern movements so the recognizer spans the full Brussels era range. Definitions follow the Brussels heritage inventory glossary and the Flemish heritage styles thesaurus. These classes have **no positive labels in the current corpus**; the scale task must deliberately source era examples (Horta-era houses, interwar fronts, 1970s–80s buildings).

| Term | Definition (source) | Period |
|---|---|---|
| **Eclecticism** | Courant architectural puisant librement son inspiration dans plusieurs styles (inventory glossary [506](https://monument.heritage.brussels/fr/glossary/506)) | ca. 1850–1914 |
| **Historicist neo-styles** (neo-Gothic, neo-Renaissance, neo-Baroque, neo-classical) | Revival fronts referencing one past style; inventory "néo" family (néo-baroque, néo-Renaissance ca. 1860–1914; néo-Louis XV/néo-rococo from ca. 1910) | mostly 1860–1914 |
| **Art Nouveau** | International movement reacting against the neo-styles; Belgian floral (Horta) and geometric (Hankar, Vienna Secession) tendencies (inventory glossary [501](https://monument.heritage.brussels/fr/glossary/501)) | 1893–ca. 1914 |
| **Art Deco** | Tendance à la géométrisation des formes et des ornements (inventory [glossary](https://monument.heritage.brussels/fr/glossary/)) | interwar |
| **Paquebot style** | Modernist nautical language: horizontal emphasis, rounded corners, bandeau and hublot windows (inventory [description](https://monument.heritage.brussels/fr/buildings/22231)) | 1930–1940 |
| **Functionalism** | Function takes precedence over form (inventory [glossary](https://monument.heritage.brussels/fr/glossary/)) | ca. 1920s–1930s |
| **Interwar modernism** | Sobriety of forms, bandeau windows, absence of decoration (inventory [description](https://monument.heritage.brussels/fr/buildings/22231)) | ca. 1920–1940 |
| **Post-war modernism** | Simple lines, large glazed openings, brick, natural stone, metal (inventory [description](https://monument.heritage.brussels/fr/buildings/22231)) | ca. 1940–1960 |
| **Expo 58 / playful modernism** | Humanized functionalism: V-pillars, angled forms, star motifs, vivid color (inventory [description](https://monument.heritage.brussels/fr/buildings/22231)) | ca. 1950–1965 |
| **Late modernism** | Rationalized, sober brick volumes with brutalist leanings (inventory [description](https://monument.heritage.brussels/fr/buildings/22231)) | ca. 1970–1980 |
| **Brutalism** | Structural legibility, raw material expression (referenced in the inventory late-modernism description; verify the exact glossary entry on first case) | ca. 1960s–1970s |
| **Postmodernism** | Reacts against functionalist sobriety; ornament restored as meaning, historical citations applied with irony (styles thesaurus [Stijlen en Culturen/26](https://thesaurus.onroerenderfgoed.be/conceptschemes/STIJLEN_EN_CULTUREN/c/26); Brussels overview: "Tien keer postmoderne architectuur in Brussel", Erfgoed Brussel 19–20) | 1970s–1980s |
| **Contemporary** | Post-1980s class (inventory glossary category "architecture contemporaine"); define boundaries when the first cases are selected | post-1980s |

Modernism sub-periods are **separate label classes** (owner decision 2026-10-09), not qualifiers of one Modernism term.

## Corpus extension (2026-10-09, from the Irismonument inventory)

Owner decisions after the Irismonument pull (`prototypes/fetch_irismonument.py`, 40,919 address-features) mapped the inventory's 340 raw style terms onto the vocabulary:

- **Neoclassical** (inventory: Néoclassicisme) — own class; 7,919 candidate records.
- **Beaux-Arts** — own class; 1,845 candidates.
- **Second Empire** — own class (significant Brussels style); 42 candidates.
- The other 19th-c. French period terms (Empire, Louis-Philippe, Rococo, Régence, Mauresque) fold into **Historicist neo-styles**.
- École d'Amsterdam, Nieuwe eenvoud, Classicisme moderne, Pré-modernisme fold into **Modernism** (sub-period by build year); Architecture high-tech folds into **Contemporary**.
- Descriptor terms (Architecture régionaliste/pittoresque/rurale/traditionnelle/traditionaliste/d'intégration) are approach descriptors, not periods — excluded from positive labels, like the vocabulary's "style not named in source" class.
- Modernism sub-period bucketing by inventory build year (BULT): 1920–1940 interwar, 1940–1950 post-war, 1950–1966 Expo 58, 1966–1981 late; out-of-range or missing year → "period undetermined".

Machine-readable artifacts: `prototypes/three-ages/data/irismonument-style-mapping.json` (term → classes) and `irismonument-case-selection.json` (per-class counts + criteria + sample), produced by `prototypes/map_irismonument_corpus.py`.

## Reviewer sign-off

Agreed with the project owner, 2026-10-09 (project chat):

- [x] Historical terms and definitions agreed; heritage terms adopted where City and heritage differ (Le Cygne → Louis XIV; Le Pigeon → Baroque with Renaissance elements)
- [x] Pilot crosswalk resolved; fabric-epoch rule agreed (restoration/reconstruction epoch recorded beside every style label)
- [x] Modern-era terms agreed: Eclecticism, Historicist neo-styles, Art Nouveau, Art Deco, Paquebot style, Functionalism, Brutalism, Postmodernism, Contemporary, plus Modernism sub-periods (interwar, post-war, Expo 58, late) as separate classes

Reviewer: project owner (user-confirmed in chat) Date: 2026-10-09

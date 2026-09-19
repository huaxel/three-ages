# Three Ages — source access checklist

This checklist records the first source-access review for the curated MVP. A source being discoverable does not mean its images are reusable.

## Historical aerial imagery

### BruCiel / Brussels Mobility

- **Landing/API:** [BruCiel information page](https://data.mobility.brussels/en/info/ortho_44/) and the listed [BruCiel API](https://urbanisme.irisnet.be/cartographie/bruciel).
- **Historical photo discovery:** [BruCiel viewer](https://bruciel.brussels/). The official description reports roughly 5,000 selected, geolocated historical photographs across different periods; reuse terms must be checked per asset.
- **1930–1935 layer:** [Ortho 1935 metadata](https://data.mobility.brussels/en/info/ortho_35/) explicitly links to [CC0](https://creativecommons.org/publicdomain/zero/1.0). The capabilities abstract states that source images were captured between 1930 and 1935.
- **1944 layer:** [Ortho 1944 metadata](https://data.mobility.brussels/en/info/ortho_44/) exposes WMS/WFS services, a web viewer and an explicit [CC0](https://creativecommons.org/publicdomain/zero/1.0) licence.
- **1996 layer:** [Ortho 1996 metadata](https://data.mobility.brussels/en/info/d5e0a5dc-e3b7-48ce-a7ae-bac5ec0b38ba/) explicitly links to [CC0](https://creativecommons.org/publicdomain/zero/1.0).
- **Other epochs:** BruCiel covers multiple periods, but each layer needs its own licence and completeness check.
- **Modern urban.brussels orthos:** the [Ortho info page](https://data.mobility.brussels/info/Ortho) states CC0 for the `urbisgrid` ortho layers, while the INSPIRE distribution record requires CC-BY attribution. Either way the 2022 layer is reusable open data; the pilot records attribution for both readings.

**Current status:** the 1930–1935 and 1996 WMS layers both return nonblank PNG extracts for the same Grand Place bounding box; the 2022 urbisgrid request supplies the aligned modern comparison. All three previews are committed. The metadata page still documents `BDU_DEP:Orthophotoplans_1935`, but the live layer has moved to `URBAN_DCC_ER:Orthophotoplans_1935`; the downloader and inventory preserve the working endpoint. The 1944 layer still fails every GetMap request with `LayerNotDefined`: its `cascaded="1"` upstream has gone away, so that endpoint remains retired. The verified CC0 1930–1935 layer now replaces it as the historical structural pilot epoch. Five reusable 1941–1942 KIK-IRPA facade photographs and the 1878/2011 La Balance pair supply case-level facade context. Source access is no longer the blocker; exact capture-year interpretation, case identity and visual observations still require review.

## Historical photographs

### KIK-IRPA / BALaT

The [KIK-IRPA BALaT catalogue](https://balat.kikirpa.be/en/photo/search/) exposes IIIF images and labels the photo assets **CC BY 4.0** (metadata is CC0). Five source records are committed in the pilot as 800px previews: [T084580](https://balat.kikirpa.be/en/photo/T084580/) (Le Cornet, 1942), [B031587](https://balat.kikirpa.be/en/photo/B031587/) (Le Cygne, 1942), [A102887](https://balat.kikirpa.be/en/photo/A102887/) (Joseph and Anne, 1941), [B024641](https://balat.kikirpa.be/en/photo/B024641/) (L'Ange, 1941) and [B031502](https://balat.kikirpa.be/en/photo/B031502/) (Le Pigeon, 1942). Each pilot record stores the source URL, IIIF URL, epoch, licence, credit line and an explicit `source preview; no reviewer annotation` status. The previews establish a permitted historical facade source, not a structural-change conclusion.

### Wikimedia Commons — Maison de la Balance

The exact-case file [Belgique - Bruxelles - Maison de la Balance - 01.jpg](https://commons.wikimedia.org/wiki/File:Belgique_-_Bruxelles_-_Maison_de_la_Balance_-_01.jpg) describes Maison de la Balance as `Grand-Place`, embeds protected-monument identifier `2043-0177/0`, was taken in 2011, and is licensed **CC BY-SA 3.0** by EmDee. It does not state `Rue de la Colline 24`. The reproducible metadata/licence check in `download_commons_previews.py` now verifies both the place description and monument identifier before downloading the preview. The file provides the modern half of the facade comparison and one side of a still-pending crosswalk: the City dataset uses `Grand-Place 24`, the official heritage inventory uses `Rue de la Colline 24`, and the 1878 British Library caption says `rue de la Colline`.

### British Library — *La Belgique illustrée* (1878) engraving

Victor Dedoncker's exact-case engraving **“Maison de la Balance, rue de la Colline”** is now committed from an institutional scan. It appears on printed page 24 (scan page 36) of *La Belgique illustrée*, volume 1, published in 1878. The [exact British Library Flickr Commons record](https://www.flickr.com/photos/britishlibrary/11271682895/) identifies book `000266582`, shelfmark `Digital Store 10270.g.3`, and labels the image **No known copyright restrictions**. Its original JPEG also carries British Library public-domain EXIF metadata.

`download_british_library_preview.py` checks the live page for the rights label, scan page, book identifier and publication year before downloading the original JPEG; it also pins the file by SHA-256. This closes La Balance's historical-facade gap and creates an 1878/2011 comparison pair, but an engraving is not a photograph and neither facade view establishes rear-volume or aerial structural change.

### Heritage Brussels contextual lead

The official [1749 drawing record 36738](https://collections.heritage.brussels/fr/objects/36738) and adjacent [record 36739](https://collections.heritage.brussels/fr/objects/36739) depict historic street stretches around Rue de la Colline. They are useful leads for the uncovered Weighing Scales case, but they do not identify that facade at building level in the pilot and are not committed as evidence. The collection's [legal notice](https://collections.heritage.brussels/fr/legal/) says illustrations require rights clearance from the named institution or rights holder; request permission before reuse.

### Brussels Archives

- [Brussels Archives legal notes](https://archives.brussels.be/legal-notes)
- [Brussels Archives reproduction or image-use request](https://archives.brussels.be/requests-reproduction-or-use-images)

The archive is a discovery source, not an assumed open-licence source. Request reuse terms, required credit and any fees before adding an image to the pilot export. A prepared submission wizard is in [`scripts/archives-image-request.sh`](../scripts/archives-image-request.sh): it walks through the catalogue search, emails `archives@brucity.be` with a ready-to-paste request, and records the reply terms in `docs/archives-request-state.env`.

## Register and building evidence

- **Current source snapshot:** [City of Brussels Grand Place dataset](https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records); its [catalogue metadata](https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place) states CC BY 4.0 with publisher `Ville de Bruxelles/Data Management` and attributions `Behind Brussels` and `Google Maps`.
- **Regional building data lead:** [UrbIS buildings technical specification](https://urbisdownload.datastore.brussels/UrbIS/TechSpec/Buildings_TechSpec_FR20250708.pdf)
- **Works/change evidence lead:** [City of Brussels planning and environmental permits](https://opendata.brussels.be/explore/dataset/permis-urbanisme-environnement-vbx/)
- **Regional statistics context:** [IBSA building stock theme](https://ibsa.brussels/themes/amenagement-du-territoire/parc-de-batiments)
- **Modern ortho comparison:** [urbisgrid WMS](https://geoservices-urbis.irisnet.be/geoserver/urbisgrid/wms?) — committed as the 2022 pilot-area comparison with both official reuse-term readings and attribution recorded.

The committed Grand Place snapshot contains restoration/history text and facade descriptions, but no official register-year field. The snapshot carries the catalogue licence and exact attribution line. The [architectural-inventory legal notice](https://monument.heritage.brussels/fr/legal/) separately permits textual quotations and information reuse with explicit source attribution; it does not grant unrestricted reuse of site illustrations. A live API check of all 34 records confirms the field inventory is limited to name, address, height, original and current function, narrative history/restorations text, facade description, protection measures and coordinates — no structured construction year. The reviewed UrbIS specification describes 2D building geometry, addresses, block/building identifiers and a January 2025 temporal snapshot, but does not list an individual construction-year attribute in the Buildings catalogue. The City of Brussels planning-permits open dataset is aggregate yearly statistics only (year, domain, category, totals; coverage from 2013) with no address-level records, so permit-to-building matching is not possible from open data. Later-work evidence would require consulting permit PDFs via the city or Urban.brussels directly.

A partial register-year proxy chain exists via Wikidata: inception claims for three pilot houses (The Swan 1698, Joseph and Anne 1695, The Angel 1695) are referenced to Brussels heritage register records through the [Heritage API](https://heritage.toolforge.org/api/api.php) (`srcountry=be-bru`, identifiers `2043-0065/009`, `/021`, `/023`). [Wikidata structured data is released under CC0 1.0](https://www.wikidata.org/wiki/Wikidata:Licensing); the inventory acknowledges Wikidata contributors even though attribution is not required. The heritage records confirm identity and listing but contain no date field, so the year itself is a Wikidata crowd-sourced value cross-checked against the city history text; CC0 reuse does not make it an official date, and agreement or disagreement is recorded per case.

A direct official-source pass now covers the three previously pending houses: the Brussels architectural heritage inventory lists reconstruction dates for [The Horn / Grand-Place 6](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/6/31123) (1697), [The Weighing Scales / Rue de la Colline 24](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Colline/24/30991) (1704) and [The Pigeon / Grand-Place 26-27](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/26/31141) (1697). These are official architectural-inventory reconstruction-date proxies, not structured original-construction-year fields; the pilot now records that distinction and each City-source comparison as structured provenance. The six-row `three-ages-register-review.csv` asks a reviewer to accept each proxy for the MVP, retain it only as reconstruction evidence, or reject the mapping. Completed decisions compile for the explorer only while the source claim and comparison remain unchanged.

## Access log

| Source | Intended use | Licence/access status | Next action |
|---|---|---|---|
| BruCiel 1930–1935 | historical structural-state epoch | CC0 stated; WMS 1.1.1 extract verified for the Grand Place bbox | compare with 1996/2022; retain the mixed 1930–1935 capture-window caveat during review |
| BruCiel 1996 | intermediate structural comparison epoch | CC0 stated; WMS 1.1.1 extract verified and aligned | request parameters preserved; alignment tested against the 2022 urbisgrid ortho (phase-correlation peak 18 sigma, offset ~4 m) |
| urbisgrid 2022 | modern structural-state epoch | open data (CC0 per Ortho info page; CC-BY per INSPIRE record); extract verified | compare with 1930–1935 and 1996 without assigning change labels before review |
| BruCiel 1944 | unavailable historical lead | CC0 stated; layer is a dead cascade on all tested endpoints; provider workspace removed | retain failure diagnosis; use 1930–1935 for the bounded pilot |
| BruCiel other epochs | optional additional evidence | unknown per layer | only add after licence check |
| KIK-IRPA BALaT | permitted historical facade imagery | five 1941–1942 photo assets verified and committed as CC BY 4.0 previews; 5/6 pilot cases have comparable historical-era views | annotate only after reviewer checks source identity and visual observation |
| Wikimedia Commons | modern exact-case La Balance facade imagery | 2011 view verified and committed under CC BY-SA 3.0 | compare with the 1878 engraving and confirm the City `Grand-Place 24` to heritage `Rue de la Colline 24` mapping |
| British Library *La Belgique illustrée* | exact historical La Balance facade imagery | 1878 engraving verified and committed from institutional scan; no known copyright restrictions | annotate the 1878/2011 pair while preserving the engraving-versus-photograph limitation |
| Heritage Brussels collection | contextual historical drawing lead | 1749 records 36738/36739 found; reproduction rights not confirmed and building-level identity is insufficient | ask the collection or named institution whether a non-commercial copy may be reused; do not treat as pilot evidence yet |
| Brussels Archives | facade/history imagery | permission/reuse request required; submission wizard prepared | run `bash scripts/archives-image-request.sh` and send the enquiry |
| Grand Place dataset | source identity/history/facade text | CC BY 4.0; City publisher plus `Behind Brussels` and `Google Maps` attributions recorded; live field inventory checked (34 records, no register year) | pair with heritage inventory dates and document semantics |
| Brussels architectural heritage inventory | official building descriptions and reconstruction-date proxies | text quotation/information reuse permitted with explicit `urban.brussels — Inventaire du patrimoine architectural` attribution; no general image licence inferred | confirm exact register-year interpretation and review each proxy |
| UrbIS buildings | building geometry/identity | provider states an Open Data licence and data.gov.be identifies Paradigm; exact licence text is not pinned for this unused source lead | retain as geometry lead only; the technical specification has no construction-year field |
| Planning permits | later works and reconstruction clues | CC0 1.0, `Ville de Bruxelles/Développement urbain`; aggregate yearly statistics only, no addresses | request permit PDFs via the city or Urban.brussels if building-level evidence is needed |

## Go/no-go gate

Do not assign a reviewed structural-age claim until both conditions hold:

1. two image epochs or equivalent archival evidence are legally reusable for the pilot; and
2. every claim has a source URL, asset epoch, exact preview checksum, licence/permission note, observation and reviewer.

Condition 1 now holds at pilot-area scale through the CC0 1930–1935 preview and reusable 2022 comparison. All ten source previews are SHA-256 pinned and checked by both their downloader and snapshot validation. Eighteen deterministic building-centred crops apply the same 160 px box across the 1930–1935, 1996 and 2022 epochs. The dedicated six-row `three-ages-structural-review.csv` binds every case to source checksums, crop paths, geometry and pixel hashes and refuses provenance drift, but condition 2 does not yet hold because no row has reviewer metadata. Until then, the prototype should keep the current `documented proxy` and official-inventory `proxy` statuses, with image-derived and reviewer-dependent claims still `pending`.

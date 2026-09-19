# Three Ages — source access checklist

This checklist records the first source-access review for the curated MVP. A source being discoverable does not mean its images are reusable.

## Historical aerial imagery

### BruCiel / Brussels Mobility

- **Landing/API:** [BruCiel information page](https://data.mobility.brussels/en/info/ortho_44/) and the listed [BruCiel API](https://urbanisme.irisnet.be/cartographie/bruciel).
- **Historical photo discovery:** [BruCiel viewer](https://bruciel.brussels/). The official description reports roughly 5,000 selected, geolocated historical photographs across different periods; reuse terms must be checked per asset.
- **1944 layer:** [Ortho 1944 metadata](https://data.mobility.brussels/en/info/ortho_44/) exposes WMS/WFS services, a web viewer and an explicit [CC0](https://creativecommons.org/publicdomain/zero/1.0) licence.
- **1996 layer:** [Ortho 1996 metadata](https://data.mobility.brussels/en/info/d5e0a5dc-e3b7-48ce-a7ae-bac5ec0b38ba/) explicitly links to [CC0](https://creativecommons.org/publicdomain/zero/1.0).
- **Other epochs:** BruCiel covers multiple periods, but each layer needs its own licence and completeness check.
- **Modern urban.brussels orthos:** the [Ortho info page](https://data.mobility.brussels/info/Ortho) states CC0 for the `urbisgrid` ortho layers, while the INSPIRE distribution record requires CC-BY attribution. Either way the 2022 layer is reusable open data; the pilot records attribution for both readings.

**Current status:** the 1996 WMS returned a small PNG extract for a Grand Place bounding box. The equivalent 1944 layer fails every GetMap request with `LayerNotDefined`. The failure is now diagnosed: the capabilities entry `URBAN_DCC_ER:Orthophotoplans_1944` is a `cascaded="1"` layer whose upstream source has gone away, and the `BDU_DEP` workspace documented on the metadata page no longer exists on any GeoServer. The official mobigis viewer itself lists no catalog entry for the layer. The 1944 endpoint is therefore treated as retired by the provider; a second epoch must come from another source (BruCiel photo API, Brussels Archives, or a public-domain photo) rather than this WMS.

## Historical photographs

- [Brussels Archives legal notes](https://archives.brussels.be/legal-notes)
- [Brussels Archives reproduction or image-use request](https://archives.brussels.be/requests-reproduction-or-use-images)

The archive is a discovery source, not an assumed open-licence source. Request reuse terms, required credit and any fees before adding an image to the pilot export. A prepared submission wizard is in [`scripts/archives-image-request.sh`](../scripts/archives-image-request.sh): it walks through the catalogue search, emails `archives@brucity.be` with a ready-to-paste request, and records the reply terms in `docs/archives-request-state.env`.

## Register and building evidence

- **Current source snapshot:** [City of Brussels Grand Place dataset](https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records)
- **Regional building data lead:** [UrbIS buildings technical specification](https://urbisdownload.datastore.brussels/UrbIS/TechSpec/Buildings_TechSpec_FR20250708.pdf)
- **Works/change evidence lead:** [City of Brussels planning and environmental permits](https://opendata.brussels.be/explore/dataset/permis-urbanisme-environnement-vbx/)
- **Regional statistics context:** [IBSA building stock theme](https://ibsa.brussels/themes/amenagement-du-territoire/parc-de-batiments)
- **Modern ortho verification reference:** [urbisgrid WMS](https://geoservices-urbis.irisnet.be/geoserver/urbisgrid/wms?) — used only to verify the 1996 extract geometry, not as pilot evidence until its licence is confirmed.

The committed Grand Place snapshot contains restoration/history text and facade descriptions, but no official register-year field. A live API check of all 34 records confirms the field inventory is limited to name, address, height, original and current function, narrative history/restorations text, facade description, protection measures and coordinates — no structured construction year. The reviewed UrbIS specification describes 2D building geometry, addresses, block/building identifiers and a January 2025 temporal snapshot, but does not list an individual construction-year attribute in the Buildings catalogue. The City of Brussels planning-permits open dataset is aggregate yearly statistics only (year, domain, category, totals; coverage from 2013) with no address-level records, so permit-to-building matching is not possible from open data. Later-work evidence would require consulting permit PDFs via the city or Urban.brussels directly.

A partial register-year proxy chain exists via Wikidata: inception claims for three pilot houses (The Swan 1698, Joseph and Anne 1695, The Angel 1695) are referenced to Brussels heritage register records through the [Heritage API](https://heritage.toolforge.org/api/api.php) (`srcountry=be-bru`, identifiers `2043-0065/009`, `/021`, `/023`). The heritage records confirm identity and listing but contain no date field, so the year itself is a Wikidata crowd-sourced value cross-checked against the city history text; agreement and disagreement are recorded per case.

A direct official-source pass now covers the three previously pending houses: the Brussels architectural heritage inventory lists reconstruction dates for [The Horn / Grand-Place 6](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/6/31123) (1697), [The Weighing Scales / Rue de la Colline 24](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Colline/24/30991) (1704) and [The Pigeon / Grand-Place 26-27](https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/26/31141) (1697). These are official architectural-inventory reconstruction-date proxies, not structured original-construction-year fields; the pilot records the distinction and keeps all six values unreviewed. The remaining register task is therefore to confirm the intended year semantics and reviewer acceptance, rather than to infer missing dates.

## Access log

| Source | Intended use | Licence/access status | Next action |
|---|---|---|---|
| BruCiel 1996 | structural comparison epoch | CC0 stated; WMS 1.1.1 extract verified and aligned | request parameters preserved; alignment tested against the 2022 urbisgrid ortho (phase-correlation peak 18 sigma, offset ~4 m) |
| urbisgrid 2022 | modern structural-state epoch | open data (CC0 per Ortho info page; CC-BY per INSPIRE record); extract verified | paired with 1996 as two legally reusable modern epochs; historical epoch still pending |
| BruCiel 1944 | second structural epoch | CC0 stated; layer is a dead cascade on all tested endpoints; provider workspace removed | find an alternative 1944-era source or ask the provider to republish the layer |
| BruCiel other epochs | optional additional evidence | unknown per layer | only add after licence check |
| Brussels Archives | facade/history imagery | permission/reuse request required; submission wizard prepared | run `bash scripts/archives-image-request.sh` and send the enquiry |
| Grand Place dataset | source identity/history/facade text | current JSON snapshot available; live field inventory checked (34 records, no register year) | pair with heritage inventory dates and document semantics |
| Brussels architectural heritage inventory | official building descriptions and reconstruction-date proxies | direct inventory pages found for all six pilot cases; three newly added to the pilot | confirm exact register-year interpretation and review each proxy |
| UrbIS buildings | building geometry/identity | access and attribute coverage to verify | inspect technical specification |
| Planning permits | later works and reconstruction clues | aggregate yearly statistics only, no addresses; matching not possible from open data | request permit PDFs via the city or Urban.brussels if needed |

## Go/no-go gate

Do not assign a reviewed structural-age claim until both conditions hold:

1. two image epochs or equivalent archival evidence are legally reusable for the pilot; and
2. every claim has a source URL, asset epoch, licence/permission note, observation and reviewer.

Until then, the prototype should keep the current `documented proxy` and official-inventory `proxy` statuses, with image-derived and reviewer-dependent claims still `pending`.

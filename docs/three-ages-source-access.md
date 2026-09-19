# Three Ages — source access checklist

This checklist records the first source-access review for the curated MVP. A source being discoverable does not mean its images are reusable.

## Historical aerial imagery

### BruCiel / Brussels Mobility

- **Landing/API:** [BruCiel information page](https://data.mobility.brussels/en/info/ortho_44/) and the listed [BruCiel API](https://urbanisme.irisnet.be/cartographie/bruciel).
- **Historical photo discovery:** [BruCiel viewer](https://bruciel.brussels/). The official description reports roughly 5,000 selected, geolocated historical photographs across different periods; reuse terms must be checked per asset.
- **1944 layer:** [Ortho 1944 metadata](https://data.mobility.brussels/en/info/ortho_44/) exposes WMS/WFS services, a web viewer and an explicit [CC0](https://creativecommons.org/publicdomain/zero/1.0) licence.
- **1996 layer:** [Ortho 1996 metadata](https://data.mobility.brussels/en/info/d5e0a5dc-e3b7-48ce-a7ae-bac5ec0b38ba/) explicitly links to [CC0](https://creativecommons.org/publicdomain/zero/1.0).
- **Other epochs:** BruCiel covers multiple periods, but each layer needs its own licence and completeness check.

**Current status:** the 1996 WMS returned a small PNG extract for a Grand Place bounding box. The equivalent 1944 WMS request returned a service error saying the layer was not found, despite the metadata page and GetCapabilities response listing the layer. The generic and workspace-specific GeoServer endpoints produced the same result. Investigate the 1944 endpoint before treating the pair as a matched image set.

## Historical photographs

- [Brussels Archives legal notes](https://archives.brussels.be/legal-notes)
- [Brussels Archives reproduction or image-use request](https://archives.brussels.be/requests-reproduction-or-use-images)

The archive is a discovery source, not an assumed open-licence source. Request reuse terms, required credit and any fees before adding an image to the pilot export.

## Register and building evidence

- **Current source snapshot:** [City of Brussels Grand Place dataset](https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records)
- **Regional building data lead:** [UrbIS buildings technical specification](https://urbisdownload.datastore.brussels/UrbIS/TechSpec/Buildings_TechSpec_FR20250708.pdf)
- **Works/change evidence lead:** [City of Brussels planning and environmental permits](https://opendata.brussels.be/explore/dataset/permis-urbanisme-environnement-vbx/)
- **Regional statistics context:** [IBSA building stock theme](https://ibsa.brussels/themes/amenagement-du-territoire/parc-de-batiments)

The committed Grand Place snapshot contains restoration/history text and facade descriptions, but no official register-year field. The reviewed UrbIS specification describes 2D building geometry, addresses, block/building identifiers and a January 2025 temporal snapshot, but does not list an individual construction-year attribute in the Buildings catalogue. Planning permits may provide later-work evidence, but cannot be treated as original construction years without verification. The register-year source therefore remains an explicit access task rather than an inferred value.

## Access log

| Source | Intended use | Licence/access status | Next action |
|---|---|---|---|
| BruCiel 1996 | structural comparison epoch | CC0 stated; small WMS extract verified | preserve request parameters and test image alignment |
| BruCiel 1944 | second structural epoch | CC0 stated; multiple WMS endpoints tested and failed | ask the data provider for the current layer endpoint or use the BruCiel API/viewer |
| BruCiel other epochs | optional additional evidence | unknown per layer | only add after licence check |
| Brussels Archives | facade/history imagery | permission/reuse request required | submit a pilot request |
| Grand Place dataset | source identity/history/facade text | current JSON snapshot available | identify official register-year field |
| UrbIS buildings | building geometry/identity | access and attribute coverage to verify | inspect technical specification |
| Planning permits | later works and reconstruction clues | dataset available; field suitability to verify | test address/building matching |

## Go/no-go gate

Do not assign a reviewed structural-age claim until both conditions hold:

1. two image epochs or equivalent archival evidence are legally reusable for the pilot; and
2. every claim has a source URL, asset epoch, licence/permission note, observation and reviewer.

Until then, the prototype should keep the current `documented proxy` and `pending` statuses.

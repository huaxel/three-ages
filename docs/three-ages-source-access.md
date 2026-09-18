# Three Ages — source access checklist

This checklist records the first source-access review for the curated MVP. A source being discoverable does not mean its images are reusable.

## Historical aerial imagery

### BruCiel / Brussels Mobility

- **Landing/API:** [BruCiel information page](https://data.mobility.brussels/en/info/ortho_44/) and the listed [BruCiel API](https://urbanisme.irisnet.be/cartographie/bruciel).
- **1944 layer:** the metadata page exposes WMS/WFS services and a web viewer. The fetched page did not display a licence statement; confirm the licence in the layer metadata before downloading or redistributing imagery.
- **1996 layer:** [Ortho 1996 metadata](https://data.mobility.brussels/en/info/d5e0a5dc-e3b7-48ce-a7ae-bac5ec0b38ba/) explicitly links to [CC0](https://creativecommons.org/publicdomain/zero/1.0).
- **Other epochs:** BruCiel covers multiple periods, but each layer needs its own licence and completeness check.

**Current status:** 1996 is the strongest reuse candidate. A second permitted epoch is still required for structural comparison.

## Historical photographs

- [Brussels Archives legal notes](https://archives.brussels.be/legal-notes)
- [Brussels Archives reproduction or image-use request](https://archives.brussels.be/requests-reproduction-or-use-images)

The archive is a discovery source, not an assumed open-licence source. Request reuse terms, required credit and any fees before adding an image to the pilot export.

## Register and building evidence

- **Current source snapshot:** [City of Brussels Grand Place dataset](https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records)
- **Regional building data lead:** [UrbIS buildings technical specification](https://urbisdownload.datastore.brussels/UrbIS/TechSpec/Buildings_TechSpec_FR20250708.pdf)
- **Works/change evidence lead:** [City of Brussels planning and environmental permits](https://opendata.brussels.be/explore/dataset/permis-urbanisme-environnement-vbx/)
- **Regional statistics context:** [IBSA building stock theme](https://ibsa.brussels/themes/amenagement-du-territoire/parc-de-batiments)

The committed Grand Place snapshot contains restoration/history text and facade descriptions, but no official register-year field. The register-year source therefore remains an explicit access task rather than an inferred value.

## Access log

| Source | Intended use | Licence/access status | Next action |
|---|---|---|---|
| BruCiel 1996 | structural comparison epoch | CC0 stated on metadata page | download/test one pilot tile |
| BruCiel 1944 | second structural epoch | service available; licence not confirmed on reviewed page | inspect layer metadata and confirm reuse |
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

# Irismonument image and metadata licence — verification (2026-10-09)

Sources consulted: monument.heritage.brussels (Conditions d'utilisation, Notice légale), collections.heritage.brussels (legal), patrimoine.brussels (crédits photographiques), balat.kikirpa.be (KIK-IRPA copyright).

## Metadata: usable

The Irismonument WFS layer (`URBAN_DCH_IBH:Irismonument_inventory`) metadata — style, build year, typology, architects, geometry — is CC0 per the BruGIS/data.mobility.brussels layer page: <https://data.mobility.brussels/nl/info/979a37d4-f855-4081-b7a0-b1c02c0fe334/>. **Labels and coordinates may be used freely** (attribution appreciated).

## Photos (FIRSTIMAGE on monument.heritage.brussels/medias): NOT blanket-licensed for training

The site's Conditions d'utilisation (https://monument.heritage.brussels/fr/conditions/) govern the photos:

- Photos taken by Region agents (marked "© Reproduction autorisée sous certaines conditions") may be reproduced **only in non-commercial publications**, subject to:
  - websites: "© SPRB-DMS" beside each image + link to monument.heritage.brussels;
  - print: send a copy to the BDU Documentation Centre + "© Monuments & Sites – Bruxelles" credit.
  - The grant covers only the photographers' copyright; rights on depicted buildings/artworks must be cleared separately.
- Photos marked "© KIK-IRPA_urban.brussels" follow the KIK-IRPA terms (BALaT: free download; per-photo citation formula e.g. "CC-BY KIK-IRPA, Brussels, photo number"; clickable link to balat.kikirpa.be when displayed on a website; proof copy within 30 days of publication; rights clearance for modern artworks).
- Third-party credits (© photographer/institution) require permission from the named rights holders.

**ML training is not a covered "publication".** The authorization is framed for web/print publication contexts; building a training dataset and publishing model weights from inventory photos is outside the clear grant. Two safe paths:

1. **KIK-IRPA BALaT route** (like the pilot's 12 committed previews): for cases whose inventory photo is a KIK-IRPA image, download from BALaT under its CC BY 4.0 attribution formula instead of scraping the inventory copy.
2. **Explicit permission**: request training-use permission from urban.brussels' Documentation Centre (doc@urban.brussels) / DPC for the SPRB-agent inventory photos.

Fallback for modern-era cases: Wikimedia Commons facade photos under per-file licences (mostly CC BY / CC BY-SA; check each), consistent with the pilot's Commons photo handling (CC BY-SA 3.0 — ShareAlike flag).

## Snapshot header

`data/irismonument-inventory.json` records `image_licence_status`; it was UNVERIFIED at fetch time and is now resolved by this doc.

## Implications for the corpus pipeline

- Metadata labels + geometry: proceed (CC0).
- Photo download for training: do NOT bulk-scrape FIRSTIMAGE; use the KIK/BALaT or permission routes per case. Bulk download of the medias files without a licence basis would violate the site's terms.
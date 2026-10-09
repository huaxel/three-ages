# BALaT photo labeling pack (reviewer-ready)

46 worksheet rows, 0 reviewed. Worksheet: `balat-photo-review.csv` (edits go there, never here). Provenance: `balat-photo-provenance.json`. Compiled reviews: `balat-photo-reviews.json` via `prototypes/three-ages/export_balat_review.py`. Manifest: `balat-training-manifest.py` (only dual-reviewed, CC-BY, eligible rows).

## Workflow (TODO-65a73811: independent annotation before confidence)

1. Two annotators label each photo INDEPENDENTLY (facade_label + facade_observation + reviewer + reviewed_at).
2. Compare: where labels agree, set confidence; where they disagree, record both annotations and their disposition (which stands, why) before any confidence value.
3. Regenerating the worksheet preserves completed reviews; it REFUSES to carry reviews forward if the underlying provenance changed — re-verify those rows from scratch.
4. Three rows are `label_eligibility=ineligible` (predecessor photos — may be annotated for the record but NEVER enter the manifest): A029757 (1942 photo predates the 1962-1971 brutalist building, fiche 37935); A104341 (1910 photo predates the 1932 functionalist building, fiche 32831); M069740 (1971 photo predates the 1978 postmodernist building, fiche 30275).

## Allowed labels (docs/facade-style-vocabulary.md, signed off 2026-10-09)

Historical: Baroque; Baroque with classical features; Louis XIV (French classical); Antique (classical orders); Mixed: Antique registers + Baroque gable; Baroque with Renaissance elements; Neoclassical; Second Empire; Beaux-Arts. Modern: Eclecticism; Historicist neo-styles; Art Nouveau; Art Deco; Paquebot style; Functionalism; Modernism (interwar); Modernism (post-war); Modernism (Expo 58); Modernism (late); Modernism (period undetermined); Brutalism; Postmodernism; Contemporary. Outcomes when the facade does not support a style label: uncertain / mixed / not-visible. FABRIC-EPOCH RULE: record the 19th-c. restoration/reconstruction epoch beside every style label where known (e.g. `Baroque (fabric: 1896-1897 reconstruction)`).

## Rows

### A008936
- Photo page: https://balat.kikirpa.be/en/photo/A008936/
- Preview: `data/historical/balat/balat-a008936.jpg` (sha256 `d36a0ce7174fea70…`)
- Address: Rue Sainte-Catherine 8 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_Sainte-Catherine/8/33033
- Suggested class from inventory: Baroque (source styles: Architecture traditionnelle, Baroque)
- Photo date: 1917; scope: facade; detail: Vue d'ensemble des façades principales à front de rue; page title: maison / Maison, Bruxelles, rue Sainte-Catherine 8
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A008936
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029710
- Photo page: https://balat.kikirpa.be/en/photo/A029710/
- Preview: `data/historical/balat/balat-a029710.jpg` (sha256 `9890e995bda89197…`)
- Address: Place Sainte-Catherine 23 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Place_Sainte-Catherine/23/33023
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1942; scope: facade; detail: façade principale; page title: maison / Maison, Bruxelles, place Sainte-Catherine 23
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029710
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029719
- Photo page: https://balat.kikirpa.be/en/photo/A029719/
- Preview: `data/historical/balat/balat-a029719.jpg` (sha256 `d14b48f31cf9c436…`)
- Address: Rue du Marché aux Herbes 55 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Marche_aux_Herbes/55/31399
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1942; scope: partial-facade; detail: partie sup. de la façade principale rue du Marché aux Herbes et de la façade latérale rue Chair et Pain; page title: maison / Maison, Bruxelles, rue du Marché aux Herbes 55
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029719
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029722
- Photo page: https://balat.kikirpa.be/en/photo/A029722/
- Preview: `data/historical/balat/balat-a029722.jpg` (sha256 `5de622e91ffd2f1d…`)
- Address: Rue de Villers 6 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_Villers/6/31853
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1942; scope: facade; detail: Façades avant; page title: maison / Maison, Bruxelles, rue de Villers 6
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029722
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029723
- Photo page: https://balat.kikirpa.be/en/photo/A029723/
- Preview: `data/historical/balat/balat-a029723.jpg` (sha256 `fb23c2fa68485c33…`)
- Address: Rue du Chêne 8 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Chene/8/30958
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1942; scope: not-stated; detail: ; page title: hôtel de maître / Hôtel de Visscher de Celles, Bruxelles, rue du Chêne 8
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029723
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029746
- Photo page: https://balat.kikirpa.be/en/photo/A029746/
- Preview: `data/historical/balat/balat-a029746.jpg` (sha256 `ee25820d90fa8212…`)
- Address: Place de la Vieille Halle aux Blés 36 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Place_de_la_Vieille_Halle_aux_Bles/36/31843
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1942; scope: facade; detail: façade principale: pignon; page title: maison / Maison, Bruxelles, Place de la Vieille Halle aux Blés 36
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029746
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029754
- Photo page: https://balat.kikirpa.be/en/photo/A029754/
- Preview: `data/historical/balat/balat-a029754.jpg` (sha256 `f6ab997f6054cbfb…`)
- Address: Rue de la Madeleine 61 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Madeleine/61/31316
- Suggested class from inventory: Baroque with classical features (source styles: Baroque classicisant)
- Photo date: 1942; scope: facade; detail: façades principales à front de rue; page title: maison / Maison Venise, Bruxelles, rue de la Madeleine 61
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029754
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029757 **[ineligible: 1942 photo predates the current building: fiche 37935 records a 1962-1971 Piet Dingemans brutalist office block; the photo shows the 19th-century predecessor police station.]**
- Photo page: https://balat.kikirpa.be/en/photo/A029757/
- Preview: `data/historical/balat/balat-a029757.jpg` (sha256 `19ed48defa584f37…`)
- Address: Place du Nouveau Marché aux Grains 8 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Place_du_Nouveau_Marche_aux_Grains/8/37935
- Suggested class from inventory: Brutalism (source styles: Brutalisme)
- Photo date: 1942; scope: other; detail: Vue du bâtiment à l'angle avec la rue A. Dansaert; page title: commissariat de police / Maison, Bruxelles, place du Nouveau-Marché-aux-Grains 8 - rue Antoine Dansaert 92
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029757
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029766
- Photo page: https://balat.kikirpa.be/en/photo/A029766/
- Preview: `data/historical/balat/balat-a029766.jpg` (sha256 `ce0530b948a5f531…`)
- Address: Rue de la Montagne 16 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Montagne/16/33693
- Suggested class from inventory: Baroque with classical features (source styles: Baroque classicisant, Régence)
- Photo date: 1942; scope: facade; detail: façade principale à front de rue; page title: maison / Maison, Bruxelles, rue de la Montagne 16
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029766
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A029771
- Photo page: https://balat.kikirpa.be/en/photo/A029771/
- Preview: `data/historical/balat/balat-a029771.jpg` (sha256 `86a6ea15267bb43b…`)
- Address: Rue de la Montagne 68 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Montagne/68/33702
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1942; scope: facade; detail: façades principales à front de rue; page title: maison / Maison, Bruxelles, rue de la Montagne 68
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A029771
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A068359
- Photo page: https://balat.kikirpa.be/en/photo/A068359/
- Preview: `data/historical/balat/balat-a068359.jpg` (sha256 `67b7138715de1629…`)
- Address: Rue de la Chapelle 15 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Chapelle/15/30937
- Suggested class from inventory: Historicist neo-styles (source styles: Renaissance flamande)
- Photo date: 1944; scope: not-stated; detail: ; page title: maison / Maison, Bruxelles, rue de la Chapelle 15
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A068359
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A068609
- Photo page: https://balat.kikirpa.be/en/photo/A068609/
- Preview: `data/historical/balat/balat-a068609.jpg` (sha256 `66bb7f369e23b05e…`)
- Address: Rue de la Violette 34 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Violette/34/31871
- Suggested class from inventory: Baroque with classical features (source styles: Baroque classicisant)
- Photo date: 1944; scope: facade; detail: Façades avant; page title: maison / Maison, Bruxelles, rue de la Violette 34-36
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A068609
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A075059
- Photo page: https://balat.kikirpa.be/en/photo/A075059/
- Preview: `data/historical/balat/balat-a075059.jpg` (sha256 `c042983b48a7ba96…`)
- Address: Rue du Pont Neuf 35 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Pont_Neuf/35/33770
- Suggested class from inventory: Art Nouveau (source styles: Néoclassicisme, Art nouveau)
- Photo date: 1944; scope: not-stated; detail: ; page title: maison / Maison, Bruxelles, rue du Pont-Neuf 35-37
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A075059
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A075097
- Photo page: https://balat.kikirpa.be/en/photo/A075097/
- Preview: `data/historical/balat/balat-a075097.jpg` (sha256 `21e64362972ea40e…`)
- Address: Rue du Marché aux Herbes 27 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Marche_aux_Herbes/27/31385
- Suggested class from inventory: Baroque; Neoclassical (source styles: Baroque, Néoclassicisme)
- Photo date: 1944; scope: facade; detail: façade, 1er étage: garde-corps de fenêtre; page title: garde-corps / Maison Den Reus, Bruxelles, rue du Marché aux Herbes 27
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A075097
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A075152
- Photo page: https://balat.kikirpa.be/en/photo/A075152/
- Preview: `data/historical/balat/balat-a075152.jpg` (sha256 `e9d04015055e6971…`)
- Address: Quai à la Chaux 5 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Quai_a_la_Chaux/5/32276
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1944; scope: detail; detail: Porche; page title: porche / Maison, Bruxelles, Quai à la Chaux 5-6
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A075152
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A075204
- Photo page: https://balat.kikirpa.be/en/photo/A075204/
- Preview: `data/historical/balat/balat-a075204.jpg` (sha256 `4153d51b93047a3e…`)
- Address: Rue du Marché aux Herbes 113 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Marche_aux_Herbes/113/31426
- Suggested class from inventory: Second Empire (source styles: Éclectisme, Second Empire)
- Photo date: 1944; scope: facade; detail: façades à front des rues du Marché aux Herbes et des Eperonniers; page title: maison / Cheval Volant, Bruxelles, rue du Marché aux Herbes 113
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A075204
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A075238
- Photo page: https://balat.kikirpa.be/en/photo/A075238/
- Preview: `data/historical/balat/balat-a075238.jpg` (sha256 `76f27173269b25ca…`)
- Address: Rue de Laeken 26 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_Laeken/26/32643
- Suggested class from inventory: Second Empire (source styles: Néoclassicisme, Second Empire)
- Photo date: 1944; scope: facade; detail: façades principales à front de rue, n° 28 à l'angle de la rue du Béguinage; page title: maison / Maison, Bruxelles, rue de Laeken 26
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A075238
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A104341 **[ineligible: 1910 photo predates the current building: fiche 32831 records a 1932 functionalist building; the photo shows the predecessor at place du Nouveau-Marché-aux-Grains 21-22-23.]**
- Photo page: https://balat.kikirpa.be/en/photo/A104341/
- Preview: `data/historical/balat/balat-a104341.jpg` (sha256 `b4da6e31fb1d31d0…`)
- Address: Place du Nouveau Marché aux Grains 22 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Place_du_Nouveau_Marche_aux_Grains/22/32831
- Suggested class from inventory: Functionalism (source styles: Modernisme, Fonctionnalisme; built 1932)
- Photo date: 1910; scope: not-stated; detail: ; page title: maison / Maison, Bruxelles, place du Nouveau-Marché-aux-Grains 21-22-23
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A104341
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A104837
- Photo page: https://balat.kikirpa.be/en/photo/A104837/
- Preview: `data/historical/balat/balat-a104837.jpg` (sha256 `a65ce9a599605972…`)
- Address: Rue de la Montagne 42 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Montagne/42/33697
- Suggested class from inventory: Baroque (source styles: Baroque, Néo-baroque)
- Photo date: 1905; scope: facade; detail: façade principale à front de rue: pignon; page title: maison / Maison, Bruxelles, rue de la Montagne 42-44
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A104837
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### A105109
- Photo page: https://balat.kikirpa.be/en/photo/A105109/
- Preview: `data/historical/balat/balat-a105109.jpg` (sha256 `48819886be48be04…`)
- Address: Rue de la Madeleine 29 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Madeleine/29/31311
- Suggested class from inventory: Baroque with classical features (source styles: Baroque classicisant, Néoclassicisme (du 18e siècle), Néoclassicisme)
- Photo date: 1910; scope: facade; detail: façade principale: lucarnes et fenêtres niveau 2; page title: maison / Maison, Bruxelles, rue de la Madeleine 29, 31
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché A105109
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M038100
- Photo page: https://balat.kikirpa.be/en/photo/M038100/
- Preview: `data/historical/balat/balat-m038100.jpg` (sha256 `866207d6fe5d2a69…`)
- Address: Rue de l'Ecuyer 48 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_l_Ecuyer/48/33480
- Suggested class from inventory: Functionalism (source styles: Fonctionnalisme)
- Photo date: 1968; scope: not-stated; detail: ; page title: immeuble de bureaux / Maison, Bruxelles, rue de l'Ecuyer 48-52
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M038100
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M069738
- Photo page: https://balat.kikirpa.be/en/photo/M069738/
- Preview: `data/historical/balat/balat-m069738.jpg` (sha256 `51f1c767ec1b03ec…`)
- Address: Rue aux Laines 35 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_aux_Laines/35/30256
- Suggested class from inventory: Eclecticism (source styles: Éclectisme, Néo-Renaissance)
- Photo date: 1971; scope: facade; detail: façade antérieure; page title: maison / Maison, Bruxelles, rue aux Laines 35
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M069738
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M069740 **[ineligible: 1971 photo predates the current building: fiche 30275 records a 1978 postmodernist building; the photo shows the predecessor at rue aux Laines 142.]**
- Photo page: https://balat.kikirpa.be/en/photo/M069740/
- Preview: `data/historical/balat/balat-m069740.jpg` (sha256 `e0696b592b16ba05…`)
- Address: Rue aux Laines 142 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_aux_Laines/142/30275
- Suggested class from inventory: Postmodernism (source styles: Postmodernisme; built 1978)
- Photo date: 1971; scope: facade; detail: façade antérieure; page title: maison / Maison, Bruxelles, rue aux Laines 142
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M069740
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M070845
- Photo page: https://balat.kikirpa.be/en/photo/M070845/
- Preview: `data/historical/balat/balat-m070845.jpg` (sha256 `f4adbc93f4035538…`)
- Address: Rue du Remblai 38 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Remblai/38/31590
- Suggested class from inventory: Neoclassical (source styles: Néoclassicisme, Beaux-Arts)
- Photo date: 1971; scope: not-stated; detail: ; page title: maison / Maison, Bruxelles, rue du Remblai 38
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M070845
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M073497
- Photo page: https://balat.kikirpa.be/en/photo/M073497/
- Preview: `data/historical/balat/balat-m073497.jpg` (sha256 `8bb30d9e0e765c28…`)
- Address: Rue des Foulons 54 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_des_Foulons/54/32533
- Suggested class from inventory: Second Empire (source styles: Néoclassicisme, Second Empire)
- Photo date: 1971; scope: facade; detail: façade antérieure; page title: maison / Maison, Bruxelles, rue des Foulons 54
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M073497
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M073570
- Photo page: https://balat.kikirpa.be/en/photo/M073570/
- Preview: `data/historical/balat/balat-m073570.jpg` (sha256 `b15dd4e71cf66e73…`)
- Address: Rue de Cureghem 4 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_Cureghem/4/32346
- Suggested class from inventory: Neoclassical (source styles: Néoclassicisme)
- Photo date: 1971; scope: not-stated; detail: ; page title: maison / Maison, Bruxelles, rue de Cureghem 4-10
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M073570
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M146594
- Photo page: https://balat.kikirpa.be/en/photo/M146594/
- Preview: `data/historical/balat/balat-m146594.jpg` (sha256 `ff0f4b3f4a6a7e81…`)
- Address: Avenue Paul Dejaer 39 — fiche: https://monument.heritage.brussels/fr/Saint-Gilles/Avenue_Paul_Dejaer/39/6821
- Suggested class from inventory: Beaux-Arts (source styles: Beaux-Arts)
- Photo date: 1980; scope: facade; detail: Façade d'angle; page title: immeuble de rapport / Maison, Saint-Gilles, avenue Paul Dejaer 39
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M146594
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M154776
- Photo page: https://balat.kikirpa.be/en/photo/M154776/
- Preview: `data/historical/balat/balat-m154776.jpg` (sha256 `9052638642d0c51c…`)
- Address: Chaussée d'Ixelles 126 — fiche: https://monument.heritage.brussels/fr/Ixelles/Chaussee_d_Ixelles/126/19845
- Suggested class from inventory: Modernism (period undetermined); Art Deco (source styles: Modernisme, Art Déco; built 1852 — 1980 photo postdates the building, so no predecessor issue, but reviewer to confirm which phase the facade shows)
- Photo date: 1980; scope: facade; detail: Façade à front de rue; page title: immeuble à appartements / Maison, Ixelles, chaussée d'Ixelles, 126-130
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M154776
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M156556
- Photo page: https://balat.kikirpa.be/en/photo/M156556/
- Preview: `data/historical/balat/balat-m156556.jpg` (sha256 `6900f41df032f463…`)
- Address: Rue Belliard 197 — fiche: https://monument.heritage.brussels/fr/Etterbeek/Rue_Belliard/197/14025
- Suggested class from inventory: Beaux-Arts (source styles: Beaux-Arts)
- Photo date: 1980; scope: facade; detail: Façade principale; page title: immeuble à appartements / Maison, Etterbeek, rue Belliard 197
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M156556
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M162362
- Photo page: https://balat.kikirpa.be/en/photo/M162362/
- Preview: `data/historical/balat/balat-m162362.jpg` (sha256 `a20f18603482ea0a…`)
- Address: Rue Arthur Diderich 10 — fiche: https://monument.heritage.brussels/fr/Saint-Gilles/Rue_Arthur_Diderich/10/989
- Suggested class from inventory: Eclecticism (source styles: Éclectisme)
- Photo date: 1980; scope: facade; detail: Façades principales à front de rue; page title: maison / Maison, Saint-Gilles, rue Arthur Diderich 4-10
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M162362
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### M167858
- Photo page: https://balat.kikirpa.be/en/photo/M167858/
- Preview: `data/historical/balat/balat-m167858.jpg` (sha256 `7195ffff04254fa5…`)
- Address: Rue de l'Argonne 37 — fiche: https://monument.heritage.brussels/fr/Saint-Gilles/Rue_de_l_Argonne/37/972
- Suggested class from inventory: Neoclassical (source styles: Éclectisme, Néoclassicisme)
- Photo date: 1981; scope: facade; detail: Façades principales à front de rue; page title: hôtel de maître / Maison, Saint-Gilles, rue de l'Argonne 37
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché M167858
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### N042656
- Photo page: https://balat.kikirpa.be/en/photo/N042656/
- Preview: `data/historical/balat/balat-n042656.jpg` (sha256 `2f237b8fc6fbac3f…`)
- Address: Rue Saint-Bernard 64 — fiche: https://monument.heritage.brussels/fr/Saint-Gilles/Rue_Saint-Bernard/64/7367
- Suggested class from inventory: Art Nouveau (source styles: Art nouveau)
- Photo date: 1980; scope: facade; detail: Façades principales à front de rue; page title: maison / Maison, Saint-Gilles, rue Saint-Bernard 64
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché N042656
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016024
- Photo page: https://balat.kikirpa.be/en/photo/T016024/
- Preview: `data/historical/balat/balat-t016024.jpg` (sha256 `c58d67fdfe2fa409…`)
- Address: Boulevard Adolphe Max 108 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Boulevard_Adolphe_Max/108/33237
- Suggested class from inventory: Second Empire (source styles: Éclectisme, Second Empire)
- Photo date: 1975; scope: facade; detail: façades antérieures; page title: immeuble de rapport / Maison, Bruxelles, boulevard Adolphe Max 108-116
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016024
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016222
- Photo page: https://balat.kikirpa.be/en/photo/T016222/
- Preview: `data/historical/balat/balat-t016222.jpg` (sha256 `8d85faa597fd1b3e…`)
- Address: Rue de Laeken 16 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_Laeken/16/32639
- Suggested class from inventory: Second Empire (source styles: Second Empire)
- Photo date: 1975; scope: facade; detail: façade antérieure rue de Laeken et façade latérale droite place du Samedi; page title: immeuble de rapport / Maison, Bruxelles, rue de Laeken 16-18
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016222
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016345
- Photo page: https://balat.kikirpa.be/en/photo/T016345/
- Preview: `data/historical/balat/balat-t016345.jpg` (sha256 `54dad4e6e88e1c0f…`)
- Address: Boulevard Emile Jacqmain 8 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Boulevard_Emile_Jacqmain/8/32411
- Suggested class from inventory: Second Empire (source styles: Éclectisme, Second Empire)
- Photo date: 1975; scope: facade; detail: façade antérieure boulevard Emile Jacqmain et façade latérale rue Van der Elst; page title: immeuble de rapport / Maison, Bruxelles, boulevard Emile Jacqmain 8-10
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016345
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016416
- Photo page: https://balat.kikirpa.be/en/photo/T016416/
- Preview: `data/historical/balat/balat-t016416.jpg` (sha256 `167473625d6c6dd2…`)
- Address: Rue des Fripiers 6 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_des_Fripiers/6/33566
- Suggested class from inventory: Second Empire (source styles: Second Empire)
- Photo date: 1975; scope: facade; detail: façades antérieures; page title: maison / Maison, Bruxelles, rue des Fripiers 6
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016416
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016422
- Photo page: https://balat.kikirpa.be/en/photo/T016422/
- Preview: `data/historical/balat/balat-t016422.jpg` (sha256 `69d7477ae25dcbc2…`)
- Address: Rue des Fripiers 36 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_des_Fripiers/36/33576
- Suggested class from inventory: Second Empire (source styles: Éclectisme, Second Empire)
- Photo date: 1975; scope: facade; detail: façade antérieure; page title: immeuble de rapport / Maison, Bruxelles, rue des Fripiers 36
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016422
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016426
- Photo page: https://balat.kikirpa.be/en/photo/T016426/
- Preview: `data/historical/balat/balat-t016426.jpg` (sha256 `c4c26a0826e80e7e…`)
- Address: Place de la Vieille Halle aux Blés 49 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Place_de_la_Vieille_Halle_aux_Bles/49/31851
- Suggested class from inventory: Baroque (source styles: Baroque)
- Photo date: 1975; scope: facade; detail: façade antérieure; page title: maison / Maison, Bruxelles, Place de la Vieille Halle aux Blés 49
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016426
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016716
- Photo page: https://balat.kikirpa.be/en/photo/T016716/
- Preview: `data/historical/balat/balat-t016716.jpg` (sha256 `b8bd9496e5580528…`)
- Address: Rue du Midi 102 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Midi/102/31479
- Suggested class from inventory: Second Empire (source styles: Éclectisme, Néoclassicisme, Second Empire)
- Photo date: 1975; scope: facade; detail: façade antérieure; page title: maison / Maison, Bruxelles, rue du Midi 102-106
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016716
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016736
- Photo page: https://balat.kikirpa.be/en/photo/T016736/
- Preview: `data/historical/balat/balat-t016736.jpg` (sha256 `c1c5208224abd9bd…`)
- Address: Rue du Midi 67 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Midi/67/31474
- Suggested class from inventory: Second Empire (source styles: Éclectisme, Néoclassicisme, Second Empire)
- Photo date: 1975; scope: facade; detail: façade antérieure; page title: hôtel de maître / Maison, Bruxelles, rue du Midi 67
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016736
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T016760
- Photo page: https://balat.kikirpa.be/en/photo/T016760/
- Preview: `data/historical/balat/balat-t016760.jpg` (sha256 `1251b65b3eddf45a…`)
- Address: Rue du Midi 40 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_du_Midi/40/31461
- Suggested class from inventory: Second Empire (source styles: Second Empire, Éclectisme, Néoclassicisme)
- Photo date: 1975; scope: facade; detail: façades antérieures; page title: maison / Maison, Bruxelles, rue du Midi 40-44
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T016760
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T017637
- Photo page: https://balat.kikirpa.be/en/photo/T017637/
- Preview: `data/historical/balat/balat-t017637.jpg` (sha256 `b024d578e63d11cc…`)
- Address: Rue de la Madeleine 33 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Rue_de_la_Madeleine/33/37914
- Suggested class from inventory: Baroque with classical features (source styles: Baroque classicisant, Néoclassicisme (du 18e siècle), Néoclassicisme)
- Photo date: 1975; scope: facade; detail: façade antérieure; page title: maison / Maison, Bruxelles, rue de la Madeleine 33
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T017637
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T017849
- Photo page: https://balat.kikirpa.be/en/photo/T017849/
- Preview: `data/historical/balat/balat-t017849.jpg` (sha256 `2992a6c77ca65c7e…`)
- Address: Boulevard de Waterloo 25 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Boulevard_de_Waterloo/25/30635
- Suggested class from inventory: Beaux-Arts (source styles: Beaux-Arts; build year unknown — reviewer to confirm the facade matches)
- Photo date: 1976; scope: facade; detail: Façades avant; page title: hôtel de maître / Maison, Bruxelles, boulevard de Waterloo 25-26
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T017849
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T018633
- Photo page: https://balat.kikirpa.be/en/photo/T018633/
- Preview: `data/historical/balat/balat-t018633.jpg` (sha256 `437153062f789371…`)
- Address: Rue Masui 47 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Extension_Nord/Rue_Masui/47/37490
- Suggested class from inventory: Neoclassical (source styles: Néoclassicisme)
- Photo date: 1975; scope: facade; detail: façade antérieure; page title: maison / Maison, Bruxelles, rue Masui 45-47
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T018633
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T019424
- Photo page: https://balat.kikirpa.be/en/photo/T019424/
- Preview: `data/historical/balat/balat-t019424.jpg` (sha256 `b8c1c7b99ba6e3ed…`)
- Address: Rue de Gravelines 39 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Extension_Est/Rue_de_Gravelines/39/18154
- Suggested class from inventory: Art Nouveau (source styles: Art nouveau)
- Photo date: 1976; scope: facade; detail: façades principales à front de rue; page title: maison / Maison, Bruxelles, rue de Gravelines 39
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T019424
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`

### T019642
- Photo page: https://balat.kikirpa.be/en/photo/T019642/
- Preview: `data/historical/balat/balat-t019642.jpg` (sha256 `c153a6910c95ea49…`)
- Address: Square Ambiorix 4 — fiche: https://monument.heritage.brussels/fr/Bruxelles_Extension_Est/Square_Ambiorix/4/18013
- Suggested class from inventory: Historicist neo-styles (source styles: Éclectisme, Néo-Renaissance)
- Photo date: 1976; scope: facade; detail: Vue des façades principales à front de rue; page title: maison / Maison, Bruxelles, square Ambiorix 4-5
- Licence: CC BY 4.0; credit: KIK-IRPA, Brussels (Belgium), cliché T019642
- Fill in: `facade_label` | `facade_observation` | `reviewer` | `reviewed_at` | `confidence`


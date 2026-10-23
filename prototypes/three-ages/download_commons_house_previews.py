#!/usr/bin/env python3
"""Download the open-licence Commons house-facade previews used as weak-label candidates.

Each asset is pinned to an exact Commons file title, its source-stated licence,
an output path and the SHA-256 of the 800px preview. Any licence change,
title change or silent upstream replacement fails the run instead of quietly
entering the candidate pool. House identity is asserted through the Commons
category and, where the file page carries one, the Brussels monument record.

These previews are source imagery. They are not reviewer visual classifications.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "three-ages-facade-style-research/1.0"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
ALLOWED_HOSTS = {"commons.wikimedia.org", "upload.wikimedia.org", "thumb.wikimedia.org"}
ALLOWED_LICENCES = {"CC0", "CC BY 2.0", "CC BY-SA 2.0", "CC BY-SA 3.0", "CC BY-SA 4.0"}

# Wikimedia rate-limits bulk clients. Space requests out and back off on 429 so
# a large run degrades into a slow run rather than an aborted one.
REQUEST_INTERVAL_SECONDS = 1.5
MAX_ATTEMPTS = 6

ASSETS = {
    "commons-belgique-bruxelles-maison-du-roi-d-espagne-01": {
        "title": "File:Belgique - Bruxelles - Maison du Roi d'Espagne - 01.jpg",
        "source_id": "001",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-roi-d-espagne-01.jpg",
        "sha256": "dabc36ddeeb37b20d93b98b22d4c69e66b8deae587f7e295be09eb9b3ac3b2ef",
    },
    "commons-maison-du-roi-d-espagne-brussels-full-view-of-the-front-faca": {
        "title": "File:Maison du Roi d'Espagne (Brussels) - Full view of the front facade.jpg",
        "source_id": "001",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/maison-du-roi-d-espagne-brussels-full-view-of-the-front-faca.jpg",
        "sha256": "e8d03190f12e6e49b329315a8962e75101fb0523fcacada6a746ea015a035689",
    },
    "commons-belgique-bruxelles-maison-de-la-brouette-05b": {
        "title": "File:Belgique - Bruxelles - Maison de la Brouette - 05b.jpg",
        "source_id": "002",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-la-brouette-05b.jpg",
        "sha256": "70c317b80bd4747a99312767ceecf7d873e06b8108520594036a11506a7e709e",
    },
    "commons-belgique-bruxelles-maison-de-la-brouette-05c": {
        "title": "File:Belgique - Bruxelles - Maison de la Brouette - 05c.jpg",
        "source_id": "002",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-la-brouette-05c.jpg",
        "sha256": "e1a54ef5ebcf383fbcf762efdac1ae1d956225650349d749dd491079271804b0",
    },
    "commons-el-saco-y-la-carretilla-grand-place-bruselas-b-lgica-2021-12": {
        "title": "File:El Saco y la Carretilla, Grand-Place, Bruselas, Bélgica, 2021-12-15, DD 187-189 HDR.jpg",
        "source_id": "003",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/el-saco-y-la-carretilla-grand-place-bruselas-b-lgica-2021-12.jpg",
        "sha256": "8b5aac746d6448dcb86470866cfbf26da87b76ee736ecfea5dad86b3641c0336",
    },
    "commons-maison-du-sac-brussels-full-view-of-the-front-facade": {
        "title": "File:Maison du Sac (Brussels) - Full view of the front facade.jpg",
        "source_id": "003",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/maison-du-sac-brussels-full-view-of-the-front-facade.jpg",
        "sha256": "14164ef7d505b81eb8db2bee52b5ea28789d62ebbf03fd779b8ac2ed50fd3fba",
    },
    "commons-grote-markt-brussel-70": {
        "title": "File:Grote Markt Brussel 70.jpg",
        "source_id": "004",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grote-markt-brussel-70.jpg",
        "sha256": "9c9803c3a879b49e271c071c52f547de8ea6672090d9cecd76f64b65127c7ae8",
    },
    "commons-grote-markt-brussel-71": {
        "title": "File:Grote Markt Brussel 71.jpg",
        "source_id": "004",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grote-markt-brussel-71.jpg",
        "sha256": "993c6e7e5d7cc6235fb8204b6551e83ff8c94fb32608c8fc9e5ccf648818f902",
    },
    "commons-grote-markt-brussel-67": {
        "title": "File:Grote Markt Brussel 67.jpg",
        "source_id": "005",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grote-markt-brussel-67.jpg",
        "sha256": "d3d41abcdaff4321c9b5860aab449fc3bd55d1fdd9dd46e15b984155fa385e20",
    },
    "commons-belgium-6484-guildhall-14121896884": {
        "title": "File:Belgium-6484 - Guildhall (14121896884).jpg",
        "source_id": "006",
        "licence": "CC BY-SA 2.0",
        "output": "data/historical/commons/belgium-6484-guildhall-14121896884.jpg",
        "sha256": "5f9124ef70d0e693f4da2e06f952e5fbfc6b6f6fac4f4e6743ab9d589cef064e",
    },
    "commons-grote-markt-brussel-69": {
        "title": "File:Grote Markt Brussel 69.jpg",
        "source_id": "006",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grote-markt-brussel-69.jpg",
        "sha256": "69573a2e8b7afd2615514a60e1f5f8f526e16d2b6882b7fe244f53397a48bfd5",
    },
    "commons-br-ssel-grand-place": {
        "title": "File:Brüssel, Grand Place.jpg",
        "source_id": "007",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/br-ssel-grand-place.jpg",
        "sha256": "7c5e4e3fd395ffd483e933f7d3738fb8a9c422b260c3f05a01f6c0cd21172243",
    },
    "commons-h-tel-de-ville-bis": {
        "title": "File:Hôtel de Ville bis.jpg",
        "source_id": "007",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/h-tel-de-ville-bis.jpg",
        "sha256": "c498d773e5ad4be969cb0c375b05162b5679faf3fcaa39403c6504df4a3b7422",
    },
    "commons-grote-markt-brussel-4258305016": {
        "title": "File:Grote Markt, Brussel-4258305016.jpg",
        "source_id": "008",
        "licence": "CC BY-SA 2.0",
        "output": "data/historical/commons/grote-markt-brussel-4258305016.jpg",
        "sha256": "6695e522fe5b303f2577f8f914cb0356ab81ef41622fefe08b84a88009c60c68",
    },
    "commons-karel-buls-straat-brussel-4532436459": {
        "title": "File:Karel Buls Straat, Brussel-4532436459.jpg",
        "source_id": "008",
        "licence": "CC BY 2.0",
        "output": "data/historical/commons/karel-buls-straat-brussel-4532436459.jpg",
        "sha256": "9c128d9270d2165ccf60a86f9736638dfffb7c6980147e2e3b6892934be27a00",
    },
    "commons-grand-place-9-bruxelles-01": {
        "title": "File:Grand-Place 9, Bruxelles.01.jpg",
        "source_id": "009",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grand-place-9-bruxelles-01.jpg",
        "sha256": "296d4855b255b6adcbcb1f874e2aaf62c2b688abf9fce8656db4e1face513968",
    },
    "commons-la-maison-du-cygne-bruxelles-2": {
        "title": "File:La Maison du Cygne, Bruxelles - 2.jpg",
        "source_id": "009",
        "licence": "CC0",
        "output": "data/historical/commons/la-maison-du-cygne-bruxelles-2.jpg",
        "sha256": "7654939a20e489755714e24b4c5ef962f6a029cf4b6c6bb9bcfe62e6440c66ff",
    },
    "commons-grand-place-10-bruxelles-01": {
        "title": "File:Grand-Place 10, Bruxelles.01.jpg",
        "source_id": "010",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grand-place-10-bruxelles-01.jpg",
        "sha256": "60f4ff9e6bcfe0d930d8bdc03f5340ce4790877707aff4d4f8e51399cbd2f64d",
    },
    "commons-grand-place-brussels-frontal-view-of-the-maison-des-brasseur": {
        "title": "File:Grand-Place (Brussels) - Frontal view of the Maison des Brasseurs (Brewers' House) facade and gilded equestrian statue.jpg",
        "source_id": "010",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grand-place-brussels-frontal-view-of-the-maison-des-brasseur.jpg",
        "sha256": "8f193c2d8cb8aad62b35372e57b24421b2f63696a6f9cfbb48f8648447c5dd87",
    },
    "commons-bruxelles-grand-place-11": {
        "title": "File:Bruxelles Grand-Place 11.jpg",
        "source_id": "011",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/bruxelles-grand-place-11.jpg",
        "sha256": "8e145dc23ea91b460214ab4b2141097a6ec17b60028c129ffb6b0b1b78df524b",
    },
    "commons-grand-place-11-12-bruxelles-01": {
        "title": "File:Grand-Place 11-12, Bruxelles.01.jpg",
        "source_id": "011",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grand-place-11-12-bruxelles-01.jpg",
        "sha256": "1224364a00b88c1bead17d10e70eebfbf878a01e383530bc43510dbbbf681e92",
    },
    "commons-belgique-bruxelles-maison-du-mont-thabor-01": {
        "title": "File:Belgique - Bruxelles - Maison du Mont Thabor - 01.jpg",
        "source_id": "012",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-mont-thabor-01.jpg",
        "sha256": "56f6c7b6bda01195a7deeac4ae58a8d19893e6c8a5c9c65fbcbe9e7e6a915517",
    },
    "commons-bruxelles-grand-place-12": {
        "title": "File:Bruxelles Grand-Place 12.jpg",
        "source_id": "012",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/bruxelles-grand-place-12.jpg",
        "sha256": "3ed0a9aa3dbe8380d41e39a336109f00ed102ebf46e8060802360b849c48cbb3",
    },
    "commons-belgique-bruxelles-maison-du-roi-de-bavi-re-02": {
        "title": "File:Belgique - Bruxelles - Maison du Roi de Bavière - 02.jpg",
        "source_id": "013",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-roi-de-bavi-re-02.jpg",
        "sha256": "4528ad91c1cce84186e02a5e3f60dc1e5fb655206ccbede676adf36b54b0e899",
    },
    "commons-maison-d-alsemberg-aux-trois-couleurs-le-roi-de-bavi-re-gr": {
        "title": "File:Maison d Alsemberg Aux Trois Couleurs Le Roi de Bavière Grand Place 12 A.jpg",
        "source_id": "013",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/maison-d-alsemberg-aux-trois-couleurs-le-roi-de-bavi-re-gr.jpg",
        "sha256": "c6adaec3989ea77a850fbed55ef937458fe10751047b6da83893bd18e623454b",
    },
    "commons-bruxelles-grand-place-maison-des-ducs-de-brabant-5": {
        "title": "File:Bruxelles Grand-Place Maison des Ducs de Brabant 5.jpg",
        "source_id": "015",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/bruxelles-grand-place-maison-des-ducs-de-brabant-5.jpg",
        "sha256": "450eaaa4e040b2702241f0de6079b3495f9e933f5ffc70442f6173a7d90776c6",
    },
    "commons-maison-des-ducs-de-brabant-brussels-full-frontal-facade-": {
        "title": "File:Maison des Ducs de Brabant (Brussels) - Full frontal facade and Grand-Place square with tourists.jpg",
        "source_id": "015",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/maison-des-ducs-de-brabant-brussels-full-frontal-facade-.jpg",
        "sha256": "7e662cb45cfeba9876d16081f927cdd497cbe176e09cec6684a35c644f49724b",
    },
    "commons-maison-des-ducs-de-brabant-brussels-main-facade-on-the-g": {
        "title": "File:Maison des Ducs de Brabant (Brussels) - Main facade on the Grand-Place with cobblestone square and tourists.jpg",
        "source_id": "015",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/maison-des-ducs-de-brabant-brussels-main-facade-on-the-g.jpg",
        "sha256": "97a72244387e6ebde99c42f0dbae984f96a4f821653adf1522282bf7425613d9",
    },
    "commons-belgique-bruxelles-maison-du-cerf-00": {
        "title": "File:Belgique - Bruxelles - Maison du Cerf - 00.jpg",
        "source_id": "021",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-cerf-00.jpg",
        "sha256": "0a3cc82d6842bf829c3b12e2650ea894c60a8fe74b75875e7ab6f979cf06ce24",
    },
    "commons-belgique-bruxelles-maison-du-cerf-01b": {
        "title": "File:Belgique - Bruxelles - Maison du Cerf - 01b.jpg",
        "source_id": "021",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-cerf-01b.jpg",
        "sha256": "cc3fd09c38a1df94ea7fd0859627f72d38369214abc0f819b5af986f5f6dbb90",
    },
    "commons-belgique-bruxelles-maison-du-cerf-01c": {
        "title": "File:Belgique - Bruxelles - Maison du Cerf - 01c.jpg",
        "source_id": "021",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-cerf-01c.jpg",
        "sha256": "f2e507f93be65958380f9b68d96d02731aba2e5c86632f3f8b42dfa9219f73dd",
    },
    "commons-belgique-bruxelles-maison-de-joseph-et-anne-00": {
        "title": "File:Belgique - Bruxelles - Maison de Joseph et Anne - 00.jpg",
        "source_id": "022",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-joseph-et-anne-00.jpg",
        "sha256": "0f697f03c94c7a1a5d1af1ea659b38bd86e4d4e540e92cf125ae9fd4a92610bc",
    },
    "commons-belgique-bruxelles-maison-de-joseph-et-anne-04c": {
        "title": "File:Belgique - Bruxelles - Maison de Joseph et Anne - 04c.jpg",
        "source_id": "022",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-joseph-et-anne-04c.jpg",
        "sha256": "201c2798ea5bb14b604c4297d2cdbe0ba4b1a7e7a57527a182dcfc7c21b1891a",
    },
    "commons-belgique-bruxelles-maison-de-l-ange-01b": {
        "title": "File:Belgique - Bruxelles - Maison de l'Ange - 01b.jpg",
        "source_id": "023",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-l-ange-01b.jpg",
        "sha256": "4f9f41ea4bdf01a6032cd99a5010d7ed868ac9738763e91548dc8325cca3ff9d",
    },
    "commons-belgique-bruxelles-maison-de-l-ange-01c": {
        "title": "File:Belgique - Bruxelles - Maison de l'Ange - 01c.jpg",
        "source_id": "023",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-l-ange-01c.jpg",
        "sha256": "58fb9473d27d3bc4ab060350fdb7a3dc2798fce00f29718d82ec20182212a57d",
    },
    "commons-brussel-heuvelstraat-24": {
        "title": "File:Brussel Heuvelstraat 24.jpg",
        "source_id": "024",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/brussel-heuvelstraat-24.jpg",
        "sha256": "d9f9806d6a1c782b2f759e6eb94d77ad0da0129beea39246a16d93f722e2f0ec",
    },
    "commons-maison-de-la-balance-rue-de-la-colline-24-bruxelles": {
        "title": "File:Maison de la Balance Rue de la Colline 24 Bruxelles.jpg",
        "source_id": "024",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/maison-de-la-balance-rue-de-la-colline-24-bruxelles.jpg",
        "sha256": "c6b2bcd149e9c063523410f965bbfe8638770b3cefb50d51a4fa34c060754d19",
    },
    "commons-belgique-bruxelles-maison-de-la-chaloupe-d-or-00": {
        "title": "File:Belgique - Bruxelles - Maison de la Chaloupe d'Or - 00.jpg",
        "source_id": "025",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-la-chaloupe-d-or-00.jpg",
        "sha256": "3a95473ea58e288775c5b6f16fe67eb092ba803af6a0f665ed4bc89cf2bab61e",
    },
    "commons-belgique-bruxelles-maison-de-la-chaloupe-d-or-06b": {
        "title": "File:Belgique - Bruxelles - Maison de la Chaloupe d'Or - 06b.jpg",
        "source_id": "025",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-la-chaloupe-d-or-06b.jpg",
        "sha256": "3a8a7a2e1d256fa898b8691ddd71cbeb7dbfad839cb5ade735acb99164741e8c",
    },
    "commons-belgique-bruxelles-maison-de-la-chaloupe-d-or-07b": {
        "title": "File:Belgique - Bruxelles - Maison de la Chaloupe d'Or - 07b.jpg",
        "source_id": "025",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-la-chaloupe-d-or-07b.jpg",
        "sha256": "0ce90e0d95f364401facf00ce1af915dbbecdc754ab4324f07d836d4e19b0714",
    },
    "commons-belgique-bruxelles-maison-du-pigeon-02": {
        "title": "File:Belgique - Bruxelles - Maison du Pigeon - 02.jpg",
        "source_id": "026",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-pigeon-02.jpg",
        "sha256": "1ca757354c97fdf8e4cacaf95db9315fa515aa5d187a89223460428b15d2eb23",
    },
    "commons-belgique-bruxelles-maison-du-pigeon-03": {
        "title": "File:Belgique - Bruxelles - Maison du Pigeon - 03.jpg",
        "source_id": "026",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-pigeon-03.jpg",
        "sha256": "b45a0590822f14e616887f38021e328edb2fe502514d39eb0f478e46949a5f6e",
    },
    "commons-belgique-bruxelles-maison-du-marchand-d-or-02b": {
        "title": "File:Belgique - Bruxelles - Maison du Marchand d'Or - 02b.jpg",
        "source_id": "027",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-marchand-d-or-02b.jpg",
        "sha256": "d4e1490bd2fd7fa49a97ca0e617275e77312a6a84451f813899ea28be7d2dcff",
    },
    "commons-belgique-bruxelles-maison-du-marchand-d-or-02c": {
        "title": "File:Belgique - Bruxelles - Maison du Marchand d'Or - 02c.jpg",
        "source_id": "027",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-marchand-d-or-02c.jpg",
        "sha256": "63425a26b637eb5f068f256cf3317a7e1133da45f1235b58bd5df1b5bd539f8a",
    },
    "commons-bruselas-plaza-mayor-04": {
        "title": "File:Bruselas, Plaza Mayor 04.jpg",
        "source_id": "028",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/bruselas-plaza-mayor-04.jpg",
        "sha256": "995d6edae0138ac309dfdd0e6ed0cfc38941491c81390d25c074c81d5fabf8fd",
    },
    "commons-grand-place-brussels-frontal-view-of-the-king-s-house-maison": {
        "title": "File:Grand-Place (Brussels) - Frontal view of the King's House (Maison du Roi) facade with visitors on the square.jpg",
        "source_id": "028",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/grand-place-brussels-frontal-view-of-the-king-s-house-maison.jpg",
        "sha256": "1313ba540da94f14ca3244ca2a8770e3dd19d8ba2fcd0396de1b33f34c855d80",
    },
    "commons-maison-du-roi-brussels-full-frontal-neo-gothic-facade-and-ce": {
        "title": "File:Maison du Roi (Brussels) - Full frontal Neo-Gothic facade and central tower view.jpg",
        "source_id": "028",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/maison-du-roi-brussels-full-frontal-neo-gothic-facade-and-ce.jpg",
        "sha256": "f1ad916829ecb69da0bf627c0cea11d23cd3a1ca10804c644fbdc6cc61dcd6f7",
    },
    "commons-belgique-bruxelles-maison-du-heaume-02": {
        "title": "File:Belgique - Bruxelles - Maison du Heaume - 02.jpg",
        "source_id": "029",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-heaume-02.jpg",
        "sha256": "62718b76b6b53108fe4b4f91f974458c5df7ec15b42d185aabf540e797030a9c",
    },
    "commons-belgique-bruxelles-maison-du-heaume-08": {
        "title": "File:Belgique - Bruxelles - Maison du Heaume - 08.jpg",
        "source_id": "029",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-heaume-08.jpg",
        "sha256": "eb1d132124a105c4c4fe03552c0511850858bb1891e0ccf700e53d95ec008669",
    },
    "commons-belgique-bruxelles-maison-du-paon-03": {
        "title": "File:Belgique - Bruxelles - Maison du Paon - 03.jpg",
        "source_id": "030",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-paon-03.jpg",
        "sha256": "36c0c7de23a04bc25ee07a8c314ac91df7a91b3a3e7683d5dd27abff0b2a73fa",
    },
    "commons-belgique-bruxelles-maison-du-paon-04": {
        "title": "File:Belgique - Bruxelles - Maison du Paon - 04.jpg",
        "source_id": "030",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-paon-04.jpg",
        "sha256": "1ed7ebc20ace2fd7826860c920292388b6d4c572aa62a1682dd0fff827300107",
    },
    "commons-belgique-bruxelles-maison-du-petit-renard-et-du-ch-ne-02": {
        "title": "File:Belgique - Bruxelles - Maison du Petit Renard et du Chêne - 02.jpg",
        "source_id": "031",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-petit-renard-et-du-ch-ne-02.jpg",
        "sha256": "c508b9e89793b6b3beda67fbd32acf80963d2e17b20c63730239a1c480f27f28",
    },
    "commons-belgique-bruxelles-maison-du-petit-renard-et-du-ch-ne-03": {
        "title": "File:Belgique - Bruxelles - Maison du Petit Renard et du Chêne - 03.jpg",
        "source_id": "031",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-du-petit-renard-et-du-ch-ne-03.jpg",
        "sha256": "f9461d60e19584170001a3a6c66b2f646a2d35b3a04c30180a5a1b97c5466a5d",
    },
    "commons-belgique-bruxelles-maison-de-sainte-barbe-02": {
        "title": "File:Belgique - Bruxelles - Maison de Sainte-Barbe - 02.jpg",
        "source_id": "033",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-sainte-barbe-02.jpg",
        "sha256": "38f58debdda34600e26b3579d2d8ed47665b76b5d8ac48282ed90b3d076b2ed3",
    },
    "commons-bruxelles-sainte-barbe-2043-0065038": {
        "title": "File:Bruxelles Sainte-Barbe 2043-0065038.jpg",
        "source_id": "033",
        "licence": "CC BY-SA 3.0",
        "output": "data/historical/commons/bruxelles-sainte-barbe-2043-0065038.jpg",
        "sha256": "3a084a3ce5277fe2137526868df88360d83b69520b1c95f1dc6385fa2a5d1a99",
    },
    "commons-belgique-bruxelles-maison-de-l-ne-02": {
        "title": "File:Belgique - Bruxelles - Maison de l'Âne - 02.jpg",
        "source_id": "034",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-l-ne-02.jpg",
        "sha256": "95237d786c05296e766686da553cc74d7f370ecb3b76237d081576f2201480db",
    },
    "commons-belgique-bruxelles-maison-de-l-ne-03": {
        "title": "File:Belgique - Bruxelles - Maison de l'Âne - 03.jpg",
        "source_id": "034",
        "licence": "CC BY-SA 4.0",
        "output": "data/historical/commons/belgique-bruxelles-maison-de-l-ne-03.jpg",
        "sha256": "8639dfa5643ccd1dbaaf7387d335df9a9504c80556ad3e2cabe17010c93aa9d1",
    },
}


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RuntimeError(f"refusing unexpected Wikimedia URL: {url}")


def request(url: str) -> bytes:
    validate_url(url)
    delay = REQUEST_INTERVAL_SECONDS
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError(f"Wikimedia Commons response exceeds {MAX_RESPONSE_BYTES:,} bytes")
            time.sleep(REQUEST_INTERVAL_SECONDS)
            return body
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == MAX_ATTEMPTS - 1:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            wait = float(retry_after) if (retry_after or "").isdigit() else delay
            print(f"  rate limited ({error.code}); waiting {wait:.0f}s")
            time.sleep(wait)
            delay = min(delay * 2, 60)
    raise RuntimeError(f"exhausted retries for {url}")


def fetch_preview(asset_id: str, expected: dict[str, str]) -> bytes:
    params = {
        "action": "query",
        "titles": expected["title"],
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 800,
        "format": "json",
        "formatversion": 2,
    }
    payload = json.loads(request(f"{API}?{urlencode(params)}"))
    pages = payload.get("query", {}).get("pages", [])
    if len(pages) != 1 or pages[0].get("title") != expected["title"]:
        raise RuntimeError(f"Commons returned an unexpected file record for {asset_id}")
    info = pages[0].get("imageinfo", [{}])[0]
    licence = info.get("extmetadata", {}).get("LicenseShortName", {}).get("value")
    if licence != expected["licence"]:
        raise RuntimeError(f"{asset_id} licence changed from {expected['licence']!r} to {licence!r}")
    if licence not in ALLOWED_LICENCES:
        raise RuntimeError(f"{asset_id} no longer carries an open licence: {licence!r}")
    thumbnail_url = info.get("thumburl")
    if not thumbnail_url:
        raise RuntimeError(f"Commons did not provide a thumbnail URL for {asset_id}")
    body = request(thumbnail_url)
    if not body.startswith(b"\xff\xd8\xff"):
        raise RuntimeError(f"Commons preview for {asset_id} is not a JPEG")
    digest = hashlib.sha256(body).hexdigest()
    if digest != expected["sha256"]:
        raise RuntimeError(f"Commons preview checksum changed for {asset_id}: {digest}")
    return body


def main() -> None:
    for asset_id, expected in ASSETS.items():
        destination = ROOT / expected["output"]
        if destination.is_file():
            existing = destination.read_bytes()
            if hashlib.sha256(existing).hexdigest() == expected["sha256"]:
                print(f"unchanged {expected['output']}")
                continue
        body = fetch_preview(asset_id, expected)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        destination.chmod(0o644)
        print(f"wrote {expected['output']} ({len(body):,} bytes)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a contact sheet for auditing cross-pole pairs by eye.

Whether a Mapillary frame really shows the building the catalogue assigns it to
cannot be settled by embeddings (see the label-noise section of
docs/three-ages-finetune-pilot-result.md). It can be settled in a few minutes by
looking: each row shows one present-day frame beside up to three publisher
pictures of the same building, with ids, coordinates and any date evidence.

The output is a self-contained HTML file with relative paths into local/, so it
opens in a browser without copying any pixels into the repository.
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA = REPO / 'local' / 'training'


def load(path: Path) -> list[dict]:
    with path.open(encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--samples', type=int, default=40)
    ap.add_argument('--publisher-per-row', type=int, default=3)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default=str(DATA / 'label-audit.html'))
    args = ap.parse_args()

    pub = load(DATA / 'manifest.csv')
    mp = load(DATA / 'mapillary_manifest.csv')
    by_building = defaultdict(list)
    for row in pub:
        by_building[row['building_id']].append(row)
    frames = defaultdict(list)
    for row in mp:
        frames[row['building_id']].append(row)

    shared = sorted(b for b in frames if b in by_building)
    if not shared:
        raise SystemExit('no building has both a present-day frame and a publisher picture')
    rng = random.Random(args.seed)
    chosen = rng.sample(shared, min(args.samples, len(shared)))

    rows_html = []
    for bid in chosen:
        p_rows = by_building[bid][:args.publisher_per_row]
        m_row = frames[bid][0]
        def img(path: Path, caption: str) -> str:
            rel = path.relative_to(REPO) if path.is_relative_to(REPO) else path
            return (f'<figure><img src="{html.escape(str(rel))}" loading="lazy">'
                    f'<figcaption>{html.escape(caption)}</figcaption></figure>')
        pub_imgs = ''.join(
            img(REPO / 'local' / 'monument-inbox' / bid / r['filename'],
                f"{r['filename']} · {r['capture_era'] or 'undated'}")
            for r in p_rows)
        map_img = img(REPO / 'local' / 'mapillary-inbox' / bid / m_row['filename'],
                      f"{m_row['filename']} · frame {m_row['capture_era'] or '?'}")
        rows_html.append(
            f'<section><h2>{html.escape(bid)}</h2>'
            f'<div class="pair">{map_img}{pub_imgs}</div>'
            f'<p class="meta">{len(by_building[bid])} publisher, '
            f'{len(frames[bid])} frames · {html.escape(m_row.get("username", ""))}</p>'
            f'</section>')

    document = f"""<!doctype html>
<meta charset="utf-8">
<title>Cross-pole label audit ({len(chosen)} buildings)</title>
<style>
 body {{ font: 14px/1.4 system-ui, sans-serif; margin: 2rem; max-width: 1100px; }}
 section {{ border-top: 1px solid #ddd; padding: 1rem 0; }}
 .pair {{ display: flex; gap: .75rem; flex-wrap: wrap; }}
 figure {{ margin: 0; width: 240px; }}
 img {{ width: 100%; height: 180px; object-fit: cover; background: #f3f3f3; }}
 figcaption {{ font-size: 11px; color: #555; word-break: break-all; }}
 .meta {{ font-size: 12px; color: #666; margin: .4rem 0 0; }}
</style>
<h1>Does each present-day frame show its assigned building?</h1>
<p>Leftmost image is the Mapillary frame; the rest are publisher pictures of the
same building from the catalogue. Sampled {len(chosen)} of {len(shared)} buildings
that have both, seed {args.seed}.</p>
{''.join(rows_html)}
"""
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding='utf-8')
    print(json.dumps({'out': str(out), 'buildings': len(chosen),
                      'available': len(shared), 'seed': args.seed}, indent=2))


if __name__ == '__main__':
    main()

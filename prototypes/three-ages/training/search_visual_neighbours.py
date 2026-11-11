#!/usr/bin/env python3
"""Find source-linked visual neighbours for already-reviewed historical pilot images.

Exploratory evidence-finding only: this does not infer construction dates, validate
style labels, train a model, or estimate retrieval generalisation. It uses the
frozen CLIP cache and a training-split gallery, excludes the Grand Place vicinity,
exact query-image byte matches, and repeated images from the same gallery building.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
from collections import Counter
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
PROTO = HERE.parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "prototypes"))
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(HERE))
from audit_facade_dataset import audit_facade_dataset  # noqa: E402
from epoch_data import load_manifest  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def distance_to_sites_m(lat: float, lon: float, sites: np.ndarray) -> float:
    """Approximate local metric distance; only used for a conservative radius filter."""
    dlat = (sites[:, 0] - lat) * 111_320
    dlon = (sites[:, 1] - lon) * 111_320 * math.cos(math.radians(lat))
    return float(np.sqrt(dlat * dlat + dlon * dlon).min())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=Path("local/training/image-isolated-20261025/manifest.csv"))
    ap.add_argument("--embeddings", type=Path, default=Path("local/training/frozen-isolated-20261025/batch64/embeddings.npz"))
    ap.add_argument("--image-root", type=Path, default=Path("local/monument-inbox"))
    ap.add_argument("--review-csv", type=Path, default=PROTO / "data/three-ages-image-review.csv")
    ap.add_argument("--city-records", type=Path, default=PROTO / "data/grand-place-buildings.json")
    ap.add_argument("--radius-m", type=float, default=200)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--out-dir", type=Path, required=True, help="new local output directory; must not exist")
    args = ap.parse_args()
    if args.top_k < 1 or args.radius_m < 0:
        ap.error("--top-k must be positive and --radius-m nonnegative")
    if args.out_dir.exists():
        ap.error(f"refusing to overwrite existing output directory: {args.out_dir}")

    manifest_digest = sha256(args.manifest)
    with np.load(args.embeddings, allow_pickle=False) as c:
        ids = c["ids"].tolist()
        vectors = c["embeddings"].astype("float32")
        cache_hashes = c["image_sha256"].astype(str).tolist()
        cache_manifest_digest = str(c["manifest_sha256"])
        model_tag = str(c["model"])
        toolchain = str(c["toolchain"])
    if manifest_digest != cache_manifest_digest:
        ap.error("embedding cache manifest SHA-256 does not match the selected manifest")
    if len(ids) != len(vectors) or len(ids) != len(cache_hashes) or len(set(ids)) != len(ids):
        ap.error("cache IDs, vectors and image hashes must align and IDs must be unique")
    if not model_tag.startswith("ViT-B-32/laion2b_s34b_b79k") or "+tuned" in model_tag:
        ap.error(f"expected the frozen ViT-B-32 cache, got {model_tag!r}")
    vector_by_id = dict(zip(ids, vectors))
    hash_by_id = dict(zip(ids, cache_hashes))

    audit = audit_facade_dataset(args.review_csv)["label_readiness"]
    contradictions = {(x["source_id"], x["asset_id"]) for x in audit["semantic_contradictions"]}
    with args.review_csv.open(encoding="utf-8", newline="") as f:
        all_reviews = list(csv.DictReader(f))
    queries = [r for r in all_reviews
               if r.get("reviewer") and (r.get("source_id", ""), r.get("asset_id", "")) not in contradictions]
    if not queries:
        ap.error("no populated, non-contradicted pilot rows available as queries")

    city = json.loads(args.city_records.read_text(encoding="utf-8"))["records"]
    sites = np.asarray([[float(r["latitude"]), float(r["longitude"])] for r in city
                        if r.get("latitude") is not None and r.get("longitude") is not None])
    if len(sites) == 0:
        ap.error("no Grand Place coordinates available for proximity exclusion")

    manifest_rows = load_manifest(args.manifest)
    candidates: list[dict] = []
    excluded_near = excluded_missing_coordinates = 0
    for row in manifest_rows:
        key = f"{row['building_id']}/{row['filename']}"
        if row["split"] != "train" or key not in vector_by_id:
            continue
        if not row.get("latitude") or not row.get("longitude"):
            excluded_missing_coordinates += 1
            continue
        distance = distance_to_sites_m(float(row["latitude"]), float(row["longitude"]), sites)
        if distance < args.radius_m:
            excluded_near += 1
            continue
        candidates.append({"key": key, "row": row, "distance_m": distance})
    if not candidates:
        ap.error("no eligible training-split gallery images remain")
    gallery = np.stack([vector_by_id[x["key"]] for x in candidates])

    import open_clip
    import torch
    from PIL import Image
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k", device=args.device)
    model.eval()

    reports = []
    exact_match_count = 0
    cache_byte_mismatch_count = 0
    for q in queries:
        preview = PROTO / q["preview"]
        actual_hash = sha256(preview)
        if actual_hash != q["preview_sha256"]:
            ap.error(f"query preview hash mismatch: {q['asset_id']}")
        duplicate_mask = np.asarray([h == actual_hash for h in (hash_by_id[x["key"]] for x in candidates)])
        exact_match_count += int(duplicate_mask.sum())
        with Image.open(preview) as im, torch.no_grad():
            image_vec = model.encode_image(preprocess(im.convert("RGB")).unsqueeze(0))
            image_vec = image_vec / image_vec.norm(dim=-1, keepdim=True)
        query_vec = image_vec.cpu().numpy().astype("float32")[0]
        similarities = gallery @ query_vec
        similarities[duplicate_mask] = -np.inf

        best_by_building: dict[str, dict] = {}
        for ix in np.argsort(-similarities):
            item = candidates[int(ix)]
            row = item["row"]
            bid = row["building_id"]
            if bid in best_by_building or not np.isfinite(similarities[ix]):
                continue
            image_path = args.image_root / bid / row["filename"]
            if not image_path.is_file() or sha256(image_path) != hash_by_id[item["key"]]:
                cache_byte_mismatch_count += 1
                continue
            styles = row.get("styles") or []
            if isinstance(styles, str):
                styles = [s for s in styles.split("|") if s.strip()]
            best_by_building[bid] = {
                "building_id": bid,
                "filename": row["filename"],
                "score": round(float(similarities[ix]), 6),
                "caption_year": row.get("caption_year"),
                "capture_era": row.get("capture_era") or "unknown",
                "weak_styles": styles,
                "distance_to_grand_place_m": round(item["distance_m"]),
                "split": row["split"],
                "image_sha256": hash_by_id[item["key"]],
            }
            if len(best_by_building) >= args.top_k:
                break
        ranked = list(best_by_building.values())
        reports.append({
            "asset_id": q["asset_id"], "source_id": q["source_id"],
            "epoch": q["epoch"], "reviewed_style": q.get("facade_style", ""),
            "preview": q["preview"], "preview_sha256": actual_hash,
            "candidates": ranked,
            "top5_capture_eras": dict(Counter(x["capture_era"] for x in ranked[:5])),
            "top5_weak_styles": Counter(s for x in ranked[:5] for s in x["weak_styles"]).most_common(5),
        })

    args.out_dir.mkdir(parents=True)
    report = {
        "method": "frozen CLIP ViT-B-32 cosine neighbours; train split; max one image per building; proximity and exact-byte exclusions",
        "interpretation": "exploratory evidence-finding only; not a style/construction-date accuracy estimate; source styles and caption dates are weak metadata",
        "inputs": {
            "manifest_sha256": manifest_digest,
            "embeddings_sha256": sha256(args.embeddings),
            "review_csv_sha256": sha256(args.review_csv),
            "model": model_tag,
            "toolchain": toolchain,
            "radius_m": args.radius_m,
            "top_k": args.top_k,
        },
        "gallery": {
            "images": len(candidates),
            "buildings": len({x["row"]["building_id"] for x in candidates}),
            "near_square_images_excluded": excluded_near,
            "missing_coordinate_images_excluded": excluded_missing_coordinates,
            "exact_query_image_matches_excluded": exact_match_count,
            "cache_byte_mismatches_excluded": cache_byte_mismatch_count,
        },
        "queries": reports,
    }
    (args.out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    page = ["<!doctype html><meta charset='utf-8'><title>Historical facade visual neighbours</title>",
            "<style>body{font:16px sans-serif;max-width:1200px;margin:2rem auto}section{border-top:2px solid #333;margin-top:2rem}.row{display:flex;gap:10px;flex-wrap:wrap}.card{width:190px}.card img{width:180px;height:220px;object-fit:cover}small{display:block;word-break:break-word}</style>",
            "<h1>Visual neighbours for reviewed pilot images</h1>",
            f"<p>Exploratory frozen-encoder search; no new training. {len(candidates):,} training-split images from {len({x['row']['building_id'] for x in candidates}):,} buildings. One image per retrieved building. Images within {args.radius_m:g}m of any Grand Place pilot coordinate and exact query-image byte matches are excluded. Catalogue styles/capture dates are weak metadata, not truth.</p>"]
    for q in reports:
        query_rel = Path(os.path.relpath(PROTO / q["preview"], args.out_dir)).as_posix()
        page.append(f"<section><h2>{html.escape(q['asset_id'])} · {html.escape(str(q['epoch']))} · current label: {html.escape(q['reviewed_style'])}</h2><div class='row'>")
        page.append(f"<div class='card'><img src='{html.escape(query_rel, quote=True)}'><small>Query · source {html.escape(q['source_id'])}</small></div>")
        for c in q["candidates"][:5]:
            img_rel = f"../../monument-inbox/{quote_path(c['building_id'])}/{quote_path(c['filename'])}"
            detail = f"{c['score']} · {c['building_id']}/{c['filename']}<br>{c['caption_year']} · {c['capture_era']}<br>{' | '.join(c['weak_styles'])}"
            page.append(f"<div class='card'><img src='{html.escape(img_rel, quote=True)}'><small>{html.escape(detail).replace('&lt;br&gt;', '<br>')}</small></div>")
        page.append("</div></section>")
    (args.out_dir / "index.html").write_text("\n".join(page), encoding="utf-8")
    print(json.dumps({"output": str(args.out_dir), "gallery": report["gallery"],
                      "queries": len(reports), "exact_matches": exact_match_count,
                      "top5": [{"asset": q["asset_id"], "eras": q["top5_capture_eras"],
                                "weak_styles": q["top5_weak_styles"]} for q in reports]}, ensure_ascii=False, indent=2))


def quote_path(value: str) -> str:
    """Encode one filename component for a relative local HTML URL."""
    from urllib.parse import quote
    return quote(value, safe="")


if __name__ == "__main__":
    main()

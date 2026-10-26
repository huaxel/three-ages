#!/usr/bin/env python3
"""Extract frozen CLIP embeddings for the on-disk training pictures.

Reads local/training/manifest.csv, embeds each stored picture with a frozen
vision encoder on CPU, and writes a compact cache (ids + float32 matrix) that
every probe trains against -- so representation and classification stay
separate experiments and re-running probes never re-pays embedding cost.

Re-run at crawl freeze for the full corpus; the cache records the model id
and manifest size it was built from.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from epoch_data import load_manifest  # noqa: E402

MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=str(Path("local/training/manifest.csv")))
    parser.add_argument("--image-root", default="local/monument-inbox")
    parser.add_argument("--out", default="local/training/embeddings.npz")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=0,
                        help="embed only the first N pictures (smoke test)")
    parser.add_argument("--checkpoint", default="",
                        help="tuned checkpoint from local/training; default keeps "
                             "the frozen laion2b weights")
    parser.add_argument("--device", default="cpu",
                        help="cpu (default) or cuda for a ROCm GPU")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; re-run with --force after the crawl grows")

    import hashlib
    import platform
    import open_clip
    import torchvision
    model, _, preprocess = open_clip.create_model_and_transforms(
        MODEL_NAME, pretrained=PRETRAINED, device=args.device)
    model_tag = f"{MODEL_NAME}/{PRETRAINED}"
    checkpoint_sha = ""
    if args.checkpoint:
        state = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
        if state.get("model") != MODEL_NAME or state.get("pretrained") != PRETRAINED:
            raise SystemExit(
                f"{args.checkpoint} was trained from "
                f"{state.get('model')}/{state.get('pretrained')}, not "
                f"{MODEL_NAME}/{PRETRAINED}")
        model.load_state_dict(state["state_dict"])
        checkpoint_sha = hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest()
        model_tag = f"{model_tag}+tuned:{Path(args.checkpoint).parent.name}"
        print(f"loaded tuned weights from {args.checkpoint}", flush=True)
    model.eval()

    rows = [r for r in load_manifest(args.manifest)]
    if args.limit:
        rows = rows[:args.limit]
    root = Path(args.image_root)
    ids: list[str] = []
    image_hashes: list[str] = []
    vectors: list[np.ndarray] = []
    batch: list[torch.Tensor] = []
    batch_ids: list[str] = []
    batch_hashes: list[str] = []

    def flush() -> None:
        with torch.no_grad():
            feats = model.encode_image(torch.stack(batch))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        ids.extend(batch_ids)
        image_hashes.extend(batch_hashes)
        vectors.extend(feats.cpu().numpy().astype("float32"))
        batch.clear()
        batch_ids.clear()
        batch_hashes.clear()

    missing = 0
    for pos, row in enumerate(rows, 1):
        path = root / row["building_id"] / row["filename"]
        if not path.is_file():
            missing += 1
            continue
        try:
            image_bytes = path.read_bytes()
            with Image.open(io.BytesIO(image_bytes)) as image:
                tensor = preprocess(image.convert("RGB")).to(args.device)
            batch.append(tensor)
            batch_ids.append(f"{row['building_id']}/{row['filename']}")
            batch_hashes.append(hashlib.sha256(image_bytes).hexdigest())
        except Exception:  # unreadable file: counted, not fatal
            missing += 1
            continue
        if len(batch) >= args.batch_size:
            flush()
        if pos % 1000 == 0:
            print(f"embedded {pos}/{len(rows)} ...", flush=True)
    if batch:
        flush()
    matrix = np.stack(vectors) if vectors else np.zeros((0, 512), dtype="float32")
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, ids=np.array(ids), embeddings=matrix,
                        image_sha256=np.array(image_hashes, dtype=str),
                        manifest_sha256=hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
                        model=model_tag, manifest_rows=len(rows),
                        checkpoint=args.checkpoint, checkpoint_sha256=checkpoint_sha,
                        # Provenance: preprocessing/resize behaviour differs between
                        # torchvision builds, so equal weights do NOT imply equal
                        # vectors. Compare caches only within one toolchain.
                        toolchain=np.array(
                            f"python{platform.python_version()}"
                            f" torch{torch.__version__}"
                            f" torchvision{torchvision.__version__}"))
    print(f"wrote {out}: {len(ids)} embeddings, {missing} missing/unreadable")


if __name__ == "__main__":
    main()

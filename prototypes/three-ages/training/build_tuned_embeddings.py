#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical provenance-aware cache builder.

Uses build_embeddings.py rather than maintaining a second encoder/cache schema.
Choose the isolated manifest explicitly; old tuned caches remain historical.
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--checkpoint', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--manifest', default=str(REPO/'local/training/manifest.csv'))
    ap.add_argument('--image-root', default=str(REPO/'local/monument-inbox'))
    ap.add_argument('--batch-size', type=int, default=64)
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--workers', type=int, default=None,
                    help='deprecated; canonical builder batches synchronously')
    args = ap.parse_args()
    if Path(args.out).exists():
        ap.error('output exists; refusing to replace a cache')
    if args.workers is not None:
        print('--workers is deprecated and ignored by the canonical builder', file=sys.stderr)
    command = [sys.executable, str(HERE.parent/'build_embeddings.py'),
               '--checkpoint', args.checkpoint, '--out', args.out,
               '--manifest', args.manifest, '--image-root', args.image_root,
               '--batch-size', str(args.batch_size), '--device', args.device]
    subprocess.run(command, check=True)


if __name__ == '__main__':
    main()

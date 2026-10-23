#!/usr/bin/env python3
"""Probe whether the committed image set supports building-level retrieval.

Style classification is not evaluable on this set: the Grand-Place is Baroque-dominant and
the source-described weak labels are not separable by style (see the annotation spec's
dataset-viability section). Retrieval is a different question, and this probe answers it
with a deliberately trivial descriptor so the result reflects the data rather than a model.

Method: each preview is resized to 24x24, reduced to a contrast-normalised grayscale vector
plus a coarse 8-bin-per-channel colour histogram. Images are ranked by cosine similarity and
scored leave-one-out at facade-unit level. Units with a single image have no positive pair and
are excluded. Near-duplicate photographs inflate retrieval, so the probe also reports the
result with near-duplicate units removed.

This is a feasibility probe, not a benchmark, and the numbers are not gate-enforced: they
depend on the installed Pillow version.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SIZE = 24
NEAR_DUPLICATE_THRESHOLD = 0.8


def descriptor(path: Path) -> list[float]:
    from PIL import Image

    image = Image.open(path).convert("RGB").resize((SIZE, SIZE))
    pixels = list(image.get_flattened_data()) if hasattr(image, "get_flattened_data") else list(image.getdata())
    gray = [(0.299 * r + 0.587 * g + 0.114 * b) / 255 for r, g, b in pixels]
    mean = sum(gray) / len(gray)
    spread = (sum((value - mean) ** 2 for value in gray) / len(gray)) ** 0.5 or 1.0
    structure = [(value - mean) / spread for value in gray]
    histogram: list[float] = []
    for channel in range(3):
        bins = [0] * 8
        for pixel in pixels:
            bins[min(7, pixel[channel] // 32)] += 1
        histogram += [count / len(pixels) for count in bins]
    return structure + [value * 3 for value in histogram]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def top_k_accuracy(keys, vectors, unit, exclude=(), k=1) -> tuple[float, int]:
    counts = Counter(unit[key] for key in keys)
    eligible = [key for key in keys if counts[unit[key]] >= 2 and unit[key] not in exclude]
    if not eligible:
        return 0.0, 0
    hits = 0
    for key in eligible:
        ranked = sorted(
            (other for other in keys if other != key and unit[other] not in exclude),
            key=lambda other: -cosine(vectors[key], vectors[other]),
        )
        if any(unit[other] == unit[key] for other in ranked[:k]):
            hits += 1
    return hits / len(eligible), len(eligible)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default=str(DATA))
    args = parser.parse_args()
    data = Path(args.data_dir)

    cases = json.loads((data / "three-ages-image-cases.json").read_text(encoding="utf-8"))["cases"]
    vectors: dict[tuple[str, str], list[float]] = {}
    unit: dict[tuple[str, str], str] = {}
    missing = []
    for case in cases:
        path = data.parent / case["preview"]
        if not path.is_file():
            missing.append(case["asset_id"])
            continue
        key = (case["source_id"], case["asset_id"])
        vectors[key] = descriptor(path)
        unit[key] = case["facade_unit_id"]
    if missing:
        raise SystemExit(f"missing previews: {', '.join(missing[:5])}")

    keys = sorted(vectors)
    counts = Counter(unit[key] for key in keys)
    print(f"images {len(keys)} across {len(counts)} facade units")
    print(f"units with >=2 images: {sum(1 for n in counts.values() if n >= 2)}")

    pairs = [
        (cosine(vectors[a], vectors[b]), unit[a])
        for a, b in itertools.combinations(keys, 2)
        if unit[a] == unit[b]
    ]
    near_duplicates = {name for score, name in pairs if score > NEAR_DUPLICATE_THRESHOLD}
    same = [score for score, _ in pairs]
    different = [cosine(vectors[a], vectors[b]) for a, b in itertools.combinations(keys, 2) if unit[a] != unit[b]]
    print(f"same-unit similarity  mean {statistics.mean(same):.3f} (n={len(same)})")
    print(f"diff-unit similarity  mean {statistics.mean(different):.3f} (n={len(different)})")
    print(f"same-unit pairs above {NEAR_DUPLICATE_THRESHOLD}: {sum(1 for s in same if s > NEAR_DUPLICATE_THRESHOLD)}")

    chance = 1 / len(counts)
    print(f"\nchance top-1 (uniform over units): {chance:.3f}")
    for label, exclude in (
        ("all units", ()),
        ("excluding the shared Dukes composition", ("gp-13-19-ducs-de-brabant",)),
        ("excluding near-duplicate units", tuple(sorted(near_duplicates))),
    ):
        for k in (1, 5):
            accuracy, n = top_k_accuracy(keys, vectors, unit, exclude=exclude, k=k)
            print(f"  {label:<38} top-{k} {accuracy:.3f} (n={n})")
    print("\nFeasibility probe only: a trivial descriptor, 27 units, and no model training.")
    print("Near-duplicate photographs inflate retrieval; read the excluded variant as the floor.")


if __name__ == "__main__":
    main()

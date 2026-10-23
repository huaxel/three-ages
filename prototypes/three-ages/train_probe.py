#!/usr/bin/env python3
"""Linear probes over frozen embeddings: the first trainable ML in the project.

Heads (single-image, linear on frozen CLIP, CPU):
  drawing      -- binary photo-vs-drawing triage (the gate for everything else)
  capture_era  -- 6-era photo dating (task A; doubles as the B backbone later)
  style        -- multi-label style-family classification (weak source labels)

The construction-era head (task B) is defined but refused without
--reviewed-labels: there is no training-grade construction label in the
source data, and training on contributor years as if they were truth would
bake the proxy in. That file is the label-campaign output; until it exists
the head stays a stub by design.

Eval reports top-1, within-one-era (ordered heads), dummy baselines, and --
the disentanglement check -- per-capture-era confusion slices, so a model
that detects film stock instead of architecture fails visibly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from epoch_data import (  # noqa: E402
    CAPTURE_ERAS, CONSTRUCTION_ERAS, FAMILY_NAMES, load_manifest,
    load_reviewed_labels, with_reviewed_labels)

HEADS = ("drawing", "capture_era", "style", "construction_era")


def targets(rows: list[dict], head: str, reviewed: dict[str, str] | None = None):
    if head == "drawing":
        return np.array([r["drawing_flag"] for r in rows], dtype=int), ["photo", "drawing"]
    if head == "capture_era":
        return np.array([CAPTURE_ERAS.index(r["capture_era"]) for r in rows]), CAPTURE_ERAS
    if head == "construction_era":
        if not reviewed:
            raise SystemExit(
                "construction_era needs --reviewed-labels: contributor years and style "
                "windows are proxies, not training truth (see epoch_data docstring).")
        return (np.array([CONSTRUCTION_ERAS.index(reviewed[r["building_id"]])
                         for r in rows]), CONSTRUCTION_ERAS)
    if head == "style":
        matrix = np.zeros((len(rows), len(FAMILY_NAMES)), dtype=int)
        for pos, row in enumerate(rows):
            for family in row["families"]:
                if family in FAMILY_NAMES:
                    matrix[pos, FAMILY_NAMES.index(family)] = 1
        return matrix, FAMILY_NAMES
    raise AssertionError(f"unreachable: {head}")


def within_one_era(true: np.ndarray, pred: np.ndarray) -> float:
    return float(np.mean(np.abs(true - pred) <= 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default="local/training/manifest.csv")
    parser.add_argument("--embeddings", default="local/training/embeddings.npz")
    parser.add_argument("--head", choices=HEADS, required=True)
    parser.add_argument("--out", default="local/training/probe_report.json")
    parser.add_argument("--reviewed-labels", default="",
                        help="required for the construction_era head (label-campaign output)")
    args = parser.parse_args()

    if args.head == "construction_era" and not args.reviewed_labels:
        raise SystemExit(
            "construction_era needs --reviewed-labels: contributor years and style "
            "windows are proxies, not training truth (see epoch_data docstring).")

    cache = np.load(args.embeddings, allow_pickle=True)
    by_id = {key: vec for key, vec in zip(cache["ids"].tolist(), cache["embeddings"])}
    rows = [r for r in load_manifest(args.manifest)
            if f"{r['building_id']}/{r['filename']}" in by_id
            and (args.head != "capture_era" or r["capture_era"])]
    reviewed: dict[str, str] = {}
    if args.head == "construction_era":
        reviewed = load_reviewed_labels(args.reviewed_labels)
        rows = with_reviewed_labels(rows, reviewed)
    if not rows:
        raise SystemExit("no labelled rows with embeddings; run build_embeddings.py first")

    X = np.stack([by_id[f"{r['building_id']}/{r['filename']}"] for r in rows])
    y, classes = targets(rows, args.head, reviewed)
    splits = np.array([r["split"] for r in rows])
    eras = [r["capture_era"] for r in rows]

    scaler = StandardScaler().fit(X[splits == "train"])
    Xs = scaler.transform(X)
    multilabel = y.ndim == 2
    base = LogisticRegression(max_iter=2000, C=1.0)
    clf = OneVsRestClassifier(base) if multilabel else base
    clf.fit(Xs[splits == "train"], y[splits == "train"])
    pred = clf.predict(Xs[splits == "test"])

    report: dict = {"head": args.head, "classes": list(classes),
                    "n_train": int((splits == "train").sum()),
                    "n_test": int((splits == "test").sum()),
                    "embeddings_model": str(cache["model"]),
                    "dummy_majority_test_accuracy": None}
    if multilabel:
        report["micro_f1_test"] = float(
            __import__("sklearn.metrics", fromlist=["f1_score"]).f1_score(
                y[splits == "test"], pred, average="micro", zero_division=0))
        per_family = {}
        for pos, family in enumerate(classes):
            col_t, col_p = y[splits == "test"][:, pos], pred[:, pos]
            per_family[family] = {
                "support": int(col_t.sum()),
                "f1": float(__import__("sklearn.metrics", fromlist=["f1_score"]).f1_score(
                    col_t, col_p, zero_division=0))}
        report["per_family"] = per_family
    else:
        report["top1_test"] = float(np.mean(pred == y[splits == "test"]))
        dummy = DummyClassifier(strategy="most_frequent").fit(
            Xs[splits == "train"], y[splits == "train"])
        report["dummy_majority_test_accuracy"] = float(dummy.score(Xs[splits == "test"], y[splits == "test"]))
        if args.head in ("capture_era", "construction_era"):
            report["within_one_era_test"] = within_one_era(y[splits == "test"], pred)
    if args.head in ("drawing", "capture_era", "construction_era"):
        # Disentanglement slices: accuracy per capture era on the test split.
        slices = {}
        for era in sorted(set(eras)):
            mask = np.array([(s == "test" and e == era) for s, e in zip(splits, eras)])
            if mask.sum() >= 20:
                slices[era] = {"n": int(mask.sum()),
                               "accuracy": float(np.mean(pred[mask[splits == "test"]] == y[mask]))}
        report["per_capture_era_test"] = slices

    out = Path(args.out)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

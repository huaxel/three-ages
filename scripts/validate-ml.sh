#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}
# These suites use synthetic fixtures only: no corpus, downloads or GPU training.
export HF_HUB_OFFLINE=1
export CUDA_VISIBLE_DEVICES=""
export HIP_VISIBLE_DEVICES=""
export ROCR_VISIBLE_DEVICES=""
"$PYTHON" prototypes/three-ages/training/test_local_pilot.py
"$PYTHON" prototypes/three-ages/training/test_three_ages.py
"$PYTHON" prototypes/three-ages/training/test_evaluation_contracts.py
"$PYTHON" prototypes/three-ages/training/test_development_cv.py
"$PYTHON" prototypes/three-ages/training/test_embedding_fingerprints.py
git diff --check
printf 'Three Ages synthetic CPU ML contracts passed\n'

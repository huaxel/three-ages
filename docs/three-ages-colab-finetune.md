# Fine-tuning: superseded by the local GPU run

**Status: historical.** The Colab handoff below was written while this machine
appeared unable to train. It was wrong about that: after an oversized
`amdgpu.vm_size` boot override was removed, the local 8060S trained the pilot at
~41 pairs/s with a clean kernel. See
[`three-ages-finetune-pilot-result.md`](three-ages-finetune-pilot-result.md) for
the measured result.

Corrected numbers for the sentence that used to open this file: frozen CLIP
retrieval scored **0.64%** publisher cross-era (fair denominator, test split) and
**0.93%** cross-pole — not 1.9% / 0.9%, which came from an earlier eligibility
rule. After one epoch of fine-tuning those became **4.58%** and **4.21%**.

The instructions below remain valid as a **fallback** — a cloud GPU is still the
right choice if the local machine is busy, or if a larger backbone or more
epochs are ever attempted. Nothing here needs to run for the current result.

## Fallback: Colab with Google AI Pro

Upload to Drive as:

```
Drive/three-ages/colab-pack/{pub,map}/     (built by local/training/build_colab_pack.py)
Drive/three-ages/manifest.csv
Drive/three-ages/mapillary_manifest.csv
Drive/three-ages/train_local_pilot.py
```

GPU runtime, then:

```python
!pip install -q open_clip_torch==3.3.0
!python train_local_pilot.py --run-dir /content/drive/MyDrive/three-ages/run-X \
  --batch-size 64 --max-steps 200      # 10-minute pipeline check first
# then the real run: drop --max-steps
```

Caveats that still apply: the 256px pack halves disk and upload cost, but the
packed JPEGs are not the originals, so results from it are not directly
comparable to the local runs, which used the full-resolution corpus.

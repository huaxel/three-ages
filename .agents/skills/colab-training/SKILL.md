---
name: colab-training
description: Run this repository's approved ML workloads on Google Colab CPU, T4, or TPU through Google's official Colab CLI without using the notebook GUI. Use when preparing, launching, monitoring, or retrieving remote training/evaluation jobs.
---

# Colab CLI for Three Ages

Use Google's official [`google-colab-cli`](https://github.com/googlecolab/google-colab-cli) to provision and operate Colab runtimes from a terminal. This skill documents a workflow; it does not itself authorize a billable run, install the CLI, authenticate an account, or access private Drive data.

## Project guardrails

- Read `docs/research-focus.md` and `prototypes/three-ages/training/README.md` before proposing a run. Compute availability does not establish scientific validity.
- The historical retrieval test cohort is spent and historical checkpoints contain shared-image leakage. Do not reuse them as clean evidence, select on test metrics, or imply that filtering evaluation inputs repairs a checkpoint trained on leakage.
- Prefer local CPU for probes over cached embeddings and analysis. Do not allocate Colab for work already demonstrated to run locally in minutes.
- Any training must use newly generated isolated manifests, a predeclared validation protocol, fresh output paths, and record inputs, code revision, environment, seed, metrics, and exclusions. Do not overwrite source manifests, reviews, reports, or checkpoints.
- Colab sessions consume account compute units and are ephemeral. Ask for explicit confirmation before provisioning an accelerator or starting a nontrivial run. Set a runtime/job budget and ensure cleanup.
- Keep pixels, credentials, caches, weights and outputs under ignored `local/`; never commit them.

## Install and authenticate

The official CLI supports Linux/macOS and documents CPU, T4/L4/A100 GPUs and TPU v5e1/v6e1. Actual accelerator allocation depends on the user's Colab account entitlement and current availability.

First inspect installation instructions at the official repository and the CLI version. Install only after the user approves third-party executable installation. The official installation examples are:

```bash
uv tool install google-colab-cli
# or, if uv is not used:
python3 -m pip install google-colab-cli
```

CLI authentication is separate from credentials available inside a runtime. The inspected CLI implementation defaults to `oauth2` (the README may describe a different default); use an explicit `--auth=adc` when relying on Application Default Credentials. Either path can require user authorization. Do not print tokens or inspect credential contents. Verify account/session access with documented read-only commands such as `colab sessions` or `colab status` before allocating compute. Do not run `colab auth` to fix CLI authentication: that command is for credentials inside a VM. The CLI may perform a background PyPI version check on ordinary commands; use display-only commands or disable that check per its documented settings when strict offline behavior is needed.

Do not assume `colab drivemount` is noninteractive. Prefer explicit file transfer or ask the user to perform any required Drive consent/mount step.

## Session lifecycle

Use a named session so it can be inspected and stopped unambiguously:

```bash
colab new -s three-ages-smoke --gpu T4
colab status -s three-ages-smoke
colab exec -s three-ages-smoke -f /absolute/path/to/smoke.py
colab stop -s three-ages-smoke
```

For one-shot scripts, `colab run --gpu T4 script.py [args...]` creates a fresh runtime, runs the script and tears it down. It is preferred when no remote state or resumable multi-step job is required. Avoid `--keep` unless continued inspection/reuse is requested; always stop kept sessions afterward, including on failure.

Colab kernels can retain state between `colab exec` calls. Use absolute paths and make scripts idempotent. Remote default working directory is `/content`. `colab exec -f local_script.py` sends the script text; it does **not** automatically send local datasets or arbitrary input files.

A bounded lifecycle shell pattern:

```bash
set -euo pipefail
session=three-ages-smoke
cleanup() { colab stop -s "$session" >/dev/null 2>&1 || true; }
trap cleanup EXIT
colab new -s "$session" --gpu T4
colab status -s "$session"
colab exec -s "$session" -f /absolute/path/to/smoke.py
# Download required artifacts before cleanup:
colab download -s "$session" /content/output.json local/training/colab-output.json
```

Ensure each `colab download` destination is new; do not overwrite prior evidence. **Do not treat `colab exec` exit code alone as proof that all notebook cells passed:** in the verified T4 smoke, a cell exception was rendered in output while the CLI process continued successfully. Have the script write a machine-readable success sentinel only after all assertions/checkpoint reloads pass; then independently verify that sentinel and downloaded artifacts. Inspect execution output/logs before reporting success.

## Data and artifact transfer

- Inventory exact inputs and total bytes before transfer. Do not upload the full 41 GB image inbox by default.
- `prototypes/three-ages/training/build_colab_pack.py` is a legacy pack builder, not a ready-to-run clean-data workflow: it hard-codes manifest paths under its source-code directory and relative image roots, while current manifests/images live under `local/`. It currently has no CLI options to select those inputs. Do not invoke it unchanged and assume it will find or package the isolated cohort. Before using it, make a separately reviewed, non-destructive adaptation that accepts explicit manifest/image-root arguments and output paths; verify the selected isolated manifests and source counts. Never assume a pack is clean merely because a builder completed.
- The pack builder skips missing/unreadable images. Compare per-source counts against the selected manifests; investigate omissions and ensure the training code handles them explicitly.
- It creates many files. Avoid uploading tens of thousands of individual files. Build a reviewed archive, record SHA-256 checksums for the archive and manifests, transfer only to the user's authorized storage, and verify hashes remotely before execution. Do not place multi-GB archives in git.
- Download checkpoints, reports and logs to a fresh ignored `local/training/...` path; hash them, record the runtime/toolchain, and preserve the source run. Never treat a remote session's surviving state as the only copy of results.

## Choosing hardware

- **CPU runtime:** preprocessing, small probes, smoke tests, and lightweight evaluation; no accelerator allocation.
- **T4:** supported PyTorch/OpenCLIP GPU workloads after a tiny compatibility and throughput smoke test. Save checkpoints and logs to durable storage at each meaningful boundary; runtime disconnection is possible.
- **TPU v5e1:** the official CLI can request it, but this repository's training code is PyTorch/OpenCLIP and is not currently a TPU/XLA training implementation. Do not select TPU for existing scripts or infer compatibility from successful allocation. A TPU experiment requires a separate port, smoke tests, and same-protocol validation before use.

The repository's encoder/cache provenance is toolchain-sensitive. Do not compare embeddings built under different `torch`/`torchvision` preprocessing versions as though the model alone changed. Record package versions, model/pretrained ID, image preprocessing, manifest and image hashes alongside every remote result. Re-encode evaluation data under the checkpoint's matching toolchain where required by existing validators.

## Before starting a real training run

1. State the research question, target semantics, training data/weak-label limitations, and the specific decision this run will enable.
2. Confirm the selected manifests pass exact-image/source isolation; document that near-duplicate and identity review are separate unresolved issues.
3. Freeze training/validation/confirmation roles. Use validation for selection; never tune on the spent test cohort.
4. Confirm data licensing, transfer destination, archive size and image exclusions.
5. Request user approval for accelerator, estimated compute/time budget, and storage transfer.
6. Run a tiny smoke job; verify accelerator and model load, one forward/backward step, checkpoint save/reload, and artifact download.
7. Run only the approved bounded experiment. Keep periodic checkpoints and arrange stop/cleanup on success, exception or cancellation.
8. Verify downloaded hashes, inspect the report and logs, compare against baselines, and record limitations. Do not claim success from a zero exit code alone.

## Official references

- [Google Colab CLI repository and command reference](https://github.com/googlecolab/google-colab-cli)
- [Colab local runtime documentation](https://research.google.com/colaboratory/local-runtimes.html)
- [Colab Enterprise REST API](https://docs.cloud.google.com/colab/docs/reference/rest) — separate product/API, not required for the standard CLI workflow.

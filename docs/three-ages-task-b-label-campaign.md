# Task B label campaign: reviewed construction eras

Task B (construction-era prediction) is the only probe head that stays a stub
by design: `train_probe.py` refuses `--head construction_era` without
`--reviewed-labels`, and `targets()` has no construction branch at all.
Contributor years and style windows are proxies, not training truth. This card
defines the campaign that produces the labels file and wires the head.

## Label contract

`local/training/reviewed_construction_eras.csv`, one row per building:

| column | meaning |
|---|---|
| `building_id` | corpus id (joins to manifest + register review) |
| `construction_era` | one of `CONSTRUCTION_ERAS` in `epoch_data.py`: pre-1850, 1850-1892, 1893-1914, 1918-1940, 1945-1975, post-1975 |
| `evidence` | source field + short quote that justifies the bin (notice text, register entry, dated plaque photo) |
| `reviewer`, `reviewed_at`, `confidence` | same convention as the image/register review CSVs |

Bins follow Brussels building history, not round numbers — do not re-bin
without re-running every reported number.

## Sampling (stratified, anchored on disentanglement)

1. Stratify across the 6 bins; unknowns are a separate queue, not a bin.
2. Prioritise the 8,239 multi-era buildings first: they anchor the
   capture-era confusion slices, so reviewed truth lands where the
   disentanglement check bites hardest. Prefer the 6,119 with Mapillary
   present-day frames secondarily (cross-pole eval material).
3. First batch: 60 buildings (10/bin). Wire the probe, run the head, expand
   only if the dummy baseline is beaten — labels are your time, spend the
   first hour proving the head can use them.

## Probe wiring (needed before batch 1 pays off)

- Add the `construction_era` branch to `targets()` in `train_probe.py`,
  joining reviewed labels by `building_id`; rows without reviewed labels are
  excluded from that head (never fall back to proxies silently).
- Same report shape as the other ordered heads: top-1, within-one-era,
  dummy baseline, per-capture-era confusion slices.

## Workbench

- Seed: `prototypes/three-ages/data/three-ages-register-review.csv` (6 rows,
  register-level convention to extend).
- Protocol: `docs/three-ages-annotation-spec.md`.
- Facade-unit adjudication follows the Grand-Place pilot pattern
  (`three-ages-image-review.csv`, 72 rows).

## Done means

The construction_era head runs end-to-end on batch 1 with dummy beaten and
per-capture-era slices reported. Expansion batches are a separate approval:
each costs reviewer hours, so each needs a number from the previous batch
justifying it.

## The queue is generated

`local/training/build_taskb_queue.py` writes `local/training/taskb_queue.csv`:
**60 buildings, 10 per proxy bin**, all multi-era and all carrying present-day
frames. It refuses to overwrite an existing queue, so work in progress is safe.

Two things this makes explicit:

- Proxies stratify, they do not label. `proxy_years` / `proxy_bin` come from
  architect/catalogue years, which are exactly the proxies that must not become
  training truth. The reviewer fills `construction_era` from the notice and
  records the quote in `evidence`.
- Only 22,834 of 26,419 buildings carry a contributor year at all, so the
  stratifying pool is smaller than the corpus. The chosen 60 are all multi-era
  with Mapillary coverage, because those are the buildings that anchor the
  capture-era confusion slices.

Verified: the queue has 60 unique buildings with blank label fields, its proxy
bins are all valid `CONSTRUCTION_ERAS`, and a *simulated* filled copy loads
through `load_reviewed_labels` and joins correctly — so the reviewer's real
output will not hit a schema surprise after hours of work. The simulated file was
written to a temporary directory and discarded; no fake labels exist in the repo.

### Queue quality checks

- All 60 `notice_url` values return **HTTP 200** (checked one request per second,
  so the source is not hammered). No dead links for the reviewer to hit.
- Addresses are populated for all 60 rows; named complexes with no street number
  fall back to the building name rather than rendering an empty cell.
- `--force` refuses to overwrite a queue that already contains reviewer edits, so
  a regeneration cannot destroy an hour of human work.

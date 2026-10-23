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

`prototypes/three-ages/training/build_taskb_queue.py` writes `local/training/taskb_queue.csv`:
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

### Notice evidence is pre-extracted (quoted, not decided)

The reviewer should not have to open 60 pages to find out what the notice says.
`prototypes/three-ages/training/extract_notice_evidence.py` reads the already
scraped records and adds three columns to the queue:

| column | meaning |
|---|---|
| `notice_excerpt` | up to three sentences from the notice that mention a year or construction verb, verbatim |
| `notice_sources` | which record field they came from (`description`, `details:Intervenant(s)`, ...) |
| `notice_years` | every four-digit year appearing in those sentences |
| `primary_years` | years from sentences that name a construction verb |
| `evidence_strength` | `construction`, `contextual` or `none` |

Two things this deliberately does not do. It never fills `construction_era` — the
reviewer still decides, because catalogue years are exactly the proxies that make
task B a campaign rather than a join. And it strips the style glossaries the site
embeds as tooltips (`<a class="info">éclectique<span>Période : env. 1840-1914
</span></a>`), whose years describe the style rather than the building; before
that fix, building 37300 was credited with 1860 and 1914 from glossary text.

Coverage, measured rather than assumed. All 60 rows carry year evidence, and in
49 of them the years come from a sentence with a construction verb (construit,
érigé, édifié). But the evidence resolves to a **single era for only 17 rows**;
the other 43 mention works from different periods — a founding, an extension, a
restoration — so the reviewer must still judge which phase the label means. My
first version credited all 60 rows with a single "reading a cell" decision; the
measurement says otherwise, and the column set now separates `primary_years`
(construction verbs) from `notice_years` (everything mentioned) so that
distinction is visible instead of glossed.

That disagreement is itself informative: of the 17 unambiguous rows, **10 agree
with the catalogue's proxy year and 7 do not**. A ~40% disagreement rate on the
easiest cases is the strongest argument yet that the proxy cannot stand in for
reviewed labels.

One quote was checked against the live notice page (`37300`: "érigé entre 1894
et 1909") and matches.

Order matters: run `build_taskb_queue.py` first, then
`extract_notice_evidence.py --force`, because rebuilding the queue writes a fresh
fixed column set. Both refuse to overwrite a queue containing reviewer edits.

### Queue quality checks

- All 60 `notice_url` values return **HTTP 200** (checked one request per second,
  so the source is not hammered). No dead links for the reviewer to hit.
- Addresses are populated for all 60 rows; named complexes with no street number
  fall back to the building name rather than rendering an empty cell.
- `--force` refuses to overwrite a queue that already contains reviewer edits, so
  a regeneration cannot destroy an hour of human work.

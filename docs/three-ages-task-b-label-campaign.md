# Task B label campaign: reviewed construction eras

Task B (construction-era prediction) is the only probe head that stays a stub
by design: `train_probe.py` refuses `--head construction_era` without
`--reviewed-labels`, and `targets()` has no construction branch at all.
Contributor years and style windows are proxies, not training truth. This card
defines the campaign that produces the labels file and wires the head.

## The label definition is undefined, and that is load-bearing

The contract says `construction_era` is one of six bins. It does not say *which
phase* of a building counts. Measuring the queue's own evidence shows why that
matters:

| measurement | value |
|---|---|
| rows whose primary years fall in one bin | 17 of 60 |
| rows spanning two bins | 19 |
| rows spanning three or more | 24 |
| rows that change bin if the rule is "latest year" instead of "earliest" | **43 of 60** |
| median span of a building's primary years | **72 years** |

So the label is mostly determined by an unwritten rule, not by the evidence. Two
reviewers applying "construction era" honestly could disagree with each other on
43 of these buildings. Labels like that would make task B unlearnable for reasons
that have nothing to do with the corpus.

**Rule, confirmed by Juan on 2026-10-23.** The era is that of the building's
*principal construction campaign*:
the earliest documented construction of the surviving principal volume, ignoring
later restorations, refits and rear extensions — but using a rebuild instead of
the original when the notice says the building was rebuilt or replaced (register
024, "reconstruction in 1704 on the preserved cellars", would be 1704, not
whatever stood before).

To keep that auditable, each label should also record the phase it came from:

| column | content |
|---|---|
| `construction_era` | the bin the rule selects |
| `phase_years` | the years of that campaign, e.g. `1894-1909` |
| `evidence` | the quoted sentence, as already supplied by `notice_excerpt` |

Two labels that disagree are then comparable ("they chose different phases")
rather than opaque ("one of them was wrong").

### A ranking "fix" that measured worse, and was reverted

Reviewing the second batch showed the extractor surfacing later sentences over
founding ones (the Institut chirurgical row suggested 1945-1975 for a building
designed in 1892). The obvious fix — rank founding sentences first — was
implemented and then **scored against the labels themselves**, which is the only
honest test available:

| ranking | agrees with the 12 reviewed labels |
|---|---|
| order of appearance (original) | **7 / 12** |
| founding sentences first | 6 / 12 |

It made things worse, and for a now-familiar reason: "founding" sentences
frequently describe a *predecessor* (Cité Verregat's 1908 hippodrome, Horta's
earlier house), so preferring them imports the same contamination the excerpts
already suffer. The change was reverted; the evidence is recorded here rather
than quietly deleted.

What was kept from that work: regeneration now **preserves reviewer-entered
fields** instead of refusing to run, so derived columns can be refreshed without
touching a single label (verified: 12 preserved, 0 altered, suggestions
unchanged after the revert).

### Review progress: 12 of 60 labelled

Six buildings were reviewed in chat on 2026-10-23 and recorded in the queue
(`construction_era`, `phase_years`, quoted evidence, reviewer, date, confidence):
37327 Meunerie Moulart (1893-1914), 39699 Institut des Sœurs de Charité
(1945-1975), 34982 chocolaterie Ruell (1893-1914), 37051 Brasserie Cantillon
(1850-1892), 37479 ancienne église protestante (1850-1892), 35003 Hôtel communal
d'Anderlecht (1850-1892). All six load through `load_reviewed_labels`.

One systematic hazard, found on the first row: **an excerpt can quote a
neighbouring property.** The Meunerie Moulart row carried a 1980 villa demolition
from the same street, which suggested `post-1975` for a mill built in 1902-1903.
The queue now carries `identity_name` (52 of 60 buildings are named in the
notice) so a reviewer can see at a glance whether the quoted history belongs to
this building, and the lesson is recorded here rather than in a comment nobody
reads.

Also fixed while doing this: `phase_years` was being written into a column that
the extractor did not know about, so the first write dropped it silently. It is a
first-class column now.

### The rule is applied as far as it can be automated

`extract_notice_evidence.py` now writes two more columns from the same quoted
text:

| column | meaning |
|---|---|
| `suggested_era` | bin of the *earliest* primary year — the rule's mechanical answer |
| `rebuild_flag` | `review` when the notice mentions reconstruction/rebuilding, i.e. where the earliest year may be the building that was replaced |

Across the 60 rows: every row gets a suggestion, spread pre-1850 (14),
1850-1892 (12), 1893-1914 (11), 1918-1940 (8), 1945-1975 (6), post-1975 (9), and
**33 rows are flagged** because the notice mentions rebuilding or destruction —
those are the ones where the rule needs a human, not the arithmetic.

Two defects were found by checking the flag against its own evidence. The first
regex ended with `\b`, so the stem `reconstru` stopped matching "reconstruction"
and eighteen rows silently lost their flag (the count moved *down* after adding
terms, which is what exposed it). The second: fifteen flags pointed at sentences
that the three-excerpt budget had dropped, so a reviewer would see "review" with
no visible reason. Flagged rows now always quote the triggering sentence, centred
on the words that triggered it, and the flag is verified to match the quoted
excerpt on all 60 rows.

So the review is now: confirm the suggestion, or overrule it where the flag says
a rebuild happened. `construction_era` stays blank until a reviewer writes it.

## Label contract

`local/training/reviewed_construction_eras.csv`, one row per building:

| column | meaning |
|---|---|
| `building_id` | corpus id (joins to manifest + register review) |
| `construction_era` | one of `CONSTRUCTION_ERAS` in `epoch_data.py`: pre-1850, 1850-1892, 1893-1914, 1918-1940, 1945-1975, post-1975 — selected by the phase rule above |
| `phase_years` | optional but recommended: the years of the campaign the label came from (`1894-1909`) |
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
  (`three-ages-image-review.csv`, 77 rows).

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

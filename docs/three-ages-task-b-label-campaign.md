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

### Batch 3 — 18 of 60 (2026-10-24)

Third chat batch, all confirmed by Juan and recorded with phase_years +
evidence + reviewer:
34949 workshops Marchand (1918-1940, 1924-1930),
19257 Galerie Louise ensemble (1945-1975, 1951-1964),
39686 Impasse Migerode (pre-1850, 1840s — the 1875 replacements were
demolished in 1993),
23601 Basilique Koekelberg (1918-1940, 1921-1970 — overriding the
1893-1914 suggestion, which came from the provisional 1904-1905 church),
38070 Cité Verregat (1918-1940, first phase 1922-1926),
39748 École technique Chomé-Wyns (1945-1975, 1955-1976 — the 1951 date is
the square, not the school).

Distribution across 18: 1850-1892 x7, 1918-1940 x4, 1893-1914 x3,
1945-1975 x3, pre-1850 x1.

Head check at n=18: 559 train / 67 test images, top-1 0.33 (was 0.24 at
n=12), dummy 0.60 still unbeaten, within-one-era 0.70. A permutation test
(100 shuffles) puts the honest result in context: true top-1 0.328 sits
*below* the permutation mean 0.353 (p=0.65), within-one 0.701 vs perm
mean 0.621 (p=0.19). The test set is only 2 buildings (36469, 39706),
so no claim of signal yet — and the learning curve over 6/9/12/16 train
buildings is flat. Dummy cannot be beaten until the test set holds more
than two buildings; at the 10% building split that means of order 30+
labelled buildings before the number is even capable of moving.

Gap-year footnote: 154 of 22,834 buildings with proxy years (0.67%) have
their earliest proxy in 1915-1917 or 1941-1944. The queue's 39723 row
carried a stale `1945-1975` proxy_bin from before the gap rule; corrected
to blank (gap, unresolved). No suggestion changed — no queue row's
earliest primary year falls in a gap.

### Batch 4 — 24 of 60 (2026-10-24)

Fourth chat batch, same day, all recorded with phase_years + evidence +
reviewer:
37936 Parc de Bruxelles (pre-1850, 1776-1783),
31346 église Notre-Dame de Bon Secours (pre-1850, 1664-1694),
23215 ancien hôtel de l'Administration centrale, rue des Palais
(1918-1940, 1936-1938 then 1946-1950 — the pre-1850 suggestion belonged
to the demolished hôtel Somzée, another predecessor case),
37766 maison de campagne Mosselman (pre-1850, avant 1810),
32578 Grand Hospice / Institut Pacheco (pre-1850, 1824-1827),
17291 cure Saint-Pierre (pre-1850, 1784 — the "plus probablement"
rebuild chosen over 1724).

Distribution across 24: 1850-1892 x7, pre-1850 x6, 1918-1940 x5,
1893-1914 x3, 1945-1975 x3.

Head check at n=24: 652 train / 130 test images (20 train / 4 test
buildings — the test set doubled to 31346, 36469, 37936, 39706, two of
them batch-4 pre-1850 labels), top-1 0.25 (was 0.33), dummy 0.31 still
unbeaten (was 0.60 — the majority baseline fell as the test set widened
beyond two buildings), within-one-era 0.61 (was 0.70). A permutation test
(100 building-level shuffles) puts the honest result in context: true
top-1 0.254 sits *above* the permutation mean 0.199 this time (p=0.28),
within-one 0.608 vs perm mean 0.551 (p=0.27) — the right side of chance,
nowhere near significant. The learning curve over 6/10/14/20 train
buildings is flat and noisy (top-1 0.23/0.31/0.23/0.25), as expected with
a four-building test set. Dummy is now beatable in principle but unbeaten
in fact; still no claim of signal.

Labelling now runs in a workbench instead of chat: `export_taskb_workbench.py`
builds a 60-row bundle (suggestion, rebuild flag, excerpt, up to 4 facade
photos) from the queue, `taskb_review.html` shows one building per screen
(keys 1-6 pick the era, `s` saves + advances), and
`scripts/apply-taskb-session.py` merges the exported session into the queue —
fingerprint-checked per row, never overwriting an existing label. Serve the
repo root (`python3 -m http.server`) so the root-relative preview paths resolve.
Each record also carries `depicts_building` (yes/partially/no, default yes) —
whether the photos show the labelled volume at all. The 37936 park case proved
ensemble rows can feed the head images with nothing to learn from; the flag
lets the reviewer mark that per row instead of burying it in prose. It is a
reviewer field, so regeneration carries it over like the label itself.

No browser? `scripts/review-taskb-cli.py` walks the same queue in the
terminal (same session schema, real fingerprints, so the same applier
merges it): `python3 scripts/review-taskb-cli.py --ids 23080,36603,23548,36728,34920,30528`.
Photos cannot display over SSH — each case prints its notice URL for a
second device, and `depicts_building` defaults to yes unless you say
otherwise.

### Batch 5 — 42 of 60 (2026-10-24)

Eighteen workbench records in one sitting — the reviewer's own eighteen rows,
not the six proposed (the queue is the menu, not the order). Notable: 18702
IRPA (1945-1975, 1959-1962 — overriding its 1850-1892 suggestion, which came
from the 1888 exhibition halls it replaced, another predecessor case), 20685
Sainte-Alice (1945-1975 — the 1905 provisional church noted and set aside),
36464 (1918-1940, the 1928 Art Deco rebuild chosen over the c.1860 house),
18722 Cinquantenaire arcade (1850-1892), and the first four post-1975 labels
(17272, 30551, 40062, 40116).

Backfill: thirteen of the eighteen blank `phase_years` were mechanical
readings of the quoted evidence (37300→1894-1909, 18702→1959-1962,
39655→1911, 18133→1900, 34920→1936, 37481→1929-1933, 39891→1923-1927,
23548→1974-1978, 36573→1955-1958, 17272→1983, 30551→1984-1988,
40062→1976-1979, 36464→1928), confirmed by Juan and written verbatim —
nothing else touched. Five need the reviewer's call: 39666 (phase stops at
1914 or runs 1913-1928 across bins?), 27463 (1923-1930 or 1937-1943?),
20685 (which post-war campaign?), 40116 (1987-1993?), 18722 (which
19th-century campaign does 1850-1892 name?). Now 37 of 42 labels carry a phase.

### Batch 6 — 56 of 60 (2026-10-24)

Fourteen more workbench records, including the first labels that override
the queue's own derived columns on judgement: 39723, the gap-year bridge
(proxy 1943, bin blank by rule), is labelled 1945-1975 — opened 23.12.1943,
millésime 1945 on the parapet, replacing the 1931 bridge bombed in 1940.
The gap rule stands for derived data; the label is a human call, and the two
now visibly disagree, which is correct. Also 37929 Sainte-Anne (post-1975,
1989-1990 — the 1839 predecessor demolished 1985), 37050 (1850-1892, the 1874
beer store transformation chosen over the 1928-1933 refit), and 36603
(post-1975, 1989-1990), which the CLI end-to-end test had briefly labelled
and restored.

Distribution across 56 is nearly flat: 1850-1892 x11, 1945-1975 x10,
1918-1940 x10, 1893-1914 x9, pre-1850 x8, post-1975 x8. Four rows left:
23080, 31548, 33035, 37072.

### Batch 7 — 59 of 60 (2026-10-24)

Seventeen pasted records, fourteen of them re-confirmations of batch 6 —
all fourteen eras match the queue exactly, a free consistency check on the
no-clobber path (all skipped, none altered). Three genuinely new: 23080
Maison des Femmes (post-1975, 2009-2010 — the 1906 Strauven building it
replaces named and set aside), 37072 D'Ieteren (1918-1940), 33035
(pre-1850 on a 1600-1650 INCONNU excerpt, the thinnest evidence in the
campaign). Only 31548 Ancienne Belgique is still open — the reviewer reports
the standing volume is modern, and the notice names a 1982-1983 De Bondt
campaign the excerpt never quotes: the likely call is post-1975 overriding
the pre-1850 suggestion.

Distribution across 59: 1850-1892 x11, 1918-1940 x11, 1945-1975 x10,
1893-1914 x9, pre-1850 x9, post-1975 x9.

Head check at n=59: 1279 train / 193 test images (48 train / 7 test
buildings), top-1 0.19 (chance, p=0.32), within-one-era 0.663 vs perm mean
0.425 — no shuffle in 100 reached it (p<0.01), the third replication. The
campaign's finding is stable across n=42/56/59: the probe cannot name the
era, but its errors are ordered far beyond chance.

Head check at n=56: 1254 train / 193 test images (45 train / 7 test
buildings), top-1 0.18 (chance, p=0.39), within-one-era 0.622 vs perm mean
0.427 — again no shuffle in 100 reached it (p<0.01). The pattern from n=42
replicates with a larger test set: no naming, but ordered errors far beyond
chance. The final n=60 check gets the whole queue behind it.

Auditing the suggestion against the 56 labels: agreement 38/56 (0.68) — a
useful prior, not truth. The rebuild flag fires on 30 rows and catches 12 of
the 18 overrides (precision 0.40, recall 0.67). The 6 unflagged overrides
reveal a second extractor defect class, recorded here and NOT fixed
mid-campaign: on 18133/39655/39891 the founding years (1900, 1911, 1923-27)
never became primary years, so the suggestion pointed at a refit; on
21072/40062 the corpus-range year 1939 ("Inventaire 1939-1999") was taken as
primary, pointing at a predecessor inventory. Incidental-as-primary and
founding-missed-as-primary — post-campaign extractor work, measured against
these labels when the time comes.

Distribution across 42: 1918-1940 x10, 1850-1892 x8, 1893-1914 x7,
1945-1975 x7, pre-1850 x6, post-1975 x4.

Head check at n=42: 1085 train / 155 test images (37 train / 5 test
buildings — 39891 joined the test set), top-1 0.20 (was 0.25), dummy 0.00
— an artifact, not a triumph: the test set holds only pre-1850, 1918-1940
and 1850-1892 images while the train majority is 1893-1914, so the majority
classifier scores literally zero. The honest baseline is the permutation
test (100 building-level shuffles): top-1 0.200 vs perm mean 0.183 (p=0.36,
chance), but within-one-era 0.690 vs perm mean 0.469 — none of the 100
shuffles reached it (p<0.01). First significant structure: the probe cannot
name the era, but its errors land adjacent far beyond chance. The learning
curve over 6/12/20/30/38 train buildings stays flat and noisy on top-1
(0.28/0.05/0.11/0.16/0.20). Signal is forming in the ordering, not the label.

### Earlier: 12 of 60 labelled

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

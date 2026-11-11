# Brussels painting study 001 — Looking, again

A first executable interpretation of **Democratiestraat 29**, from the owner's
*Buildings of Brussels* photograph. Geometry is agent-authored from visual
inspection, not extracted by CV. No model was trained. No architectural period
or fidelity result is asserted.

The question for this study: **can a deliberately simplified painting retain
what makes this ordinary corner building particular?** This artifact supplies
something to critique; it does not establish an answer or generalization.

## Review: choose, then carry on

The review is now an artwork-first, viewport-sized session rather than a long
form. Desktop shows both paintings; phones have a horizontally swipeable,
scroll-snapped card rail. **Swiping only browses; it never records a judgment.**
Two explicit taps complete a review: first which painting to keep, then which
better retains the building's character. There are no inferred/default fidelity
answers. Both/neither, similar/unsure, pass, optional notes, full-size inspection
and editing earlier choices remain available.

Keyboard: `1`/`2` choose A/B in either step; `T`/`N` mean both/neither in taste;
`S`/`U` mean similar/unsure in fidelity. Hold Space for the original photograph;
arrows browse without voting. Shortcuts are suppressed in note inputs and dialogs.
Phone buttons stay in reach, artwork fits short viewports, and reduced-motion
preferences are respected. The previous giant introductory block and export-first
workflow are gone. Details, program downloads and optional backups live behind `?`.

### Automatic saving

Completed choices go to the same private server automatically. The existing
per-event browser keys remain as an offline outbox; old browser-only choices are
backfilled against their original pool metadata without changing IDs or fields.
A second device on this personal server restores progress from server history.
The provided 22-choice original export can be imported idempotently:

```sh
node experiments/paint-brussels/pool/import-reviews.mjs path/to/preferences.jsonl
```

The real ledger is ignored by Git at `local/paint-brussels/reviews/<pool-ID>/`.
One private JSON receipt per event stores the unchanged vote, server receipt time
and canonical SHA-256. These are validated append-only events, not generated
labels or model scores. Edits create new events; repeated/conflicting answers are
retained for later interpretation, not silently adjudicated.

The server checks every source/program/render/revision binding, writes and fsyncs
an exclusive temporary file, publishes it with an exclusive hard link, then
fsyncs the directory before acknowledging. Retrying the same ID/content is safe;
reusing an ID with different content returns a conflict without overwriting.
Payloads are bounded to 16 KiB, each pool to 5,000 events / 16 MiB, and queued
storage operations to 32. Reads reject corrupt/non-regular/symlinked files rather
than resetting the ledger. Temporary files are not exposed as completed receipts.

The UI says **Saved to server only after a matching receipt**, queues interrupted
delivery with backoff, renews expired sessions, and retries exact event IDs after
lost responses. If browser backup is refused, it warns to keep the tab open until
server acknowledgment. Malformed or conflicting saved entries are preserved and
quarantined. Optional JSONL/recovery downloads remain escape hatches, not the
normal workflow. This is an outbox for an already-loaded page, not a service-worker
promise of cold-start offline access. Drafts before the second tap are not complete
judgments and have not yet been sent.

`GET /api/review/session` bootstraps the same-origin session; protected
`GET /api/review/events?pool=<ID>` restores receipts and `POST /api/review/events`
accepts a single bounded JSON vote. Host validation, exact Origin checks,
Fetch-Metadata checks, non-simple JSON/token headers, no CORS, no-store responses
and a per-process CSRF token fence cross-site pages and DNS-rebinding bootstrap.
**This token is CSRF protection, not an account login.** The service is single-owner
and relies on its loopback/private Tailscale network: other authorized network
peers are trusted. Do not publicly expose it or combine different reviewers as
one person. Two devices do not constitute independent human reviewers. No choices
are automatically forwarded to model APIs, and no training starts from a vote.

Backend tests exercise atomic/idempotent delivery, concurrent edits, quotas,
corrupt/symlinked files, origin/host/token/body rejection and restart persistence.
Sync tests cover lost acknowledgment, offline retry, old-pool backfill, restored
server history, refused browser writes and conflicts. Real-browser checks use an
**isolated temporary ledger**, never the human store; their saved events are
explicitly synthetic. A fresh independent read-only review found no important
issues in the new saving code.

## Current round: colour-led economy on eight more buildings

[Open round three](http://127.0.0.1:8765/taste.html?pool=pool-1794410963145-26abf5be).
Your first transfer review reached the backend as ten append-only events covering
eight comparisons. Using the latest answer per pair, the existing brief won four,
four were ties, and the extra-guided brief won none. In the town-hall pair, taste
favoured the existing brief while fidelity favoured the guided image: accuracy
and artistic preference should still remain separate. This small sample does not
prove a general effect, but gives no reason to intensify the same prescriptions.

Round three retains the unchanged luminous-print baseline and compares it against
a colour-led, more economical print direction: larger warm/cool relationships,
expressive material and selective structural accents, rather than more hatching
or brick counts everywhere. This is a new exploratory art-direction comparison,
not evidence that the owner has endorsed that alternative or that a policy learned.

The eight newly selected source posts cover Congres station, Lambin's house,
the Ropsy Chaudron market, Saint Job's church, Hotel Haerens, VUB student housing,
the former Banque Lambert headquarters, and Institut Anneessens-Funck. They were
selected for contrast before generation, excluding every previously painted post.
Two candidates per source give **16 paintings and eight counterbalanced pairs**;
each has one own-render revision opportunity, bounded to 32 painting-model calls.
All attempts and any runtime failures remain in the immutable pool history.
Fifteen final images are successful visual-feedback revisions. One school-facade
candidate exceeded the call budget on its initial attempt and reached a valid
image through text-based code repair instead; that difference is retained in
provenance, not hidden or scored as bad art. All 16 active images were replay-checked.

`pool/round-three-plan.json` pins photographs, conditions, the prior feedback
snapshot SHA, eight distinct human pairs and ten source events. The exact snapshot
is preserved privately under `local/paint-brussels/preferences/`; historical edits
are not counted as independent votes. Preparation accepts the selected plan:

```sh
python3 experiments/paint-brussels/prepare-transfer.py --plan experiments/paint-brussels/pool/round-three-plan.json
node experiments/paint-brussels/pool/generate.mjs --plan experiments/paint-brussels/pool/round-three-plan.json
```

These commands do not overwrite an earlier pool or train a model. Older round
links, judgments and backend receipts remain available; automatic saving is the
same workflow in all rounds. Source-post/image-byte disjointness and the unchanged
baseline are checked in the offline unit suite.

## Earlier transfer: preference guidance on eight new subjects

The owner's public Tumblr feed indexes **182 photo posts with 182 distinct full-image
URLs**. All four metadata pages are cached privately in
`local/paint-brussels/archive/`; this does not mean all 182 full photographs were
downloaded. Eight new source photographs were selected for architectural contrast
before any candidate generation: a glasshouse, balconies/ornament, a brick facade
with neighbours, a tower/corner town hall, a house with trees, a curved ceramic bay,
a glazed high-rise and a dense material screen. All eight exclude the four previously
painted source posts. They are new to this experiment, not verified absent from the
foundation model's pretraining, and not a random sample of the portfolio.

Open <http://127.0.0.1:8765/taste.html?pool=pool-1794404292208-9057af08>:
**16 paintings, eight same-source pairs**, with condition positions counterbalanced
four/four. Each source gets one fresh program using the existing luminous-print
brief and one using that same brief plus provisional guidance from the first
22 human judgments. Both retain the earlier colour-immersion guidance; the new arm
adds coherent linework, selective material/joinery detail, neighbouring geometry
and specific vegetation. The hypothesis is not that more marks are always better.
No winner/condition labels are shown in the review surface. Conditions remain
inspectable in the local provenance; this is not a formal blinded clinical trial.

Both arms use the same model, instrument, code limits and one own-render revision
opportunity. The run used **32 model requests**, with no automatic replacements or
hand-edited painting programs. Fourteen final images are successful visual-feedback
revisions. For the museum material-screen pair, both revised programs exceeded the
12,000-call budget: both successful initial images are retained instead. These are
execution failures, not bad-art labels. All successful attempts were replay-checked;
the two conditions use the same active revision stage within each source pair.

This is **prompt conditioning, not training**. One stochastic candidate per arm per
subject and eight manually selected subjects cannot establish a general effect.
The next evidence is the owner's blind relative judgments, including neither and
unsure; no beauty score, reward model or policy update is inferred automatically.
Original 22 human records remain privately preserved under
`local/paint-brussels/preferences/pool-1794398580935-6b370c8d/`, with their exact
SHA-256 in `pool/transfer-plan.json`. Synthetic browser-test exports are separate.

```sh
python3 experiments/paint-brussels/prepare-transfer.py
# Calls the configured subscription model: 16 candidates × 2 attempts = 32 requests.
node experiments/paint-brussels/pool/generate.mjs --plan experiments/paint-brussels/pool/transfer-plan.json
```

A fresh run gets a new pool ID; completed pools are not overwritten. The plan is
data-only and bounded to 18 candidates / 36 requests. `pool/task-plan.mjs` validates
source identity, pinned bytes, approved source hosts and task counts. Finite-domain
tests cover supported subject/brief cardinalities and counterbalancing. Pairing
version 2 balances positions by source; absent/version 1 preserves every original
A/B binding. Explicit `/pool/<ID>.json`, `/pool-data/<ID>/…` and `?pool=<ID>` links
keep earlier rounds available when the current pointer changes. Existing human
records were revalidated unchanged after this addition. An independent read-only
review found no important issues in the transfer changes.

## First model-authored painting pool

Open <http://127.0.0.1:8765/taste.html?pool=pool-1794398580935-6b370c8d> on the same preview server. The first
private pool contains **18 distinct programs and images: six per photograph**.
These are complete model-authored `paint(p)` programs, not seeds or palettes of
the earlier hand-authored facade schema. Their visual languages still have a
strong family resemblance; this is an exploratory pool, not established taste
coverage or a held-out evaluation.

The generator made 36 bounded subscription-model requests, one initial attempt
and one revision opportunity per candidate. **Five candidates actually received
their previous render as visual feedback.** Container startup failures prevented
that for the others, whose second responses received text/infrastructure feedback.
A separate recovery run rerendered unchanged programs without additional model
requests. Original failures, prompts, responses, programs and revisions remain
intact; infrastructure failures are not aesthetic judgments.

The recovered first pool is `pool-1794398580935-6b370c8d`, derived from
`pool-1794397205953-0d9f9576`. Its 36 program attempts were each replayed twice;
all 18 active candidates have distinct program and render fingerprints. Saved
artifacts live under ignored `local/paint-brussels/pools/`, not in Git.

### Compare and preserve your judgments

The first pool interleaves 45 distinct **same-photograph** pairs; the transfer
round has eight paired comparisons. Candidate names and
briefs are hidden. Taste (which would you keep?) and architectural fidelity are
separate explicit choices, with no default answers. You can choose neither,
abstain on fidelity, skip, leave a detail note, or stop at any point. Current
images must finish loading before a vote is enabled. Full-size inspection and
plain-text program downloads are available; candidate JavaScript is never
executed in the preview.

Each decision remains an immutable event under its own random ID, bound to the
exact pool, photograph, program, render and revision hashes. It is now delivered
automatically to the private server, with an append-only browser backup and retry
queue. Edits retain history. If both network and browser backup fail, keep the tab
open until the server acknowledges or use the optional backup download. Once the
saving indicator confirms delivery, no manual export is needed to change devices.
No choice automatically starts training.

### Execution boundary and checks

`pool/model-client.mjs` uses a configured vision-capable Pi subscription through
its installed SDK, in fresh contexts without tools. It refuses API-billed
connections. Only the painting brief, relevant photograph, and that candidate's
own feedback are sent; generation does not inherit an agent's filesystem tools.

Generated JavaScript runs only in rootless Podman: no network, read-only root
and host mounts, no proxy forwarding, bounded scratch tmpfs, dropped capabilities,
and no host credentials or reference pixels mounted. A task-owned delegated
systemd user scope avoids privileged transient-scope creation. Effective limits
are checked inside: 1.5 GiB memory, two CPUs and 256 processes. The driver enforces
a 35-second deadline and 64 KiB code budget. PNG output is bounded stdout data,
not a writable host directory; the host never opens renderer-created files,
symlinks or FIFOs. API-call, opaque-image and output-size checks are eligibility
gates, **not beauty scores**. Arbitrary JS can bypass API conventions; this is
not yet an adversarial RL reward environment or proof against dependency exploits.

Independent read-only review found writable-output disk exhaustion and FIFO-open
risks. Both were removed by switching to bounded stdout and read-only input
mounts. Renderer, browser and kernel dependencies remain part of the trust boundary.

```sh
npm test --prefix experiments/paint-brussels
npm run check:pool-sandbox --prefix experiments/paint-brussels
npm run check:pool-replay --prefix experiments/paint-brussels
npm run check:pool-ui --prefix experiments/paint-brussels
```

Unit tests run offline without model calls and are included in the project gate.
The sandbox check uses real containers and tests replay, active resource limits,
call/code budgets and deadline cleanup. Replay checks saved image/program/source
hashes against the current hardened transport using the saved paint API. Historical
container-runner snapshots remain preserved; transport changes do not silently
change the painting instrument. Browser checks cover actual images, separate
judgments, keyboard/touch interaction, automatic receipts, new-device resume,
concurrent edits, offline reload/retry, slow images, corrupt storage, quota refusal,
zoom and short-phone layout. Browser-generated test events are explicitly
synthetic and **must not be treated as human preference data**.

This runtime currently depends on Linux cgroup v2, a working systemd user manager,
Podman, the locally cached renderer image pinned in `pool/render-program.mjs`,
Playwright dependencies and cached high-resolution references pinned by
`pool/plan.json`. It is a working local prototype, not a portable image-builder
or training service. Serving the existing pool needs no model credentials.

The model-calling entry point is `node experiments/paint-brussels/pool/generate.mjs`.
For the default first-pool plan, `--limit 1` makes a two-request warm-up; `--resume <pool-ID> --limit 18` continues
completed-candidate checkpoints, bounded to 36 total requests. For another plan,
pass the same `--plan` when resuming; its candidate count and two-attempt budget
are derived from that validated plan. Completed pools
are immutable. Mid-candidate crash recovery is not automatic: inspect retained
records rather than blindly resume. `pool/recover-renders.mjs <completed-pool-ID>`
creates a separate derived pool from unchanged programs, with no model calls.
None of these commands trains a policy or assigns an automatic quality score.

## Open the original studio

From the repository root:

```sh
python3 experiments/paint-brussels/prepare.py
node experiments/paint-brussels/serve.mjs
```

Open <http://127.0.0.1:8765/>. No npm install is needed to view the study.
`PORT` changes the port; `HOST` changes the bind address (loopback by default).
The server exposes only allowlisted study/pool assets and the bounded review API,
not the rest of the repository. Binding to another interface makes photographs,
paintings and this personal review service reachable there; keep it private.

Compare photograph and painting, reveal the three passes, change palette or
seed, save the PNG, or download the executable scene module. A URL records
palette, pass and seed. Named marks mean one polygon wash or drawn line, not
individual bristle contacts. The JavaScript module still needs the companion
renderer; it is not a standalone painting file.

## Four visual directions

Open <http://127.0.0.1:8765/directions.html> for a contact sheet of the **same
building geometry** rendered four ways:

1. **The graphic city** — flat color planes, sharp silhouettes, no texture.
2. **Built in paint** — opaque directional marks and broken color.
3. **Measured light** — architectural linework, hatching, selective color.
4. **City in fragments** — an invented print/collage treatment with cut edges,
   missing ink, halftone and registration shifts.

These use authored Canvas 2D mark-making, not the p5.brush watercolor engine,
physical paint simulation, or an image model. Both palette and rendering change:
this is an art-direction comparison, not a controlled medium-only experiment.
Click an image to inspect it beside the original; save individual PNGs or the
whole contact sheet. Seed changes affect textured treatments; the flat graphic
version deliberately has no random variation. The original watercolor page and
its outputs remain available.

## Fifth study — An architectural print (03 + 04 → 05)

The gallery features a hybrid of **Measured light** and **City in fragments**.
After feedback that the first hybrid lacked the color immersion of 1 and 4,
the main study now uses a saturated ochre sky, vermilion brick, cool blue-green
shadow and lit cream bands. Precise lines remain over the printed color planes.
Texture and registration shifts apply to color, not to architectural geometry.
This is an authored recipe, not a blend of finished images or a learned style.

The first, quieter hybrid remains under **The quieter version — kept for
comparison**. It is rendered from its original palette and ink allocations with
the active seed; at seed 29 it reproduces the previous PNG byte-for-byte in the
tested browser. Its sky is still unprinted. In code, use
`renderTreatment(canvas, 'hybrid', {seed: 29, colour: 'restrained'})`; the default
`colour: 'full'` renders the richer revision. Both versions have PNG downloads.

Open <http://127.0.0.1:8765/directions.html#hybrid-feature>. The original four stay
below it, with their algorithms unchanged. Download the hybrid separately, or
save the new **3 / 5 / 4 comparison**; the original four-panel contact sheet remains
available as a separate export.

## First transfer batch — one painter, three new subjects

Open <http://127.0.0.1:8765/batch.html>. The industrial Ackermans frontage,
Louis Mettewielaan apartment building and Veeweide projecting bays all use the
same saturated hybrid instrument. Each photograph has a JSON interpretation
rather than its own drawing program: 17–19 elements compile to 53–63 marks.
No per-building branch or palette was added to the painter.

```sh
python3 experiments/paint-brussels/prepare-batch.py
npm run validate:batch --prefix experiments/paint-brussels
npm run render:batch --prefix experiments/paint-brussels
```

`batch-catalog.json` pins the three source URLs, SHA-256 values and filenames.
Photographs and batch renders remain in `local/paint-brussels/batch/`, ignored by
Git. `prepare-batch.py` preserves an existing reference whose bytes differ.
The preview serves only catalog-approved scene/photo paths; only the batch page
permits same-origin JSON reads through CSP. No external requests run in the page.

`scenes/*.json` are **agent-authored from visual inspection**, not outputs of an
unattended extractor. The pilot is deliberately small and selected for contrast;
it is not a held-out quality evaluation. The visible trees, curved bays and arches
expose limitations: foliage is schematic, curves are flattened, and some openings
are simplified. Per-scene omission notes are displayed beside each painting.
Foreground scene masses mask earlier architectural lines, including overlapping
silhouettes; they do not reconstruct hidden architecture.

### The next image-to-scene handoff

`scene-request.txt` specifies a constrained model task: polygons, facade grids
and lines in 500×500 source coordinates, semantic paint roles, explicit omissions,
no scripts or renderer changes. `scene-format.mjs` validates types, bounds, simple
polygons, convex facade quads, ordered window intervals and resource limits:
32,768 UTF-8 bytes, 80 elements and 1,200 compiled marks. Scene IDs must match an
approved catalog source before candidates can be used by the batch page/CLI.

A model can write a **new candidate file** and receive deterministic feedback:

```sh
node experiments/paint-brussels/batch-cli.mjs validate /path/to/candidate.json
```

This command is read-only. Invalid geometry is rejected before painting. The
instrument accepts compiled scenes only in the full-color hybrid treatment.
Catalogs and contact sheets support 1–24 pilot subjects without clipping exports;
this is not yet a city-scale scheduler. The exported collection contains paintings,
not the original photographs.

**Status:** this constrained image-to-scene handoff remains unconnected. The
new code-painting pilot above deliberately takes a different route: complete
model-authored programs rather than schema edits. No model API calls, paid
compute, uploads or training were launched for this original hand-authored batch.
Its separate independent review has not been run.

## Make a decision, not a benchmark score

Look for the turning corner, cream bands, window rhythm and central pilaster.
Where does simplification help? Where does it erase character? Is the invented
palette interesting, or just decorative? Compare the last pass with the middle
one: extra detail is not automatically an improvement.

The same geometry drives the watercolor palettes, the four starting points and
the hybrid.
That explores visual languages, not whether a learned painter can interpret a
second building. First identify treatments worth pursuing; then try different
buildings and preserve rejected outputs as well as favorites before considering
preference training or RL.

## Files and verification

- `scene.mjs`: source provenance, palettes, perspective helpers, named decisions.
- `studio.mjs`: local p5.brush painting passes and PNG capture.
- `directions.html`, `directions.css`, `hybrid.css`, `directions.mjs`: featured
  hybrid, original four-up comparison, full-size inspection, reference, seed
  controls and separate original/hybrid contact-sheet exports.
- `treatments.mjs`: five Canvas 2D mark-making systems over the same scene.
  `hybridPlate` explicitly allocates printed color without changing line geometry.
- `treatments.test.mjs`: palette coverage, seed validation and deterministic randomness.
- `directions-render.mjs`: actual browser pixels, replay after changing seeds,
  PNG exports, both contact sheets, saturated sky in the richer study, retained
  restrained rendering and its unprinted sky, dialog controls and mobile fitting.
- `serve.mjs`: allowlisted preview server; no rendering service or arbitrary-code API.
- `prepare.py`, `prepare-batch.py`: byte-verified reference acquisition into ignored `local/`.
- `batch.html`, `batch.css`, `batch.mjs`: source/painting collection and export.
- `batch-catalog.json`, `scenes/*.json`: approved sources and data-only interpretations.
- `scene-format.mjs`, `batch-cli.mjs`: bounded validation, compilation and candidate checks.
- `scene-format.test.mjs`: malformed-input tests, 100 generated facade-grid cases,
  opening-count/bounds/non-mutation checks and all supported export layouts.
- `batch-render.mjs`: browser evidence, pinned references, replay, exports, mobile,
  missing-image fallback, invalid-scene refusal and foreground-occlusion tests.
- `sheet-layout.mjs`, `test_prepare.py`, `scene-request.txt`: export layout,
  offline cache-safety tests and the next model handoff.
- `vendor/`: unmodified MIT-licensed p5.brush 3.0.0 standalone renderer,
  with upstream commit, SHA-256 and license. No CDN requests at runtime.
- `scene.test.mjs`: geometry, options, pass ordering, vendor integrity and server tests.
- `render.mjs`: real Chromium rendering, same-seed repaint equality, palette/pass
  controls, reference loading, PNG export and mobile overflow checks.

```sh
npm ci --prefix experiments/paint-brussels --ignore-scripts
npm test --prefix experiments/paint-brussels
# Once, if Chromium is not already installed:
(cd experiments/paint-brussels && npx playwright install chromium)
npm run render --prefix experiments/paint-brussels
```

`CHROMIUM_PATH` can select an existing Chromium binary. Render evidence goes to
`local/paint-brussels/`: `painting.png`, `masses.png`, `rhythm.png`, `dusk.png`,
`replay.png`, desktop/mobile studio screenshots, and `render-checks.json`.
The direction renders live separately under `local/paint-brussels/directions/`:
`graphic.png`, `opaque.png`, `drawing.png`, `print.png`, `hybrid.png`,
`hybrid-restrained.png`,
`contact-sheet.png` (the original four), `hybrid-comparison.png` (3 / 5 / 4),
desktop/mobile screenshots and `render-checks.json`. To check only the new gallery,
run `npm run render:directions --prefix experiments/paint-brussels`.

Seed equality is checked within one browser/renderer environment; cross-GPU or
cross-version pixel equality is not promised. The render check opens and closes
its own temporary loopback server and browser. The baseline uses software WebGL;
the direction and batch galleries need only Canvas 2D. Batch evidence lives in
`local/paint-brussels/batch/renders/`: one PNG per scene, `contact-sheet.png`,
desktop/mobile screenshots and `render-checks.json`.

## Local Qwen + deterministic structure/operator branch

This is a **controlled colour/material search**, not yet open-ended painting-program
invention or six convincing physical media. It keeps the free-program pilot intact.
The operator library supplies six procedural material approximations; local Qwen
proposes their bounded RGB matrices, offsets, ink palettes, contour and texture
settings as JSON. A trusted compiler owns geometry and mark-making. Generated
operator JSON is never executed as host-side code.

```text
Existing model-authored interpretation → capture rich ordered paths once → cache
Source photograph → deterministic 16-colour median-cut palette → local Qwen context
Local Qwen → six declarative operators → three fixed control settings each
Cached structure × operator × controls → isolated deterministic renderer
Three photograph shortlists → consider a model comparison only after human choice
```

`pool/structure-plan.json` freezes three original baseline programs selected before
operator generation: Mettewie, the former Solvay HQ, and Congres station. Captures
have 2,015 / 1,478 / 3,174 instrument calls, including non-geometric state/random
calls. They retain curves, individual openings, clipping and layer order; they are
**cached model interpretations, not verified CV geometry or semantic building
models**. Exact identity replay reproduces all three original PNGs. This prevents
new coordinate hallucinations between operator variants, not mistakes in the
original interpretation. Fixed paths also do not guarantee perceptual legibility:
colour compression can hide architectural detail.

The corrected sweep is `pool-1794416963314-842d8080` (`source-alpha-preserved-v1`):
54 parameter attempts, **51 usable images**, three blank-output failures (the most
aggressive silkscreen setting), no exact duplicate variants. All 51 usable images
matched a second render and the separate final replay. Six accepted operators took
eight local generation requests, including two overlong-description repairs. Warm
requests took 3.08–5.22 seconds end-to-end; server-reported decoding was about
86–106 tokens/second on these compact outputs, not a benchmark of long programs.
A separate connectivity smoke test and read-only code review are not included in
those eight operator requests. No new photograph/geometry calls went to a remote
model. No training or automatic forwarding of human judgments occurred.

An earlier, inactive sweep (`pool-1794414739602-54d11baf`) is retained unchanged.
An audit found source RGBA alpha was being dropped during colour conversion; the
corrected compiler preserves transparent fills and translucent source ink, with a
regression test. Do not merge the two sweeps as independent human comparisons.
A local read-only model review was attempted but was truncated and produced clear
false positives; it is limited evidence, not an independent approval. Invariant,
pixel-replay, sandbox and real-browser checks are the primary verification.

### Run and review

These commands require the private source pools and the existing pinned renderer
container/dependencies. They do not download models or install executable packages.
The local endpoint is `http://127.0.0.1:8000/v1/chat/completions`, using
`Qwen3.6-35B-A3B-MTP`. Its availability was verified by actual inference.

```sh
npm run freeze:structure --prefix experiments/paint-brussels
npm run generate:operators --prefix experiments/paint-brussels
npm run render:structure --prefix experiments/paint-brussels
# Use the pool ID printed by the render command:
npm run check:structure-ui --prefix experiments/paint-brussels -- <pool-ID>
npm run check:pool-replay --prefix experiments/paint-brussels -- <pool-ID>
```

The default private cache is `local/paint-brussels/structure-search/`. Existing
captures and accepted operators are verified/reused, not overwritten. For a new
source plan use a **fresh** `PAINT_STRUCTURE_CACHE` consistently for all three
preparation/generation/render commands, and pass the plan path to
`pool/freeze-structure.mjs`. Generation is sequential, bounded to twelve local
requests and three attempts per family. Reservations retain interrupted requests
rather than silently spending them again. The sweep creates a new immutable pool;
it deliberately does **not** activate `pools/current.json` before UI verification.
Raw local responses, failed attempts, operators, controls and compiled programs
remain available for audit. Source scene JSON and program downloads are byte-pinned;
replay supplies the exact scene dependency, not merely the painter entry point.

`explore.html?pool=<pool-ID>` presents six approaches per photograph, with variant
arrows/touch swipes, full-size inspection, up to two explicit keepers, neither/pass,
notes, and automatic server receipt. That is three source shortlists rather than
hundreds of forced pairs. Changing a selected card's variation clears that pick;
it never silently votes for the new image. Keyboard 1–6 selects an already viewed
approach; an unseen approach first scrolls into view without selecting it.

Shortlists use separate **v2** events: all available exact candidate references,
explicit selections, decision and cumulative exposure for that source. Exposure
means a decoded variant was at least half-visible in the gallery viewport or was
opened in the inspector; it is not gaze tracking. Below-fold decoding alone does
not count. Saved exposure is inherited when editing, while every changed judgment
is appended. Unviewed alternatives must not be treated as rejected. Neither/pass
never invent architectural-fidelity labels. Original v1 taste/fidelity event bytes,
keys and receipts remain unchanged. The same private trusted-network, single-owner
backend/outbox handles retries and cross-device restoration; this is not public
multi-user authentication.

`structure.test.mjs` checks all six families across five bounded control settings,
non-mutation and coordinate/order invariants, alpha preservation, malformed input,
legacy canonical bytes, exact shortlist binding and durable offline recovery.
`pool/explore-browser.mjs` uses an **isolated temporary ledger**, not owner data,
and covers desktop/short-phone layout, actual touch swipes, below-fold exposure,
explicit voting, cross-device/concurrent edits, offline reload, quota/corruption,
and slow-image gating. Its exported events under
`local/paint-brussels/structure-search/browser-checks/` are synthetic, never training
feedback. The normal project gate is `bash scripts/validate-prototypes.sh`.

## Persistent artist personas and proposed style evolution

The owner described the operator batch as not great, and reported that his wife,
who paints, found it nice but lacking **painting character**. That is not treated
as a request for more grain. Three fictional artist voices now have persistent
notebooks: `colourist`, `material-painter`, and `architectural-observer`.

Each separates its stable voice from versioned working rules, one stated
experiment, evidence, reusable program code, failed attempts and explicit style
decisions. This is context/file memory, **not trained weights or real people**.
A proposed style is not an adopted style. New hypotheses append versions and
preserve their parent fingerprint; they cannot silently change the artist's
charter. Successful procedures can be reused instead of reinvented each prompt.
Failed procedures and their per-source errors are remembered too. Writes are
non-overwriting and serialized per artist. A `retain` decision additionally
requires explicit owner approval; shortlist selections alone never promote it.

The first persona trial used three structural inputs and two seeds per voice,
with at most two local program requests per persona (six total). All first
programs failed interface checks. Revised programs produced 16 replayable images
from 18 intended cases; the material painter exceeded the drawing-call budget on
both Congres seeds. Two procedures worked across all three sources. The inactive
pool `pool-1794420952760-e677c138` retains their 12 new images plus six unchanged
earlier keepers; the third persona's partial results/failures remain in its
notebook and private run cache. An earlier, abandoned two-program trial is also
retained and is not counted as persona evolution.

**Artistic success is not claimed.** Visual inspection still found the outputs
too illustrative and insufficiently distinct. The active review pointer was NOT
switched to this trial. Persona names and storage alone did not supply the missing
painting character. At that point concrete visual references were suggested. The owner instead
explicitly asked for organic development without supplying references; the
subsequent photographic studio below follows that direction. No persona style
has been retained, no owner feedback on this trial was fabricated, and no training
or automatic background evolution was started.

The model now receives one generic instrument: normal drawing operations plus
`p.entries`, `p.state`, `p.shape`, `p.clipped`, and `p.rgba`. This removes ambiguous
legacy CSS/RGBA arrays and manual SVG parsing. Its generated code is syntax-parsed
without running it on the host, then executed/replayed only in the existing
isolated renderer. Inputs are shared cached interpretations, not guaranteed
unchanged output geometry. Medium/role wording remains a hypothesis, not proof.

```sh
# Initial persona proposals + explicit keeper snapshot (does not activate a pool):
node experiments/paint-brussels/pool/program-search.mjs init personas
node experiments/paint-brussels/pool/program-search.mjs preview 0
# Only when a bounded repair/critique is needed and saved feedback exists:
node experiments/paint-brussels/pool/program-search.mjs preview 1
node experiments/paint-brussels/pool/program-search.mjs seal

# Inspect a notebook, including failures:
node experiments/paint-brussels/pool/persona-style.mjs show colourist
# Propose a specific change after actual owner feedback (not automatic adoption):
node experiments/paint-brussels/pool/persona-style.mjs propose colourist \
  --owner-comment 'Explicit owner feedback goes here' \
  --hypothesis 'One visual experiment to test' --rule 'A revised working rule'
# --pool <reviewed-persona-pool-ID> instead uses byte-verified real receipts,
# latest distinct sources, actual exposure, and the exact persona/style proposal.
# Old references and unviewed alternatives are not rejection evidence.
```

`persona-style.mjs decide <persona> --decision retain --owner-approved ...` is
reserved for an actual explicit owner instruction; do not infer that authorization
from local files, a model's claims, or a shortlist. Owner-comment input is an
explicit local operator assertion, not service-verified feedback. Raw receipts
remain private. Distilled, explicitly requested feedback may inform local persona
proposals; no cloud forwarding is added. Notebooks live under ignored
`local/paint-brussels/personas/`; run evidence under `program-search/`. Stage labels
distinguish code repair from a new artistic style version. The lifecycle tests use
synthetic data in temporary directories, never the owner ledger.

## Organic development without reference homework

The owner explicitly chose **“you can just develop them organically.”** Personas
now work through observation, painting, actual visual self-critique and a specific
next experiment, rather than requiring outside paintings or treating every change
as an owner-approved favourite.

The major methodological change is **fresh photographic interpretation**. The
existing subscription-backed vision painter (`openai-codex` / `gpt-6.1-sol` in this
run) sees the photo and a byte-pinned earlier working painting, writes an independent
program, then sees its actual render and revises. It is not restricted to repainting
the cached vector mark graph. Earlier images may depict another building; they
are explicitly marked as style memory, not geometry to copy. This changes both
model and representation from the local text-only coding path, so it is exploration,
**not a fair model benchmark**. Raw owner receipts/notes are not forwarded.

Two bounded rounds completed, six vision requests each (three voices × initial
painting + visual revision), on one familiar photograph. Working styles v1 and v2
are linked to the same stable artist charters. The second experiment used closer
composition, broader masses, less mechanically complete geometry and more selective
edges. All twelve initial/revised paintings rendered and replayed successfully.
The three voices still share considerable visual vocabulary and often read as
faceted illustration; these are developing studies, not proof of three mature
painters or physical pigment simulation.

- Round v1: `pool-1794422704890-3ac184b0`.
- Round v2: `pool-1794423105027-fecf5253`.
- Browseable history: `pool-1794423447220-17048279`, six images, three named cards,
  arrows/touch swipes between v1/v2, visible notebook hypotheses, optional keepers.
- A working-example checkpoint is selected by **assistant visual inspection**,
  explicitly `ownerApproved:false`. It never writes the owner's retained-style
  pointer. Older styles can be retained with an explicit `--style-version` decision.
- No infinite generation daemon was started. The twelve-request development burst
  has finished; later experiments must build on saved visual observations instead
  of resetting the persona's initial rules.

```sh
# Agent supplies its next observations/rules after looking at actual results:
node experiments/paint-brussels/pool/organic-personas.mjs init 0 <experiments.json>
# Use the private cache path printed by init:
node experiments/paint-brussels/pool/generate.mjs \
  --plan <cache>/plan.json --history <cache>/history.json \
  --brief experiments/paint-brussels/pool/persona-painting-brief.txt \
  --revision-goal experiments/paint-brussels/pool/persona-revision-goal.txt \
  --activate false
node experiments/paint-brussels/pool/organic-personas.mjs record <completed-pool-ID>
node experiments/paint-brussels/pool/organic-personas.mjs working <completed-pool-ID>
```

`generate.mjs` preserves legacy defaults, but the organic controller explicitly
uses `--activate false`: completion never implies an approved direction. Brief,
revision-goal and history fingerprints bind resume. The source/earlier-work image
bytes are checked; all successful programs replay in the same isolated renderer.
Photographic shortlist candidates use `free-program-v1` and do not falsely declare
a frozen-scene dependency. Their exact program/image/source bytes still bind v2
feedback. No phantom geometry download is exposed for a photo-only pool. New photo-persona outbox entries use `brussels-persona-photo-v2:` so already-open older clients ignore unsupported future pools; newer clients still restore legacy keys without changing their canonical event bytes.

`organic-gallery.mjs` copies immutable snapshots into the version-history viewer.
`organic-browser.mjs` verifies named voices, notebook hypotheses, both working
versions, browse/zoom without voting, explicit version selection, cross-device
restoration, append-only edits, offline reload/retry and actual phone touch swipes.
It also verifies no vote can automatically mutate persona memory or retain a style.
All browser writes go to an isolated temporary ledger; files under
`local/paint-brussels/organic-personas/browser-checks/` are synthetic, never owner
feedback or training data. The actual source pools, earlier failed trials and
owner judgments remain unchanged.

## Larger six-building persona sample

On the owner's request for a bigger sample, `persona-sample-plan.json` preselects
six additional subjects relative to the one-photo studio: Lambin's house, Congres
station, Saint Job's church, Hotel Haerens, Ropsy Chaudron market and VUB student
housing. Each gets all three personas: **18 final paintings**, with an initial
program and one visual revision per painting (maximum **36** existing-subscription
vision requests). These are not claimed globally unseen or statistically held out;
Congres appeared in earlier structural prototypes. This specifically tests the
current working-v2 voices on additional subjects.

`persona-sample.mjs` verifies source bytes, disjointness from the current studio,
unique posts/photos, persona proposal hashes and working-example pixels. It freezes
the same three style policies and image memories for every target. It does not
promote a style version or replace a working checkpoint. The model is explicitly
told to inherit painting decisions, not the earlier building's geometry, yellow
facade or literal palette. Raw owner feedback is snapshotted privately, not included
in model prompts. All code/render revisions and failures remain auditable.

```sh
node experiments/paint-brussels/pool/persona-sample.mjs
# Use the printed cache path:
node experiments/paint-brussels/pool/generate.mjs \
  --plan <cache>/plan.json --history <cache>/history.json \
  --brief <cache>/painting-brief.txt --revision-goal <cache>/revision-goal.txt \
  --activate false
node experiments/paint-brussels/pool/organic-personas.mjs record <completed-pool-ID>
node experiments/paint-brussels/pool/persona-sample-browser.mjs <completed-pool-ID>
```

The viewer now has **Next/Back browsing without voting**. Draft picks/notes survive
moving between subjects in that tab; they reach the backend only on explicit
confirmation, neither or pass. A swipe on a single-version card cannot silently
clear a pick. The fixed-v2 sample uses one image per artist/subject; the previous
v1/v2 studio remains unchanged and accessible through history.

`persona-sample.test.mjs` checks ordered/disjoint source selection, duplicate/missing
refusal and the 18-candidate/36-request ceiling. `persona-sample-browser.mjs` checks
all six subjects, three named artists per source, explicit source-bound saving,
new-device resume, offline reload/retry, append-only edits, completion, all six
short-phone layouts and no style-memory changes. Its ledger is TEMP-only and its
exports under `sample-browser-checks/` are synthetic, never human/training data.

## Source and rights

Photograph: [Buildings of Brussels — Democratiestraat 29](https://www.tumblr.com/buildingsofbrussels/162278233614/democratiestraat-29-veeweide-aurora-district).
The user identifies this as their photographic project; no public reuse license
was verified. Reference bytes and generated images remain in ignored `local/`.
Revisit source and derivative redistribution rights before publication. This
study does not publicly publish the corpus. The model-authored pilot sends
reference photographs and feedback renders to the configured vision provider;
browser preference choices are automatically delivered to this private server,
not directly to model APIs. The repository has no blanket
license for new code or artworks; the vendor's MIT license applies to its files.

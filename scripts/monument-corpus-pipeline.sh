#!/usr/bin/env bash
# Chain the inventory corpus stages into one unattended run.
#
# The text sweep (labels + descriptions) and the picture pass must not run at the
# same time: robots.txt sets `Crawl-delay: 2`, that delay is per crawler, and two
# concurrent crawlers would present the publisher with 1 request/s instead of the
# 0.5 they asked for. So this script waits for the sweep to finish, then fetches
# the pictures, then derives the small browsing copies locally rather than
# spending a second 21-hour crawl on the publisher's own thumbnails.
#
# Every stage is resumable, so re-running after an interruption continues instead
# of starting over. Pictures stay under the gitignored local/ tree: the
# inventory's permission for them is conditional and non-commercial, and the
# per-building manifests carry the obligations that permission requires.
#
# Usage:  scripts/monument-corpus-pipeline.sh
# Monitor: tail -f local/pipeline.log
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

OUT=${MONUMENT_OUT:-local/scraped}
IMAGES=${MONUMENT_IMAGES:-local/monument-inbox}
PLACES_OUT=${MONUMENT_PLACES_OUT:-local/scraped-places}
SWEEP_LOG=${MONUMENT_SWEEP_LOG:-local/sweep.log}
RIGHTS=${MONUMENT_RIGHTS_BASIS:-conditional-noncommercial}
LANG_CODE=${MONUMENT_LANG:-fr}
POLL=${MONUMENT_POLL_SECONDS:-60}
MAX_WAIT=${MONUMENT_MAX_WAIT_SECONDS:-0}   # 0 waits as long as the sweep needs
LONG_EDGE=${MONUMENT_PREVIEW_LONG_EDGE:-500}
EXPECTED_RECORDS=${MONUMENT_EXPECTED_RECORDS:-26419}

SCRAPER=prototypes/three-ages/scrape_monument.py
SUMMARY=prototypes/three-ages/summarise_corpus.py
DERIVE=prototypes/three-ages/derive_previews.py
PLACES=prototypes/three-ages/summarise_places.py
# Matches the running sweep without matching this script or its own picture pass.
# Overridable like every other setting here: a different python path, a wrapper, or a
# test that must not collide with a real run.
SWEEP_PATTERN=${MONUMENT_SWEEP_PATTERN:-'^python3 .*scrape_monument\.py --from-index'}
IMAGES_PATTERN=${MONUMENT_IMAGES_PATTERN:-'scrape_monument\.py --images-only'}

log() { printf '%s [PIPELINE] %s\n' "$(date -Is)" "$*"; }

# Match a running crawler by process *kind*, not just by command line. A plain
# `pgrep -f` also matches the shell that invokes it whenever that shell's own
# command line contains the pattern text — which happened, and because this script
# refuses to start while a picture pass runs, the false positive stopped the whole
# run instead of merely delaying it. Only a python3 process counts as the crawler.
running_crawler() {
    local pattern=$1 pid
    for pid in $(pgrep -f "$pattern" 2>/dev/null); do
        if [[ "$(ps -o comm= -p "$pid" 2>/dev/null)" == python3 ]]; then
            return 0
        fi
    done
    return 1
}

record_count() {
    local count
    count=$(find "$OUT" -maxdepth 1 -name "*.$LANG_CODE.json" \
        ! -name "_*" ! -name "rubrics.*" 2>/dev/null | wc -l)
    printf '%s' "$count"
}

if running_crawler "$IMAGES_PATTERN"; then
    log "refusing to start: a picture pass is already running"
    exit 2
fi

log "pipelines started; text sweep log: $SWEEP_LOG"
log "corpus: $(record_count) of ~$EXPECTED_RECORDS record(s) stored under $OUT"

# --------------------------------------------------------------------------- #
# Stage 0: wait for the text sweep, and say which way it ended
# --------------------------------------------------------------------------- #
if running_crawler "$SWEEP_PATTERN"; then
    log "waiting for the text sweep to finish (polling every ${POLL}s)"
    waited=0
    ticks=0
    while running_crawler "$SWEEP_PATTERN"; do
        if (( MAX_WAIT > 0 && waited >= MAX_WAIT )); then
            log "text sweep still running after ${waited}s (limit ${MAX_WAIT}s); not starting pictures"
            exit 1
        fi
        sleep "$POLL"
        waited=$((waited + POLL))
        ticks=$((ticks + 1))
        if (( ticks % 10 == 0 )); then
            log "still waiting: ${waited}s elapsed, $(record_count) record(s) stored"
        fi
    done
    log "text sweep finished"
else
    log "no text sweep running; starting the picture pass"
fi

# A sweep that was killed, or that died on an outage, leaves no [FINAL] line. The
# picture pass would happily run on a partial corpus, so say so rather than let a
# silent gap become a silently incomplete dataset.
if [[ -f "$SWEEP_LOG" ]] && ! grep -q '^\[FINAL\]' "$SWEEP_LOG"; then
    log "WARNING: $SWEEP_LOG has no [FINAL] line; the sweep may have been killed, not finished"
fi
log "corpus before pictures: $(record_count) record(s) of ~$EXPECTED_RECORDS"

# --------------------------------------------------------------------------- #
# Stage 0: repair the notices whose contributor dates were mis-parsed before the
# year-continuation fix in extract_contributors
#
# The site truncates some ranges (1875 then -19), and the 2-digit fragment used to
# be filed as a contributor role. Only the affected notices are re-fetched, so a
# repair costs a handful of requests instead of replaying a 15-hour sweep over
# data that is already correct. The suspect list and the integrity check share one
# definition (summarise_corpus.date_like_roles), so they cannot disagree.
# --------------------------------------------------------------------------- #
log "stage 0/7: checking for mis-parsed contributor dates"
SUSPECTS=()
mapfile -t SUSPECTS < <(python3 "$SUMMARY" --suspect-ids --lang "$LANG_CODE" 2>/dev/null || true)
if (( ${#SUSPECTS[@]} )); then
    log "re-fetching ${#SUSPECTS[@]} mis-parsed notice(s): ${SUSPECTS[*]}"
    for id in "${SUSPECTS[@]}"; do
        # Drop the stored record first: --fail-on-change would otherwise report the
        # extraction fix as upstream drift and refuse to overwrite it.
        rm -f "$OUT/$id.$LANG_CODE.json"
    done
    set +e
    python3 "$SCRAPER" "${SUSPECTS[@]}" --out "$OUT" --lang "$LANG_CODE" \
        --dedupe-rubrics --fail-on-change --quiet
    repair=$?
    set -e
    (( repair == 0 )) || log "WARNING: repair exited $repair"
else
    log "no notice needs re-fetching"
fi
# Declared here so the final summary can always report a repair outcome, including
# the common case where nothing needed repairing.
repair=${repair:-0}

# The coordinate correction is a pure function of the stored record and the cached
# index, so it belongs here rather than in a crawl: a re-scrape would produce the same
# fields, and deleting records to re-fetch them would swallow any upstream drift for
# exactly the records being rewritten. Idempotent — a second run finds nothing to do.
set +e
python3 "$SCRAPER" --amend-coordinates --out "$OUT" --lang "$LANG_CODE" --index-file \
    "${MONUMENT_INDEX_FILE:-local/monument-index/monuments.fr.json}" > "$OUT/../records-amendment.log" 2>&1
amendment=$?
set -e
if (( amendment != 0 )); then
    log "WARNING: coordinate amendment exited $amendment (see $OUT/../records-amendment.log)"
else
    log "coordinates: $(grep -E '^[0-9]+ record\(s\) corrected' "$OUT/../records-amendment.log" || echo 'no amendment report')"
fi

# --------------------------------------------------------------------------- #
# Stage 1: pictures (the originals; the source of truth)
# --------------------------------------------------------------------------- #
log "stage 1/7: fetching originals into $IMAGES"
# Record what this stage expects before it starts, so the log can be compared with
# what actually happened a day and a half later. Zero requests.
python3 "$SCRAPER" --images-only --dry-run --out "$OUT" --image-dir "$IMAGES" \
    --lang "$LANG_CODE" --rights-basis "$RIGHTS" --image-size full --quiet \
    || log "WARNING: could not record the picture plan"
set +e
python3 "$SCRAPER" --images-only --out "$OUT" --image-dir "$IMAGES" \
    --lang "$LANG_CODE" --rights-basis "$RIGHTS" --image-size full \
    --robots-cache "$OUT/robots.txt" --progress-every 200
pictures=$?
set -e
# Exit 3 is the pass's outage abort. Stop here rather than deriving previews from a
# picture set that is about to be resumed: that is wasted work, and it is exactly
# when someone restarts the pass, which would put two writers on the same manifests.
if (( pictures == 3 )); then
    log "picture pass aborted: the source stopped answering, so the remaining"
    log "pictures were not attempted. Previews and verification are skipped because"
    log "the picture set is incomplete; rerun this script to resume where it stopped."
    log "[FINAL] pipeline stopped: pictures $pictures (outage), previews skipped, verification skipped"
    exit 3
fi
if (( pictures != 0 )); then
    log "WARNING: picture pass exited $pictures (see $OUT/_image_failures.$LANG_CODE.json)"
else
    log "picture pass complete"
fi

# --------------------------------------------------------------------------- #
# Stage 2: browsing copies, derived locally so the source is not crawled twice
# --------------------------------------------------------------------------- #
log "stage 2/7: deriving ${LONG_EDGE}px browsing copies"
set +e
python3 "$DERIVE" --images-dir "$IMAGES" --long-edge "$LONG_EDGE" --progress-every 500
previews=$?
set -e
if (( previews != 0 )); then
    log "WARNING: preview derivation exited $previews"
fi

# --------------------------------------------------------------------------- #
# Stage 3: prove the result, because 32 GB of pictures cannot be checked by eye
# and a resume reporting "0 fetched" only proves the code trusted its own manifest
# --------------------------------------------------------------------------- #
log "stage 3/7: verifying the picture tree against the stored notices"
set +e
python3 "$SCRAPER" --verify-images --out "$OUT" --image-dir "$IMAGES" \
    --lang "$LANG_CODE" --image-size full
verify=$?
set -e
(( verify == 0 )) || log "WARNING: picture audit exited $verify; the tree is incomplete or has defects"

# --------------------------------------------------------------------------- #
# Stage 4: the place notices, a corpus of their own
#
# Streets, squares and avenues carry the introductions the building notices only
# reference. They live at the four-segment address URL the building parser refuses as
# a trap, so they are scraped in their own mode into their own directory, and
# enumerated from the building corpus — which already links every street its buildings
# sit on. There is no places index to read: /medias/places.fr.json and
# /medias/lieux.fr.json are real 404s.
#
# NOTE: this fetches the place *pages* only. Their gallery pictures are a separate
# crawl of comparable size, deliberately not started here without an agreed cost.
# --------------------------------------------------------------------------- #
log "stage 4/7: place notices into $PLACES_OUT"
set +e
python3 "$SCRAPER" --places --from-streets "$OUT" --places-out "$PLACES_OUT" \
    --lang "$LANG_CODE" --skip-existing --fail-on-change \
    --robots-cache "$OUT/robots.txt" --progress-every 200
places=$?
set -e
if (( places == 0 )); then
    log "place scrape complete"
else
    log "WARNING: place scrape exited $places (see $PLACES_OUT/_failures.$LANG_CODE.json)"
fi

# --------------------------------------------------------------------------- #
# Stage 5: prove the place corpus, the way stage 3 proves the picture tree
#
# Its shape is different from a building notice, so it has its own verifier: identity
# (place_id, filename and URL must agree), the prose must be free of the page's own
# navigation label, two pictures of one place must not collide as filenames, and a
# place cannot be both present and recorded as having no page.
# --------------------------------------------------------------------------- #
log "stage 5/7: verifying the place corpus"
set +e
python3 "$PLACES" "$PLACES_OUT" --lang "$LANG_CODE"
placecheck=$?
set -e
if (( placecheck == 0 )); then
    log "place corpus verified"
else
    log "WARNING: place verifier exited $placecheck; the corpus is missing or has problems"
fi

# --------------------------------------------------------------------------- #
# Stage 6: the record corpus itself
#
# The picture tree and the place corpus each have a verifier stage; without this one the
# primary deliverable's integrity would only be checked by hand. It reports coverage,
# prose, picture counts, the coordinate cross-check against the publisher's index and
# the caption-year span, and exits non-zero on any integrity problem.
# --------------------------------------------------------------------------- #
log "stage 6/7: verifying the building records"
set +e
python3 "$SUMMARY" "$OUT" --lang "$LANG_CODE"
records_check=$?
set -e
if (( records_check == 0 )); then
    log "building records verified"
else
    log "WARNING: record check exited $records_check; the corpus has integrity problems"
fi

log "[FINAL] pipeline done: repair $repair, amendment $amendment, picture pass $pictures, previews $previews, verification $verify, places $places, place check $placecheck, records $records_check"
if (( pictures != 0 || previews != 0 || verify != 0 || places != 0 || placecheck != 0 || records_check != 0 )); then
    log "some stage did not finish cleanly; every stage is resumable, so rerun this script"
    # The log states the verdict, but a supervisor reads the exit code, and until now
    # this script reported success whatever happened.
    exit 1
fi

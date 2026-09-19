#!/usr/bin/env bash
set -euo pipefail

# Wizard: submit an image-use request to the Brussels City Archives
# (Archives de la Ville de Bruxelles / Stadsarchief Brussel) for historical
# Grand Place photographs needed by the Three Ages pilot.
#
# Run:  bash scripts/archives-image-request.sh
# Writes captured values to docs/archives-request-state.env (KEY=VALUE lines).

TOTAL_STAGES=5
ENV_FILE="docs/archives-request-state.env"
CURRENT_STAGE=0

stage() {
  local title=$1
  if [[ -t 1 ]]; then
    clear
  fi
  CURRENT_STAGE=$((CURRENT_STAGE + 1))
  printf '\n[%d/%d] %s\n' "$CURRENT_STAGE" "$TOTAL_STAGES" "$title"
  printf '%s\n' '────────────────────────────────────────'
}

say() {
  printf '%s\n' "$*"
}

step() {
  printf '  • %s\n' "$*"
}

pause() {
  local prompt=${1:-Press Enter when ready}
  read -r -p "$prompt " _
}

confirm() {
  local prompt=${1:-Continue?}
  local answer
  read -r -p "$prompt [y/N] " answer
  [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]
}

open_url() {
  local url=$1
  if command -v wslview >/dev/null 2>&1; then
    wslview "$url"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
  elif command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 &
  elif command -v explorer.exe >/dev/null 2>&1; then
    explorer.exe "$url" >/dev/null 2>&1 &
  else
    say "Open this URL in your browser: $url"
  fi
}

ask() {
  local __result=$1 prompt=$2 default=${3:-} answer
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default] " answer
    answer=${answer:-$default}
  else
    read -r -p "$prompt " answer
  fi
  printf -v "$__result" '%s' "$answer"
}

ask_secret() {
  local __result=$1 prompt=$2 answer
  read -r -s -p "$prompt " answer
  printf '\n'
  printf -v "$__result" '%s' "$answer"
}

write_env() {
  local key=$1 value=$2 dir tmp
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
    printf 'Invalid environment variable name: %s\n' "$key" >&2
    return 1
  }
  dir=$(dirname "$ENV_FILE")
  mkdir -p "$dir"
  touch "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  tmp=$(mktemp "${ENV_FILE}.tmp.XXXXXX")
  WIZARD_ENV_VALUE=$value awk -v key="$key" '
    BEGIN { value = ENVIRON["WIZARD_ENV_VALUE"]; replaced = 0 }
    $0 ~ ("^" key "=") {
      if (!replaced) print key "=" value
      replaced = 1
      next
    }
    { print }
    END { if (!replaced) print key "=" value }
  ' "$ENV_FILE" >"$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$ENV_FILE"
}

set_secret() {
  local name=$1 value=$2
  command -v gh >/dev/null 2>&1 || {
    say "gh is not installed; skipped GitHub secret $name"
    return 0
  }
  printf '%s' "$value" | gh secret set "$name"
}

set_var() {
  local name=$1 value=$2
  command -v gh >/dev/null 2>&1 || {
    say "gh is not installed; skipped GitHub variable $name"
    return 0
  }
  printf '%s' "$value" | gh variable set "$name"
}

finish() {
  local status=$?
  if (( status == 0 )); then
    printf '\nWizard complete. %d/%d stages finished.\n' "$CURRENT_STAGE" "$TOTAL_STAGES"
  else
    printf '\nWizard stopped after stage %d/%d.\n' "$CURRENT_STAGE" "$TOTAL_STAGES" >&2
  fi
  exit "$status"
}
trap finish EXIT

# ── STAGES ──────────────────────────────────────────────────────────────────

stage "Scope the request"
say "The Three Ages pilot needs historical photographs of the Grand Place,"
say "ideally from the 1940s, for six buildings:"
say "  Grand-Place 6 (The Horn), 9 (The Swan), 21-22 (Joseph and Anne),"
say "  23 (The Angel), 24 (The Weighing Scales), 26-27 (The Pigeon)."
say "The Weighing Scales is also indexed by the heritage inventory as"
say "Maison de la Balance, Rue de la Colline 24 (inventory 30991)."
say ""
say "The images will be used for a non-commercial, source-documented pilot"
say "that compares facade and structural change across historical epochs."
step "We will first look up catalogue references, then email the archives,"
step "then record the reuse terms they offer (credit, fees, resolution)."
pause "Press Enter to start."

stage "Find catalogue references"
say "Open the Brussels City Archives search pages:"
open_url "https://archives.brussels.be/online-archives"
open_url "https://archives.brussels.be/how-search"
open_url "https://archives.brussels.be/search?search=Rue%20de%20la%20Colline%2024"
open_url "https://archives.brussels.be/search?search=Maison%20de%20la%20Balance"
say ""
say "Look for photographs of the Grand Place, preferably 1940s era."
say "Suggested search terms: 'Grand-Place', 'Grote Markt', 'Brussel 1940',"
say "'Brussel 1944', 'bevrijding' (liberation), 'Rue de la Colline 24',"
say "'Maison de la Balance' and 'De Weegschaal'."
say ""
say "If you find anything, note the catalogue/shelf references (e.g. an"
say "inventory number or collection name). It is fine to write 'none found'."
ask REQUEST_CATALOGUE_REFS "Catalogue references found (or 'none found'): "
write_env "REQUEST_CATALOGUE_REFS" "$REQUEST_CATALOGUE_REFS"

stage "Send the enquiry email"
say "Email the archives at:  archives@brucity.be"
say ""
say "Use this draft (fill the three placeholders):"
say ""
say "------------------------------------------------------------"
say "Subject: Request for reuse permission - historical Grand Place photographs"
say ""
say "Dear Brussels City Archives,"
say ""
say "I am preparing a non-commercial educational pilot (bachelor project) on"
say "the structural history of the Grand Place. I would like permission to"
say "reuse historical photographs of the square from the 1940s for six"
say "buildings: Grand-Place 6, 9, 21-22, 23, 24 and 26-27."
say ""
say "Catalogue references I found: [fill in, or 'I could not identify the"
say "right records - can you help locate suitable photographs?']"
say ""
say "Please let me know:"
say "  1. which images you can provide for this purpose;"
say "  2. the reuse terms (licence, required credit, any fees);"
say "  3. the maximum resolution available;"
say "  4. how the images should be cited."
say ""
say "Thank you,"
say "[your name]  [your e-mail]  [your institution/programme]"
say "------------------------------------------------------------"
say ""
step "Your name/e-mail are only used in the email; they are not stored."
ask REQUEST_CHANNEL "Submission channel (email / web form / other): " "email"
ask REQUEST_DATE "Date you send it (YYYY-MM-DD): "
write_env "REQUEST_CHANNEL" "$REQUEST_CHANNEL"
write_env "REQUEST_DATE" "$REQUEST_DATE"
pause "Press Enter after you have sent the enquiry."

stage "Record the archives reply"
say "The archives usually reply with their reuse contract form (credit,"
say "resolution, and possibly fees), or a request for more detail."
ask REQUEST_REFERENCE "Reference from their reply (or 'none yet'): " "none yet"
ask RESPONSE_TERMS "Terms offered (licence/credit/fees; or 'awaiting reply'): " "awaiting reply"
ask RESPONSE_EXPECTED_TIMELINE "Expected reply timeline (e.g. '2 weeks'): " "unknown"
write_env "REQUEST_REFERENCE" "$REQUEST_REFERENCE"
write_env "RESPONSE_TERMS" "$RESPONSE_TERMS"
write_env "RESPONSE_EXPECTED_TIMELINE" "$RESPONSE_EXPECTED_TIMELINE"

stage "Summary"
say "Captured request state:"
grep -E "^(REQUEST_|RESPONSE_)" "$ENV_FILE" 2>/dev/null | sed 's/^/  /' || true
say ""
say "Saved to: $ENV_FILE"
say ""
say "When the archives reply, tell the agent the outcome so it can update"
say "docs/three-ages-source-access.md and the pilot evidence notes."
pause "Press Enter to finish."
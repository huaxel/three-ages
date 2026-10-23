#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

command -v opam >/dev/null || {
  printf 'opam is required; see ocaml/README.md\n' >&2
  exit 2
}
command -v node >/dev/null || {
  printf 'Node.js is required; see ocaml/README.md\n' >&2
  exit 2
}
if ! (cd ocaml && node -e "require('deasync')" >/dev/null 2>&1); then
  printf 'Bonsai test dependencies are missing; run: npm ci --prefix ocaml\n' >&2
  exit 2
fi

if [ -d "$ROOT/_opam" ]; then
  eval "$(opam env --switch=.)"
else
  eval "$(opam env)"
fi
(cd ocaml && dune build --profile release main.bc.js draft_test.bc reviews_test.bc app_test.bc.js \
  && dune exec --profile release ./draft_test.bc \
  && dune exec --profile release ./reviews_test.bc \
  && node _build/default/app_test.bc.js \
  && node smoke_bonsai.js)
printf 'Bonsai validation passed\n'

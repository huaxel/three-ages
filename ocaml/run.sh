#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
eval "$(opam env --switch=. 2>/dev/null || opam env)"
(cd ocaml && dune build --profile release main.bc.js)
printf 'Three Ages Bonsai slice: http://127.0.0.1:%s/ocaml/index.html\n' "${PORT:-8000}"
python3 -m http.server "${PORT:-8000}" --bind 127.0.0.1

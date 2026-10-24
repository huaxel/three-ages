#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
PORT=${PORT:-}

command -v tailscale >/dev/null || {
  printf 'tailscale is required; install and authenticate it first\n' >&2
  exit 2
}
command -v python3 >/dev/null || {
  printf 'python3 is required\n' >&2
  exit 2
}

TAILSCALE_IP=${TAILSCALE_IP:-$(tailscale ip -4 | awk 'NF { print $1; exit }')}
if [[ ! $TAILSCALE_IP =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  printf 'could not determine a Tailscale IPv4 address; set TAILSCALE_IP explicitly\n' >&2
  exit 2
fi

if [[ -z $PORT ]]; then
  PORT=$(python3 - "$TAILSCALE_IP" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind((sys.argv[1], 0))
    print(sock.getsockname()[1])
PY
  )
fi

cd "$ROOT"
printf 'Serving Three Ages on Tailscale address %s:%s\n' "$TAILSCALE_IP" "$PORT"
printf 'Explorer:  http://%s:%s/prototypes/three-ages/\n' "$TAILSCALE_IP" "$PORT"
printf 'Workbench: http://%s:%s/prototypes/three-ages/review.html\n' "$TAILSCALE_IP" "$PORT"
printf 'Task-B labels: http://%s:%s/prototypes/three-ages/taskb_review.html\n' "$TAILSCALE_IP" "$PORT"
printf 'Stop with Ctrl-C. This binds only to the selected Tailscale interface.\n'
python3 -m http.server "$PORT" --bind "$TAILSCALE_IP"

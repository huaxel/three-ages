#!/usr/bin/env python3
"""Terminal reviewer for the task-B label queue (for SSH sessions: no browser needed).

Walks unlabelled rows one at a time, prints the review context as text, and
writes a taskb-session JSON with the same schema as the workbench export, so
scripts/apply-taskb-session.py merges it identically.

Usage: python3 scripts/review-taskb-cli.py [--ids 23080,36603,...] [--out taskb-session.json]
  --ids   review only these buildings (default: all unlabelled, queue order)
  --out   session file to write (default: taskb-session-<date>.json)

Photos cannot display in a terminal. Each case prints its preview paths and
the monument notice URL — open the URL on any device with a browser to see
the building. If you cannot see the photos, leave depicts at its default
(yes) and say so in the evidence; the flag can be corrected later.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_applier_spec = spec_from_file_location(
    "apply_taskb_session", ROOT / "scripts" / "apply-taskb-session.py")
_applier = module_from_spec(_applier_spec)
_applier_spec.loader.exec_module(_applier)
djb2 = _applier.djb2_utf16
QUEUE = ROOT / "local" / "training" / "taskb_queue.csv"
INBOX = ROOT / "local" / "monument-inbox"
ERAS = ["pre-1850", "1850-1892", "1893-1914", "1918-1940", "1945-1975", "post-1975"]
DEPICTS = {"y": "yes", "p": "partially", "n": "no"}


def prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{text}{suffix}: ").strip()
    except EOFError:
        print()
        raise SystemExit("input closed; session NOT saved")
    return answer or default


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", default=f"taskb-session-{date.today()}.json")
    args = ap.parse_args()

    with open(QUEUE, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    unl = [r for r in rows if not (r.get("construction_era") or "").strip()]
    if args.ids:
        wanted = set(args.ids.split(","))
        unl = [r for r in unl if r["building_id"] in wanted]
        missing = wanted - {r["building_id"] for r in unl}
        if missing:
            print(f"not unlabelled/in-queue: {sorted(missing)}")
    if not unl:
        print("nothing to review.")
        return

    reviewer = prompt("Reviewer name")
    if not reviewer:
        raise SystemExit("need a reviewer name; session NOT saved")
    records = []
    for i, r in enumerate(unl, 1):
        print(f"\n=== {i}/{len(unl)} · {r['building_id']} · {(r.get('identity_name') or '').strip()}")
        print(f"address: {r.get('address', '')} · styles: {r.get('styles', '')}")
        print(f"suggestion: {r.get('suggested_era', '')} "
              f"(proxy {r.get('proxy_years', '')} / primary {r.get('primary_years', '')})")
        if (r.get("rebuild_flag") or "").strip():
            print("!! REBUILD FLAG: the notice mentions reconstruction — "
                  "the earliest year may belong to a replaced building.")
        print(f"--- excerpt ---\n{(r.get('notice_excerpt') or '').strip()}")
        preview_dir = INBOX / r["building_id"] / "preview"
        previews = sorted(p.name for p in preview_dir.glob("*.jpg")) if preview_dir.exists() else []
        print(f"--- photos ({len(previews)} previews; open notice URL to view) ---")
        print(f"notice: {r.get('notice_url', '')}")
        for name in previews[:4]:
            print(f"  local/monument-inbox/{r['building_id']}/preview/{name}")

        print("eras: " + "  ".join(f"{n + 1}={e}" for n, e in enumerate(ERAS)))
        era = ""
        while era not in ("1", "2", "3", "4", "5", "6"):
            era = prompt("Era (1-6, or 'skip')")
            if era == "skip":
                break
        if era == "skip":
            continue
        phase = prompt("Phase years (e.g. 1894-1909)")
        depicts = prompt("Photos depict the building? (y/p/n)", "y").lower()
        depicts = DEPICTS.get(depicts, "yes")
        confidence = prompt("Confidence (high/medium/low)", "medium").lower()
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        evidence = prompt("Evidence (quoted sentence; empty keeps full excerpt)")
        records.append({
            "building_id": r["building_id"],
            "construction_era": ERAS[int(era) - 1],
            "phase_years": phase,
            "evidence": evidence or (r.get("notice_excerpt") or "").strip(),
            "reviewer": f"{reviewer} (cli, {date.today()})",
            "reviewed_at": str(date.today()),
            "confidence": confidence,
            "depicts_building": depicts,
            "fingerprint": djb2((r.get("notice_excerpt") or "") + "|" + (r.get("suggested_era") or "")),
        })
        print(f"saved {r['building_id']} -> {ERAS[int(era) - 1]} ({len(records)} this session)")

    out = Path(args.out)
    out.write_text(json.dumps({"schema": "taskb-session/1", "records": records},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out} ({len(records)} records). Apply with:")
    print(f"  python3 scripts/apply-taskb-session.py {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Derive small browsing copies from downloaded inventory pictures, locally.

The inventory publishes each gallery picture twice: the original under
``/medias/buildings/`` and a ~500px rendition under ``/medias/500/buildings/``
that the notice page itself displays. Fetching both would double an already
21-hour picture pass over ~39,000 files, so this script reproduces the small copy
from the original instead, using the Pillow dependency the repository already
carries for the structural crops.

That substitution is only honest if the two renditions agree, and they were
measured before it was made: the published thumbnail is a plain downscale to a
500px long edge (1085x1600 -> 339x500, aspect ratio 0.6781 against 0.6780), not a
crop and not a re-frame. The derived file therefore has the same framing but is
**not the publisher's asset** — different encoder, different bytes — so every
manifest records the derivation, the long edge, the encoder settings and the
SHA-256 of the original it came from. Nothing here may be described as the
source's own rendition.

These pictures remain inside the gitignored ``local/`` tree: the inventory's
permission for them is conditional and non-commercial.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as error:  # pragma: no cover - depends on local tooling
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from error

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGES = REPO_ROOT / "local" / "monument-inbox"
DEFAULT_LONG_EDGE = 500
DEFAULT_QUALITY = 82
DERIVATION_NOTE = (
    "Derived locally from the stored original, not fetched from the source. The "
    "inventory's own ~500px rendition is a plain downscale to the same long edge "
    "(verified: 1085x1600 -> 339x500), so the framing matches; the bytes do not."
)


def file_hash(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def preview_path(building_dir: Path, filename: str) -> Path:
    """Browsing copies live beside the originals, so a manifest never implies a size."""
    return building_dir / "preview" / filename


def load_manifest(building_dir: Path) -> dict[str, object] | None:
    path = building_dir / "manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def derive_one(
    source: Path, target: Path, long_edge: int, quality: int
) -> tuple[int, int, str]:
    """Downscale one picture to the long edge, atomically; return (w, h, format).

    The orientation tag is honoured, because a browsing copy has to look like the
    photograph rather than like its pixel grid: a source tagged to display rotated
    would otherwise yield a sideways thumbnail in the review workbench. Measured on
    the 252 real inventory files downloaded first, 17 carry an EXIF block and every
    one of those is already upright (Orientation 1, never 6 or 8), so this is
    insurance for an unmeasured 77,000 rather than a fix for something observed — and
    it is a size-preserving no-op for all of them, which is what makes it safe.

    The output keeps a PNG source's PNG, because the derived file inherits the
    source's name and **22 of the 77,175 references are named `.png`**: saving JPEG
    bytes into a `.png` would ship a name that contradicts its own content, which is
    the same mislabelling the downloader's signature check exists to prevent.
    Everything else becomes a JPEG browsing copy. Callers record the format, so no
    consumer has to infer it from an extension.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        upright = ImageOps.exif_transpose(image)
        output = "png" if (image.format or "").upper() == "PNG" else "jpeg"
        copy = upright.convert("RGB") if upright.mode != "RGB" else upright.copy()
    copy.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)
    temporary = target.with_suffix(target.suffix + ".part")
    try:
        if output == "png":
            copy.save(temporary, format="PNG", optimize=True)
        else:
            copy.save(temporary, format="JPEG", quality=quality, optimize=True)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return copy.size[0], copy.size[1], output


def recorded_derivations(manifest: dict[str, object] | None) -> dict[str, dict]:
    section = (manifest or {}).get("derived_previews") or {}
    entries = section.get("images") or [] if isinstance(section, dict) else []
    return {
        str(entry["filename"]): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("filename")
    }


def derive_building(
    building_dir: Path, long_edge: int, quality: int, force: bool = False
) -> tuple[list[dict], int]:
    """Derive previews for one building; return (entries, derived_count).

    A preview is current only when its recorded source hash still matches the
    original on disk, so a re-downloaded original is re-derived instead of being
    silently shadowed by a stale thumbnail.
    """
    manifest = load_manifest(building_dir)
    if manifest is None:
        return [], 0
    recorded = recorded_derivations(manifest)
    entries: list[dict] = []
    derived = 0
    for image in manifest.get("images") or []:
        if not isinstance(image, dict) or not image.get("filename"):
            continue
        filename = str(image["filename"])
        source = building_dir / filename
        if not source.exists():
            continue  # not downloaded: nothing to derive from, and not an error
        source_hash = file_hash(source)
        target = preview_path(building_dir, filename)
        previous = recorded.get(filename)
        current = (
            not force
            and target.exists()
            and previous is not None
            and previous.get("source_sha256") == source_hash
            and previous.get("long_edge") == long_edge
            and previous.get("quality") == quality
        )
        if not current:
            width, height, output_format = derive_one(source, target, long_edge, quality)
            derived += 1
        else:
            with Image.open(target) as existing:
                width, height = existing.size
                output_format = (existing.format or "jpeg").lower()
        entries.append(
            {
                "filename": filename,
                "path": str(target.relative_to(building_dir)),
                "format": output_format,
                "source_sha256": source_hash,
                "sha256": file_hash(target),
                "bytes": target.stat().st_size,
                "width": width,
                "height": height,
                "long_edge": long_edge,
                "quality": quality,
            }
        )
    return entries, derived


def update_manifest(building_dir: Path, entries: list[dict]) -> bool:
    """Record the derivation on the manifest; return True when it changed.

    The section is only rewritten when its content moved, so a no-op resume does
    not touch the file and a manifest cannot drift just from being re-checked. The
    write goes through a temporary file for the same reason the picture pass does
    it: a kill must leave either the old manifest or the new one, never half of one.
    """
    manifest = load_manifest(building_dir)
    if manifest is None:
        return False
    section = {
        "tool": "prototypes/three-ages/derive_previews.py",
        "derived": True,
        "note": DERIVATION_NOTE,
        "images": entries,
    }
    if manifest.get("derived_previews") == section:
        return False
    manifest["derived_previews"] = section
    path = building_dir / "manifest.json"
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Derive small browsing copies of downloaded inventory pictures"
    )
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES,
                        help=f"directory of per-building download folders (default: {DEFAULT_IMAGES})")
    parser.add_argument("--long-edge", type=int, default=DEFAULT_LONG_EDGE,
                        help=f"longest edge of the derived copy (default: {DEFAULT_LONG_EDGE})")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY,
                        help=f"JPEG quality of the derived copy (default: {DEFAULT_QUALITY})")
    parser.add_argument("--limit", type=int, default=None,
                        help="maximum number of buildings to examine")
    parser.add_argument("--progress-every", type=int, default=500,
                        help="log progress every N buildings to stderr (0 disables)")
    parser.add_argument("--force", action="store_true",
                        help="re-derive every preview even when it is already current")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the final summary line")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.long_edge < 1 or not 1 <= args.quality <= 95:
        print("--long-edge must be positive and --quality between 1 and 95", file=sys.stderr)
        return 2
    images_dir = args.images_dir
    if not images_dir.is_dir():
        print(f"no such directory: {images_dir}", file=sys.stderr)
        return 2

    directories = sorted(
        path for path in images_dir.iterdir()
        if path.is_dir() and (path / "manifest.json").exists()
    )
    if args.limit is not None:
        directories = directories[: args.limit]
    if not directories:
        print(f"no downloaded buildings under {images_dir}", file=sys.stderr)
        return 2

    started = time.monotonic()
    derived = skipped = examined = 0
    failures: list[dict[str, str]] = []
    for count, building_dir in enumerate(directories, start=1):
        try:
            entries, made = derive_building(building_dir, args.long_edge, args.quality, args.force)
        except (OSError, ValueError) as error:
            # One corrupt picture must not abandon the other twenty-five thousand.
            failures.append({"target": building_dir.name, "error": str(error)[:200]})
            print(f"error: {building_dir.name}: {error}", file=sys.stderr, flush=True)
            continue
        if entries:
            examined += 1
            update_manifest(building_dir, entries)
        derived += made
        skipped += len(entries) - made
        if args.progress_every and count % args.progress_every == 0:
            elapsed = max(time.monotonic() - started, 0.001)
            print(
                f"[{count}/{len(directories)}] {building_dir.name} · {derived} derived · "
                f"{skipped} current · {derived / elapsed:.1f}/s · {len(failures)} failed",
                file=sys.stderr,
                flush=True,
            )
    if not args.quiet:
        print(
            f"{derived} preview(s) derived, {skipped} already current, "
            f"across {examined} building(s) under {images_dir}"
        )
    print(
        f"[FINAL] {'finished with problems' if failures else 'complete'}: "
        f"{derived} derived, {skipped} current, {examined} building(s) examined, "
        f"{len(failures)} failed",
        file=sys.stderr,
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

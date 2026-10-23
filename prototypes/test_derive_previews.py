#!/usr/bin/env python3
"""Offline tests for the local preview derivation.

The pictures this script works on are the inventory's, so a derived thumbnail
must never be able to pose as the publisher's own rendition. These tests pin
that: the derivation is recorded on the manifest with the source hash, a re-run
is a no-op, and a changed original is re-derived rather than shadowed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "three-ages" / "derive_previews.py"


def load_script():
    spec = importlib.util.spec_from_file_location("derive_previews", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_picture(path: Path, size: tuple[int, int], colour: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, colour)
    image.save(path, format="JPEG", quality=90)


def make_building(root: Path, building_id: str, filenames: list[str]) -> Path:
    """A download folder shaped like the one scrape_monument.py writes."""
    building_dir = root / building_id
    images = []
    for index, filename in enumerate(filenames):
        source = building_dir / filename
        # Originals are portrait 1085x1600, like the inventory's own pictures.
        write_picture(source, (1085, 1600), (40 * index, 80, 120))
        images.append({
            "url": f"https://monument.heritage.brussels/medias/buildings/{filename}",
            "filename": filename,
            "variant": "full",
            "bytes": source.stat().st_size,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        })
    (building_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "images": images}, indent=2), encoding="utf-8"
    )
    return building_dir


def test_preview_matches_the_published_framing(module) -> None:
    """The substitution is only honest if the geometry agrees with the source's own
    500px rendition, measured at 1085x1600 -> 339x500."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "inbox"
        building_dir = make_building(root, "23775", ["10810001_0001_P01.JPG"])
        entries, derived = module.derive_building(building_dir, 500, 82)
        assert derived == 1 and len(entries) == 1
        entry = entries[0]
        assert (entry["width"], entry["height"]) == (339, 500)
        assert entry["long_edge"] == 500
        target = building_dir / entry["path"]
        assert target.exists()
        assert target.parent.name == "preview"
        assert hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]
        assert entry["source_sha256"] == hashlib.sha256(
            (building_dir / entry["filename"]).read_bytes()
        ).hexdigest()

        # The manifest has to say the file is derived, or it reads as published.
        module.update_manifest(building_dir, entries)
        manifest = json.loads((building_dir / "manifest.json").read_text(encoding="utf-8"))
        section = manifest["derived_previews"]
        assert section["derived"] is True
        assert "not fetched from the source" in section["note"]
        assert section["tool"].endswith("derive_previews.py")
        assert section["images"][0]["source_sha256"] == entry["source_sha256"]


def test_rerun_is_a_no_op(module) -> None:
    """A resume over ~39,000 files must not re-encode what is already current."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "inbox"
        building_dir = make_building(root, "23775", ["a.JPG", "b.JPG"])
        entries, derived = module.derive_building(building_dir, 500, 82)
        assert derived == 2
        assert module.update_manifest(building_dir, entries) is True
        before = (building_dir / "manifest.json").read_text(encoding="utf-8")
        stamp = (building_dir / "manifest.json").stat().st_mtime_ns

        again, derived_again = module.derive_building(building_dir, 500, 82)
        assert derived_again == 0, "current previews must not be re-derived"
        assert [entry["sha256"] for entry in again] == [entry["sha256"] for entry in entries]
        assert module.update_manifest(building_dir, again) is False, "manifest must not drift"
        assert (building_dir / "manifest.json").read_text(encoding="utf-8") == before
        assert (building_dir / "manifest.json").stat().st_mtime_ns == stamp


def test_changed_original_is_rederived(module) -> None:
    """A re-downloaded original must not be shadowed by its stale thumbnail."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "inbox"
        building_dir = make_building(root, "23775", ["a.JPG"])
        entries, _ = module.derive_building(building_dir, 500, 82)
        module.update_manifest(building_dir, entries)
        first = entries[0]["sha256"]

        write_picture(building_dir / "a.JPG", (1085, 1600), (200, 10, 10))
        stale, derived = module.derive_building(building_dir, 500, 82)
        assert derived == 1
        assert stale[0]["sha256"] != first
        assert stale[0]["source_sha256"] != entries[0]["source_sha256"]

        # A different long edge is a different rendition, not a current one.
        _, resized = module.derive_building(building_dir, 300, 82)
        assert resized == 1

        # --force is explicit: it re-derives even a current preview.
        _, forced = module.derive_building(building_dir, 300, 82, force=True)
        assert forced == 1


def test_missing_originals_are_skipped(module) -> None:
    """A picture the picture pass has not fetched yet is not an error here."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "inbox"
        building_dir = make_building(root, "23775", ["a.JPG", "b.JPG"])
        (building_dir / "b.JPG").unlink()
        entries, derived = module.derive_building(building_dir, 500, 82)
        assert derived == 1
        assert [entry["filename"] for entry in entries] == ["a.JPG"]

        # No manifest at all: nothing to derive, and nothing to invent.
        empty = root / "1000"
        empty.mkdir()
        assert module.derive_building(empty, 500, 82) == ([], 0)


def test_exif_orientation_is_honoured(module) -> None:
    """A browsing copy must look like the photograph, not like its pixel grid.

    A source tagged to display rotated would otherwise produce a sideways thumbnail
    in the review workbench, where facades are compared visually. Measured on the 252
    real inventory files downloaded so far: 17 carry EXIF and every one is already
    upright, so this behaviour is insurance for an unmeasured 77,000 rather than a
    fix for something observed.
    """
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "rotated.JPG"
        image = Image.new("RGB", (1600, 900), (10, 20, 30))
        exif = Image.Exif()
        exif[274] = 6  # 6 = rotate 90 degrees for display: the photo is portrait
        image.save(source, format="JPEG", exif=exif)
        with Image.open(source) as stored:
            assert stored.size == (1600, 900), "the stored grid is landscape"
            assert stored.getexif()[274] == 6

        target = Path(tmp) / "preview" / "rotated.JPG"
        width, height, output_format = module.derive_one(source, target, 500, 82)
        assert height == 500, (width, height)
        assert width < height, f"the copy must be portrait like the photo: {width}x{height}"
        assert width in (281, 282), (width, height)
        assert output_format == "jpeg", output_format
        with Image.open(target) as made:
            assert made.size == (width, height)

        # An untagged source is untouched by the orientation handling.
        plain = Path(tmp) / "plain.JPG"
        Image.new("RGB", (1600, 900), (1, 2, 3)).save(plain, format="JPEG")
        assert module.derive_one(plain, Path(tmp) / "p2.JPG", 500, 82) == (500, 281, "jpeg")


def test_png_source_yields_a_png_copy(module) -> None:
    """The derived file inherits the source's name, so it must keep the source's kind.

    22 of the 77,175 picture references are named `.png`. Saving JPEG bytes under
    that name would ship a file whose extension contradicts its content — the same
    mislabelling the downloader's signature check exists to prevent upstream — and a
    consumer could not tell without opening it. The manifest entry records the
    format too, so nothing has to infer it from an extension either.
    """
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "plan.png"
        Image.new("RGB", (1200, 600), (5, 6, 7)).save(source, format="PNG")

        target = Path(tmp) / "preview" / "plan.png"
        width, height, output_format = module.derive_one(source, target, 500, 82)
        assert output_format == "png", output_format
        assert (width, height) == (500, 250), (width, height)
        with Image.open(target) as made:
            assert made.format == "PNG", made.format  # the bytes agree with the name

        # And the entry carries it, so the copy describes itself.
        building_dir = Path(tmp) / "9"
        building_dir.mkdir()
        (building_dir / "plan.png").write_bytes(source.read_bytes())
        (building_dir / "manifest.json").write_text(json.dumps({
            "schema_version": 2,
            "images": [{"filename": "plan.png", "url": "https://h/medias/buildings/plan.png",
                        "bytes": source.stat().st_size,
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
        }), encoding="utf-8")
        entries, derived = module.derive_building(building_dir, 500, 82)
        assert derived == 1 and entries[0]["format"] == "png", entries


def test_main_reports_and_isolates_failures(module) -> None:
    """One unreadable original must cost its own building, not the whole run."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "inbox"
        good = make_building(root, "23775", ["a.JPG"])
        bad = make_building(root, "1000", ["b.JPG"])
        (bad / "b.JPG").write_bytes(b"not a picture at all")

        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = module.main(["--images-dir", str(root), "--progress-every", "0"])

        assert code == 1
        assert "1000" in err.getvalue()
        assert "[FINAL] finished with problems" in err.getvalue()
        # The healthy building still got its preview.
        assert (good / "preview" / "a.JPG").exists()
        assert not (bad / "preview" / "b.JPG").exists()

        # Anonymous download folders without a manifest are ignored, not guessed at:
        # a manifest is the only thing that states what a file is and where it came from.
        anonymous = Path(tmp) / "anonymous"
        (anonymous / "9999").mkdir(parents=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.main(["--images-dir", str(anonymous)]) == 2


def test_arguments_are_validated(module) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "inbox"
        make_building(root, "23775", ["a.JPG"])
        for argv in (
            ["--images-dir", str(root), "--long-edge", "0"],
            ["--images-dir", str(root), "--quality", "0"],
            ["--images-dir", str(root), "--quality", "100"],
        ):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                assert module.main(argv) == 2, argv
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert module.main(["--images-dir", str(Path(tmp) / "absent")]) == 2


def main() -> None:
    module = load_script()
    tests = [
        test_preview_matches_the_published_framing,
        test_rerun_is_a_no_op,
        test_changed_original_is_rederived,
        test_exif_orientation_is_honoured,
        test_png_source_yields_a_png_copy,
        test_missing_originals_are_skipped,
        test_main_reports_and_isolates_failures,
        test_arguments_are_validated,
    ]
    for test in tests:
        test(module)
    print(f"Three Ages preview derivation passed ({len(tests)} offline checks)")


if __name__ == "__main__":
    sys.exit(main())

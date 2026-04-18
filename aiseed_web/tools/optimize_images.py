"""Convert <site>/images/**/* into responsive WebP variants under
<site>/build/assets/images/.

Produces <stem>-480.webp, <stem>-800.webp, <stem>-1200.webp plus <stem>.webp
(full-size, capped at 1600 px). Use srcset in templates to pick a size.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from PIL import Image

SIZES = [480, 800, 1200]
FULL_MAX = 1600
QUALITY = 85
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"}


def convert_one(src: Path, rel: Path, out_root: Path) -> int:
    out_dir = out_root / rel.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = rel.stem
    written = 0

    with Image.open(src) as img:
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        full = img
        if full.width > FULL_MAX:
            ratio = FULL_MAX / full.width
            full = full.resize((FULL_MAX, int(full.height * ratio)), Image.LANCZOS)
        full.save(out_dir / f"{stem}.webp", "WEBP", quality=QUALITY, method=6)
        written += 1

        for w in SIZES:
            if img.width < w:
                continue
            ratio = w / img.width
            resized = img.resize((w, int(img.height * ratio)), Image.LANCZOS)
            resized.save(out_dir / f"{stem}-{w}.webp", "WEBP", quality=QUALITY, method=6)
            resized.close()
            written += 1

        if full is not img:
            full.close()
    return written


def resolve_site(cli_value: str | None) -> Path:
    candidate = cli_value or os.environ.get("AISEED_WEB_SITE") or os.getcwd()
    site = Path(candidate).resolve()
    if not (site / "images").exists():
        raise SystemExit(
            f"[images] {site}/images not found. Pass --site <path>."
        )
    return site


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Path to the site data directory.")
    args = parser.parse_args()

    site = resolve_site(args.site)
    src_root = site / "images"
    out_root = site / "build" / "assets" / "images"

    total_files = 0
    total_written = 0
    for path in src_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if path.name.startswith("."):
            continue
        rel = path.relative_to(src_root)
        written = convert_one(path, rel, out_root)
        total_files += 1
        total_written += written
        print(f"[images] {rel} → {written} variants")

    print(f"[images] processed {total_files} source images, wrote {total_written} files")


if __name__ == "__main__":
    main()

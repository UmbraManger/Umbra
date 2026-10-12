"""Regenerate the shipped app icon and logo from the source artwork.

    python tools/make_icon.py [path/to/source.png]

Source art lives outside the repo (it's a design asset); this bakes the three
files the app actually ships:

    frontend/img/umbra.png     sidebar brand + About + drawn title bar
    frontend/img/favicon.png   browser tab icon
    backend/umbra.ico          the exe/taskbar icon (referenced by Obscura.spec)
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(os.path.expanduser("~"), "Downloads", "umbra.png")
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.isfile(src):
        print(f"source art not found: {src}")
        return 1

    im = Image.open(src)
    print(f"source: {im.format} {im.mode} {im.size[0]}x{im.size[1]}")

    # Windows .ico wants an opaque 256px square; the browser is happy with RGBA.
    # Pad to square first so the round art is never cropped by the icon builder.
    side = max(im.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))

    img_dir = os.path.join(ROOT, "frontend", "img")
    os.makedirs(img_dir, exist_ok=True)

    logo = square.resize((256, 256), Image.LANCZOS)
    logo.save(os.path.join(img_dir, "umbra.png"))
    logo.resize((64, 64), Image.LANCZOS).save(os.path.join(img_dir, "favicon.png"))

    ico = os.path.join(ROOT, "backend", "umbra.ico")
    square.save(ico, format="ICO", sizes=ICO_SIZES)
    print(f"wrote: frontend/img/umbra.png (256), frontend/img/favicon.png (64), "
          f"backend/umbra.ico {ICO_SIZES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Command line: logo-to-svg logo.png -o logo.svg [--text ... --weight ...]"""
import argparse
import sys

from . import __version__
from .core import vectorize
from .util import LogoError

DESCRIPTION = """Turn a blurry single-colour raster logo into a clean SVG.

The graphic is traced with potrace; text lines are re-set with a free font
and converted to paths, so the SVG looks identical everywhere.

Examples
--------
# Trace everything (graphic + text) as shapes:
logo-to-svg logo.png -o logo.svg

# Trace the graphic, re-set the two text lines below it with Montserrat:
logo-to-svg logo.png -o logo.svg --preview preview.png \\
    --text "DR. JANE DOE" --weight 600 \\
    --text "Physician"    --weight 300

Text lines are matched to the LAST horizontal bands of the image (top to
bottom), so pass them in reading order. ALL-CAPS lines are sized by cap
height, lines with lowercase letters by ascender-to-descender height
(see --fit). Tracing small text (< ~12 px tall) destroys it, so always
re-set small text with --text.
"""


def build_parser():
    ap = argparse.ArgumentParser(prog="logo-to-svg", description=DESCRIPTION,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="logo.svg")
    ap.add_argument("--preview", help="also render a PNG preview (white bg); needs the [preview] extra")
    ap.add_argument("--text", action="append", default=[],
                    help="text line to re-set (repeat, top to bottom)")
    ap.add_argument("--weight", action="append", default=[],
                    help="font weight per --text line (default 400)")
    ap.add_argument("--font", action="append", default=[],
                    help="local .ttf/.otf/.woff per line (overrides --family)")
    ap.add_argument("--family", default="Montserrat",
                    help="@fontsource family to download (default Montserrat)")
    ap.add_argument("--fit", choices=["auto", "caps", "bounds"], default="auto",
                    help="how text is sized: caps = cap height equals band height, bounds = "
                         "ascenders..descenders equal band height, auto = bounds for lines "
                         "with lowercase letters (default)")
    ap.add_argument("--color", help="override colour, e.g. #000000")
    ap.add_argument("--scale", type=int, default=12, help="trace upscale factor")
    ap.add_argument("--smooth", type=float, default=0.6,
                    help="blur before tracing, in source px (raise to 1.0-1.5 for "
                         "pixelated/jagged sources; too high rounds off details)")
    ap.add_argument("--pad", type=float, default=10, help="viewBox padding (px)")
    ap.add_argument("--fixed-size", action="store_true",
                    help="keep width/height attributes (default: viewBox only)")
    ap.add_argument("--version", action="version", version=f"logo-to-svg {__version__}")
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        report = vectorize(a.input, a.output, texts=a.text, weights=a.weight, fonts=a.font,
                           family=a.family, color=a.color, scale=a.scale, smooth=a.smooth,
                           pad=a.pad, fixed_size=a.fixed_size, preview=a.preview, fit=a.fit)
    except (LogoError, OSError) as e:
        sys.exit(f"logo-to-svg: {e}")
    print("\n".join(report))


if __name__ == "__main__":
    main()

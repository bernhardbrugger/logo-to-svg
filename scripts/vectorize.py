#!/usr/bin/env python3
"""Entry point used by the Claude skill (SKILL.md): `python scripts/vectorize.py logo.png -o logo.svg ...`.

Works straight from a copied skill folder, without installing the package. Same options as the
`logo-to-svg` command; run with --help for the full list.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from logo_to_svg.cli import main
except ImportError as e:
    sys.exit(f"Missing deps ({e}): pip install potracer opencv-python-headless pillow numpy "
             "fonttools brotli cairosvg")

if __name__ == "__main__":
    main()

"""Shared fixtures: a tiny generated font and synthetic logos, so tests need no network, npm or system fonts."""
import numpy as np
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from PIL import Image

# glyph boxes in font units (1000 per em): x0, y0, x1, y1
GLYPH_BOXES = {
    ".notdef": (50, 0, 450, 700),
    "A": (50, 0, 550, 700),      # cap height 700
    "B": (50, 0, 550, 700),
    "g": (50, -200, 450, 500),   # x-height 500 with a 200-unit descender
}
ADVANCES = {".notdef": 500, "A": 600, "B": 600, "g": 500, "space": 300}


def _rect(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()


@pytest.fixture(scope="session")
def test_font(tmp_path_factory):
    path = tmp_path_factory.mktemp("font") / "box.ttf"
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A", "B", "g", "space"])
    fb.setupCharacterMap({65: "A", 66: "B", 103: "g", 32: "space"})
    glyphs = {}
    for name, box in GLYPH_BOXES.items():
        pen = TTGlyphPen(None)
        _rect(pen, *box)
        glyphs[name] = pen.glyph()
    glyphs["space"] = TTGlyphPen(None).glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (w, GLYPH_BOXES.get(n, (0,))[0]) for n, w in ADVANCES.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Box", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200,
                sCapHeight=700, sxHeight=500)
    fb.setupPost()
    fb.save(str(path))
    return str(path)


def path_bounds(d):
    """(xmin, ymin, xmax, ymax) of SVG path data."""
    bp = BoundsPen(None)
    parse_path(d, bp)
    return bp.bounds


def make_logo(path, size=(400, 300), background=255, ink=30, inverted=False, text_blocks=((120, 280, 190, 215),)):
    """A filled circle as the 'graphic' plus solid blocks standing in for text lines.

    text_blocks: (x0, x1, y0, y1) with y1 exclusive.
    """
    w, h = size
    img = np.full((h, w, 3), background, np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    img[(xx - 200) ** 2 + (yy - 90) ** 2 <= 50 ** 2] = ink
    for x0, x1, y0, y1 in text_blocks:
        img[y0:y1, x0:x1] = ink
    if inverted:
        img = 255 - img
    Image.fromarray(img).save(path)
    return str(path)

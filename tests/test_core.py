import numpy as np
import pytest

from logo_to_svg.core import bbox, load_ink, row_bands, text_extent, trace_region
from logo_to_svg.util import LogoError, fmt

from conftest import make_logo, path_bounds


def test_fmt_trims_zeros():
    assert fmt(1.0) == "1"
    assert fmt(1.2345) == "1.23"
    assert fmt(0.5) == "0.5"


def test_load_ink_finds_colour_and_mask(tmp_path):
    img = make_logo(tmp_path / "logo.png", ink=40)
    g, ink, bg, colour = load_ink(img)
    assert bg == pytest.approx(255)
    assert colour == "#282828"
    assert ink[90, 200] and not ink[5, 5]


def test_load_ink_colour_ignores_dark_edge_overshoot(tmp_path):
    # A sharpened export: flat ink #1F4037 with a darker one-pixel rim around every shape.
    # The rim must not pull the detected colour darker (it used to give the rim colour).
    import cv2
    from PIL import Image
    h, w = 300, 400
    yy, xx = np.mgrid[0:h, 0:w]
    shape = (xx - 200) ** 2 + (yy - 90) ** 2 <= 50 ** 2
    shape |= (xx >= 120) & (xx < 280) & (yy >= 190) & (yy < 215)
    rim = shape & ~cv2.erode(shape.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    img = np.full((h, w, 3), 255, np.uint8)
    img[shape] = (0x1F, 0x40, 0x37)
    img[rim] = (0x0A, 0x28, 0x1E)
    Image.fromarray(img).save(tmp_path / "sharpened.png")
    _, _, _, colour = load_ink(str(tmp_path / "sharpened.png"))
    assert colour == "#1F4037"


def test_load_ink_colour_of_thin_strokes(tmp_path):
    # Two-pixel lines have no interior after erosion: the darkest-half fallback applies.
    from PIL import Image
    img = np.full((60, 200, 3), 255, np.uint8)
    img[20:22, 10:190] = (0x80, 0x10, 0x10)
    img[40:42, 10:190] = (0x80, 0x10, 0x10)
    Image.fromarray(img).save(tmp_path / "thin.png")
    _, _, _, colour = load_ink(str(tmp_path / "thin.png"))
    assert colour == "#801010"


def test_load_ink_inverts_dark_backgrounds(tmp_path):
    img = make_logo(tmp_path / "logo.png", inverted=True)
    g, ink, bg, colour = load_ink(img)
    assert ink[90, 200] and not ink[5, 5]


def test_blank_image_is_rejected(tmp_path):
    import numpy as np
    from PIL import Image
    Image.fromarray(np.full((50, 50, 3), 255, np.uint8)).save(tmp_path / "blank.png")
    with pytest.raises(LogoError, match="No ink"):
        load_ink(str(tmp_path / "blank.png"))


def test_row_bands_split_on_gaps(tmp_path):
    img = make_logo(tmp_path / "logo.png", text_blocks=((120, 280, 190, 215), (150, 250, 240, 250)))
    _, ink, _, _ = load_ink(img)
    assert row_bands(ink) == [(40, 140), (190, 214), (240, 249)]


def test_text_extent_measures_block_edges(tmp_path):
    img = make_logo(tmp_path / "logo.png")
    g, ink, bg, _ = load_ink(img)
    left, right, top, bottom = text_extent(g, ink, bg, 190, 214)
    assert (left, right, top, bottom) == pytest.approx((120, 280, 190, 215), abs=0.6)


def test_bbox_of_graphic(tmp_path):
    img = make_logo(tmp_path / "logo.png")
    g, ink, bg, _ = load_ink(img)
    x0, x1, y0, y1 = bbox(g, ink, bg, 40, 140)
    assert (x0, x1, y0, y1) == pytest.approx((150, 250, 40, 140), abs=2)


def test_trace_region_follows_the_shape(tmp_path):
    img = make_logo(tmp_path / "logo.png")
    g, ink, bg, _ = load_ink(img)
    d = trace_region(g, 150, 40, 250, 140, scale=6)
    assert d.startswith("M") and d.endswith("Z")
    xmin, ymin, xmax, ymax = path_bounds(d)
    # the circle has radius 50 around (200, 90)
    assert (xmin, ymin, xmax, ymax) == pytest.approx((150, 40, 250, 140), abs=2.5)

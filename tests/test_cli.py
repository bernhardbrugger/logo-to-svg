import pathlib
import xml.etree.ElementTree as ET

import pytest

from logo_to_svg import vectorize
from logo_to_svg.cli import main
from logo_to_svg.util import LogoError

from conftest import make_logo, path_bounds

NS = "{http://www.w3.org/2000/svg}"
EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "before.png"


def svg_paths(svg_file):
    root = ET.parse(svg_file).getroot()
    return root, [p.get("d") for p in root.iter(NS + "path")]


def test_graphic_only(tmp_path):
    src = make_logo(tmp_path / "in.png", text_blocks=())
    out = tmp_path / "out.svg"
    vectorize(src, str(out), scale=6)
    root, paths = svg_paths(out)
    assert len(paths) == 1
    assert root.get("viewBox") and root.get("width") is None     # responsive by default


def test_text_line_is_reset_to_the_measured_box(tmp_path, test_font):
    src = make_logo(tmp_path / "in.png")                          # block at x120..280, y190..215
    out = tmp_path / "out.svg"
    report = vectorize(src, str(out), texts=["AB"], fonts=[test_font], scale=6)
    _, paths = svg_paths(out)
    assert len(paths) == 2
    xmin, ymin, xmax, ymax = path_bounds(paths[1])
    assert (xmin, xmax) == pytest.approx((120, 280), abs=0.7)
    assert (ymin, ymax) == pytest.approx((190, 215), abs=0.7)
    assert any("cap" in line for line in report)


def test_mixed_case_line_uses_ascender_descender_fit(tmp_path, test_font):
    # one block = 190..225: 'Ag' has cap 700 and descender -200 -> 900 units must fill all 35 px
    src = make_logo(tmp_path / "in.png", text_blocks=((120, 280, 190, 225),))
    out = tmp_path / "out.svg"
    report = vectorize(src, str(out), texts=["Ag"], fonts=[test_font], scale=6)
    _, paths = svg_paths(out)
    _, ymin, _, ymax = path_bounds(paths[1])
    assert (ymin, ymax) == pytest.approx((190, 225), abs=0.7)
    assert any("ascender-to-descender" in line for line in report)


def test_fit_caps_can_be_forced(tmp_path, test_font):
    src = make_logo(tmp_path / "in.png")
    out = tmp_path / "out.svg"
    report = vectorize(src, str(out), texts=["Ag"], fonts=[test_font], fit="caps", scale=6)
    assert any("cap " in line for line in report)


def test_too_many_text_lines(tmp_path, test_font):
    src = make_logo(tmp_path / "in.png")
    with pytest.raises(LogoError, match="horizontal band"):
        vectorize(src, str(tmp_path / "o.svg"), texts=["A", "B", "A"], fonts=[test_font])


def test_invalid_fit_value(tmp_path):
    src = make_logo(tmp_path / "in.png")
    with pytest.raises(LogoError, match="fit must be"):
        vectorize(src, str(tmp_path / "o.svg"), fit="nope")


def test_color_override_and_fixed_size(tmp_path):
    src = make_logo(tmp_path / "in.png", text_blocks=())
    out = tmp_path / "out.svg"
    vectorize(src, str(out), color="#112233", fixed_size=True, scale=6)
    root = ET.parse(out).getroot()
    assert root.get("width") and root.get("height")
    assert root.find(NS + "g").get("fill") == "#112233"


def test_cli_reports_errors_without_traceback(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main([str(tmp_path / "missing.png"), "-o", str(tmp_path / "o.svg")])
    assert "logo-to-svg:" in str(e.value)


def test_cli_end_to_end(tmp_path, test_font, capsys):
    src = make_logo(tmp_path / "in.png")
    out = tmp_path / "out.svg"
    main([src, "-o", str(out), "--text", "AB", "--font", test_font, "--scale", "6"])
    assert "wrote" in capsys.readouterr().out
    assert len(svg_paths(out)[1]) == 2


def test_example_logo_is_traced_deterministically(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    a, b = tmp_path / "one" / "logo.svg", tmp_path / "two" / "logo.svg"
    vectorize(str(EXAMPLE), str(a))
    vectorize(str(EXAMPLE), str(b))
    assert a.read_bytes() == b.read_bytes()
    root, paths = svg_paths(a)
    assert paths and 20_000 < a.stat().st_size < 40_000


def two_colour_logo(path, subtitle=None):
    """Teal circle above a dark headline block; optionally a thin, blurred subtitle line
    (antialiased all the way through, so no pixel reaches its full ink colour)."""
    import cv2
    import numpy as np
    from PIL import Image
    h, w = 300, 400
    yy, xx = np.mgrid[0:h, 0:w]
    img = np.full((h, w, 3), 255, np.float32)
    img[(xx - 200) ** 2 + (yy - 90) ** 2 <= 50 ** 2] = (0x1F, 0x8A, 0x70)
    img[190:215, 120:280] = (0x22, 0x22, 0x22)
    if subtitle:
        line = np.zeros((h, w), np.float32)
        line[245:247, 140:260] = 1
        a = np.clip(cv2.GaussianBlur(line, (0, 0), 0.8) * 1.3, 0, 0.85)[..., None]
        img = img * (1 - a) + np.array(subtitle, np.float32) * a
    Image.fromarray(img.round().astype(np.uint8)).save(path)
    return str(path)


def fills(svg_file):
    return [p.get("fill") for p in ET.parse(svg_file).getroot().iter(NS + "path")]


def test_graphic_and_text_keep_their_own_colours(tmp_path, test_font):
    src = two_colour_logo(tmp_path / "in.png")
    out = tmp_path / "out.svg"
    report = vectorize(src, str(out), texts=["AB"], fonts=[test_font], scale=6)
    assert fills(out) == ["#1F8A70", "#222222"]
    assert "colours graphic #1F8A70, text 1 #222222" in report[-1]


def test_thin_line_takes_the_colour_it_is_a_blend_of(tmp_path, test_font):
    # Measured directly the subtitle would come out light grey; it is a blend of the headline ink.
    src = two_colour_logo(tmp_path / "in.png", subtitle=(0x22, 0x22, 0x22))
    out = tmp_path / "out.svg"
    vectorize(src, str(out), texts=["AB", "AB"], fonts=[test_font], scale=6)
    assert fills(out) == ["#1F8A70", "#222222", "#222222"]


def test_thin_line_in_a_colour_of_its_own(tmp_path, test_font):
    src = two_colour_logo(tmp_path / "in.png", subtitle=(0xC0, 0x20, 0x20))
    out = tmp_path / "out.svg"
    vectorize(src, str(out), texts=["AB", "AB"], fonts=[test_font], scale=6)
    graphic, headline, subtitle = fills(out)
    assert (graphic, headline) == ("#1F8A70", "#222222")
    r, g, b = (int(subtitle[i:i + 2], 16) for i in (1, 3, 5))
    assert r > 150 and g < 90 and b < 90          # red, not a grey or the teal


def test_single_colour_logo_keeps_one_fill(tmp_path, test_font):
    src = make_logo(tmp_path / "in.png", ink=40)
    out = tmp_path / "out.svg"
    vectorize(src, str(out), texts=["AB"], fonts=[test_font], scale=6)
    root = ET.parse(out).getroot()
    assert root.find(NS + "g").get("fill") == "#282828"
    assert fills(out) == [None, None]


def test_color_override_applies_to_every_part(tmp_path, test_font):
    src = two_colour_logo(tmp_path / "in.png")
    out = tmp_path / "out.svg"
    vectorize(src, str(out), texts=["AB"], fonts=[test_font], color="#000000", scale=6)
    assert ET.parse(out).getroot().find(NS + "g").get("fill") == "#000000"
    assert fills(out) == [None, None]

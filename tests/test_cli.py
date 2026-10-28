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

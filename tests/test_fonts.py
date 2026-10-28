import io
import tarfile

import pytest

import logo_to_svg.fonts as fonts
from logo_to_svg.fonts import _safe_extract, fetch_fontsource, has_lowercase, text_path
from logo_to_svg.util import LogoError

from conftest import path_bounds


def test_has_lowercase():
    assert has_lowercase("Studio")
    assert not has_lowercase("STUDIO 24 & CO.")


def test_caps_fit_hits_width_and_cap_height(test_font):
    d = text_path(test_font, "AB", 10, 210, baseline=100, cap_px=70)
    xmin, ymin, xmax, ymax = path_bounds(d)
    assert (xmin, xmax) == pytest.approx((10, 210), abs=0.01)      # tracked to the target width
    assert (ymin, ymax) == pytest.approx((30, 100), abs=0.01)      # cap height 70 above the baseline


def test_bounds_fit_includes_descender(test_font):
    d = text_path(test_font, "Ag", 10, 210, baseline=0, fit_box=(20, 110))
    xmin, ymin, xmax, ymax = path_bounds(d)
    # glyph A spans 0..700, g spans -200..500 -> the whole line (900 units) fills 20..110
    assert (xmin, xmax) == pytest.approx((10, 210), abs=0.01)
    assert (ymin, ymax) == pytest.approx((20, 110), abs=0.01)


def test_size_px_takes_precedence(test_font):
    d = text_path(test_font, "A", 0, 50, baseline=100, size_px=100, cap_px=999)
    _, ymin, _, ymax = path_bounds(d)
    assert (ymin, ymax) == pytest.approx((30, 100), abs=0.01)      # 700 units at 100 px/em = 70 px


def test_empty_text_is_rejected(test_font):
    with pytest.raises(LogoError):
        text_path(test_font, "", 0, 10, 10, cap_px=5)


def test_missing_npm_gives_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(fonts, "CACHE", str(tmp_path))
    monkeypatch.setattr(fonts.shutil, "which", lambda name: None)
    with pytest.raises(LogoError, match="npm was not found"):
        fetch_fontsource("Some Family", "400")


def test_npm_is_resolved_via_which_not_a_bare_name(monkeypatch, tmp_path):
    """On Windows npm is npm.cmd; a bare 'npm' cannot be launched (the original bug)."""
    monkeypatch.setattr(fonts, "CACHE", str(tmp_path))
    monkeypatch.setattr(fonts.shutil, "which", lambda name: r"C:\Program Files\nodejs\npm.cmd")
    seen = {}

    class Result:
        returncode, stderr = 1, "boom"

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return Result()

    monkeypatch.setattr(fonts.subprocess, "run", fake_run)
    with pytest.raises(LogoError, match="Could not fetch"):
        fetch_fontsource("Some Family", "400")
    assert seen["cmd"][0].endswith("npm.cmd")


def test_unknown_weight_lists_available_ones(monkeypatch, tmp_path):
    files = tmp_path / "some-family" / "package" / "files"
    files.mkdir(parents=True)
    (files / "some-family-latin-400-normal.woff").write_bytes(b"x")
    (files / "some-family-latin-700-normal.woff").write_bytes(b"x")
    monkeypatch.setattr(fonts, "CACHE", str(tmp_path))
    with pytest.raises(LogoError, match="Available: 400, 700"):
        fetch_fontsource("Some Family", "300")
    assert fetch_fontsource("Some Family", "400").endswith("some-family-latin-400-normal.woff")


def test_tar_path_traversal_is_refused(tmp_path):
    tgz = tmp_path / "evil.tgz"
    with tarfile.open(tgz, "w:gz") as tar:
        info = tarfile.TarInfo("../escaped.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(LogoError, match="unsafe"):
        _safe_extract(str(tgz), str(dest))
    assert not (tmp_path / "escaped.txt").exists()

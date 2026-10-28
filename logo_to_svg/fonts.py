"""Fonts: download from @fontsource via npm, and turn text into SVG path data."""
import glob
import os
import re
import shutil
import subprocess
import tarfile
import tempfile

from .util import LogoError, fmt

CACHE = os.path.join(tempfile.gettempdir(), "logo-to-svg-fonts")


def _safe_extract(tgz, dest):
    """Extract a tarball, refusing anything that would land outside `dest`."""
    root = os.path.realpath(dest)
    with tarfile.open(tgz) as tar:
        for member in tar.getmembers():
            target = os.path.realpath(os.path.join(dest, member.name))
            if not (target == root or target.startswith(root + os.sep)):
                raise LogoError(f"Refusing unsafe path in font package: {member.name}")
            if not (member.isfile() or member.isdir()):
                raise LogoError(f"Refusing unexpected entry in font package: {member.name}")
        tar.extractall(dest)


def fetch_fontsource(family, weight):
    """Download a font from @fontsource via npm (no Google Fonts access needed)."""
    pkg = family.lower().replace(" ", "-")
    d = os.path.join(CACHE, pkg)
    files = os.path.join(d, "package", "files")
    if not os.path.isdir(files):
        # shutil.which resolves "npm" to npm.cmd on Windows, where a bare "npm" cannot be launched.
        npm = shutil.which("npm")
        if not npm:
            raise LogoError("npm was not found, so the font cannot be downloaded automatically. "
                            "Install Node.js, or pass a local font file with --font.")
        os.makedirs(d, exist_ok=True)
        r = subprocess.run([npm, "pack", f"@fontsource/{pkg}", "--silent"],
                           cwd=d, capture_output=True, text=True)
        tgz = glob.glob(os.path.join(d, "*.tgz"))
        if r.returncode or not tgz:
            raise LogoError(f"Could not fetch @fontsource/{pkg} via npm. "
                            f"Pass a local font file with --font instead.\n{r.stderr}")
        _safe_extract(tgz[0], d)
    cand = glob.glob(os.path.join(files, f"*-latin-{weight}-normal.woff"))
    if not cand:
        avail = sorted({re.search(r"-(\d{3})-normal", f).group(1)
                        for f in glob.glob(os.path.join(files, "*-latin-*-normal.woff"))})
        raise LogoError(f"{family} has no weight {weight}. Available: {', '.join(avail)}")
    return cand[0]


def has_lowercase(text):
    return any(ch.islower() for ch in text)


def text_path(fontfile, text, x0, x1, baseline, cap_px=None, size_px=None, fit_box=None):
    """Glyph outlines for `text`, tracked to fill x0..x1.

    Size, in order of precedence:
      size_px  - font size in px
      fit_box  - (top, bottom) in px: scale so the ink of this line (ascenders to
                 descenders) exactly fills that box; `baseline` is then derived. Use for mixed case.
      cap_px   - cap height in px (ALL CAPS lines); the baseline is `baseline`.
    """
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    if not text:
        raise LogoError("Empty text line.")
    f = TTFont(fontfile)
    gs, cmap = f.getGlyphSet(), f.getBestCmap()
    glyphs = [cmap.get(ord(ch), ".notdef") for ch in text]

    def bounds(g):
        bp = BoundsPen(gs)
        gs[g].draw(bp)
        return bp.bounds

    if size_px:
        s = size_px / f["head"].unitsPerEm
    elif fit_box is not None:
        boxes = [b for b in (bounds(g) for g in glyphs) if b]
        if not boxes:
            raise LogoError(f"The font has no outlines for {text!r}.")
        ymin, ymax = min(b[1] for b in boxes), max(b[3] for b in boxes)
        s = (fit_box[1] - fit_box[0]) / (ymax - ymin)
        baseline = fit_box[0] + ymax * s
    else:
        s = cap_px / f["OS/2"].sCapHeight

    adv = sum(gs[g].width for g in glyphs)
    n = max(1, len(glyphs) - 1)
    # trim side bearings of first/last glyph so ink edges hit x0/x1 exactly
    lb = (bounds(glyphs[0]) or (0, 0, 0, 0))[0]
    lastb = bounds(glyphs[-1]) or (0, 0, gs[glyphs[-1]].width, 0)
    rb = gs[glyphs[-1]].width - lastb[2]
    track = ((x1 - x0) / s - (adv - lb - rb)) / n
    pen = SVGPathPen(gs, ntos=fmt)
    x = -lb
    for g in glyphs:
        gs[g].draw(TransformPen(pen, (s, 0, 0, -s, x0 + x * s, baseline)))
        x += gs[g].width + track
    return pen.getCommands()

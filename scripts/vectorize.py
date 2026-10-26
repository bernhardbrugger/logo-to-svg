#!/usr/bin/env python3
"""
logo-to-svg: turn a blurry single-color raster logo into a clean SVG.

The graphic is traced with potrace; text lines are re-set with a free font
and converted to paths, so the SVG looks identical everywhere.

Examples
--------
# Trace everything (graphic + text) as shapes:
python vectorize.py logo.png -o logo.svg

# Trace the graphic, re-set the two text lines below it with Montserrat:
python vectorize.py logo.png -o logo.svg --preview preview.png \
    --text "DR. CHRISTINA BRUGGER" --weight 600 \
    --text "ARBEITSMEDIZINERIN"   --weight 300

Text lines are matched to the LAST horizontal bands of the image (top to
bottom), so pass them in reading order. Re-set text assumes ALL-CAPS lines
(band height = cap height). Tracing small text (< ~12 px tall) destroys it,
so always re-set small text with --text.
"""
import argparse, os, re, subprocess, sys, tempfile, glob
import numpy as np
from PIL import Image

try:
    import cv2, potrace
except ImportError:
    sys.exit("Missing deps: pip install potracer opencv-python-headless pillow numpy "
             "fonttools brotli cairosvg")


# ---------------------------------------------------------------- analysis
def load_ink(path):
    """Return (gray float image, boolean ink mask, ink color hex)."""
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    rgb = np.array(im.convert("RGB")).astype(np.float32)
    g = rgb.mean(axis=2)
    border = np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])
    if np.median(border) < 128:          # dark background -> invert
        g = 255 - g
    bg = float(np.median(np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])))
    darkest = float(np.percentile(g, 0.5))
    if bg - darkest < 20:
        sys.exit("No ink found in image.")
    # Lenient mask: catches thin/light strokes (small text, JPEG exports).
    ink = g < bg - 0.3 * (bg - darkest)
    # drop JPEG speckles (tiny isolated blobs)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    keep = np.zeros(n, bool); keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 3
    ink = keep[lab]
    # colour = median of the darkest half of ink pixels
    dark = g < np.percentile(g[ink], 50)
    col = np.median(rgb[ink & dark], axis=0).astype(int)
    return g, ink, bg, "#%02X%02X%02X" % tuple(col)


def row_bands(ink, min_gap=3):
    """Horizontal bands of rows containing ink: list of (y0, y1) inclusive."""
    rows = np.where(ink.any(axis=1))[0]
    bands, start, prev = [], rows[0], rows[0]
    for r in rows[1:]:
        if r - prev > min_gap:
            bands.append((start, prev)); start = r
        prev = r
    bands.append((start, prev))
    return [(int(a), int(b)) for a, b in bands]


def bbox(g, ink, bg, y0, y1):
    """Ink bbox of a band, measured at the 50% edge between background and the
    band's own darkest value (so light/thin text is measured correctly)."""
    band = g[y0:y1 + 1]
    m = (band < (bg + band[ink[y0:y1 + 1]].min()) / 2) & ink[y0:y1 + 1]
    if not m.any():
        m = ink[y0:y1 + 1]
    ys, xs = np.where(m)
    return int(xs.min()), int(xs.max()), int(ys.min() + y0), int(ys.max() + y0)


def text_extent(g, ink, bg, y0, y1):
    """Sub-pixel ink extent of a text band: (left, right, top, bottom) as edge
    positions in px. Partial edge rows/columns count by their coverage, so a
    15 px cap height is not over-measured by antialiasing."""
    band = np.where(ink[y0:y1 + 1], g[y0:y1 + 1], bg)
    dark = band.min()
    cov = np.clip((bg - band) / max(bg - dark, 1), 0, 1)

    def edges(profile):
        idx = np.where(profile > 0.05)[0]
        a, b = idx[0], idx[-1]
        return a + (1 - profile[a]), b + profile[b]

    # 0.9 quantile per row/col: robust to single speckles, keeps true stems
    rows = np.clip(np.sort(cov, axis=1)[:, -2] / np.quantile(cov.max(axis=1), 0.9), 0, 1)
    cols = np.clip(cov.max(axis=0) / np.quantile(cov.max(axis=0)[cov.max(axis=0) > 0], 0.9), 0, 1)
    t, b = edges(rows)
    l, r = edges(cols)
    return l, r, t + y0, b + y0


# ---------------------------------------------------------------- tracing
def fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def trace_region(g, x0, y0, x1, y1, scale=12, pad=4, smooth=0.6):
    h, w = g.shape
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(w - 1, x1 + pad), min(h - 1, y1 + pad)
    crop = g[y0:y1 + 1, x0:x1 + 1]
    big = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), scale * smooth)
    thr, _ = cv2.threshold(big.astype(np.uint8), 0, 255,
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    def run(mask):
        return potrace.Bitmap(mask).trace(turdsize=int(scale * scale * 1.5),
                                          alphamax=1.2, opticurve=True,
                                          opttolerance=0.4)

    def covers_frame(path):
        # wrong polarity => one curve hugs the whole crop rectangle
        H, W = big.shape
        for c in path:
            pts = [c.start_point] + [s.end_point for s in c.segments]
            xs = [p.x for p in pts]; ys = [p.y for p in pts]
            if (max(xs) - min(xs)) > 0.97 * W and (max(ys) - min(ys)) > 0.97 * H:
                return True
        return False

    # potracer treats False as "filled" for numpy input; verify and flip if needed
    path = run(big >= thr)
    if covers_frame(path):
        path = run(big < thr)

    def P(p):
        return f"{fmt(p.x / scale + x0)} {fmt(p.y / scale + y0)}"

    out = []
    for c in path:
        s = [f"M{P(c.start_point)}"]
        for seg in c.segments:
            if seg.is_corner:
                s.append(f"L{P(seg.c)}L{P(seg.end_point)}")
            else:
                s.append(f"C{P(seg.c1)} {P(seg.c2)} {P(seg.end_point)}")
        out.append("".join(s) + "Z")
    return "".join(out)


# ---------------------------------------------------------------- fonts
CACHE = os.path.join(tempfile.gettempdir(), "logo-to-svg-fonts")


def fetch_fontsource(family, weight):
    """Download a font from @fontsource via npm (no Google Fonts access needed)."""
    pkg = family.lower().replace(" ", "-")
    d = os.path.join(CACHE, pkg)
    files = os.path.join(d, "package", "files")
    if not os.path.isdir(files):
        os.makedirs(d, exist_ok=True)
        r = subprocess.run(["npm", "pack", f"@fontsource/{pkg}", "--silent"],
                           cwd=d, capture_output=True, text=True)
        tgz = glob.glob(os.path.join(d, "*.tgz"))
        if r.returncode or not tgz:
            sys.exit(f"Could not fetch @fontsource/{pkg} via npm. "
                     f"Pass a local font file with --font instead.\n{r.stderr}")
        subprocess.run(["tar", "xzf", tgz[0]], cwd=d, check=True)
    cand = glob.glob(os.path.join(files, f"*-latin-{weight}-normal.woff"))
    if not cand:
        avail = sorted({re.search(r"-(\d{3})-normal", f).group(1)
                        for f in glob.glob(os.path.join(files, "*-latin-*-normal.woff"))})
        sys.exit(f"{family} has no weight {weight}. Available: {', '.join(avail)}")
    return cand[0]


def text_path(fontfile, text, x0, x1, baseline, cap_px=None, size_px=None):
    """Glyph outlines for `text`, scaled to cap height and tracked to fill x0..x1."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    f = TTFont(fontfile)
    gs, cmap = f.getGlyphSet(), f.getBestCmap()
    if size_px:
        s = size_px / f["head"].unitsPerEm
    else:
        s = cap_px / f["OS/2"].sCapHeight
    glyphs = [cmap.get(ord(ch), ".notdef") for ch in text]
    adv = sum(gs[g].width for g in glyphs)
    n = max(1, len(glyphs) - 1)
    # trim side bearings of first/last glyph so ink edges hit x0/x1 exactly
    from fontTools.pens.boundsPen import BoundsPen
    def bounds(g):
        bp = BoundsPen(gs); gs[g].draw(bp); return bp.bounds
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


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="logo.svg")
    ap.add_argument("--preview", help="also render a PNG preview (white bg)")
    ap.add_argument("--text", action="append", default=[],
                    help="text line to re-set (repeat, top to bottom)")
    ap.add_argument("--weight", action="append", default=[],
                    help="font weight per --text line (default 400)")
    ap.add_argument("--font", action="append", default=[],
                    help="local .ttf/.otf/.woff per line (overrides --family)")
    ap.add_argument("--family", default="Montserrat",
                    help="@fontsource family to download (default Montserrat)")
    ap.add_argument("--color", help="override colour, e.g. #000000")
    ap.add_argument("--scale", type=int, default=12, help="trace upscale factor")
    ap.add_argument("--smooth", type=float, default=0.6,
                    help="blur before tracing, in source px (raise to 1.0-1.5 for "
                         "pixelated/jagged sources; too high rounds off details)")
    ap.add_argument("--pad", type=float, default=10, help="viewBox padding (px)")
    ap.add_argument("--fixed-size", action="store_true",
                    help="keep width/height attributes (default: viewBox only)")
    a = ap.parse_args()

    g, ink, bg, color = load_ink(a.input)
    color = a.color or color
    bands = row_bands(ink)
    nt = len(a.text)
    if nt > len(bands) - 1:
        sys.exit(f"Found {len(bands)} horizontal band(s) but {nt} --text line(s); "
                 f"need at least one band left for the graphic. Bands: {bands}")

    paths = []
    gfx = bands[:len(bands) - nt] if nt else bands
    gx0, gx1, gy0, gy1 = bbox(g, ink, bg, gfx[0][0], gfx[-1][1])
    paths.append(trace_region(g, gx0, gy0, gx1, gy1, a.scale, smooth=a.smooth))
    report = [f"graphic: traced region x{gx0}-{gx1} y{gy0}-{gy1}"]
    small = [b for b in gfx if b[1] - b[0] + 1 < 12]
    if small:
        report.append(f"WARNING: {len(small)} thin band(s) {small} were traced; if they "
                      f"are text they will look broken. Re-set them with --text.")

    for i, line in enumerate(a.text):
        y0, y1 = bands[len(bands) - nt + i]
        x0, x1, ty0, ty1 = text_extent(g, ink, bg, y0, y1)
        w = a.weight[i] if i < len(a.weight) else "400"
        font = a.font[i] if i < len(a.font) else (a.font[0] if a.font else
                                                   fetch_fontsource(a.family, w))
        paths.append(text_path(font, line, x0, x1, ty1, cap_px=ty1 - ty0))
        report.append(f"text {i+1}: '{line}' {os.path.basename(font)} cap {ty1-ty0:.1f}px")

    ys, xs = np.where(ink)
    p = a.pad
    vb = (xs.min() - p, ys.min() - p, xs.max() - xs.min() + 1 + 2 * p,
          ys.max() - ys.min() + 1 + 2 * p)
    vbs = " ".join(fmt(v) for v in vb)
    size = (f' width="{fmt(vb[2]*3)}" height="{fmt(vb[3]*3)}"' if a.fixed_size else "")
    title = os.path.splitext(os.path.basename(a.output))[0]
    body = "".join(f'<path d="{d}"/>' for d in paths)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vbs}"{size}>'
           f'<title>{title}</title><g fill="{color}" fill-rule="evenodd">{body}</g></svg>')
    with open(a.output, "w") as fh:
        fh.write(svg)
    report.append(f"wrote {a.output} ({len(svg)/1024:.1f} KB, colour {color})")

    if a.preview:
        import cairosvg
        bgrect = (f'<rect x="{fmt(vb[0])}" y="{fmt(vb[1])}" width="{fmt(vb[2])}" '
                  f'height="{fmt(vb[3])}" fill="#fff"/>')
        prev = svg.replace("<g ", bgrect + "<g ", 1)
        cairosvg.svg2png(bytestring=prev.encode(), write_to=a.preview, output_width=2000)
        report.append(f"wrote {a.preview}")
    print("\n".join(report))


if __name__ == "__main__":
    main()

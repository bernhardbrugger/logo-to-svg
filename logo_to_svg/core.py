"""logo-to-svg: turn a blurry flat-colour raster logo into a clean SVG.

The graphic is traced with potrace; text lines are re-set with a free font and converted to
paths, so the SVG looks identical everywhere.
"""
import os

import cv2
import numpy as np
import potrace
from PIL import Image

from .fonts import fetch_fontsource, has_lowercase, text_path
from .util import LogoError, fmt


# ---------------------------------------------------------------- analysis
def load_ink(path):
    """Return (gray float image, boolean ink mask, background level, ink colour hex)."""
    g, ink, bg, colour, _ = _load(path)
    return g, ink, bg, colour


def _load(path):
    """load_ink plus the RGB image, for per-part colours."""
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
        raise LogoError("No ink found in image.")
    # Lenient mask: catches thin/light strokes (small text, JPEG exports).
    ink = g < bg - 0.3 * (bg - darkest)
    # drop JPEG speckles (tiny isolated blobs)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 3
    ink = keep[lab]
    return g, ink, bg, ink_colour(rgb, g, ink), rgb


def ink_colour(rgb, g, ink):
    """Hex colour of the ink: the median of its interior pixels.

    Edge pixels are blended with the background and, in sharpened or JPEG exports, often
    overshoot darker than the real ink, so they are left out by eroding the mask one pixel.
    Strokes too thin to have an interior fall back to the darkest half of the ink pixels.
    """
    core = cv2.erode(ink.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    if core.sum() < 10:
        cut = np.percentile(g[ink], 50)
        core = ink & (g < cut)
        if not core.any():   # flat, non-antialiased ink: every pixel equals the median
            core = ink & (g <= cut)
    col = np.median(rgb[core], axis=0).round().astype(int)
    return "#%02X%02X%02X" % tuple(col)


def _rgb(hex_colour):
    return np.array([int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)], np.float32)


def solid_colour(rgb, part):
    """Median colour of a part's solid interior (strokes at least 5 px wide), or None if the
    part is too thin to have one."""
    solid = cv2.erode(part.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    return _hex(np.median(rgb[solid], axis=0)) if solid.sum() >= 20 else None


def part_colour(rgb, g, part, known, tol=30):
    """Colour of one part of the logo (the graphic or one text band).

    known - colours measured elsewhere in the logo, most trusted first (the overall ink colour,
            then the solid parts). A part that matches one of them gets exactly that colour, so a
            single-colour logo keeps exactly one colour.

    Thin strokes (small or light text) never reach their full ink colour: every pixel is blended
    with the background, so measuring them directly comes out far too light. A part is therefore
    measured directly only if it has a solid interior. A thin part takes the first known colour
    whose blends with the background its pixels are; only if none fits does it get its own
    colour, from its darkest pixels.
    """
    own = solid_colour(rgb, part)
    if own is not None:
        near = [c for c in known if np.linalg.norm(_rgb(c) - _rgb(own)) <= tol]
        return near[0] if near else own
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    paper = np.median(border, axis=0)
    v = rgb[part] - paper
    for c in known:
        d = _rgb(c) - paper
        t = np.clip(v @ d / max(float(d @ d), 1.0), 0, 1.15)  # no darker than the candidate
        if np.median(np.linalg.norm(v - t[:, None] * d, axis=1)) <= tol / 2:
            return c
    darkest = part & (g <= np.percentile(g[part], 10))
    return _hex(np.median(rgb[darkest], axis=0))


def _hex(col):
    return "#%02X%02X%02X" % tuple(np.clip(np.round(col), 0, 255).astype(int))


def row_bands(ink, min_gap=3):
    """Horizontal bands of rows containing ink: list of (y0, y1) inclusive."""
    rows = np.where(ink.any(axis=1))[0]
    bands, start, prev = [], rows[0], rows[0]
    for r in rows[1:]:
        if r - prev > min_gap:
            bands.append((start, prev))
            start = r
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
def trace_region(g, x0, y0, x1, y1, scale=12, pad=4, smooth=0.6):
    """Trace a rectangular region of the grey image into SVG path data (Bezier curves)."""
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
            xs = [p.x for p in pts]
            ys = [p.y for p in pts]
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


# ---------------------------------------------------------------- main API
def vectorize(input_path, output_path, texts=(), weights=(), fonts=(), family="Montserrat",
              color=None, scale=12, smooth=0.6, pad=10, fixed_size=False, preview=None, fit="auto"):
    """Vectorize `input_path` into `output_path`. Returns a list of report lines.

    texts   - text lines to re-set, top to bottom (matched to the bottom-most bands)
    weights - font weight per text line (default "400")
    fonts   - local font files per line (override `family`)
    fit     - "caps" (cap height = band height), "bounds" (ascenders to descenders = band height,
              for mixed case) or "auto" (bounds if the line contains lowercase letters)
    """
    if fit not in ("auto", "caps", "bounds"):
        raise LogoError(f"fit must be auto, caps or bounds, not {fit!r}")
    g, ink, bg, detected, rgb = _load(input_path)
    bands = row_bands(ink)


    nt = len(texts)
    if nt > len(bands) - 1:
        raise LogoError(f"Found {len(bands)} horizontal band(s) but {nt} --text line(s); "
                        f"need at least one band left for the graphic. Bands: {bands}")

    paths = []
    gfx = bands[:len(bands) - nt] if nt else bands
    # one colour per part (graphic, then each text line), unless --color overrides them all
    parts = [(gfx[0][0], gfx[-1][1])] + bands[len(bands) - nt:]
    if color:
        colours = [color] * len(parts)
    else:
        masks = []
        for y0, y1 in parts:
            m = np.zeros_like(ink)
            m[y0:y1 + 1] = ink[y0:y1 + 1]
            masks.append(m)
        known = [detected] + [c for c in (solid_colour(rgb, m) for m in masks) if c]
        colours = []
        for m in masks:   # a colour found on a thin line is offered to the lines after it
            colours.append(part_colour(rgb, g, m, known))
            if colours[-1] not in known:
                known.append(colours[-1])
    gx0, gx1, gy0, gy1 = bbox(g, ink, bg, gfx[0][0], gfx[-1][1])
    paths.append(trace_region(g, gx0, gy0, gx1, gy1, scale, smooth=smooth))
    report = [f"graphic: traced region x{gx0}-{gx1} y{gy0}-{gy1}"]
    small = [b for b in gfx if b[1] - b[0] + 1 < 12]
    if small:
        report.append(f"WARNING: {len(small)} thin band(s) {small} were traced; if they "
                      f"are text they will look broken. Re-set them with --text.")

    for i, line in enumerate(texts):
        y0, y1 = bands[len(bands) - nt + i]
        x0, x1, ty0, ty1 = text_extent(g, ink, bg, y0, y1)
        w = weights[i] if i < len(weights) else "400"
        font = fonts[i] if i < len(fonts) else (fonts[0] if fonts else fetch_fontsource(family, w))
        use_bounds = fit == "bounds" or (fit == "auto" and has_lowercase(line))
        if use_bounds:
            paths.append(text_path(font, line, x0, x1, ty1, fit_box=(ty0, ty1)))
            how = "ascender-to-descender fit"
        else:
            paths.append(text_path(font, line, x0, x1, ty1, cap_px=ty1 - ty0))
            how = f"cap {ty1 - ty0:.1f}px"
        report.append(f"text {i + 1}: '{line}' {os.path.basename(font)} {how}")

    ys, xs = np.where(ink)
    p = pad
    vb = (xs.min() - p, ys.min() - p, xs.max() - xs.min() + 1 + 2 * p,
          ys.max() - ys.min() + 1 + 2 * p)
    vbs = " ".join(fmt(v) for v in vb)
    size = (f' width="{fmt(vb[2] * 3)}" height="{fmt(vb[3] * 3)}"' if fixed_size else "")
    title = os.path.splitext(os.path.basename(output_path))[0]
    if len(set(colours)) == 1:
        body = "".join(f'<path d="{d}"/>' for d in paths)
        group = f'<g fill="{colours[0]}" fill-rule="evenodd">{body}</g>'
        used = f"colour {colours[0]}"
    else:   # e.g. an icon in the brand colour above dark text: one fill per part
        body = "".join(f'<path fill="{c}" d="{d}"/>' for c, d in zip(colours, paths))
        group = f'<g fill-rule="evenodd">{body}</g>'
        used = "colours " + ", ".join(
            f"{name} {c}" for name, c in
            zip(["graphic"] + [f"text {i + 1}" for i in range(nt)], colours))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vbs}"{size}>'
           f'<title>{title}</title>{group}</svg>')
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    report.append(f"wrote {output_path} ({len(svg) / 1024:.1f} KB, {used})")

    if preview:
        try:
            import cairosvg
        except (ImportError, OSError) as e:  # OSError: the native Cairo library is missing
            raise LogoError(f"--preview needs cairosvg and the Cairo library ({e}). "
                            f"Install with: pip install cairosvg") from e
        bgrect = (f'<rect x="{fmt(vb[0])}" y="{fmt(vb[1])}" width="{fmt(vb[2])}" '
                  f'height="{fmt(vb[3])}" fill="#fff"/>')
        prev = svg.replace("<g ", bgrect + "<g ", 1)
        cairosvg.svg2png(bytestring=prev.encode(), write_to=preview, output_width=2000)
        report.append(f"wrote {preview}")
    return report

---
name: logo-to-svg
description: Turn a blurry raster logo (PNG/JPG, e.g. from Canva or AI tools) into a clean, scalable SVG for free: trace the graphic, re-set the text as paths.
---

# Logo to SVG (raster → clean vector)

Turn a low-resolution, single-color logo into an SVG that works for web and print, using only free, open-source tools. The graphic is traced with potrace; text is re-set with a free font and converted to paths, so it renders identically everywhere.

**Good fit:** line-art logos, flat shapes, one color. **Poor fit:** gradients, photos, multiple colors – say so honestly and suggest a redesign instead.

Reply in the user's language.

## Workflow

1. **Install dependencies** (once per environment):
   `pip install potracer opencv-python-headless pillow numpy fonttools brotli cairosvg`
   (add `--break-system-packages` if the environment requires it; `npm` is needed for automatic font download)

2. **Look at the logo** and note, top to bottom, every text line exactly as written (case, punctuation, spacing). Estimate the font weight per line (300 = light, 400 = regular, 600 = semibold, 700 = bold) and pick a similar free font family available on Fontsource (default: Montserrat). Never guess the text of an unreadable line – ask the user.

3. **Run the script** (`scripts/vectorize.py`, relative to this skill folder):
   ```
   python scripts/vectorize.py logo.png -o logo.svg --preview preview.png \
       --text "COMPANY NAME" --weight 600 \
       --text "TAGLINE" --weight 300
   ```
   - Text lines are matched to the bottom-most horizontal bands of the image, in order. Everything above them is traced as the graphic.
   - Without `--text`, everything is traced. Fine for large lettering; small text (< ~12 px) breaks – the script prints a warning, then re-run with `--text`.
   - If the traced lines look jagged/stair-stepped (source exported without antialiasing), re-run with `--smooth 1.2` (up to ~1.5; higher rounds off fine details).
   - ALL-CAPS lines are sized by cap height; lines with lowercase letters are sized from ascender to descender (`--fit auto`, override with `--fit caps` or `--fit bounds`).
   - Options: `--family "Josefin Sans"`, `--font file.ttf` (local font, per line), `--color "#000000"`, `--pad 10`, `--fixed-size`.

4. **Check the preview** by viewing `preview.png` next to the original. Look for: line traced (not a filled box with a hole – the script auto-corrects polarity, but verify), text aligned and same width as original, weight close to original. Adjust weight/family and re-run if needed.

5. **Deliver** the SVG (transparent background, viewBox only, no fixed size) plus the preview. Briefly state what was done (traced, font used, color) and offer variants: white version for dark backgrounds (`--color "#FFFFFF"`), symbol only for a favicon, text beside the symbol.

## Limits to mention honestly
- Irregularities in the source image carry over into the trace.
- The re-set font is a close match, not the original (unless the user supplies it via `--font`).
- Single color only.

## Tone
Short, friendly, encouraging.

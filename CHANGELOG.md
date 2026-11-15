# Changelog

## Unreleased
- **New:** the graphic and each text line get their own colour, so a logo with an icon in the brand colour above dark text no longer comes out in one mixed colour. Thin text, which never reaches its full ink colour in a raster export, takes the colour of the part it is a blend of. Single-colour logos still get one fill, and the SVG for them is unchanged byte for byte. `--color` still sets one colour for everything.
- **Fix:** the detected colour came out too dark on logos with a darker edge (sharpened or JPEG exports): the README example with ink `#1F4037` gave `#15372E`. The colour is now the median of the ink's interior pixels; strokes too thin to have an interior keep the previous rule.
- **Fix:** `--preview` without `cairosvg` wrote the SVG, then exited with an error and no report, so it looked as if nothing was produced (the skill workflow uses `--preview` by default). The dependency is now checked first: the run stops before any work and says to install `cairosvg` or drop `--preview`.

## 0.2.0
- **Fix:** automatic font download failed on Windows (`npm` is `npm.cmd` there and could not be launched). It now resolves npm properly and gives a clear message if Node.js is missing.
- **Fix:** logos with flat, non-antialiased ink produced an invalid fill colour (`#-8000…`).
- **New:** lines with lowercase letters are sized from ascender to descender (`--fit auto|caps|bounds`); previously only ALL-CAPS text was supported.
- **New:** installable package with a `logo-to-svg` command and a Python API (`from logo_to_svg import vectorize`); `scripts/vectorize.py` stays as the entry point for the Claude skill.
- Font packages are extracted with a path check; output is written as UTF-8; errors are plain messages instead of tracebacks.
- Tests (27, no network needed). CI runs the tests on Linux and Windows (`.github/workflows/ci.yml`).
- SVG output for existing inputs is unchanged byte for byte.

## 0.1.0
- First version as a Claude skill with `scripts/vectorize.py`.

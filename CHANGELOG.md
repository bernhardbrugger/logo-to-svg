# Changelog

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

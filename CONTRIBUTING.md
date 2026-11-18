# Contributing to logo-to-svg

Bug reports with a logo that comes out wrong are the most useful contribution. Pull requests are welcome too.

## Set up and run the tests

```bash
git clone https://github.com/bernhardbrugger/logo-to-svg
cd logo-to-svg
python -m venv .venv            # .venv/Scripts/activate on Windows, source .venv/bin/activate elsewhere
pip install -e ".[dev]"
pytest -q                       # or a single file: pytest -q tests/test_core.py
```

The tests need no network, npm or system fonts: `tests/conftest.py` builds a tiny font and synthetic logos. CI runs the same `pytest` on Linux and Windows with Python 3.9 and 3.12, so do not use syntax newer than 3.9.

To try a change by hand, `logo-to-svg examples/before.png -o out.svg --text "..."` uses the installed package, and `python scripts/vectorize.py ...` is the same command as the Claude skill runs it (from a copied folder, without installing). Both must keep working.

## Reporting a bug

Open an issue with:

- the logo (or a cut-down version that still shows the problem) and the exact command you ran,
- what you expected and what you got (the SVG, or a screenshot of it next to the original),
- `logo-to-svg --version`, your Python version and OS.

If the logo is not yours to share, say so; a synthetic image with the same problem works just as well.

## Pull requests

- One change per pull request, with a test that fails without it. For output changes, say whether the SVG for existing inputs stays the same byte for byte; the changelog has noted this for every release so far.
- Add a line under `## Unreleased` in `CHANGELOG.md` when users would notice the change.
- Keep the dependencies small. A new one needs a good reason; anything that needs a native library (like `cairosvg` for `--preview`) stays optional and is checked before any work starts.
- Commit messages say what changed and why, in the imperative ("Fix ...", "docs: ...").

## Out of scope

Multi-colour graphics, gradients and photos are listed under Limits in the README. A pull request that changes that is welcome, but please open an issue first so we can agree on the approach.

By contributing you agree that your work is released under the MIT licence of this project.

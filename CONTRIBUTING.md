# Contributing to lumen-napari

Thanks for helping. Bug reports, examples of images it gets wrong, docs fixes and code are all welcome.

## Report a problem

Open an [issue](https://github.com/holoviz-topics/lumen-napari/issues) with:

- what you asked in the chat, and what happened instead;
- the outline image from the chat's napari message, if segmentation looks wrong;
- the image type (fluorescence, brightfield, tissue, 3D, plate...) and, if you can share it, a small example image;
- your versions: `python -c "import lumen, napari, lumen_napari; print(lumen.__version__, napari.__version__)"` and the LLM provider.

Never paste API keys into issues, logs or screenshots.

## Set up

```bash
git clone https://github.com/holoviz-topics/lumen-napari.git
cd lumen-napari
uv venv && uv pip install -e ".[qt,test,docs]"
```

lumen-napari tracks the `main` branches of Lumen and napari. Reinstall them when upstream changes: `uv pip install --reinstall-package lumen --reinstall-package napari -e ".[qt,test]"`.

## Run the tests and checks

```bash
pytest                 # needs a display; on headless Linux: xvfb-run -a pytest
ruff check src tests
mkdocs build --strict  # the docs
```

CI runs the same three on every pull request.

## Make a change

1. Branch from `main`.
2. Write a failing test first, then the code. Tests live in `tests/`, one file per module.
3. Keep changes small and commit often, with short conventional messages: `fix: ...`, `feat: ...`, `docs: ...`, `test: ...`.
4. Update the docs page the change affects, under `docs/`.
5. Open a pull request saying what changed and why, with a before and after screenshot for anything visible.

## How the code is laid out

| Module | What it does |
|---|---|
| `segment.py` | Segmentation methods, automatic method and object detection |
| `measure.py` | One table row per object, with units |
| `controls.py` | The chat actions that make tables (segment, measure, folders, regions, whole slides) |
| `tools.py` | The chat tools that act on napari (show, color, filter, pixel size, compare) |
| `app.py` | Builds the Lumen app and the server |
| `upload.py`, `files.py` | Uploaded files and file metadata |
| `batch.py`, `plate.py`, `stats.py` | Folders, plates and statistics |
| `region.py`, `tiles.py` | Large images and whole slides |
| `widget.py` | The napari dock |

[How it works](https://holoviz-topics.github.io/lumen-napari/explanation/how_it_works/) explains the threads, the shared database and the click-back.

## Writing style

Code follows the surrounding code: short functions, docstrings that say what and why, few comments. Docs are written for scientists, not programmers: plain words, real example questions, and numbers you can check.

## License

By contributing you agree that your contributions are licensed under the BSD 3-Clause license of this project.

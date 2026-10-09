# Installation

lumen-napari needs Python 3.11 or newer. It currently installs Lumen and napari from their `main` branches.

## Install

=== "pip"

    ```bash
    pip install "lumen-napari[qt] @ git+https://github.com/holoviz-topics/lumen-napari.git"
    ```

=== "uv"

    ```bash
    uv pip install "lumen-napari[qt] @ git+https://github.com/holoviz-topics/lumen-napari.git"
    ```

The `qt` extra installs PyQt6, which napari needs to open a window. Leave it out if your environment already has a Qt binding (PyQt5, PySide2 or PySide6).

!!! tip "Use a fresh environment"
    napari and the deep learning extras pull in many packages. A new virtual environment or conda environment avoids version clashes with other projects.

## Optional extras

Add extras in the brackets, separated by commas, for example `lumen-napari[qt,cellpose,bioio]`.

| Extra | Installs | Gives you |
|---|---|---|
| `qt` | PyQt6 | A Qt binding for the napari window |
| `cellpose` | `cellpose>=4` | The `cellpose` segmentation method |
| `stardist` | `stardist`, `tensorflow` | The `stardist` segmentation method |
| `bioimageio` | `bioimageio.core` | Models from the [BioImage.IO](https://bioimage.io) zoo |
| `bioio` | `bioio`, `bioio-ome-tiff`, `bioio-ome-zarr` | Channel names, pixel size and plate wells from OME-TIFF and OME-Zarr files |

For CZI, ND2 or LIF files, install the matching bioio reader as well: `bioio-czi`, `bioio-nd2` or `bioio-lif`.

Otsu segmentation needs no extra. When you ask for a method that is not installed, the chat says which extra to add.

## Check the install

```bash
python -c "import lumen_napari, napari, lumen; print('ok')"
napari
```

In napari, the **Plugins** menu should list **Ask Lumen**, and **File > Open Sample** should list **Lumen**.

## Set up an LLM

Lumen needs a large language model. The quickest way is an API key in your environment, set before you start napari:

```bash
export OPENAI_API_KEY=sk-...
```

See [Choosing an LLM](llm.md) for other providers and local models.

## Development install

```bash
git clone https://github.com/holoviz-topics/lumen-napari.git
cd lumen-napari
uv venv && uv pip install -e ".[qt,test]"
pytest
```

The test suite needs a display for the Qt tests. On a headless Linux machine, run it under `xvfb-run -a pytest`.

To build these docs locally:

```bash
uv pip install -e ".[docs]"
mkdocs serve
```

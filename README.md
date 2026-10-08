# lumen-napari

Ask questions about your napari images in plain language.

lumen-napari connects [napari](https://napari.org) to [Lumen](https://github.com/holoviz/lumen), an AI data explorer. You ask "how many nuclei are there and how big are they?", Lumen segments the image in your napari viewer, measures every object into a table and answers with SQL and charts. Each answer can jump back to the exact object in napari.

```
"Segment the nuclei layer, then tell me how many objects there are and their mean area"

  napari   adds a `nuclei labels` layer, every object measured
  Lumen    "It found 354 objects, with a mean area of 83.94."
```

## What it does

- **Segment** an image layer (Otsu with watershed splitting, or Cellpose) and add the result as a labels layer.
- **Measure** every object (area, centroid, bounding box, shape, intensity) in physical units taken from the layer scale. Measurements are also stored on the labels layer, so hovering an object in napari shows its values.
- **Load features** that other plugins wrote on points, shapes, labels, tracks, surface or vectors layers.
- **Large images** (OME-Zarr, multiscale, dask) are read at the finest pyramid level that fits in memory, or only for the region on screen at full detail ("segment what I'm looking at"). Only the needed chunks are read.
- **Batch** a whole folder or plate into one table without opening each image. Rows are keyed by `image_id` and by `well` when file names contain one (`plate1_B02_s1.tif`). OME-TIFF, OME-Zarr and CZI files (with the `[bioio]` extra) supply their own channel names, pixel size and plate well, so sizes come out in micrometers with no setup. Pass a plate map (`.csv`, `.tsv`, `.xlsx`, `.parquet` with a `well` or `image_id` column) to join compounds and doses onto every object.
- **Ask** follow-up questions in plain language. Lumen writes the SQL and charts, and you can upload a CSV (a plate map, treatments) to join with the measurements.
- **Show** any object in napari: "show me the largest nucleus" zooms the viewer to it and selects it.
- **Plate heatmap** of any per-well measurement on a 96 or 384 well layout. Clicking a well opens its image in napari.
- **Color** objects by any measurement ("color nuclei by area"), a heatmap on the image itself.
- **Filter** what napari shows with a SQL condition ("hide objects smaller than 50 µm²"), in place or as a new labels layer.
- **Regions**: draw shapes in napari and ask about them ("compare nuclear density inside vs outside the region I drew").
- **Hand corrections flow back**: painting, filling or erasing a measured labels layer, or moving points, re-measures it and updates the tables the chat queries.
- **Click back** from a chart: ask to "explore the objects" for a scatter of every object. Clicking a point zooms napari to that object.
- **Export** the segmentation and measurement steps as a Python script with **Export script** in the dock, so the analysis can be rerun without the chat.

## Install

lumen-napari currently tracks the `main` branches of Lumen and napari.

```bash
pip install "lumen-napari[qt] @ git+https://github.com/ghostiee-11/lumen-napari.git"
```

Add `[cellpose]` for the Cellpose segmentation method and `[bioio]` to read metadata from OME-TIFF and OME-Zarr files (install `bioio-czi` too for CZI).

Lumen needs an LLM. Set the key for your provider before starting napari, for example:

```bash
export OPENAI_API_KEY=...
```

Lumen supports OpenAI, Anthropic, Google, Mistral, Azure, Ollama, llama.cpp and other providers. See the [Lumen docs](https://lumen.holoviz.org).

## Use

1. Open napari and load an image, or try **File > Open Sample > Lumen > HeLa nuclei (2D)**.
2. Open **Plugins > Ask Lumen** and click **Start Lumen**. The chat opens in your browser.
3. Ask, for example:
   - "Segment the nuclei layer and plot the distribution of object area"
   - "Which objects are the brightest? Show the top one in napari"
   - "Plot area against mean intensity for every object"
   - "Explore the objects and click one to see it in napari"
   - "Color the nuclei by area, then hide the ones smaller than 50 µm²"
   - "Segment every image in ~/data/plate1 with the plate map ~/data/plate1_map.csv. Which compounds shrink nuclei compared to DMSO?"

The chat server only listens on `localhost`, and it stops when napari closes.

## From Python

```python
import napari
from lumen_napari.app import LumenServer

viewer = napari.Viewer()
viewer.open_sample("lumen-napari", "mitosis")
server = LumenServer(viewer)
print(server.start())
napari.run()
```

## Development

```bash
uv venv && uv pip install -e ".[qt,test]"
pytest
```

## License

BSD 3-Clause

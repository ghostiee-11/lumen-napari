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
- **Ask** follow-up questions in plain language. Lumen writes the SQL and charts, and you can upload a CSV (a plate map, treatments) to join with the measurements.
- **Show** any object in napari: "show me the largest nucleus" zooms the viewer to it and selects it.
- **Click back** from a chart: ask to "explore the objects" for a scatter of every object. Clicking a point zooms napari to that object.
- **Export** the segmentation and measurement steps as a Python script with **Export script** in the dock, so the analysis can be rerun without the chat.

## Install

lumen-napari currently tracks the `main` branches of Lumen and napari.

```bash
pip install "lumen-napari[qt] @ git+https://github.com/ghostiee-11/lumen-napari.git"
```

Add `[cellpose]` for the Cellpose segmentation method.

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

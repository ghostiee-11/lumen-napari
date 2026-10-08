# Use from Python

Everything the chat does is plain Python underneath. Use it to start the chat from a script or notebook, or skip the chat and call the functions yourself.

## Start the chat from a script

```python
import napari
from lumen_napari.app import LumenServer

viewer = napari.Viewer()
viewer.open_sample("lumen-napari", "mitosis")

server = LumenServer(viewer, port=5050)
print(server.start())  # http://localhost:5050
napari.run()
```

`LumenServer` runs the chat on a background thread, listening only on `127.0.0.1`. Without `port`, a free port is picked. Keyword arguments go to Lumen's `ExplorerUI`, so you can set the LLM, title, suggestions and more:

```python
from lumen.ai.llm import ClaudeCode

server = LumenServer(viewer, llm=ClaudeCode(), title="Nuclei screen")
```

Call `server.stop()` to stop it. `server.script` holds the recorded steps, questions and charts.

## Embed the chat in your own Panel app

`build_ui` returns the Lumen `ExplorerUI` bound to a viewer:

```python
from lumen_napari.app import build_ui

ui = build_ui(viewer)
ui.servable()
```

## Segment and measure without the chat

```python
from skimage import data
from lumen_napari.measure import measure, to_features
from lumen_napari.segment import segment

image = data.human_mitosis()
labels = segment(image, method="otsu", min_size=20)
table = measure(labels, image, spacing=(0.65, 0.65), unit="um")
table[["label", "area_um2", "intensity_mean"]].describe()

viewer.add_labels(labels, features=to_features(table), scale=(0.65, 0.65))
```

## A whole plate

```python
from pathlib import Path
import pandas as pd
from lumen_napari.batch import join_plate_map, measure_files
from lumen_napari.stats import compare

files = sorted(Path("~/data/plate1").expanduser().glob("*.tif"))
objects = measure_files(files, method="otsu", min_size=20)
objects = join_plate_map(objects, pd.read_csv("~/data/plate1_map.csv"))
compare(objects, "area", "compound", "DMSO", replicate="well")
```

## Large images

```python
from lumen_napari.region import choose_level, load_region, visible_region
from lumen_napari.tiles import segment_tiled

layer = viewer.layers["slide"]
level = choose_level(layer)                       # finest level under 50 M pixels
image, scale, translate = load_region(layer, level)

region = visible_region(layer)                    # what is on screen, full-res pixels
image, scale, translate = load_region(layer, 0, region)

table, n_tiles = segment_tiled(layer, tile=2048)  # every object, tile by tile
```

See the [Python API reference](../reference/api.md) for every function.

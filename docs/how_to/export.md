# Export a script or report

A chat is not a method section. lumen-napari records what it did, so you can rerun the analysis without the chat and share it with people who were not there.

## Export a script

Click **Export script** in the **Ask Lumen** dock and choose a file name.

The script is plain Python. It opens the same images, segments them with the same settings, measures them and rebuilds every table into a `tables` dictionary:

```python
"""Reproduces the lumen-napari steps run on this viewer."""

import napari
import pandas as pd

from lumen_napari.controls import intensity
from lumen_napari.measure import measure, to_features
from lumen_napari.region import load_region
from lumen_napari.segment import segment

viewer = napari.Viewer()
tables = {}
viewer.open('/data/hela.tif')[0].name = 'hela'
image, scale, translate = load_region(viewer.layers['hela'], level=0, region=None)
labels = segment(image, method='otsu', min_size=20, split_touching=True, model='')
table = tables['hela_labels'] = measure(labels, image, spacing=scale, unit='um', origin=translate, channels={})
viewer.add_labels(labels, name='hela labels', features=to_features(table), scale=scale, translate=translate)

napari.run()
```

Run it with `python analysis.py`. It needs lumen-napari installed but no LLM.

What the script records:

| Step | Recorded |
|---|---|
| Segment, measure, whole slide | Yes, with every setting |
| Segment a folder, plate map | Yes |
| Load a table, compare conditions | Yes |
| Layers opened from a file | `viewer.open(path)` |
| Layers made in memory (samples, uploads from Python) | A comment where to load them |
| Hand edits | A comment to save the edited layer |
| Drawn regions | A comment; save the shapes layer |
| SQL queries and charts | No; they are in the report |

## Export a report

Click **Export report** to save one HTML file to send to a colleague or attach to a lab notebook. It contains:

1. **Questions** you asked in the chat, in order.
2. **napari**: a snapshot of the canvas when you exported.
3. **Steps and checks**: every napari message from the chat, with the segmentation outlines.
4. **Charts**: Lumen's charts, interactive.
5. **Methods**: the reproducing script.

The file is standalone except for the chart libraries, which load from a CDN, so charts need an internet connection to display. Everything else, images included, is embedded.

## Lumen's own exports

Lumen's export menu in the chat still works for its own outputs, such as a notebook of the queries and charts.

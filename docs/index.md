# lumen-napari

**Ask questions about your napari images in plain language.**

lumen-napari connects [napari](https://napari.org), the multi-dimensional image viewer, to [Lumen](https://lumen.holoviz.org), the HoloViz AI data explorer. You type a question in a chat. Lumen segments the image open in napari, measures every object into a table, and answers with SQL, statistics and charts. Every answer links back to the pixels: click a point on a chart and napari zooms to that cell.

```text
You      How many nuclei are there, and how big are they?

napari   adds a `nuclei labels` layer, every object measured
Lumen    Segmented `nuclei`: 354 objects into table `nuclei_labels`.
         The mean area is 83.94 pixels.
```

## Why

napari is good at looking at pixels. Most questions a biologist asks are about populations: how many cells, how big, how bright, which treatment changed them, and which cell is the odd one out. Answering them usually means a segmentation script, a measurement script, a spreadsheet and a plotting notebook, glued together by hand.

lumen-napari puts that loop in one place:

1. **Segment** an image in napari (Otsu with watershed, Cellpose, StarDist or a BioImage.IO model).
2. **Measure** every object into a SQL table, in physical units.
3. **Ask** questions about the table: counts, distributions, comparisons, plate statistics.
4. **Look** at any object behind an answer: charts, tables and plate heatmaps click back to napari.
5. **Keep** the analysis: export a Python script that reruns it, or an HTML report to share.

## What you can do

| You ask | What happens |
|---|---|
| "Segment the nuclei and plot the distribution of area" | A labels layer appears in napari, a histogram in the chat |
| "Show me the largest nucleus" | napari zooms to it and selects it |
| "Color the nuclei by mean intensity" | The objects become a heatmap on the image |
| "Hide objects smaller than 50 µm²" | napari shows only the matches |
| "The pixel size is 0.65 µm" | Sizes are measured again in micrometers |
| "Explore the objects" | A scatter of every object; clicking a point zooms napari to it |
| "Segment every image in ~/plate1 with the plate map ~/map.csv" | One table for the whole plate, joined with compounds and doses |
| "Which compounds shrink nuclei compared to DMSO?" | Wells as replicates, fold change, z-score and Welch t-test |
| "Show a plate heatmap of nuclear area" | A 96 or 384 well heatmap; clicking a well opens its image |
| "Compare density inside and outside the region I drew" | Objects assigned to your drawn shapes |

You can also drop an image file (PNG, TIFF, OME-TIFF, CZI, ND2, LIF) into the chat. It opens in napari, segmented and measured, ready for questions.

## Where to go next

- New here? Start with [Installation](getting_started/installation.md) and the [Quickstart](getting_started/quickstart.md).
- Have a task in mind? The **How-to guides** cover each workflow, from [plates](how_to/plates.md) to [whole slides](how_to/large_images.md).
- Looking for a parameter or a column name? See the **Reference**: [chat actions and tools](reference/chat_actions.md), [measurement columns](reference/measurements.md), [file formats](reference/file_formats.md) and the [Python API](reference/api.md).
- Want to know how it works, or where it stops working? Read [How it works](explanation/how_it_works.md) and [Limitations](explanation/limitations.md).

## Status

lumen-napari is in early development (`0.1.0.dev0`). It tracks the `main` branches of Lumen and napari, so expect changes.

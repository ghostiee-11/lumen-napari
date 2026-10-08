# Quickstart

This walk-through takes five minutes. You open a sample image, start the chat, and ask your first questions.

## 1. Open napari and an image

```bash
export OPENAI_API_KEY=sk-...   # or another provider, see Choosing an LLM
napari
```

Open **File > Open Sample > Lumen > HeLa nuclei (2D)**. A layer called `nuclei` appears. It is the scikit-image `human_mitosis` image: about 350 fluorescent nuclei.

You can also open your own image with **File > Open**, or drag it onto the napari window.

## 2. Start the chat

Open **Plugins > Ask Lumen**. A dock with four buttons appears on the right of napari:

| Button | What it does |
|---|---|
| **Start Lumen** | Starts the chat server and opens it in your browser. Click again to stop it. |
| **Open in browser** | Opens the running chat again, for example after you closed the tab. |
| **Export script** | Saves the segmentation and measurement steps as a Python script. |
| **Export report** | Saves an HTML report with questions, checks, charts and a napari snapshot. |

Click **Start Lumen**. Your browser opens the chat at `http://localhost:<port>`. The server listens only on your own machine, and stops when napari closes.

## 3. Ask your first question

Type:

> How many nuclei are there and what is their mean area?

Three things happen:

1. napari gets a new layer, `nuclei labels`, with one color per object.
2. A **napari** message appears in the chat. It says what was segmented, with which settings, and shows the outlines on the image so you can check them.
3. Lumen answers: about 350 objects, and their mean area.

!!! note "Sizes are in pixels"
    The sample image has no pixel size, so the chat warns that areas are in pixels. Tell it the pixel size to measure in micrometers:

    > The pixel size is 0.65 µm

    The labels layer is measured again, and columns such as `area` become `area_um2`.

## 4. Keep asking

Each question builds on the table from the last one. Try:

- "Plot the distribution of nuclear area"
- "Show me the largest nucleus in napari"
- "Color the nuclei by mean intensity"
- "Hide the nuclei smaller than 50 µm²"
- "Explore the objects", then click a point in the scatter plot

Hover an object in napari: the status bar shows its measurements, because they are also stored on the labels layer.

## 5. Keep the analysis

Click **Export script** in the dock. The saved file opens the same images, segments them with the same settings and rebuilds every table, without the chat or an LLM:

```bash
python analysis.py
```

Click **Export report** for a single HTML page with your questions, the segmentation checks, the charts and the reproducing script.

## Next steps

- [Upload images](../how_to/upload_images.md) from the chat instead of napari.
- [Segment and measure](../how_to/segment.md): choose a method and check the result.
- [Screens and plates](../how_to/plates.md): a whole folder of images in one table.

# Limitations

lumen-napari is early software. These are the known limits, so you can judge when to trust it.

## Science

- **Check the segmentation.** Every number depends on it. Look at the outline image in the chat, or the labels in napari, before reading the statistics. Otsu is fast but fails on tissue, uneven illumination and crowded cells. With Cellpose installed, stained tissue switches to it automatically; for crowded fluorescence, ask for Cellpose.
- **Automatic object detection** (bright, dark, or cells inside walls) is a rule of thumb from the thresholded image. Check the outline image; say "the objects are dark" or "bright" to override it.
- **Otsu on folders uses one threshold per image.** Images with very different brightness are cut differently. Whole-slide segmentation, by contrast, uses one threshold for the whole slide.
- **Sizes in pixels** cannot be compared across instruments. Set a pixel size, or use files that carry one.
- **Statistics assume independent wells.** Plate effects (edge wells, rows, batches) are not corrected. A small number of wells gives weak tests; a condition with one well gets no test.
- **The LLM writes the SQL.** Lumen shows the query behind each answer; read it when a number matters.

## Data

- **Memory.** Plain segmentation reads at most 50 million pixels. Measuring an existing labels layer reads it, and its intensity image, at full resolution.
- **Whole slides** are 2D only, and objects are shown as points, not outlines.
- **Regions** work on 2D labels layers. Objects are assigned by centroid.
- **Time series** are not handled as time: bioio files are read at the first time point.
- **Pyramid levels** are assumed to be aligned at pixel corners; the half-pixel shift of downsampled levels is ignored.
- **Folders** keep at most 500 files by default (`max_files`), and are segmented one after another.

## The app

- **One viewer per process** receives chart clicks: the most recent one bound.
- **Uploaded files** stay in a temporary folder until you delete them.
- **Exported scripts** cannot replay hand edits, drawn regions or images created in memory. They leave a comment instead.
- **Reports** load the chart libraries from a CDN.
- **Subscription providers** (Claude Code, Codex, Copilot, Antigravity CLIs) are slower than API keys and cannot see images.
- **Lumen and napari `main`.** Changes upstream can break lumen-napari until it is updated.

## Privacy

Segmentation and measurement run locally. The LLM provider receives your questions, layer and column names, table summaries and query results. Use a [local model](../getting_started/llm.md#local-models) if that is not acceptable for your data.

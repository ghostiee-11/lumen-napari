# Large images and whole slides

napari can show images far larger than memory, such as OME-Zarr pyramids, multiscale TIFFs and dask arrays, by reading only the chunks on screen. lumen-napari does the same: it never loads more than it needs.

## Segment at the finest level that fits

> Segment the slide layer

For a multiscale image, lumen-napari picks the **finest pyramid level with at most 50 million pixels** and segments that. The chat reports the level used (`level=2`), and the labels layer is scaled and placed to sit exactly on the image.

To force a level (0 is full resolution):

> Segment the slide at level 1

If even the coarsest level is over the budget, the chat says so and asks you to zoom in.

## Segment what you are looking at

Zoom napari to the area you care about, then:

> Segment what I'm looking at

Only the region on screen is read, at the finest level that fits, often full resolution. Axes you are not viewing (z in a 2D view of a volume, for example) are kept whole. Centroids are in world coordinates, so the objects line up with the full image.

## Segment a whole slide at full resolution

For counting every cell of a whole-slide image at full resolution:

> Segment the whole slide

The image is processed in tiles of 2048 × 2048 pixels, so only one tile is in memory at a time:

1. **One threshold for the whole slide.** With Otsu, the threshold is computed once from a coarse view (the coarsest pyramid level, or a sample of about 4 million pixels), so tiles do not get different cut-offs.
2. **Overlapping tiles.** Each tile is read with 64 extra pixels on every side, so objects on a seam are seen whole.
3. **No double counting.** An object belongs to the tile its centroid falls in; copies in neighbouring tiles' margins are dropped.
4. **Unique labels.** Objects are renumbered across the slide.

The result is a table, `<image>_objects`, and a napari **points** layer with one orange point per object at its centroid (a full-resolution labels layer would not fit in memory). Clicking a chart point from this table centres napari on that position.

| Setting | Default | Meaning |
|---|---|---|
| `tile_size` | 2048 | Tile side in pixels; smaller uses less memory |
| `method`, `model`, `min_size`, `split_touching` | as in [Segment and measure](segment.md) | |

Whole-slide segmentation works on 2D images. RGB slides (H&E, for example) are converted to gray first; for stained tissue, `cellpose` or a BioImage.IO model will do better than Otsu.

## Which to use

| Image | Question | Use |
|---|---|---|
| Fits in memory | anything | plain segmentation |
| Large, need an overview | "roughly how many cells, where?" | finest level that fits |
| Large, one area matters | "what's in this region?" | segment what I'm looking at |
| Whole slide, every cell | "count every nucleus at full resolution" | whole slide |

# Segment and measure

Segmentation finds the objects (nuclei, cells, spots) in an image layer and adds them to napari as a labels layer. Measurement turns each object into one table row.

You rarely need to ask for segmentation directly. Any question about objects ("how many nuclei?", "color them by area") segments the first image layer when nothing is segmented yet. Ask explicitly when you want a specific layer, method or setting.

## Segment an image layer

> Segment the nuclei layer

lumen-napari then:

1. Reads the layer's pixels (RGB images are converted to gray).
2. Segments them and adds a labels layer named `<image> labels`, with the same scale and position as the image.
3. Measures every object and stores the table both in Lumen (as `<image>_labels`) and on the labels layer's `features`, so hovering an object in napari shows its values.
4. Posts a **napari** message in the chat with the settings, the object count, the units, and the outlines drawn on the image.

Look at the outlines before trusting the numbers. If they are wrong, ask again with other settings.

Asking for the same segmentation twice reuses the first result instead of recomputing it.

## Choose a method

Ask which methods are available:

> Which segmentation methods can I use?

| Method | Best for | Install |
|---|---|---|
| `otsu` | Bright, well separated nuclei on a dark background. Fast, no model. Fails on tissue, uneven lighting or crowding. | built in |
| `cellpose` | The best default for cells and nuclei in tissue, crowded or unevenly lit images. Cellpose 4, no diameter needed. | `[cellpose]` |
| `stardist` | Round, star-convex nuclei in fluorescence, 2D or 3D. | `[stardist]` |
| `bioimageio` | A specialised model from the [BioImage.IO](https://bioimage.io) zoo, given by its id. | `[bioimageio]` |

> Segment the nuclei with cellpose

> Segment the nuclei with the BioImage.IO model affable-shark

When Lumen chooses the method itself, it says why in the chat ("**Why cellpose:** the nuclei are crowded and unevenly lit").

### How Otsu works here

lumen-napari first looks at the image to decide what the objects are:

| The image | Detected as | Example |
|---|---|---|
| Bright objects on a dark background | bright objects, split where they touch | fluorescent nuclei, galaxies |
| A bright network spanning the image | dark cells inside walls, not split (the walls separate them) | plant tissue, membrane stains |
| Mostly bright | dark objects on a bright background | brightfield |

The chat says what it detected ("detected from the image: dark objects inside walls"). Say otherwise in plain words to override it. Then:

1. In 3D, the volume is smoothed (Gaussian, sigma 2) first, so textured nuclei do not shatter into pieces. 2D images are not smoothed.
2. Pixels brighter than Otsu's threshold are foreground; holes are filled.
3. Objects smaller than `min_size` pixels are dropped.
4. With `split_touching` (on by default), touching objects are split by a watershed on the distance transform. Seeds stay at least 0.8 of the median object radius apart, so objects split where they touch but do not over-split.

### Deep learning methods

- **Cellpose** runs `CellposeModel` on the CPU.
- **StarDist** uses `2D_versatile_fluo` for 2D and `3D_demo` for 3D unless you name another model. Images are normalised to the 1st and 99.8th percentile first.
- **BioImage.IO** models that output labels are used as is. Models that output a foreground probability are thresholded at 0.5 and split with a watershed.

## Settings

Say them in plain language, or name them:

| Setting | Default | Meaning |
|---|---|---|
| `method` | `otsu` | See above |
| `model` | empty | StarDist model name or BioImage.IO id |
| `min_size` | 20 | Drop objects with fewer pixels |
| `split_touching` | from the image | Watershed split of touching objects (Otsu only) |
| `visible_only` | off | Segment only what is on screen, see [Large images](large_images.md) |
| `level` | finest that fits | Pyramid level of a multiscale image, 0 is full resolution |
| `measure_layers` | none | Other channels to measure intensity in |
| `dark_objects` | from the image | Find dark objects, such as cells outlined by bright walls (Otsu only) |

> Segment the nuclei with min_size 50 and without splitting touching objects

## Cells outlined by walls or membranes

Plant tissue and membrane stains show bright walls around dark cells. This is detected automatically, so just ask:

> How many cells are in lily-blue?

Try it on **File > Open Sample > Lumen > Lily stem cells (4 channels)**: about 1,700 cells, with `lily-green` marking the lignified walls of the vascular bundles. Very dim corners can merge into a few large objects; hide them with a size filter.

## Measure more channels

Every other image layer that lines up with the segmented one (same shape, scale and position, such as the other channels of one file) is measured automatically. Name channels to pick only some:

> Segment the dapi layer and measure the actin and tubulin layers too

Each extra channel adds `intensity_mean_<layer>`, `intensity_min_<layer>` and `intensity_max_<layer>` columns. See [Measurement columns](../reference/measurements.md).

## Measure an existing labels layer

Labels drawn by hand, or made by another plugin, can be measured without segmenting:

> Measure the cells layer with intensities from the gfp layer

If the labels layer is named `<image> labels` and you name no image, intensities come from that image.

## Load features from other plugins

Points, shapes, labels, tracks, surface and vectors layers can carry a `features` table, written by plugins such as napari-clusters-plotter or a tracker. Load it as a Lumen table:

> Load the features of the tracks layer

For points and other layers with coordinates, the table gets `position_0`, `position_1`... columns. Moving points re-loads the table.

## Color images

RGB images (photos, H&E and IHC slides, astronomy) are segmented in gray, and each object also gets `intensity_mean_red`, `intensity_mean_green` and `intensity_mean_blue`, so you can ask "which galaxies are the reddest?". Stained tissue segments much better with `cellpose` than with Otsu.

## Images it cannot segment

- **Blank or empty images:** the chat says no objects were found and what to try.
- **Missing pixels (NaN)** are treated as background.
- **4D and higher** (time and z together): open one time point as its own layer first.

## 3D images

Volumes are segmented and measured in 3D. `area` becomes `volume`, perimeter, eccentricity and solidity are left out, and the check image shows the slice with the most objects. Try **File > Open Sample > Lumen > Mouse embryo nuclei (3D)**, which has a voxel size of 0.29 × 0.26 × 0.26 µm.

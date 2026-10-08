# Chat actions and tools

The LLM answers by calling these actions and tools. You do not call them directly; ask in plain language and Lumen picks one. Knowing them helps you phrase a question, or name a setting.

**Actions** create or replace a table. Each table is added to one DuckDB database per chat session, so every table stays queryable and joinable with SQL. **Tools** act on napari and report what they did.

Layer names can be given as the layer name (`nuclei labels`) or its table name (`nuclei_labels`). Where a tool needs a labels layer, the image name (`nuclei`) also works.

## Actions

### Segment Layer

Find the objects in an image layer, add a labels layer and measure each object. Guide: [Segment and measure](../how_to/segment.md).

| Parameter | Type | Default | |
|---|---|---|---|
| `image_layer` | str | required | Image layer to segment |
| `method` | `auto`, `otsu`, `cellpose`, `stardist`, `bioimageio` | `auto` | `auto` picks from the image |
| `model` | str | `""` | StarDist model or BioImage.IO id |
| `reason` | str | `""` | Why this method fits, shown in the chat |
| `min_size` | int | 20 | Drop objects with fewer pixels |
| `split_touching` | bool | from the image | Watershed split (Otsu only) |
| `visible_only` | bool | `False` | Only the region on screen |
| `level` | int | -1 | Pyramid level; -1 picks the finest that fits |
| `measure_layers` | list[str] | aligned layers | More channels to measure intensity in |
| `dark_objects` | bool | from the image | Dark objects inside walls or on a bright background (Otsu only) |

Adds layer `<image> labels`. Table: `<image>_labels`.

### Measure Layer

Measure an existing labels layer. If there is no labels layer yet, segments the image instead.

| Parameter | Type | Default | |
|---|---|---|---|
| `labels_layer` | str | required | Labels layer to measure |
| `image_layer` | str | the labels' source image | Image for intensities |
| `measure_layers` | list[str] | none | More channels |

Table: `<labels layer>` as a table name.

### Layer Features

Load the `features` of a labels, points, shapes, tracks, surface or vectors layer. Points and other coordinate layers get `position_0`, `position_1`... columns.

| Parameter | Type | |
|---|---|---|
| `layer` | str | Layer name |

### Segment Folder

Segment and measure every image file in a folder into one table. Guide: [Screens and plates](../how_to/plates.md).

| Parameter | Type | Default | |
|---|---|---|---|
| `folder` | str | required | Folder path |
| `pattern` | str | `*.tif` | Glob pattern |
| `method`, `model`, `reason`, `min_size` | | as Segment Layer | |
| `max_files` | int | 500 | |
| `plate_map` | str | `""` | Table with a `well` or `image_id` column |
| `channels` | dict[str, str] | none | Channel name to file name token |
| `segment_channel` | str | first channel | Channel to segment |

Table: `<folder>_objects`, with `image_id`, `well` (when found) and `path`.

### Load Table

Load a `.csv`, `.tsv`, `.xlsx` or `.parquet` file, such as a plate map.

| Parameter | Type | |
|---|---|---|
| `path` | str | File path |

Table: the file name without extension.

### Measure Regions

Assign each object to the drawn shape its centroid lies in. Guide: [Regions and hand corrections](../how_to/regions_and_edits.md).

| Parameter | Type | |
|---|---|---|
| `labels_layer` | str | Labels layer with the objects |
| `shapes_layer` | str | Shapes layer with the regions |

Table: `<labels>_by_region`, with `region` and `region_area`.

### Segment Whole Slide

Segment a very large 2D image at full resolution, tile by tile. Guide: [Large images](../how_to/large_images.md).

| Parameter | Type | Default | |
|---|---|---|---|
| `image_layer` | str | required | |
| `tile_size` | int | 2048 | Tile side in pixels |
| `method` | `otsu`, `cellpose`, `stardist`, `bioimageio` | `otsu` | No `auto`: tiles share one threshold |
| `model`, `reason`, `min_size`, `split_touching` | | as Segment Layer | |

Adds points layer `<image> objects`. Table: `<image>_objects`.

## Tools

### list_napari_layers

Lists the open layers with type, shape and scale. Labels layers include their object count and mean sizes and intensities. Image layers without labels are marked "not segmented yet"; when nothing is segmented, the first image is segmented first.

### show_object_in_napari

Zoom napari to one object and select it. Guide: [Explore objects](../how_to/explore_in_napari.md).

| Parameter | Type | Default | |
|---|---|---|---|
| `label` | int | 0 | Object label |
| `rank_by` | str | `""` | Show the largest by this column |
| `smallest` | bool | `False` | With `rank_by`, the smallest |
| `labels_layer` | str | most recent | |
| `image_id` | str | `""` | Open this image from a segmented folder |

### color_objects_by

Color each object by a measurement. No column resets the colors.

| Parameter | Type | Default |
|---|---|---|
| `column` | str | `""` |
| `labels_layer` | str | most recent |
| `colormap` | str | `viridis` |

### filter_objects

Show only objects matching a SQL condition. No condition shows all again.

| Parameter | Type | Default | |
|---|---|---|---|
| `where` | str | `""` | SQL condition, units allowed |
| `labels_layer` | str | most recent | |
| `as_new_layer` | bool | `False` | Add `<layer> filtered` instead of hiding |

### set_pixel_size

Set the pixel size of an image and its labels, and measure the labels again. Guide: [Physical units](../how_to/units.md).

| Parameter | Type | Default |
|---|---|---|
| `size` | float | required |
| `unit` | str | `um` |
| `z_size` | float | `size` |
| `layer` | str | first image |

### segmentation_methods

Lists the four methods, whether each is installed (with the install command if not), and when each fits.

### compare_conditions

Compare conditions against a control with wells as replicates. Guide: [Compare conditions](../how_to/statistics.md).

| Parameter | Type | Default | |
|---|---|---|---|
| `table` | str | required | Object table |
| `measurement` | str | required | Column to compare |
| `condition` | str | required | Such as `compound` |
| `control` | str | required | Such as `DMSO` |
| `replicate` | str | `well` | |
| `dose` | str | `""` | Dose column for a dose-response fit |

Table: `<table>_vs_<control>`.

## Analyses

Lumen offers these in its analysis menu when the table has the needed column.

| Analysis | Needs column | Controls | Click |
|---|---|---|---|
| **ObjectExplorer** | `label` | `x`, `y` | Zooms napari to the object, opening its image for folder tables |
| **PlateHeatmap** | `well` | `value`, `statistic` (`mean`, `median`, `count`, `sum`, `std`) | Opens one image of the well in napari |

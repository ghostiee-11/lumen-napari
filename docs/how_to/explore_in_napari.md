# Explore objects in napari

Every answer about objects can be checked in napari. This guide covers the ways to get from a number or a chart back to the pixels.

## Show one object

> Show me the largest nucleus

> Show the dimmest cell by intensity_mean

> Show object 42

napari centres the camera on the object, zooms until it fills about half the canvas, steps to its middle slice in 3D, and selects it in the labels layer. The chat says which object it showed and why ("the largest by area_um2 (212.4)").

| Setting | Meaning |
|---|---|
| `label` | The object's label, the `label` column of a table |
| `rank_by` | A measurement to rank by; shows the largest |
| `smallest` | With `rank_by`, show the smallest instead |
| `labels_layer` | Which labels layer; defaults to the most recent |
| `image_id` | For objects from a [segmented folder](plates.md): opens that image first |

## Click a point on a chart

Lumen's own charts are clickable when each point is one object. Ask for a chart of objects:

> Plot area against mean intensity for every object

Click a point, and napari zooms to that object. This works when the chart's rows carry a `label` column (and `image_id` for folders), or `centroid_*` columns for [whole slides](large_images.md). Charts of aggregates, such as a mean per compound, have no single object behind a point and are not clickable.

## The object explorer

For a dedicated scatter plot with a hover tooltip of every measurement:

> Explore the objects

The explorer plots two measurements (area and mean intensity by default; change them with the **x** and **y** dropdowns). Clicking a point:

- zooms napari to the object, or
- for a folder or plate, opens that image in napari, segmented exactly as before, and zooms to the object.

The explorer appears in Lumen's analysis menu for any table with a `label` column. If the table holds only labels (for example the result of a SQL filter), it takes the measurements from the labels layer.

## Color objects by a measurement

> Color the nuclei by area

> Color them by intensity_mean_tubulin with magma

Each object is filled with its value on a colormap: a heatmap on the image itself, so spatial patterns stand out. The chat says the range ("from 21 to 412"). Any napari colormap name works (`viridis`, `magma`, `turbo`, `plasma`...).

> Reset the colors

goes back to napari's default label colors.

## Show only some objects

> Hide nuclei smaller than 50 µm²

> Show only cells with intensity_mean > 200 and eccentricity < 0.8

The condition is SQL on the layer's measurement columns. Objects that do not match are made transparent. To keep the original layer untouched, ask for a new layer:

> Put the round nuclei (eccentricity < 0.5) in a new layer

This adds `<layer> filtered` with only the matches and their measurements.

> Show every object again

clears the filter.

Filters run in an in-memory DuckDB database with file and network access switched off, so a condition can only read the layer's own measurements.

## Hover in napari

The measurements are also stored on the labels layer (`layer.features`). Hover an object in napari to see its values in the status bar, or open napari's own **Features table** widget for the whole table.

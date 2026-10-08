# Physical units

Areas in pixels cannot be compared across microscopes or objectives. lumen-napari measures in physical units whenever it knows the pixel size, and says so when it does not.

## Where the pixel size comes from

lumen-napari reads the `scale` and `units` of the napari layer:

- **OME-TIFF, OME-Zarr, CZI, ND2, LIF** with the `[bioio]` extra: from the file's metadata, in micrometers.
- **napari readers** that set `scale` and `units` on the layer, such as napari-ome-zarr.
- **You**, in the chat, or in Python with `viewer.add_image(data, scale=(0.65, 0.65), units=("um", "um"))`.

All spatial axes must share one unit. Mixed units, or the default `pixel`, mean sizes are measured in pixels.

## Set the pixel size in the chat

> The pixel size is 0.65 µm

> The voxel size is 0.26 µm in xy and 0.29 µm between slices

This sets the scale and unit of the image layer and its labels layer, and, if the image is already segmented, measures its labels again so the table switches to physical units right away. Otherwise the next segmentation uses the new size.

| Setting | Default | Meaning |
|---|---|---|
| `size` | required | Pixel size along x and y |
| `unit` | `um` | Unit, such as `um` or `nm` |
| `z_size` | `size` | Spacing between slices, for 3D |
| `layer` | first image | The image layer |

## What changes in the table

With a unit, size columns carry it in their name, so a query can never mix pixels and micrometers:

| Pixels | Micrometers, 2D | Micrometers, 3D |
|---|---|---|
| `area` | `area_um2` | `volume_um3` |
| `perimeter` | `perimeter_um` | |
| `equivalent_diameter_area` | `equivalent_diameter_area_um` | `equivalent_diameter_area_um` |
| `centroid_0`, `centroid_1` | `centroid_0_um`, `centroid_1_um` | plus `centroid_2_um` |

`bbox_*` columns stay in pixels. Centroids are in world coordinates, so they match napari's cursor position.

## When sizes are in pixels

The first measurement of a layer without a pixel size posts a warning in the chat:

> ⚠️ **Sizes are in pixels**: this image has no pixel size, so areas cannot be compared across instruments.

Later measurements of the same layer only say "Sizes are in pixels."

## Filters understand units

You can write units in filters. They are removed before the SQL runs, and a bare `area` is matched to `area_um2` when only that column exists:

> Hide nuclei smaller than 50 µm²

keeps the objects where `area_um2 >= 50`.

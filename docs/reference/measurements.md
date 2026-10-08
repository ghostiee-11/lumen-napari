# Measurement columns

Every object becomes one row. Columns come from scikit-image's [`regionprops_table`](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.regionprops_table), renamed to be SQL friendly (`centroid-0` becomes `centroid_0`).

## Shape

| Column | 2D | 3D | Meaning |
|---|---|---|---|
| `label` | ✓ | ✓ | The object's value in the labels layer |
| `area` | ✓ | | Pixels, or area in unit² |
| `volume` | | ✓ | Voxels, or volume in unit³ |
| `centroid_0`, `centroid_1` (`centroid_2`) | ✓ | ✓ | Centre in world coordinates (axis order of napari: z, y, x) |
| `bbox_0` ... | ✓ | ✓ | Bounding box, min then max per axis, always in pixels |
| `equivalent_diameter_area` | ✓ | ✓ | Diameter of a circle (sphere) with the same area (volume) |
| `extent` | ✓ | ✓ | Area divided by bounding box area |
| `eccentricity` | ✓ | | 0 for a circle, towards 1 for a line |
| `perimeter` | ✓ | | Boundary length |
| `solidity` | ✓ | | Area divided by convex hull area; low for irregular shapes |

## Intensity

With an intensity image (the segmented image, or the labels' source image):

| Column | Meaning |
|---|---|
| `intensity_mean` | Mean pixel value inside the object |
| `intensity_min` | Minimum |
| `intensity_max` | Maximum |

Each extra channel adds the same three with the channel's name: `intensity_mean_tubulin`, `intensity_min_tubulin`, `intensity_max_tubulin`. For image layers, the name is the layer's table name (`screen_a01_actin`); for files, the channel name (`actin`).

## Units

When the layer has a pixel size, size columns carry the unit:

| Column | With unit `um` |
|---|---|
| `area` | `area_um2` |
| `volume` | `volume_um3` |
| `centroid_N` | `centroid_N_um` |
| `equivalent_diameter_area` | `equivalent_diameter_area_um` |
| `perimeter` | `perimeter_um` |

Unit names are made SQL safe: `µm` becomes `um`.

## Added by other actions

| Column | Added by | Meaning |
|---|---|---|
| `image_id` | Segment Folder | File name without extensions |
| `well` | Segment Folder | Plate well, such as `B02` |
| `path` | Segment Folder | Full file path |
| plate map columns | `plate_map` | Whatever the map has: `compound`, `dose`... |
| `region`, `region_area` | Measure Regions | Region name and area |
| `position_0`, `position_1`... | Layer Features | Coordinates of points and other non-labels layers |

## In napari

The same table is stored on the labels layer as `layer.features`, keyed by an `index` column holding the label, as napari expects. In Lumen tables that column is called `label`.

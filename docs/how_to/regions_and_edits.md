# Regions and hand corrections

napari is where you draw and paint. lumen-napari picks up what you do there.

## Compare regions you drew

1. Add a **Shapes** layer in napari and draw one or more polygons, rectangles or ellipses: a tumour margin, a wound edge, a tissue compartment.
2. Ask:

> Compare nuclear density inside and outside the region I drew

> What is the mean intensity of cells in each region?

Every object is assigned to the shape its centroid lies in, or to `outside`. The table `<labels>_by_region` has one row per object with its measurements plus:

| Column | Content |
|---|---|
| `region` | The shape's name, or `region 1`, `region 2`..., or `outside` |
| `region_area` | The region's area (`region_area_um2` with a pixel size) |

Density is objects per area: `COUNT(*) / region_area` per region, which Lumen writes for you.

To name regions, add a `name` feature to the shapes layer (in the layer's features table, or `shapes.features["name"] = ["tumour", "stroma"]`). Where shapes overlap, the earlier shape wins. The shapes layer may have a different scale or position than the labels; vertices are mapped onto the labels' pixel grid.

Regions work on 2D labels layers.

## Fix the segmentation by hand

No segmentation is perfect. Use napari's labels tools on a measured labels layer:

- **Paint** to add or extend an object,
- **Fill** to merge objects or relabel one,
- **Erase** to remove a false detection.

Half a second after you stop, the layer is measured again. Its `features` and the Lumen table both update, so the next question uses the corrected objects:

> How many nuclei are there now?

Intensities are measured from the same image and channels as before.

Moving points in a points layer you loaded into Lumen updates its table the same way.

## Reproducing edits

Hand edits cannot be replayed from code. The exported script notes which layers were edited, so save those layers (**File > Save Selected Layers**) next to the script.

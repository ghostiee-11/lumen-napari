# Screens and plates

A screen has hundreds of images: wells, fields, channels. lumen-napari segments a whole folder into one table without opening each image in napari, joins the plate map, and opens any image on demand.

## Segment a folder

> Segment every image in ~/data/plate1

> Segment all the *.png files in ~/data/plate1 with cellpose

Every file matching the pattern (default `*.tif`) is segmented with the same settings and measured. The result is one table, `<folder>_objects`, with one row per object and these extra columns:

| Column | Content |
|---|---|
| `image_id` | The file name without extensions (`plate1_B02_s1`) |
| `well` | The plate well, zero padded (`B02`), when every file has one |
| `path` | The full path of the file |

The chat reports how many images and objects there were, the median objects per image, and the images with the fewest and most objects. Check those extremes: ask to show an object from them.

| Setting | Default | Meaning |
|---|---|---|
| `folder` | required | The folder; `~` works |
| `pattern` | `*.tif` | Glob pattern for the files |
| `method`, `model`, `min_size` | `otsu`, empty, 20 | As in [Segment and measure](segment.md) |
| `max_files` | 500 | Stop after this many files |
| `plate_map` | none | A table to join, see below |
| `channels` | none | Channel tokens for one-file-per-channel screens |
| `segment_channel` | first channel | The channel to segment |

## Where the well comes from

1. **OME plate metadata.** OME-TIFF and OME-Zarr files from a plate record which well holds each image. Needs the `[bioio]` extra.
2. **The file name.** A well id such as `B02`, `B2` or `P24`, set off by non-alphanumerics: `plate1_B02_s1.tif`, `scan-H12.png`. Rows A to P, columns 1 to 24.

If any file has no well, the `well` column is left out and rows are keyed by `image_id` only.

## Join a plate map

A plate map says what is in each well. Any `.csv`, `.tsv`, `.xlsx` or `.parquet` with a `well` column (or an `image_id` column) works:

```text
well,compound,dose_um
A01,DMSO,0
A02,DMSO,0
B01,taxol,0.1
B02,taxol,1
```

> Segment every image in ~/data/plate1 with the plate map ~/data/plate1_map.csv

Every object gets the map's columns. Wells in the map can be written `B2` or `B02`. You can also load a table on its own and let Lumen join it with SQL:

> Load ~/data/plate1_map.csv

or upload it in the chat.

## Several channels

### One file per channel

Many screens (for example BBBC021) save each channel as its own file, marked by a token in the name: `A01_s1_w1.tif` for DAPI, `A01_s1_w2.tif` for tubulin. Tell lumen-napari the tokens:

> Segment ~/data/plate1 with channels dapi=_w1, tubulin=_w2, actin=_w4, segmenting dapi

Files are grouped into sites by the part of the name before the token. The `segment_channel` is segmented; every other channel adds `intensity_mean_<channel>`, `intensity_min_<channel>` and `intensity_max_<channel>` columns. Sites missing a channel are left out.

### Multi-channel files

OME-TIFF, OME-Zarr and CZI files store their channels and names inside. Name the channel to segment:

> Segment ~/data/ome_plate with pattern *.ome.tiff, segmenting the dapi channel

Without `segment_channel`, the first channel is segmented.

## Plate heatmap

> Show a plate heatmap of the mean nuclear area per well

The heatmap draws a 96 well plate (rows A to H, 12 columns), or a 384 well plate when the wells need it. Pick the measurement with the **value** dropdown and the statistic (`mean`, `median`, `count`, `sum`, `std`) with **statistic**. `count` shows objects per well.

Click a well to open one of its images in napari, segmented exactly as in the batch, and zoom to it.

## Open any image from the table

> Show object 12 of image plate1_B02_s1

> Show the largest nucleus in well C03

The image and its labels open in napari, re-segmented with the batch's settings so the labels match the table, and napari zooms to the object.

## Next

[Compare conditions](statistics.md): which compounds changed the cells.

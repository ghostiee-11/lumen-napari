# File formats

## Images

| Format | Extensions | Reader | Channels | Pixel size | Plate well | Extra needed |
|---|---|---|---|---|---|---|
| PNG, JPEG | `.png`, `.jpg`, `.jpeg` | scikit-image | one (RGB to gray) | no | from file name | |
| TIFF | `.tif`, `.tiff` | scikit-image | one (RGB to gray) | no | from file name | |
| OME-TIFF | `.ome.tif`, `.ome.tiff` | bioio | named | yes, µm | OME plate, or file name | `[bioio]` |
| OME-Zarr | `.zarr` | bioio | named | yes, µm | OME plate, or file name | `[bioio]` |
| Zeiss CZI | `.czi` | bioio | named | yes, µm | file name | `[bioio]`, `bioio-czi` |
| Nikon ND2 | `.nd2` | bioio | named | yes, µm | file name | `[bioio]`, `bioio-nd2` |
| Leica LIF | `.lif` | bioio | named | yes, µm | file name | `[bioio]`, `bioio-lif` |

These apply to [folders](../how_to/plates.md) and [chat uploads](../how_to/upload_images.md). Images opened in napari by any reader plugin work too: lumen-napari reads the layer, with whatever scale and units the reader set.

Notes:

- bioio files are read at the first time point (`T=0`). Volumes keep their z axis.
- Channel names are lower-cased and made SQL safe (`DAPI` becomes `dapi`); unnamed channels are `c0`, `c1`...
- When a file has no physical pixel size, sizes are in pixels.

## Plate well from file names

A well id is a row letter `A` to `P` followed by a column number `1` to `24`, not touching other letters or digits. It is zero padded:

| File name | Well |
|---|---|
| `plate1_B02_s1.tif` | `B02` |
| `scan-H12.png` | `H12` |
| `A1_dapi.tif` | `A01` |
| `ABC123.tif` | none |

## Tables

Plate maps and other tables can be `.csv`, `.tsv`, `.xlsx` or `.parquet`. A plate map needs a `well` column (values like `B2` or `B02`) or an `image_id` column matching the file names without extension.

Tables uploaded in the chat use Lumen's own readers, which accept more formats.

## Samples

The plugin adds three samples under **File > Open Sample > Lumen**:

| Sample | Key | Content |
|---|---|---|
| HeLa nuclei (2D) | `mitosis` | scikit-image `human_mitosis`, 512 × 512, no pixel size |
| Mouse embryo nuclei (3D) | `cells3d` | nuclei channel of scikit-image `cells3d`, 60 × 256 × 256, voxel 0.29 × 0.26 × 0.26 µm |

| Lily stem cells (4 channels) | `lily` | scikit-image `lily`, 922 × 922, four layers `lily-magenta`, `lily-green`, `lily-yellow`, `lily-blue` |

Open them from Python with `viewer.open_sample("lumen-napari", "mitosis")`.

# Upload images

You can add an image from the chat instead of opening it in napari. It opens in napari, gets segmented and measured, and is ready for questions.

## Upload

In the chat, click the **+** button next to the input, or drag files onto the chat. Supported image files:

| Extension | Read with | Metadata kept |
|---|---|---|
| `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff` | scikit-image | none; color images stay in color |
| `.ome.tif`, `.ome.tiff` | bioio (`[bioio]` extra) | channel names, pixel size, plate well |
| `.czi` | bioio + `bioio-czi` | channel names, pixel size |
| `.nd2` | bioio + `bioio-nd2` | channel names, pixel size |
| `.lif` | bioio + `bioio-lif` | channel names, pixel size |

Table files (`.csv`, `.xlsx`, `.parquet` and others) still go to Lumen as data, for example a plate map to join with the measurements.

## What happens

For each uploaded image:

1. **One napari layer per channel.** A single-channel file becomes a layer named after the file (`hela_nuclei`); a color image stays one color layer. A multi-channel file becomes one layer per channel (`screen_A01 dapi`, `screen_A01 actin`), each with its own colormap and blended together, as napari opens multichannel images, with the file's pixel size and unit set on each layer.
2. **Side by side.** Each upload is placed to the right of what is already open, so several uploads do not hide each other. napari zooms out to show them all.
3. **Segmented and measured.** The first channel is segmented with Otsu, which detects whether the objects are bright, dark, or cells inside walls. The other channels are measured inside each object, as columns such as `intensity_mean_screen_a01_actin`.
4. **Ready to query.** The table is named after the labels layer, such as `hela_nuclei_labels`. A napari message in the chat shows the outlines to check.

Then ask about it:

> What is the mean nuclear area in each uploaded image?

## Try it

lumen-napari's own test images work well. Generate a few with Python, or use any fluorescence image you have:

```python
from skimage import data, io

io.imsave("hela_nuclei.png", data.human_mitosis())
```

## Re-segment with other settings

Uploads always start with Otsu. If the outlines look wrong, ask for something else:

> Segment hela_nuclei again with cellpose

See [Segment and measure](segment.md) for the options.

## Where uploads are stored

Uploaded files are written to a temporary folder (`lumen-napari-uploads-*` in your system temp directory) for the session, so napari and bioio can read them. They are not deleted automatically.

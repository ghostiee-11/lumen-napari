import io

import numpy as np
from skimage.io import imread

from lumen_napari.report import overlay_png, segmentation_report, size_note


def blobs(shape=(40, 40)):
    image = np.zeros(shape)
    labels = np.zeros(shape, int)
    image[5:15, 5:15] = labels[5:15, 5:15] = 1
    return image, labels


def test_overlay_is_a_png_with_orange_outlines():
    picture = imread(io.BytesIO(overlay_png(*blobs())))
    assert picture.shape == (40, 40, 3)
    assert (picture == [255, 140, 0]).all(axis=-1).any()


def test_large_images_are_shrunk():
    image, labels = blobs((2000, 1000))
    assert imread(io.BytesIO(overlay_png(image, labels))).shape[:2] == (600, 300)


def test_volumes_show_the_busiest_slice():
    image = np.zeros((5, 20, 20))
    labels = np.zeros((5, 20, 20), int)
    labels[3, 2:6, 2:6] = 1
    labels[3, 10:14, 10:14] = 2
    assert imread(io.BytesIO(overlay_png(image, labels))).shape == (20, 20, 3)


def test_size_note_warns_about_pixels():
    assert "Sizes are in pixels" in size_note(None, (1.0, 1.0))
    assert size_note("um", (0.65, 0.65)) == "Sizes are in um (pixel size 0.65, 0.65 um)."


def test_segmentation_report_shows_the_work():
    text = segmentation_report("nuclei", 348, {"method": "otsu", "min_size": 20}, None, (1, 1),
                               "nuclei_labels")
    assert "**Segmented `nuclei`: 348 objects**" in text
    assert "method='otsu', min_size=20" in text
    assert "Does the outline look right?" in text

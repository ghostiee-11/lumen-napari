import numpy as np
import pytest

from lumen_napari.segment import segment


def blobs():
    image = np.zeros((40, 40))
    image[5:12, 5:12] = 1
    image[25:35, 25:35] = 1
    image[2, 30] = 1
    return image


def test_otsu_finds_each_object():
    labels = segment(blobs(), split_touching=False)
    assert labels.max() == 3


def test_min_size_drops_specks():
    labels = segment(blobs(), min_size=4, split_touching=False)
    assert labels.max() == 2


def test_min_size_keeps_objects_of_exactly_that_size():
    assert segment(blobs(), min_size=49, split_touching=False).max() == 2


def test_split_touching_separates_two_disks():
    yy, xx = np.mgrid[:40, :60]
    image = ((yy - 20) ** 2 + (xx - 20) ** 2 < 100) | ((yy - 20) ** 2 + (xx - 37) ** 2 < 100)
    assert segment(image.astype(float), split_touching=False).max() == 1
    assert segment(image.astype(float)).max() == 2


def test_works_in_3d():
    image = np.zeros((10, 20, 20))
    image[2:6, 3:8, 3:8] = 1
    assert segment(image, split_touching=False).max() == 1


def test_unknown_method():
    with pytest.raises(ValueError, match="Unknown method"):
        segment(blobs(), method="magic")

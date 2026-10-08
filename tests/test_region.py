import numpy as np
import pytest
from napari.layers import Image

from lumen_napari.region import choose_level, factors, load_region, pixels, visible_region


@pytest.fixture
def pyramid():
    full = np.arange(64 * 128, dtype=float).reshape(64, 128)
    return Image([full, full[::2, ::2], full[::4, ::4]], multiscale=True, scale=(0.5, 0.5),
                 translate=(10, 20))


def test_factors(pyramid):
    assert factors(pyramid).tolist() == [[1, 1], [2, 2], [4, 4]]


def test_choose_the_finest_level_in_budget(pyramid):
    assert choose_level(pyramid, budget=64 * 128) == 0
    assert choose_level(pyramid, budget=1000) == 2
    assert choose_level(pyramid, region=((0, 16), (0, 16)), budget=300) == 0


def test_nothing_fits(pyramid):
    with pytest.raises(ValueError, match="Zoom in"):
        choose_level(pyramid, budget=10)


def test_load_a_crop_of_a_coarse_level(pyramid):
    image, scale, translate = load_region(pyramid, level=1, region=((8, 24), (40, 72)))
    assert image.shape == (8, 16)
    assert image[0, 0] == pyramid.data[0][8, 40]
    assert scale == (1.0, 1.0)
    assert translate == (10 + 4 * 1.0, 20 + 20 * 1.0)
    assert pixels(pyramid, 1, ((8, 24), (40, 72))) == 8 * 16


def test_load_everything_by_default():
    layer = Image(np.zeros((5, 6)))
    image, scale, translate = load_region(layer)
    assert image.shape == (5, 6) and scale == (1.0, 1.0) and translate == (0.0, 0.0)


def test_rgb_becomes_gray():
    layer = Image(np.ones((4, 4, 3)), rgb=True)
    assert load_region(layer)[0].shape == (4, 4)


def test_visible_region_in_full_resolution_pixels(pyramid):
    pyramid.data_level = 1
    pyramid.corner_pixels = np.array([[4, 10], [11, 29]])
    assert visible_region(pyramid) == ((8, 24), (20, 60))


def test_undisplayed_axes_are_kept_whole():
    layer = Image(np.zeros((7, 30, 40)))
    layer.corner_pixels = np.array([[0, 5, 6], [0, 9, 19]])
    assert visible_region(layer) == ((0, 7), (5, 10), (6, 20))


def test_lazy_dask_levels_read_only_the_crop():
    da = pytest.importorskip("dask.array")
    reads = []
    full = da.from_array(np.ones((1000, 1000)), chunks=100)
    tracked = full.map_blocks(lambda block: reads.append(block.shape) or block, dtype=float)
    layer = Image([tracked, tracked[::4, ::4]], multiscale=True)
    reads.clear()
    image, _, _ = load_region(layer, level=0, region=((0, 100), (0, 100)))
    assert image.shape == (100, 100)
    assert len(reads) == 1

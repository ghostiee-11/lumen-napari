import numpy as np
import pytest
from napari.layers import Image
from skimage.draw import disk

from lumen_napari.measure import measure
from lumen_napari.segment import segment
from lumen_napari.tiles import segment_tiled, tiles


def slide(shape=(300, 300), step=37, radius=6):
    image = np.zeros(shape)
    for y in range(15, shape[0] - 10, step):
        for x in range(15, shape[1] - 10, step):
            image[disk((y, x), radius, shape=shape)] = 1
    return image


def test_tiles_cover_the_image_once():
    covered = np.zeros((10, 7), int)
    for core, crop in tiles((10, 7), 4, 1):
        covered[core] += 1
        assert crop[0].start <= core[0].start and crop[1].stop >= core[1].stop
    assert (covered == 1).all()


@pytest.mark.parametrize("tile", [64, 100, 1000])
def test_tiled_matches_one_pass_whatever_the_tile_size(tile):
    image = slide()
    whole = measure(segment(image, min_size=0, split_touching=False), image)
    df, n = segment_tiled(Image(image), tile=tile, overlap=20, min_size=0, split_touching=False)
    assert len(df) == len(whole)
    assert sorted(df.area) == sorted(whole.area)
    assert df.label.tolist() == list(range(1, len(df) + 1))
    assert n == (300 // tile + (300 % tile > 0)) ** 2


def test_world_units_and_positions():
    image = np.zeros((200, 200))
    image[disk((150, 50), 5)] = 1
    layer = Image(image, scale=(0.5, 0.5), translate=(10, 20))
    df, _ = segment_tiled(layer, tile=64, overlap=16, min_size=0, unit="um")
    assert df.centroid_0_um.iat[0] == pytest.approx(10 + 150 * 0.5)
    assert df.centroid_1_um.iat[0] == pytest.approx(20 + 50 * 0.5)
    assert df.area_um2.iat[0] == pytest.approx(np.sum(image) * 0.25)


def test_empty_slide():
    df, n = segment_tiled(Image(np.zeros((50, 50))), tile=20)
    assert len(df) == 0 and n == 9


def test_only_2d():
    with pytest.raises(ValueError, match="2D"):
        segment_tiled(Image(np.zeros((2, 5, 5))))

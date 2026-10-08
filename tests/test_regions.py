import numpy as np
import pandas as pd
import pytest
from napari.layers import Labels, Shapes

from lumen_napari.measure import measure, to_features
from lumen_napari.regions import objects_by_region


@pytest.fixture
def labels():
    data = np.zeros((40, 40), int)
    data[2:6, 2:6] = 1      # inside the square
    data[10:14, 10:14] = 2  # inside the square
    data[30:34, 30:34] = 3  # outside
    return Labels(data, features=to_features(measure(data)))


def test_objects_are_assigned_to_regions(labels):
    shapes = Shapes([[[0, 0], [0, 20], [20, 20], [20, 0]]], shape_type="rectangle")
    df = objects_by_region(labels, shapes)
    assert list(df.region) == ["region 1", "region 1", "outside"]
    areas = df.groupby("region").region_area.first()
    # napari rasterizes shape edges inclusively, so a 20 x 20 square covers 21 x 21 pixels.
    assert areas["region 1"] == pytest.approx(400, rel=0.11)
    assert areas["region 1"] + areas["outside"] == 1600
    assert list(df.area) == [16, 16, 16]


def test_density_question(labels):
    shapes = Shapes([[[0, 0], [0, 20], [20, 20], [20, 0]]], shape_type="rectangle")
    df = objects_by_region(labels, shapes)
    density = df.groupby("region").apply(lambda g: len(g) / g.region_area.iat[0], include_groups=False)
    assert density["region 1"] > density["outside"]


def test_layers_with_different_scales_line_up():
    data = np.zeros((40, 40), int)
    data[30:34, 30:34] = 1
    scaled = Labels(data, scale=(0.5, 0.5))
    # Drawn in world units: the object sits at world 15-17.
    shapes = Shapes([[[14, 14], [14, 18], [18, 18], [18, 14]]], shape_type="rectangle")
    df = objects_by_region(scaled, shapes)
    assert list(df.region) == ["region 1"]
    assert df.region_area.iat[0] == pytest.approx(16, rel=0.3)


def test_named_shapes_and_ellipses(labels):
    shapes = Shapes([[[0, 0], [0, 8], [8, 8], [8, 0]]], shape_type="ellipse",
                    features=pd.DataFrame({"name": ["tumor"]}))
    df = objects_by_region(labels, shapes)
    assert list(df.region) == ["tumor", "outside", "outside"]


def test_3d_is_refused():
    with pytest.raises(ValueError, match="2D"):
        objects_by_region(Labels(np.zeros((2, 4, 4), int)), Shapes())

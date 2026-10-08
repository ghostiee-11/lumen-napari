import numpy as np
from napari.layers import Labels

from lumen_napari.measure import measure, to_features


def two_objects():
    labels = np.zeros((10, 10), int)
    labels[1:3, 1:3] = 1
    labels[5:9, 5:9] = 2
    return labels


def test_one_row_per_label():
    df = measure(two_objects())
    assert list(df.label) == [1, 2]
    assert list(df.area) == [4, 16]


def test_columns_are_sql_friendly():
    df = measure(two_objects())
    assert "centroid_0" in df.columns
    assert not any("-" in c for c in df.columns)


def test_intensity_columns_only_with_image():
    labels = two_objects()
    assert "intensity_mean" not in measure(labels).columns
    df = measure(labels, intensity=labels * 10.0)
    assert list(df.intensity_mean) == [10, 20]


def test_spacing_scales_area():
    df = measure(two_objects(), spacing=(0.5, 0.5))
    assert list(df.area) == [1, 4]


def test_3d_skips_2d_only_properties():
    labels = np.zeros((4, 6, 6), int)
    labels[1:3, 1:4, 1:4] = 1
    df = measure(labels)
    assert df.volume[0] == 18
    assert "eccentricity" not in df.columns


def test_features_line_up_with_napari_labels():
    labels = two_objects()
    layer = Labels(labels, features=to_features(measure(labels)))
    assert "area: 4" in layer.get_status((1, 1))["coordinates"]
    assert "area: 16" in layer.get_status((6, 6))["coordinates"]


def test_units_are_added_to_size_columns():
    df = measure(two_objects(), spacing=(0.5, 0.5), unit="um")
    assert list(df.area_um2) == [1, 4]
    assert "centroid_0_um" in df.columns
    assert "perimeter_um" in df.columns
    assert "bbox_0" in df.columns


def test_3d_size_is_called_volume():
    labels = np.zeros((4, 6, 6), int)
    labels[1:3, 1:4, 1:4] = 1
    assert measure(labels, unit="um").volume_um3[0] == 18


def test_origin_moves_centroids_to_world_space():
    df = measure(two_objects(), origin=(100, 200))
    assert list(df.centroid_0) == [101.5, 106.5]
    assert list(df.centroid_1) == [201.5, 206.5]

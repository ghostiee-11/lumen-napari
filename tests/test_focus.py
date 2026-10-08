import numpy as np
import pytest
from napari.components import ViewerModel

from lumen_napari.focus import focus_label, label_bbox


def viewer_with_labels(labels, **kwargs):
    viewer = ViewerModel()
    layer = viewer.add_labels(labels, **kwargs)
    return viewer, layer


def test_bbox_in_world_coordinates():
    labels = np.zeros((20, 20), int)
    labels[4:8, 10:12] = 3
    _, layer = viewer_with_labels(labels, scale=(2, 2))
    lo, hi = label_bbox(layer, 3)
    assert list(lo) == [8, 20]
    assert list(hi) == [16, 24]


def test_missing_label():
    _, layer = viewer_with_labels(np.zeros((5, 5), int))
    with pytest.raises(ValueError, match="Label 7 not found"):
        label_bbox(layer, 7)


def test_focus_centers_zooms_and_selects():
    labels = np.zeros((100, 100), int)
    labels[10:20, 60:70] = 5
    viewer, layer = viewer_with_labels(labels)
    focus_label(viewer, layer, 5)
    assert viewer.scene.camera.center[-2:] == (15, 65)
    assert viewer.scene.camera.zoom == pytest.approx(0.5 * min(viewer.canvas.size) / 10)
    assert layer.selected_label == 5


def test_focus_steps_to_the_object_slice_in_3d():
    labels = np.zeros((30, 50, 50), int)
    labels[20:24, 5:9, 5:9] = 2
    viewer, layer = viewer_with_labels(labels)
    focus_label(viewer, layer, 2)
    assert viewer.dims.point[0] == 22
    assert viewer.scene.camera.center[-2:] == (7, 7)

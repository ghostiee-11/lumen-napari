import numpy as np
import pytest
from napari.components import ViewerModel

from lumen_napari.pick import centroid, show_row


@pytest.fixture
def viewer(qapp):
    viewer = ViewerModel()
    labels = np.zeros((60, 60), int)
    labels[40:50, 10:20] = 3
    viewer.add_labels(labels, name="nuclei labels")
    return viewer


def test_label_rows_zoom_to_the_object(viewer):
    assert show_row(viewer, "nuclei_labels", {"label": 3}) == "object 3 of 'nuclei labels'"
    assert viewer.layers["nuclei labels"].selected_label == 3
    assert viewer.scene.camera.center[-2:] == (45, 15)


def test_whole_slide_rows_center_on_the_centroid(qapp):
    viewer = ViewerModel()
    assert show_row(viewer, "slide_objects", {"centroid_0_um": 120.0, "centroid_1_um": 80.0}) \
        == "position (120.0, 80.0)"
    assert viewer.scene.camera.center[-2:] == (120, 80)


def test_rows_without_identity(qapp):
    with pytest.raises(ValueError, match="no label or position"):
        show_row(ViewerModel(), "t", {"compound": "DMSO"})


def test_centroid():
    assert centroid({"centroid_0": 1, "centroid_1": 2}) == (1.0, 2.0)
    assert centroid({"area": 3}) is None

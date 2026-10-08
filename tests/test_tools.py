import threading

import numpy as np
import pytest
from napari.components import ViewerModel

from lumen_napari.tools import make_tools


@pytest.fixture
def viewer(qapp):
    viewer = ViewerModel()
    viewer.add_image(np.zeros((50, 60)), name="nuclei")
    labels = np.zeros((50, 60), int)
    labels[10:20, 30:40] = 4
    viewer.add_labels(labels, name="nuclei labels")
    viewer.add_points([[1, 1], [2, 2]], name="spots")
    return viewer


@pytest.fixture
def tools(viewer):
    return {tool.name: tool.function for tool in make_tools(viewer)}


async def test_tools_ignore_the_planner_step_title(viewer):
    outputs, _ = await make_tools(viewer)[0].respond([], {}, step_title="List layers")
    assert "napari layers" in outputs[0]


def test_list_layers(tools):
    text = tools["list_napari_layers"]()
    assert "- 'nuclei': image, shape (50, 60), scale (1.0, 1.0)" in text
    assert "- 'spots': points, 2 items" in text


def test_list_layers_empty(qapp):
    assert make_tools(ViewerModel())[0].function() == "napari has no layers open."


def test_show_object_from_another_thread(qtbot, viewer, tools):
    out = {}
    thread = threading.Thread(target=lambda: out.update(msg=tools["show_object_in_napari"](4)))
    thread.start()
    qtbot.waitUntil(lambda: not thread.is_alive(), timeout=10_000)
    assert out["msg"] == "Showing object 4 of 'nuclei labels' in napari."
    assert viewer.scene.camera.center[-2:] == (15, 35)
    assert viewer.layers["nuclei labels"].selected_label == 4


def test_show_object_needs_labels(qapp):
    show = make_tools(ViewerModel())[1].function
    with pytest.raises(ValueError, match="Segment an image first"):
        show(1)


def ranked_viewer(qapp):
    from lumen_napari.measure import measure, to_features

    viewer = ViewerModel()
    labels = np.zeros((50, 60), int)
    labels[2:4, 2:4] = 1
    labels[20:40, 30:50] = 2
    labels[10:15, 10:15] = 3
    viewer.add_labels(labels, name="cells", features=to_features(measure(labels)))
    return viewer


def test_show_largest_by_measurement(qtbot, qapp):
    viewer = ranked_viewer(qapp)
    show = make_tools(viewer)[1].function
    assert show(rank_by="area") == "Showing object 2 of 'cells' in napari."
    assert show(rank_by="area", smallest=True) == "Showing object 1 of 'cells' in napari."
    assert viewer.layers["cells"].selected_label == 1


def test_show_refuses_to_guess(qapp):
    show = make_tools(ranked_viewer(qapp))[1].function
    with pytest.raises(ValueError, match="Give a label, or rank_by"):
        show()
    with pytest.raises(ValueError, match="no 'volume' measurement"):
        show(rank_by="volume")


def test_show_object_from_a_folder_image(qapp, tmp_path):
    from skimage.io import imsave

    from lumen_napari.batch import measure_files

    image = np.zeros((30, 50), np.uint8)
    image[5:8, 5:8] = 200
    image[5:20, 25:45] = 200
    imsave(tmp_path / "C07.png", image, check_contrast=False)
    measure_files([tmp_path / "C07.png"], min_size=0)
    viewer = ViewerModel()
    show = make_tools(viewer)[1].function
    assert show(image_id="C07", rank_by="area") == "Showing object 2 of 'C07 labels' in napari."

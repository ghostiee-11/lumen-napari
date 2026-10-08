import threading

import numpy as np
import pytest
from lumen.ai.tools import FunctionTool
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
    return {tool.__name__: tool for tool in make_tools(viewer)}


def test_tools_wrap_as_lumen_function_tools(tools):
    for tool in tools.values():
        FunctionTool(tool)


def test_list_layers(tools):
    text = tools["list_napari_layers"]()
    assert "- 'nuclei': image, shape (50, 60), scale (1.0, 1.0)" in text
    assert "- 'spots': points, 2 items" in text


def test_list_layers_empty(qapp):
    assert make_tools(ViewerModel())[0]() == "napari has no layers open."


def test_show_object_from_another_thread(qtbot, viewer, tools):
    out = {}
    thread = threading.Thread(target=lambda: out.update(msg=tools["show_object_in_napari"](4)))
    thread.start()
    qtbot.waitUntil(lambda: not thread.is_alive(), timeout=10_000)
    assert out["msg"] == "Showing object 4 of 'nuclei labels' in napari."
    assert viewer.scene.camera.center[-2:] == (15, 35)
    assert viewer.layers["nuclei labels"].selected_label == 4


def test_show_object_needs_labels(qapp):
    show = make_tools(ViewerModel())[1]
    with pytest.raises(ValueError, match="Segment an image first"):
        show(1)

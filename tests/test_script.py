import numpy as np
import pandas as pd
import pytest
from napari.components import ViewerModel

from lumen_napari import controls as controls_module
from lumen_napari.controls import NapariControls
from lumen_napari.measure import measure, to_features
from lumen_napari.script import HEADER, Script
from lumen_napari.segment import segment


@pytest.fixture
def viewer(qapp):
    viewer = ViewerModel()
    image = np.zeros((40, 40))
    image[5:12, 5:12] = 1
    image[25:35, 25:35] = 2
    viewer.add_image(image, name="nuclei", scale=(0.5, 0.5))
    return viewer


def replay(script, viewer):
    """Run the recorded steps on a fresh viewer that has the same source image."""
    fresh = ViewerModel()
    fresh.add_image(viewer.layers["nuclei"].data, name="nuclei", scale=(0.5, 0.5))
    namespace = {
        "viewer": fresh, "tables": {}, "segment": segment, "measure": measure,
        "to_features": to_features, "intensity": controls_module.intensity,
    }
    exec(script.body(), namespace)  # noqa: S102
    return fresh, namespace["tables"]


def test_segment_step_replays_to_the_same_table(viewer):
    controls = NapariControls(viewer=viewer)
    df = controls.segment_layer("nuclei", min_size=0)
    fresh, tables = replay(controls.script, viewer)
    pd.testing.assert_frame_equal(tables["nuclei_labels"], df)
    assert fresh.layers["nuclei labels"].scale[0] == 0.5


def test_measure_step_replays(viewer):
    controls = NapariControls(viewer=viewer)
    controls.segment_layer("nuclei", min_size=0)
    df = controls.measure_layer("nuclei labels", image_layer="nuclei")
    _, tables = replay(controls.script, viewer)
    pd.testing.assert_frame_equal(tables["nuclei_labels"], df)


def test_unsaved_layers_get_a_load_comment(viewer):
    controls = NapariControls(viewer=viewer)
    controls.segment_layer("nuclei")
    assert controls.script.lines[0] == "# Load the 'nuclei' layer into the viewer here."


def test_layers_from_files_are_opened():
    from napari.layers import Image
    from napari.layers._source import layer_source

    path = "/data/cells.tif"
    with layer_source(path=path):
        layer = Image(np.zeros((8, 8)), name="cells")
    script = Script()
    script.load(layer)
    script.load(layer)
    assert script.lines == ["viewer.open('/data/cells.tif')[0].name = 'cells'"]


def test_render_is_a_runnable_script():
    script = Script()
    script.add("print('hi')")
    text = script.render()
    assert text.startswith(HEADER)
    assert text.endswith("napari.run()\n")
    compile(text, "script.py", "exec")


def test_folder_step_replays(viewer, tmp_path):
    from skimage.io import imsave

    image = np.zeros((20, 20), np.uint8)
    image[2:8, 2:8] = 200
    imsave(tmp_path / "a.png", image, check_contrast=False)
    controls = NapariControls(viewer=viewer)
    df = controls.segment_folder(str(tmp_path), pattern="*.png", min_size=0)
    _, tables = replay(controls.script, viewer)
    pd.testing.assert_frame_equal(tables[controls.table_name], df)

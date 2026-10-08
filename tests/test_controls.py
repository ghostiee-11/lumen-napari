import asyncio
import threading

import numpy as np
import pandas as pd
import pytest
from napari.components import ViewerModel

from lumen_napari.controls import NapariControls, table_name


@pytest.fixture
def viewer(qapp):
    viewer = ViewerModel()
    image = np.zeros((40, 40))
    image[5:12, 5:12] = 1
    image[25:35, 25:35] = 2
    viewer.add_image(image, name="nuclei", scale=(0.5, 0.5))
    return viewer


@pytest.fixture
def controls(viewer):
    return NapariControls(viewer=viewer)


def run(qtbot, controls, action, **params):
    """Run an action off the Qt thread, as the Lumen server does, while Qt keeps processing events."""
    out = {}
    thread = threading.Thread(
        target=lambda: out.update(result=asyncio.run(controls.load_action(action, **params)))
    )
    thread.start()
    qtbot.waitUntil(lambda: not thread.is_alive(), timeout=60_000)
    return out["result"]


def query(result, sql):
    return result.sources[0].execute(sql)


def test_table_name():
    assert table_name("nuclei labels") == "nuclei_labels"
    assert table_name("C1-cells (2)") == "c1_cells_2"


def test_actions_are_registered(controls):
    assert [name for name, _ in controls.as_tools()] == [
        "Segment Layer", "Measure Layer", "Layer Features", "Segment Folder",
    ]


def test_segment_layer_adds_labels_and_a_table(qtbot, viewer, controls):
    result = run(qtbot, controls, "Segment Layer", image_layer="nuclei", min_size=0)
    assert result.table == "nuclei_labels"
    df = query(result, "SELECT label, area, intensity_mean FROM nuclei_labels ORDER BY label")
    assert list(df.area) == [49 * 0.25, 100 * 0.25]
    labels = viewer.layers["nuclei labels"]
    assert labels.data.max() == 2
    assert labels.scale[0] == 0.5
    assert "area: 25" in labels.get_status((30, 30))["coordinates"]


def test_segment_twice_updates_the_same_layer(qtbot, viewer, controls):
    run(qtbot, controls, "Segment Layer", image_layer="nuclei")
    run(qtbot, controls, "Segment Layer", image_layer="nuclei")
    assert [layer.name for layer in viewer.layers] == ["nuclei", "nuclei labels"]


def test_measure_existing_labels(qtbot, viewer, controls):
    labels = np.zeros((40, 40), int)
    labels[0:4, 0:4] = 7
    viewer.add_labels(labels, name="manual")
    result = run(qtbot, controls, "Measure Layer", labels_layer="manual", image_layer="nuclei")
    df = query(result, "SELECT label, area FROM manual")
    assert list(df.label) == [7]


def test_points_features_include_positions(qtbot, viewer, controls):
    viewer.add_points([[1, 2], [3, 4]], name="spots", features=pd.DataFrame({"kind": ["a", "b"]}))
    result = run(qtbot, controls, "Layer Features", layer="spots")
    df = query(result, "SELECT kind, position_0, position_1 FROM spots")
    assert df.to_dict("list") == {"kind": ["a", "b"], "position_0": [1, 3], "position_1": [2, 4]}


def test_missing_layer_lists_available_ones(qtbot, controls):
    result = run(qtbot, controls, "Segment Layer", image_layer="cells")
    assert not result.sources
    assert "Available: 'nuclei'" in result.message


def test_lumen_source_agent_builds_every_action(controls):
    from lumen.ai.agents.source import SourceAgent

    tools = SourceAgent._build_tools({"source_controls": [controls]}, result_store=[])
    assert [tool.name for tool in tools] == [
        "segment_layer", "measure_layer", "layer_features", "segment_folder",
    ]


def test_layer_features_rejects_image_layers(qtbot, controls):
    result = run(qtbot, controls, "Layer Features", layer="nuclei")
    assert not result.sources
    assert "No labels or points" in result.message


def test_layer_units_name_the_columns(qtbot, viewer, controls):
    viewer.layers["nuclei"].units = ("um", "um")
    result = run(qtbot, controls, "Segment Layer", image_layer="nuclei", min_size=0)
    df = query(result, "SELECT area_um2 FROM nuclei_labels ORDER BY label")
    assert list(df.area_um2) == [49 * 0.25, 100 * 0.25]


def test_unit_of_pixels_is_none(viewer):
    from lumen_napari.controls import unit_of

    assert unit_of(viewer.layers["nuclei"]) is None


@pytest.fixture
def plate(tmp_path):
    from skimage.io import imsave

    for well, count in (("A01", 1), ("A02", 2), ("B01", 3)):
        image = np.zeros((40, 60), np.uint8)
        for i in range(count):
            image[5:15, 5 + 18 * i:15 + 18 * i] = 200
        imsave(tmp_path / f"{well}.png", image, check_contrast=False)
    return tmp_path


def test_segment_folder_makes_one_table(qtbot, controls, plate):
    result = run(qtbot, controls, "Segment Folder", folder=str(plate), pattern="*.png", min_size=0)
    table = result.table
    df = query(result, f"SELECT file, COUNT(*) AS n FROM {table} GROUP BY file ORDER BY file")
    assert df.to_dict("list") == {"file": ["A01.png", "A02.png", "B01.png"], "n": [1, 2, 3]}


def test_segment_folder_without_matches(qtbot, controls, plate):
    result = run(qtbot, controls, "Segment Folder", folder=str(plate), pattern="*.tif")
    assert "No files match '*.tif'" in result.message


def test_source_agent_path_keeps_our_table_name(qtbot, controls):
    from lumen.ai.agents.source import SourceAgent
    from lumen.ai.controls import SourceResult

    store = []
    [tool] = [t for t in SourceAgent._build_tools({"source_controls": [controls]}, result_store=store)
              if t.name == "segment_layer"]
    thread = threading.Thread(target=lambda: tool.function(image_layer="nuclei", min_size=0))
    thread.start()
    qtbot.waitUntil(lambda: not thread.is_alive(), timeout=60_000)
    result = store[0]["result"]
    assert isinstance(result, SourceResult)
    assert result.table == "nuclei_labels"

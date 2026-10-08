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
    assert show(rank_by="area") == "Showing object 2 of 'cells' in napari, the largest by area (400)."
    assert show(rank_by="area", smallest=True) == (
        "Showing object 1 of 'cells' in napari, the smallest by area (4).")
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
    assert show(image_id="C07", rank_by="area").startswith("Showing object 2 of 'C07 labels' in napari")


def test_color_objects_by_a_measurement(qapp):
    viewer = ranked_viewer(qapp)
    color = make_tools(viewer)[2].function
    message = color("area", colormap="gray")
    assert message == "Colored 'cells' by area from 4 to 400 with gray."
    layer = viewer.layers["cells"]
    assert list(layer.colormap.map(1)[:3]) == [0, 0, 0]
    assert list(layer.colormap.map(2)[:3]) == [1, 1, 1]
    assert color() == "Reset the colors of 'cells'."
    assert type(layer.colormap).__name__ == "CyclicLabelColormap"


def test_filter_hides_objects_that_do_not_match(qapp):
    viewer = ranked_viewer(qapp)
    filter_objects = make_tools(viewer)[3].function
    assert filter_objects("area >= 25") == "Showing 2 of 3 objects of 'cells' where area >= 25."
    layer = viewer.layers["cells"]
    assert layer.colormap.map(1)[3] == 0
    assert layer.colormap.map(2)[3] == 1
    assert filter_objects() == "Showing every object of 'cells'."
    assert layer.colormap.map(1)[3] == 1


def test_filter_into_a_new_layer(qapp):
    viewer = ranked_viewer(qapp)
    filter_objects = make_tools(viewer)[3].function
    filter_objects("area < 30", as_new_layer=True)
    new = viewer.layers["cells filtered"]
    assert sorted(np.unique(new.data)) == [0, 1, 3]
    assert list(new.features["index"]) == [1, 3]


def test_filter_sql_cannot_read_files(qapp):
    filter_objects = make_tools(ranked_viewer(qapp))[3].function
    with pytest.raises(Exception, match="disabled"):
        filter_objects("label IN (SELECT 1 FROM read_csv('/etc/hosts'))")


def test_layers_are_found_by_their_table_name(qapp):
    viewer = ViewerModel()
    viewer.add_labels(np.ones((4, 4), int), name="nuclei labels")
    show = make_tools(viewer)[1].function
    assert show(1, labels_layer="nuclei_labels") == "Showing object 1 of 'nuclei labels' in napari."


def test_set_pixel_size_updates_image_and_labels(viewer):
    set_size = make_tools(viewer)[4].function
    message = set_size(0.65)
    assert message.startswith("Set the pixel size of 'nuclei' to 0.65 um.")
    assert tuple(viewer.layers["nuclei"].scale) == (0.65, 0.65)
    assert str(viewer.layers["nuclei"].units[0]) == "micrometer"
    assert tuple(viewer.layers["nuclei labels"].scale) == (0.65, 0.65)


def test_set_voxel_size_in_3d(qapp):
    viewer = ViewerModel()
    viewer.add_image(np.zeros((4, 8, 8)), name="stack")
    make_tools(viewer)[4].function(0.26, z_size=0.29)
    assert tuple(viewer.layers["stack"].scale) == (0.29, 0.26, 0.26)


def test_segmentation_methods_lists_what_is_installed(qapp):
    text = make_tools(ViewerModel())[5].function()
    assert text.splitlines()[0].startswith("- otsu (installed): Fast global threshold")
    assert "- cellpose (not installed: pip install 'lumen-napari[cellpose]')" in text


async def test_compare_tool_hands_its_results_to_the_answer(qapp):
    import pandas as pd

    from lumen_napari.controls import NapariControls

    viewer = ViewerModel()
    controls = NapariControls(viewer=viewer)
    controls._publish_table("objects", pd.DataFrame({
        "well": ["A1", "A2", "B1", "B2"], "compound": ["DMSO", "DMSO", "x", "x"],
        "area": [100.0, 110.0, 200.0, 230.0]}))
    tool = make_tools(viewer, controls)[-1]
    assert tool.name == "compare_conditions"
    _, context = await tool.respond([], {}, table="objects", measurement="area",
                                    condition="compound", control="DMSO", replicate="well", dose="")
    assert "`x`: fold change 2.05" in context["data"]


def test_tools_segment_first_when_nothing_is_segmented(qtbot, qapp):
    import threading

    from lumen_napari.controls import NapariControls

    viewer = ViewerModel()
    image = np.zeros((40, 40))
    image[5:15, 5:15] = 1
    image[25:30, 25:30] = 1
    viewer.add_image(image, name="nuclei")
    controls = NapariControls(viewer=viewer)
    color = make_tools(viewer, controls)[2].function
    out = {}
    thread = threading.Thread(target=lambda: out.update(msg=color("area")))
    thread.start()
    qtbot.waitUntil(lambda: not thread.is_alive(), timeout=60_000)
    assert "nuclei labels" in viewer.layers
    assert out["msg"].startswith("Colored 'nuclei labels' by area")


@pytest.mark.parametrize(("where", "columns", "expected"), [
    ("area >= 20 µm²", ["area"], "area >= 20"),
    ("area > 3.5um2 AND eccentricity < 0.8", ["area", "eccentricity"], "area > 3.5 AND eccentricity < 0.8"),
    ("area < 50 pixels", ["area"], "area < 50"),
    ("area >= 20", ["area_um2", "label"], "area_um2 >= 20"),
    ("volume > 100 µm³", ["volume_um3"], "volume_um3 > 100"),
    ("area_um2 > 1", ["area_um2"], "area_um2 > 1"),
])
def test_clean_condition(where, columns, expected):
    from lumen_napari.tools import clean_condition

    assert clean_condition(where, columns) == expected


def test_filter_reports_columns_on_bad_sql(qapp):
    filter_objects = make_tools(ranked_viewer(qapp))[3].function
    with pytest.raises(ValueError, match="Columns: \\['area'"):
        filter_objects("size > 3")


async def test_actions_reach_the_answer_as_data(qapp):
    tools = make_tools(ranked_viewer(qapp))
    color, filter_objects = tools[2], tools[3]
    await color.respond([], {}, column="area", labels_layer="", colormap="viridis")
    _, out = await filter_objects.respond([], {}, where="area >= 25", labels_layer="",
                                          as_new_layer=False)
    assert out["data"].startswith("Done in napari:\n- Colored 'cells' by area")
    assert "- Showing 2 of 3 objects of 'cells' where area >= 25." in out["data"]


def test_layer_list_answers_simple_counts(qapp):
    from lumen_napari.measure import measure, to_features

    viewer = ViewerModel()
    viewer.add_image(np.zeros((20, 20)), name="nuclei")
    viewer.add_image(np.zeros((20, 20)), name="other")
    labels = np.zeros((20, 20), int)
    labels[1:3, 1:3] = 1
    labels[5:9, 5:9] = 2
    viewer.add_labels(labels, name="nuclei labels", features=to_features(measure(labels)))
    text = make_tools(viewer)[0].function()
    assert "'nuclei labels': labels, shape (20, 20), scale (1.0, 1.0); 2 measured objects, mean area 10" in text
    assert "'other': image" in text and text.count("not segmented yet") == 1


def test_listing_segments_when_nothing_is_segmented(qtbot, qapp):
    import threading

    from lumen_napari.controls import NapariControls

    viewer = ViewerModel()
    image = np.zeros((40, 40))
    image[5:15, 5:15] = 1
    viewer.add_image(image, name="nuclei")
    listing = make_tools(viewer, NapariControls(viewer=viewer))[0].function
    out = {}
    thread = threading.Thread(target=lambda: out.update(text=listing()))
    thread.start()
    qtbot.waitUntil(lambda: not thread.is_alive(), timeout=60_000)
    assert "'nuclei labels': labels" in out["text"] and "1 measured objects" in out["text"]
    assert make_tools(ViewerModel())[0].function() == "napari has no layers open."


async def test_tools_hand_lumen_the_current_table(qapp):
    from lumen_napari.controls import NapariControls

    viewer = ViewerModel()
    image = np.zeros((40, 40))
    image[5:15, 5:15] = 1
    viewer.add_image(image, name="nuclei")
    controls = NapariControls(viewer=viewer)
    controls.segment_layer(image_layer="nuclei", min_size=0)
    tools = make_tools(viewer, controls)
    _, out = await tools[0].respond([], {})
    assert out["table"] == "nuclei_labels"
    assert out["pipeline"].table == "nuclei_labels"
    _, out = await tools[4].respond([], {}, size=0.5, unit="um", z_size=0, layer="")
    assert "measured 'nuclei labels' again" in out["data"]
    assert "area_um2" in out["pipeline"].data.columns

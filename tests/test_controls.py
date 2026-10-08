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
        "Segment Layer", "Measure Layer", "Layer Features", "Segment Folder", "Load Table",
        "Measure Regions",
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
        "segment_layer", "measure_layer", "layer_features", "segment_folder", "load_table",
        "measure_regions",
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
    df = query(result, f"SELECT well, COUNT(*) AS n FROM {table} GROUP BY well ORDER BY well")
    assert df.to_dict("list") == {"well": ["A01", "A02", "B01"], "n": [1, 2, 3]}


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


def test_folder_table_joins_an_uploaded_plate_map(qtbot, controls, plate):
    """The SQL agent mirrors tables from separate sources into one DuckDB to join them."""
    from types import SimpleNamespace

    from lumen.ai.agents.sql import SQLAgent
    from lumen.sources.duckdb import DuckDBSource

    result = run(qtbot, controls, "Segment Folder", folder=str(plate), pattern="*.png", min_size=0)
    plate_map = DuckDBSource.from_df(tables={"plate_map": pd.DataFrame({
        "well": ["A01", "A02", "B01"], "compound": ["DMSO", "taxol", "taxol"],
    })})
    plate_map.tables["plate_map"] = "SELECT * FROM plate_map"
    sources = {("napari", result.table): result.sources[0], ("upload", "plate_map"): plate_map}
    refs = [SimpleNamespace(source="napari", table=result.table),
            SimpleNamespace(source="upload", table="plate_map")]
    merged, _ = SQLAgent._merge_sources(None, sources, refs)
    df = merged.execute(
        f"SELECT compound, COUNT(*) AS n FROM {result.table} o "
        "JOIN plate_map p USING (well) GROUP BY compound ORDER BY compound"
    )
    assert df.to_dict("list") == {"compound": ["DMSO", "taxol"], "n": [1, 5]}


def test_load_table(qtbot, controls, tmp_path):
    pd.DataFrame({"well": ["A01"], "compound": ["DMSO"]}).to_csv(tmp_path / "Plate Map.csv", index=False)
    result = run(qtbot, controls, "Load Table", path=str(tmp_path / "Plate Map.csv"))
    assert result.table == "plate_map"
    assert query(result, "SELECT compound FROM plate_map").compound[0] == "DMSO"
    assert controls.script.lines[-2] == f"tables['plate_map'] = pd.read_csv({str(tmp_path / 'Plate Map.csv')!r})"


def test_load_table_rejects_other_files(qtbot, controls, tmp_path):
    result = run(qtbot, controls, "Load Table", path=str(tmp_path / "notes.txt"))
    assert "Cannot read 'notes.txt'" in result.message


def test_parallel_actions_share_one_source(qtbot, controls, plate, tmp_path):
    """The LLM may call several actions at once and Lumen keeps only the first result."""
    pd.DataFrame({"well": ["A01"], "compound": ["DMSO"]}).to_csv(tmp_path / "map.csv", index=False)
    results = {}

    def call(name, **params):
        results[name] = controls._actions[name](**params)

    threads = [
        threading.Thread(target=call, args=("Segment Folder",),
                         kwargs={"folder": str(plate), "pattern": "*.png", "min_size": 0}),
        threading.Thread(target=call, args=("Load Table",), kwargs={"path": str(tmp_path / "map.csv")}),
    ]
    for thread in threads:
        thread.start()
    qtbot.waitUntil(lambda: not any(t.is_alive() for t in threads), timeout=60_000)
    first = results["Load Table"]
    assert results["Segment Folder"].sources[0] is first.sources[0]
    df = query(first, f"SELECT COUNT(*) AS n FROM {results['Segment Folder'].table} JOIN map USING (well)")
    assert df.n[0] == 1


def test_segment_folder_joins_a_plate_map(qtbot, controls, plate, tmp_path):
    pd.DataFrame({"well": ["A01", "A02", "B01"], "compound": ["DMSO", "taxol", "taxol"]}).to_csv(
        tmp_path / "map.csv", index=False)
    result = run(qtbot, controls, "Segment Folder", folder=str(plate), pattern="*.png", min_size=0,
                 plate_map=str(tmp_path / "map.csv"))
    df = query(result, f"SELECT compound, COUNT(*) AS n FROM {result.table} GROUP BY 1 ORDER BY 1")
    assert df.to_dict("list") == {"compound": ["DMSO", "taxol"], "n": [1, 5]}


@pytest.fixture
def big(viewer):
    full = np.zeros((80, 80))
    full[10:30, 10:30] = 1
    full[50:70, 50:70] = 1
    return viewer.add_image([full, full[::2, ::2]], multiscale=True, name="slide")


def test_large_images_use_a_coarser_level(qtbot, viewer, controls, big, monkeypatch):
    monkeypatch.setattr("lumen_napari.region.MAX_PIXELS", 2000)
    result = run(qtbot, controls, "Segment Layer", image_layer="slide", min_size=0)
    labels = viewer.layers["slide labels"]
    assert labels.data.shape == (40, 40)
    assert labels.scale[0] == 2
    df = query(result, "SELECT area, centroid_0 FROM slide_labels ORDER BY label")
    assert list(df.area) == [400, 400]
    assert list(df.centroid_0) == [19, 59]


def test_visible_only_segments_the_crop_at_full_detail(qtbot, viewer, controls, big):
    big.data_level = 1
    big.corner_pixels = np.array([[20, 20], [39, 39]])
    result = run(qtbot, controls, "Segment Layer", image_layer="slide", min_size=0,
                 visible_only=True)
    labels = viewer.layers["slide labels"]
    assert labels.data.shape == (40, 40)
    assert tuple(labels.translate) == (40, 40)
    assert query(result, "SELECT COUNT(*) AS n FROM slide_labels").n[0] == 1


def test_measure_other_channels(qtbot, viewer, controls):
    viewer.add_image(viewer.layers["nuclei"].data * 10, name="Tubulin")
    result = run(qtbot, controls, "Segment Layer", image_layer="nuclei", min_size=0,
                 measure_layers=["Tubulin"])
    df = query(result, "SELECT intensity_mean, intensity_mean_tubulin FROM nuclei_labels ORDER BY label")
    assert list(df.intensity_mean_tubulin) == list(df.intensity_mean * 10)

    result = run(qtbot, controls, "Measure Layer", labels_layer="nuclei labels",
                 measure_layers=["Tubulin"])
    assert "intensity_max_tubulin" in query(result, "SELECT * FROM nuclei_labels").columns


def test_table_names_are_ascii():
    assert table_name("Kern β-Färbung") == "kern_f_rbung"


def test_measure_regions(qtbot, viewer, controls):
    run(qtbot, controls, "Segment Layer", image_layer="nuclei", min_size=0)
    viewer.layers["nuclei"].units = ("um", "um")
    viewer.layers["nuclei labels"].units = ("um", "um")
    viewer.add_shapes([[[0, 0], [0, 8], [8, 8], [8, 0]]], shape_type="rectangle", name="roi")
    result = run(qtbot, controls, "Measure Regions", labels_layer="nuclei labels", shapes_layer="roi")
    assert result.table == "nuclei_labels_by_region"
    df = query(result, "SELECT region, COUNT(*) AS n, ANY_VALUE(region_area_um2) AS a "
                       "FROM nuclei_labels_by_region GROUP BY region ORDER BY region")
    assert df.region.tolist() == ["outside", "region 1"]
    assert df.n.tolist() == [1, 1]


def test_painting_by_hand_remeasures_the_table(qtbot, viewer, controls):
    result = run(qtbot, controls, "Segment Layer", image_layer="nuclei", min_size=0)
    layer = viewer.layers["nuclei labels"]
    assert len(layer.features) == 2
    layer.brush_size = 3
    layer.paint((0, 39), 9)  # draw a new object by hand
    qtbot.waitUntil(lambda: len(layer.features) == 3, timeout=5_000)
    df = query(result, "SELECT label FROM nuclei_labels ORDER BY label")
    assert df.label.tolist() == [1, 2, 9]
    assert "was edited by hand" in controls.script.lines[-2]


def test_moving_points_updates_their_table(qtbot, viewer, controls):
    viewer.add_points([[1, 2]], name="spots")
    result = run(qtbot, controls, "Layer Features", layer="spots")
    viewer.layers["spots"].data = [[5, 6]]
    qtbot.waitUntil(lambda: query(result, "SELECT position_0 FROM spots").position_0[0] == 5,
                    timeout=5_000)

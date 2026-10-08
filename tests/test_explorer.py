import numpy as np
import pytest
from lumen.pipeline import Pipeline
from lumen.sources.duckdb import DuckDBSource
from napari.components import ViewerModel

from lumen_napari.explorer import ObjectExplorer, explorer_for
from lumen_napari.measure import measure, to_features


@pytest.fixture
def viewer(qapp):
    viewer = ViewerModel()
    labels = np.zeros((60, 60), int)
    labels[2:6, 2:6] = 1
    labels[30:50, 30:50] = 2
    viewer.add_labels(labels, name="nuclei labels", features=to_features(measure(labels)))
    other = np.zeros((60, 60), int)
    other[10:12, 10:12] = 1
    viewer.add_labels(other, name="other")
    return viewer


def pipeline_for(viewer, table="nuclei_labels"):
    df = measure(viewer.layers["nuclei labels"].data)
    source = DuckDBSource.from_df(tables={table: df})
    source.tables[table] = f"SELECT * FROM {table}"
    return Pipeline(source=source, table=table)


async def test_applies_to_object_tables(viewer):
    assert await ObjectExplorer.applies(pipeline_for(viewer))


def test_click_zooms_napari_to_the_object(viewer):
    explorer = explorer_for(viewer).instance()
    pane = explorer(pipeline_for(viewer), {})
    assert pane.object.kdims[0].name == "area"
    explorer._selection.event(index=[1])
    layer = viewer.layers["nuclei labels"]
    assert layer.selected_label == 2
    assert viewer.scene.camera.center[-2:] == (40, 40)
    assert explorer._dynamic_provides == {"selected_object": 2}


def test_unknown_table_uses_latest_labels_layer(viewer):
    explorer = explorer_for(viewer).instance()
    explorer(pipeline_for(viewer, table="biggest"), {})
    explorer._selection.event(index=[0])
    assert viewer.layers["other"].selected_label == 1


def test_viewer_is_not_copied(viewer):
    assert explorer_for(viewer).instance().viewer is viewer

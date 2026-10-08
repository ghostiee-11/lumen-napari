import numpy as np
import pandas as pd
import panel as pn
import pytest
from lumen.pipeline import Pipeline
from lumen.sources.duckdb import DuckDBSource
from lumen.views.base import VegaLiteView
from napari.components import ViewerModel

from lumen_napari import clickable
from lumen_napari.clickable import PICK, make_charts_clickable, pick_fields, with_pick

SCATTER = {"mark": "point", "encoding": {"x": {"field": "area", "type": "quantitative"},
                                          "y": {"field": "label", "type": "quantitative"}}}


@pytest.fixture
def viewer(qapp, monkeypatch):
    monkeypatch.setattr(VegaLiteView, "get_panel", clickable._original)
    viewer = ViewerModel()
    labels = np.zeros((60, 60), int)
    labels[2:6, 2:6] = 1
    labels[40:50, 40:50] = 2
    viewer.add_labels(labels, name="nuclei labels")
    make_charts_clickable(viewer)
    return viewer


def view_of(df, spec=SCATTER, table="nuclei_labels"):
    source = DuckDBSource.from_df(tables={table: df})
    source.tables[table] = f"SELECT * FROM {table}"
    return VegaLiteView(pipeline=Pipeline(source=source, table=table), spec=spec)


def test_pick_fields():
    assert pick_fields(pd.DataFrame(columns=["label", "area", "centroid_0", "centroid_1_um"])) == [
        "label", "centroid_0", "centroid_1_um"]
    assert pick_fields(pd.DataFrame(columns=["compound", "mean_area"])) == []


def test_with_pick_goes_on_a_unit_spec_or_the_first_mark_layer():
    assert with_pick({"mark": "point"}, ["label"])["params"][0]["name"] == PICK
    layered = with_pick({"layer": [{"mark": "rule"}, {"mark": "point"}]}, ["label"])
    assert layered["layer"][0]["params"][0]["select"]["fields"] == ["label"]
    assert with_pick({"hconcat": []}, ["label"]) == {"hconcat": []}


def test_clicking_a_chart_point_zooms_napari(viewer):
    pane = view_of(pd.DataFrame({"label": [1, 2], "area": [16, 100]})).get_panel()
    assert isinstance(pane, pn.pane.Vega)
    pane.selection.param.update(**{PICK: [{"label": 2}]})
    assert viewer.layers["nuclei labels"].selected_label == 2
    assert viewer.scene.camera.center[-2:] == (45, 45)


def test_aggregate_charts_are_left_alone(viewer):
    pane = view_of(pd.DataFrame({"compound": ["a"], "mean_area": [3.0]}),
                   {"mark": "bar", "encoding": {}}).get_panel()
    assert "params" not in pane.object


def test_drawn_charts_are_recorded_as_json(qapp, monkeypatch):
    import json

    monkeypatch.setattr(VegaLiteView, "get_panel", clickable._original)
    seen = []
    make_charts_clickable(ViewerModel(), on_chart=seen.append)
    view_of(pd.DataFrame({"compound": ["a"], "mean_area": [3.0]}),
            {"mark": "bar", "encoding": {}}).get_panel()
    assert seen[0]["data"]["values"] == [{"compound": "a", "mean_area": 3.0}]
    json.dumps(seen[0], default=str)

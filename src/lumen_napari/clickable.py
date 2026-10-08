"""Make Lumen's own charts clickable: a point that is one object zooms napari to it."""

from __future__ import annotations

import pandas as pd
from lumen.views.base import VegaLiteView
from napari.components import ViewerModel

from .pick import show_row

PICK = "napari_pick"

# ponytail: one viewer per process (the latest bound); keep a viewer per session if several
_viewer: list[ViewerModel] = []
_on_chart: list = []
_original = VegaLiteView.get_panel


def pick_fields(df: pd.DataFrame) -> list[str]:
    """Columns that identify or locate an object, sent back when a chart point is clicked.
    Empty when the chart's rows are not objects (an aggregate like a mean per compound)."""
    return [c for c in df.columns
            if c in ("label", "image_id") or c.startswith(("centroid_0", "centroid_1"))]


def with_pick(spec: dict, fields: list[str]) -> dict:
    """The spec with a point selection on `fields`, added to the first unit (single mark)."""
    selection = {"name": PICK, "select": {"type": "point", "fields": fields}}
    if "mark" in spec:
        return {**spec, "params": [*spec.get("params", []), selection]}
    if "layer" in spec:
        layers = list(spec["layer"])
        for i, layer in enumerate(layers):
            if "mark" in layer:
                layers[i] = {**layer, "params": [*layer.get("params", []), selection]}
                return {**spec, "layer": layers}
    return spec


def _get_panel(self):
    pane = _original(self)
    for record in _on_chart:
        record(jsonable(pane.object))
    if not _viewer:
        return pane
    fields = pick_fields(self.get_data())
    if not fields:
        return pane
    pane.object = with_pick(pane.object, fields)
    if PICK in pane.selection.param:
        viewer, table = _viewer[-1], self.pipeline.table
        pane.selection.param.watch(lambda event: _show(viewer, table, event.new), PICK)
    return pane


def _show(viewer: ViewerModel, table: str, picked) -> None:
    if picked:
        show_row(viewer, table, picked[0])


def jsonable(spec: dict) -> dict:
    """The spec with its data frames turned into records, ready for json and vega-embed."""
    def convert(value):
        if isinstance(value, pd.DataFrame):
            return value.to_dict("records")
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        return value

    return convert(spec)


def make_charts_clickable(viewer: ViewerModel, on_chart=None) -> None:
    """Send clicks on Lumen's charts to this viewer, and every drawn spec to `on_chart`."""
    _viewer[:] = [viewer]
    _on_chart[:] = [on_chart] if on_chart else []
    VegaLiteView.get_panel = _get_panel

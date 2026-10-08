"""Make Lumen's own charts clickable: a point that is one object zooms napari to it."""

from __future__ import annotations

import pandas as pd
from lumen.views.base import VegaLiteView
from napari.components import ViewerModel

from .pick import show_row

PICK = "napari_pick"

# ponytail: one viewer per process (the latest bound); keep a viewer per session if several
_viewer: list[ViewerModel] = []
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


def make_charts_clickable(viewer: ViewerModel) -> None:
    """Send clicks on Lumen's charts to this viewer."""
    _viewer[:] = [viewer]
    VegaLiteView.get_panel = _get_panel

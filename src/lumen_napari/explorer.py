"""A Lumen analysis that plots measured objects and shows a clicked one in napari."""

import holoviews as hv
import pandas as pd
import panel as pn
import param
from lumen.ai.analysis import Analysis
from napari.components import ViewerModel
from napari.layers import Labels

from .batch import open_in_viewer
from .controls import table_name
from .tools import _focus, _labels_layer

hv.extension("bokeh", logo=False)


class ObjectExplorer(Analysis):
    """Scatter plot of segmented objects. Clicking a point zooms napari to that object."""

    columns = param.List(default=["label"], constant=True)

    x = param.Selector(default=None, objects=[], doc="Measurement on the x axis.")

    y = param.Selector(default=None, objects=[], doc="Measurement on the y axis.")

    viewer = param.ClassSelector(class_=ViewerModel, instantiate=False, precedence=-1)

    _field_params = ("x", "y")

    def __call__(self, pipeline, context):
        df = pipeline.data
        default_x, default_y = _default_axes(df)
        x, y = self.x or default_x, self.y or default_y
        batch = "image_id" in df.columns
        layer = None if batch else _layer_for(self.viewer, pipeline.table)
        where = "open its image in napari" if batch else f"show it in napari ({layer.name!r})"
        points = hv.Points(df, kdims=[x, y], vdims=[c for c in df.columns if c not in (x, y)]).opts(
            tools=["tap", "hover"], size=6, responsive=True, height=400,
            selection_color="#e8590c", nonselection_alpha=0.3,
            title=f"Click an object to {where}",
        )
        self._selection = hv.streams.Selection1D(source=points)
        self._selection.add_subscriber(lambda index: self.show(df, layer, index))
        return pn.pane.HoloViews(points, sizing_mode="stretch_width")

    def show(self, df: pd.DataFrame, layer: Labels | None, index: list[int]) -> None:
        if not index:
            return
        row = df.iloc[index[0]]
        label = int(row["label"])
        if layer is None:
            layer = open_in_viewer(self.viewer, row["image_id"])
        _focus(self.viewer, layer, label)
        self._dynamic_provides = {"selected_object": label}


def explorer_for(viewer: ViewerModel) -> type[ObjectExplorer]:
    """The analysis class bound to one viewer; Lumen instantiates analyses itself."""
    return type("ObjectExplorer", (ObjectExplorer,), {"viewer": param.ClassSelector(
        class_=ViewerModel, default=viewer, instantiate=False, precedence=-1,
    )})


def _layer_for(viewer: ViewerModel, table: str) -> Labels:
    """The labels layer a table was measured from, else the most recent labels layer."""
    for layer in viewer.layers:
        if isinstance(layer, Labels) and table_name(layer.name) == table:
            return layer
    return _labels_layer(viewer, "")


def _default_axes(df: pd.DataFrame) -> tuple[str, str]:
    numeric = [c for c in df.select_dtypes("number").columns if c != "label"]
    preferred = [c for c in numeric if c.startswith(("area", "volume", "intensity_mean"))]
    ordered = preferred + [c for c in numeric if c not in preferred]
    return ordered[0], ordered[1] if len(ordered) > 1 else ordered[0]

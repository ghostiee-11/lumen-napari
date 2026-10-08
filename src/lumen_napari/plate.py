"""A Lumen analysis that draws a plate heatmap of a per-well measurement."""

import holoviews as hv
import pandas as pd
import panel as pn
import param
from lumen.ai.analysis import Analysis
from napari.components import ViewerModel
from superqt.utils import ensure_main_thread

from .batch import open_in_viewer

hv.extension("bokeh", logo=False)

ROWS_96, COLS_96 = "ABCDEFGH", 12
ROWS_384, COLS_384 = "ABCDEFGHIJKLMNOP", 24


class PlateHeatmap(Analysis):
    """Heatmap of a measurement per well on a 96 or 384 well plate. Clicking a well opens one
    of its images in napari."""

    columns = param.List(default=["well"], constant=True)

    value = param.Selector(default=None, objects=[], doc="Measurement to color the wells by.")

    statistic = param.Selector(default="mean", objects=["mean", "median", "count", "sum", "std"])

    viewer = param.ClassSelector(class_=ViewerModel, instantiate=False, precedence=-1)

    _field_params = ("value",)

    def __call__(self, pipeline, context):
        df = pipeline.data
        value = self.value or _default_value(df)
        wells = per_well(df, value, self.statistic)
        rows, cols = plate_shape(wells["well"])
        label = f"{self.statistic} {value}" if self.statistic != "count" else "objects"
        heatmap = hv.HeatMap(wells, kdims=["column", "row"], vdims=[label, "well"]).opts(
            tools=["tap", "hover"], cmap="viridis", colorbar=True, responsive=True,
            height=40 * len(rows) + 80, invert_yaxis=True, xticks=list(range(1, cols + 1)),
            title=f"{label} per well (click a well to open it in napari)",
        ).redim.range(column=(0.5, cols + 0.5)).redim.values(row=list(rows))
        self._wells = wells
        self._selection = hv.streams.Selection1D(source=heatmap)
        self._selection.add_subscriber(lambda index: self.open(df, index))
        return pn.pane.HoloViews(heatmap, sizing_mode="stretch_width")

    def open(self, df: pd.DataFrame, index: list[int]) -> None:
        if not index or "image_id" not in df.columns:
            return
        well = self._wells.iloc[index[0]]["well"]
        image_id = df.loc[df["well"] == well, "image_id"].iloc[0]
        _fit(self.viewer, open_in_viewer(self.viewer, image_id))
        self._dynamic_provides = {"selected_well": well}


def per_well(df: pd.DataFrame, value: str, statistic: str = "mean") -> pd.DataFrame:
    """One row per well with its row letter, column number and the statistic."""
    label = f"{statistic} {value}" if statistic != "count" else "objects"
    grouped = df.groupby("well")[value].agg(statistic).rename(label).reset_index()
    grouped["row"] = grouped["well"].str[0]
    grouped["column"] = grouped["well"].str[1:].astype(int)
    # HoloViews HeatMap cannot reshape pandas' Arrow-backed strings.
    text = {"row": object, "well": object}
    return grouped[["column", "row", label, "well"]].astype(text)


def plate_shape(wells: pd.Series) -> tuple[str, int]:
    """Rows and column count of the smallest standard plate holding these wells."""
    rows = set(wells.str[0])
    cols = wells.str[1:].astype(int)
    if rows <= set(ROWS_96) and cols.max() <= COLS_96:
        return ROWS_96, COLS_96
    return ROWS_384, COLS_384


def plate_for(viewer: ViewerModel) -> type[PlateHeatmap]:
    """The analysis class bound to one viewer; Lumen instantiates analyses itself."""
    return type("PlateHeatmap", (PlateHeatmap,), {"viewer": param.ClassSelector(
        class_=ViewerModel, default=viewer, instantiate=False, precedence=-1,
    )})


@ensure_main_thread(await_return=True, timeout=10_000)
def _fit(viewer: ViewerModel, layer) -> None:
    viewer.fit_to_view(layers=[layer])


def _default_value(df: pd.DataFrame) -> str:
    numeric = [c for c in df.select_dtypes("number").columns if c != "label"]
    preferred = [c for c in numeric if c.startswith(("area", "volume", "intensity_mean"))]
    return (preferred or numeric)[0]

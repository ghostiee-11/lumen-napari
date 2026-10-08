"""Show the napari object behind a clicked chart row."""

from __future__ import annotations

from napari.components import ViewerModel
from napari.layers import Labels
from superqt.utils import ensure_main_thread

from .batch import open_in_viewer
from .controls import table_name
from .tools import _focus, _labels_layer


def labels_for(viewer: ViewerModel, table: str) -> Labels:
    """The labels layer a table was measured from, else the most recent labels layer."""
    for layer in viewer.layers:
        if isinstance(layer, Labels) and table_name(layer.name) == table:
            return layer
    return _labels_layer(viewer, "")


def centroid(row: dict) -> tuple[float, float] | None:
    """The (y, x) world position in a row of a whole-slide table, if it has one."""
    ys = [k for k in row if k.startswith("centroid_0")]
    xs = [k for k in row if k.startswith("centroid_1")]
    return (float(row[ys[0]]), float(row[xs[0]])) if ys and xs else None


def show_row(viewer: ViewerModel, table: str, row: dict) -> str:
    """Zoom napari to the object a row describes; returns what was shown."""
    if "label" in row and "image_id" in row:
        layer = open_in_viewer(viewer, row["image_id"])
        _focus(viewer, layer, int(row["label"]))
        return f"object {int(row['label'])} of {row['image_id']!r}"
    if "label" in row and any(isinstance(layer, Labels) for layer in viewer.layers):
        layer = labels_for(viewer, table)
        _focus(viewer, layer, int(row["label"]))
        return f"object {int(row['label'])} of {layer.name!r}"
    if position := centroid(row):
        _center(viewer, position)
        return f"position {position}"
    raise ValueError("The clicked row has no label or position to show in napari.")


@ensure_main_thread(await_return=True, timeout=10_000)
def _center(viewer: ViewerModel, position: tuple[float, float]) -> None:
    viewer.scene.camera.center = position
    viewer.scene.camera.zoom = max(viewer.scene.camera.zoom, 4)

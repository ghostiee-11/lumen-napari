"""Move the napari camera to a single labeled object."""

from __future__ import annotations

import numpy as np
from napari.components import ViewerModel
from napari.layers import Labels


def label_bbox(layer: Labels, label: int) -> tuple[np.ndarray, np.ndarray]:
    """World-space (min, max) corners of one label."""
    data = layer.data[0] if layer.multiscale else layer.data
    # ponytail: full scan of the label array, read bbox from the features table if this gets slow
    coords = np.argwhere(np.asarray(data) == label)
    if not len(coords):
        raise ValueError(f"Label {label} not found in layer {layer.name!r}.")
    lo = layer.data_to_world(coords.min(axis=0))
    hi = layer.data_to_world(coords.max(axis=0) + 1)
    return np.minimum(lo, hi), np.maximum(lo, hi)


def focus_label(viewer: ViewerModel, layer: Labels, label: int, fill: float = 0.5) -> None:
    """Center and zoom on one label, step to its middle slice, and select it."""
    lo, hi = label_bbox(layer, label)
    center = (lo + hi) / 2
    offset = viewer.dims.ndim - len(center)
    for axis, value in enumerate(center):
        if axis + offset not in viewer.dims.displayed:
            viewer.dims.set_point(axis + offset, value)
    shown = [d - offset for d in viewer.dims.displayed if d >= offset]
    camera = viewer.scene.camera
    camera.center = tuple(center[shown])
    size = np.max(hi[shown] - lo[shown])
    camera.zoom = fill * np.min(viewer.canvas.size) / size
    layer.selected_label = label

"""Lumen tools that inspect and steer the live napari viewer."""

from __future__ import annotations

from collections.abc import Callable

from napari.components import ViewerModel
from napari.layers import Image, Labels, Layer
from superqt.utils import ensure_main_thread

from .focus import focus_label


def make_tools(viewer: ViewerModel) -> list[Callable]:
    """Build the viewer tools as plain functions, which Lumen wraps as FunctionTools."""

    def list_napari_layers() -> str:
        """List the layers open in napari with their type, shape and pixel size."""
        if not len(viewer.layers):
            return "napari has no layers open."
        return "napari layers:\n" + "\n".join(_describe(layer) for layer in viewer.layers)

    def show_object_in_napari(label: int, labels_layer: str = "") -> str:
        """Zoom the napari viewer to one segmented object and select it.

        Parameters
        ----------
        label : int
            The object's label value, the `label` column of a measurement table.
        labels_layer : str
            Name of the napari labels layer. Defaults to the most recently added one.
        """
        layer = _labels_layer(viewer, labels_layer)
        _focus(viewer, layer, int(label))
        return f"Showing object {label} of {layer.name!r} in napari."

    return [list_napari_layers, show_object_in_napari]


def _describe(layer: Layer) -> str:
    kind = type(layer).__name__.lower()
    scale = tuple(float(s) for s in layer.scale)
    if isinstance(layer, Image | Labels):
        size = f"shape {tuple(layer.data[0].shape if layer.multiscale else layer.data.shape)}"
    else:
        size = f"{len(layer.data)} items"
    return f"- {layer.name!r}: {kind}, {size}, scale {scale}"


def _labels_layer(viewer: ViewerModel, name: str) -> Labels:
    layers = [layer for layer in viewer.layers if isinstance(layer, Labels)]
    if not layers:
        raise ValueError("napari has no labels layer. Segment an image first.")
    if not name:
        return layers[-1]
    for layer in layers:
        if layer.name == name:
            return layer
    raise ValueError(f"No labels layer named {name!r}. Available: {[l.name for l in layers]}.")


@ensure_main_thread(await_return=True, timeout=10_000)
def _focus(viewer: ViewerModel, layer: Labels, label: int) -> None:
    focus_label(viewer, layer, label)

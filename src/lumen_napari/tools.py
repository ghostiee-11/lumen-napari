"""Lumen tools that inspect and steer the live napari viewer."""

from __future__ import annotations

from lumen.ai.tools import FunctionTool
from napari.components import ViewerModel
from napari.layers import Image, Labels, Layer
from superqt.utils import ensure_main_thread

from .focus import focus_label


class ViewerTool(FunctionTool):
    """FunctionTool that ignores the step title Lumen's planner passes to every actor."""

    # ponytail: drop once Lumen's FunctionTool stops forwarding step_title to the function
    async def respond(self, messages, context, step_title=None, **kwargs):
        return await super().respond(messages, context, **kwargs)


def make_tools(viewer: ViewerModel) -> list[ViewerTool]:
    """Build the Lumen tools that read and steer the viewer."""

    def list_napari_layers() -> str:
        """List the layers open in napari with their type, shape and pixel size."""
        if not len(viewer.layers):
            return "napari has no layers open."
        return "napari layers:\n" + "\n".join(_describe(layer) for layer in viewer.layers)

    def show_object_in_napari(
        label: int = 0, rank_by: str = "", smallest: bool = False, labels_layer: str = ""
    ) -> str:
        """Zoom the napari viewer to one segmented object and select it.

        Give either the object's label, or rank_by to pick the largest (or smallest) object by
        a measurement. Use rank_by for requests like "show the biggest nucleus" instead of
        guessing a label.

        Parameters
        ----------
        label : int
            The object's label value, the `label` column of a measurement table.
        rank_by : str
            Measurement column to rank by, such as 'area' or 'intensity_mean'.
        smallest : bool
            With rank_by, show the smallest object instead of the largest.
        labels_layer : str
            Name of the napari labels layer. Defaults to the most recently added one.
        """
        layer = _labels_layer(viewer, labels_layer)
        if rank_by:
            label = _ranked_label(layer, rank_by, smallest)
        elif not label:
            raise ValueError("Give a label, or rank_by a measurement column such as 'area'.")
        _focus(viewer, layer, int(label))
        return f"Showing object {label} of {layer.name!r} in napari."

    return [ViewerTool(list_napari_layers), ViewerTool(show_object_in_napari)]


def _describe(layer: Layer) -> str:
    kind = type(layer).__name__.lower()
    scale = tuple(float(s) for s in layer.scale)
    if isinstance(layer, Image | Labels):
        size = f"shape {tuple(layer.data[0].shape if layer.multiscale else layer.data.shape)}"
    else:
        size = f"{len(layer.data)} items"
    return f"- {layer.name!r}: {kind}, {size}, scale {scale}"


def _ranked_label(layer: Labels, column: str, smallest: bool) -> int:
    features = layer.features
    if column not in features.columns:
        columns = [c for c in features.columns if c != "index"]
        raise ValueError(f"{layer.name!r} has no {column!r} measurement. Columns: {columns}.")
    row = features[column].idxmin() if smallest else features[column].idxmax()
    return int(features.loc[row, "index"])


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

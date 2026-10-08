"""Lumen tools that inspect and steer the live napari viewer."""

from __future__ import annotations

from lumen.ai.tools import FunctionTool
from napari.components import ViewerModel
from napari.layers import Image, Labels, Layer
from napari.utils.colormaps import DirectLabelColormap, ensure_colormap, label_colormap
from superqt.utils import ensure_main_thread

from .batch import open_in_viewer
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
        label: int = 0,
        rank_by: str = "",
        smallest: bool = False,
        labels_layer: str = "",
        image_id: str = "",
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
        image_id : str
            For objects from a segmented folder: the image_id of their image, which is then
            opened in napari.
        """
        layer = open_in_viewer(viewer, image_id) if image_id else _labels_layer(viewer, labels_layer)
        if rank_by:
            label = _ranked_label(layer, rank_by, smallest)
        elif not label:
            raise ValueError("Give a label, or rank_by a measurement column such as 'area'.")
        _focus(viewer, layer, int(label))
        return f"Showing object {label} of {layer.name!r} in napari."

    def color_objects_by(column: str = "", labels_layer: str = "", colormap: str = "viridis") -> str:
        """Color every object in a napari labels layer by one of its measurements, a heatmap on
        the image itself. Call with no column to go back to the default colors.

        Parameters
        ----------
        column : str
            Measurement column to color by, such as 'area' or 'intensity_mean'.
        labels_layer : str
            Name of the napari labels layer. Defaults to the most recently added one.
        colormap : str
            Name of a colormap such as 'viridis', 'magma' or 'turbo'.
        """
        layer = _labels_layer(viewer, labels_layer)
        if not column:
            _set_colormap(layer, label_colormap())
            return f"Reset the colors of {layer.name!r}."
        values = _column(layer, column).astype(float)
        low, high = values.min(), values.max()
        scaled = (values - low) / (high - low) if high > low else values * 0
        colors = ensure_colormap(colormap).map(scaled.to_numpy())
        labels = layer.features["index"]
        mapping = {int(label): color for label, color in zip(labels, colors, strict=True)}
        _set_colormap(layer, DirectLabelColormap(color_dict={None: (0, 0, 0, 0), **mapping}))
        return f"Colored {layer.name!r} by {column} from {low:g} to {high:g} with {colormap}."

    return [
        ViewerTool(list_napari_layers),
        ViewerTool(show_object_in_napari),
        ViewerTool(color_objects_by),
    ]


def _describe(layer: Layer) -> str:
    kind = type(layer).__name__.lower()
    scale = tuple(float(s) for s in layer.scale)
    if isinstance(layer, Image | Labels):
        size = f"shape {tuple(layer.data[0].shape if layer.multiscale else layer.data.shape)}"
    else:
        size = f"{len(layer.data)} items"
    return f"- {layer.name!r}: {kind}, {size}, scale {scale}"


def _column(layer: Labels, column: str):
    features = layer.features
    if column not in features.columns:
        columns = [c for c in features.columns if c != "index"]
        raise ValueError(f"{layer.name!r} has no {column!r} measurement. Columns: {columns}.")
    return features[column]


def _ranked_label(layer: Labels, column: str, smallest: bool) -> int:
    values = _column(layer, column)
    row = values.idxmin() if smallest else values.idxmax()
    return int(layer.features.loc[row, "index"])


@ensure_main_thread(await_return=True, timeout=10_000)
def _set_colormap(layer: Labels, colormap) -> None:
    layer.colormap = colormap


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

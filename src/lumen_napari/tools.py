"""Lumen tools that inspect and steer the live napari viewer."""

from __future__ import annotations

import functools
import re

import duckdb
import numpy as np
import param
from lumen.ai.tools import FunctionTool
from napari.components import ViewerModel
from napari.layers import Image, Labels, Layer
from napari.utils.colormaps import DirectLabelColormap, ensure_colormap, label_colormap
from superqt.utils import ensure_main_thread

from .batch import open_in_viewer
from .controls import find_layer
from .focus import focus_label
from .segment import INSTALL, METHODS, available


class ViewerTool(FunctionTool):
    """FunctionTool that ignores the step title Lumen's planner passes to every actor. With a
    shared `done` list, what it did reaches the answer as data, with the other recent steps,
    so the reply knows napari was changed."""

    done = param.List(default=None, allow_None=True, instantiate=False, doc="""
        Shared list of recent napari actions.""")

    # ponytail: drop step_title once Lumen's FunctionTool stops forwarding it to the function
    async def respond(self, messages, context, step_title=None, **kwargs):
        outputs, out = await super().respond(messages, context, **kwargs)
        if self.done is not None and "data" in out:
            self.done.append(str(out["data"]))
            del self.done[:-5]
            out["data"] = "Done in napari:\n" + "\n".join(f"- {step}" for step in self.done)
        return outputs, out


def make_tools(viewer: ViewerModel, controls=None) -> list[ViewerTool]:
    """Build the Lumen tools that read and steer the viewer. With the session's napari
    controls, statistics on their tables are a tool too."""

    done: list[str] = []

    def objects_layer(name: str) -> Labels:
        """The labels layer to act on, segmenting the first image first if nothing is
        segmented yet, so a question works whatever order it is asked in."""
        nothing_segmented = not any(isinstance(layer, Labels) for layer in viewer.layers)
        images = [layer.name for layer in viewer.layers if isinstance(layer, Image)]
        if controls is not None and nothing_segmented and images:
            controls.segment_layer(
                image_layer=images[0],
                reason="Nothing was segmented yet, so the image was segmented first.",
            )
        return _labels_layer(viewer, name)

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
        layer = open_in_viewer(viewer, image_id) if image_id else objects_layer(labels_layer)
        why = ""
        if rank_by:
            label = _ranked_label(layer, rank_by, smallest)
            value = _column(layer, rank_by)[layer.features["index"] == label].iat[0]
            why = f", the {'smallest' if smallest else 'largest'} by {rank_by} ({value:g})"
        elif not label:
            raise ValueError("Give a label, or rank_by a measurement column such as 'area'.")
        _focus(viewer, layer, int(label))
        return f"Showing object {label} of {layer.name!r} in napari{why}."

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
        layer = objects_layer(labels_layer)
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

    def filter_objects(where: str = "", labels_layer: str = "", as_new_layer: bool = False) -> str:
        """Show only the objects of a napari labels layer that match a SQL condition on their
        measurements, such as "area >= 50" or "intensity_mean > 200 AND eccentricity < 0.8".
        The others are hidden, or with as_new_layer a new labels layer holds just the matches.
        Call with no condition to show every object again.

        Parameters
        ----------
        where : str
            SQL condition on the layer's measurement columns.
        labels_layer : str
            Name of the napari labels layer. Defaults to the most recently added one.
        as_new_layer : bool
            Put the matching objects in a new labels layer instead of hiding the others.
        """
        layer = objects_layer(labels_layer)
        if not where:
            _set_colormap(layer, label_colormap())
            return f"Showing every object of {layer.name!r}."
        keep = _matching(layer, where)
        if as_new_layer:
            name = f"{layer.name} filtered"
            _add_filtered(viewer, layer, keep, name)
            return f"Added {name!r} with the {len(keep)} objects where {where}."
        colors = {label: layer.colormap.map(label) for label in keep}
        _set_colormap(layer, DirectLabelColormap(color_dict={None: (0, 0, 0, 0), **colors}))
        return f"Showing {len(keep)} of {len(layer.features)} objects of {layer.name!r} where {where}."

    def set_pixel_size(size: float, unit: str = "um", z_size: float = 0, layer: str = "") -> str:
        """Set the physical pixel size of a napari image layer and its labels layer, so sizes
        are measured in real units such as micrometers. Use when the user gives the pixel or
        voxel size.

        Parameters
        ----------
        size : float
            Pixel size along x and y.
        unit : str
            Unit of the size, such as 'um' or 'nm'.
        z_size : float
            For 3D images, the spacing between slices. Defaults to size.
        layer : str
            Name of the image layer. Defaults to the first image layer.
        """
        images = [l for l in viewer.layers if isinstance(l, Image)]
        if not images:
            raise ValueError("napari has no image layer.")
        image = find_layer(images, layer) if layer else images[0]
        if image is None:
            raise ValueError(f"No image layer named {layer!r}. Available: {[l.name for l in images]}.")
        scale = (z_size or size,) * (image.ndim - 2) + (size, size)
        targets = [image] + [l for l in viewer.layers
                             if isinstance(l, Labels) and l.name == f"{image.name} labels"]
        _set_scale(targets, scale, unit)
        return (f"Set the pixel size of {image.name!r} to {size:g} {unit}"
                f"{f' with {z_size:g} {unit} between slices' if z_size else ''}. "
                f"Segment or measure it again to get sizes in {unit}.")

    def segmentation_methods() -> str:
        """List the segmentation methods installed here and when each fits the image. Call
        this before segmenting to pick a method, and give the reason when you segment."""
        found = available()
        return "\n".join(
            f"- {name} ({'installed' if found[name] else 'not installed: ' + INSTALL[name]}): "
            f"{text}" for name, text in METHODS.items()
        )

    return [
        ViewerTool(list_napari_layers),
        ViewerTool(show_object_in_napari, provides=["data"], done=done),
        ViewerTool(color_objects_by, provides=["data"], done=done),
        ViewerTool(filter_objects, provides=["data"], done=done),
        ViewerTool(set_pixel_size, provides=["data"], done=done),
        ViewerTool(segmentation_methods),
    ] + ([_compare_tool(controls)] if controls is not None else [])


def _compare_tool(controls) -> ViewerTool:
    """compare_conditions as its own planner step, after the measurements exist, so its
    results reach the answer as text."""

    @functools.wraps(controls.compare_conditions)
    def compare_conditions(**params) -> str:
        return controls.compare_conditions(**params)

    return ViewerTool(compare_conditions, provides=["data"])


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


# Units the LLM writes after numbers ("area >= 20 µm²"), which are not SQL.
UNITS = re.compile(r"(?<=\d)\s*(?:[µμu]m[²³23]?|nm[²³23]?|px|pixels?)(?![A-Za-z0-9_])")


def clean_condition(where: str, columns) -> str:
    """Drop units after numbers, and point bare names at unit-suffixed columns (area to
    area_um2) when only the suffixed one exists."""
    where = UNITS.sub("", where)
    for column in columns:
        base = re.sub(r"_(?:[a-z]+[23]?)$", "", column)
        if base != column and base not in columns:
            where = re.sub(rf"\b{re.escape(base)}\b(?!_)", column, where)
    return where


def _matching(layer: Labels, where: str) -> list[int]:
    """Labels whose measurements match a SQL condition. The query runs on an in-memory copy of
    the features, with DuckDB's file and network access switched off."""
    features = layer.features.rename(columns={"index": "label"})
    con = duckdb.connect(config={"enable_external_access": False})
    con.register("objects", features)
    condition = clean_condition(where, list(features.columns))
    try:
        rows = con.execute(f"SELECT label FROM objects WHERE {condition}").fetchall()
    except duckdb.Error as e:
        raise ValueError(f"Cannot filter with {where!r}: {e}. "
                         f"Columns: {[c for c in features.columns if c != 'label']}.") from e
    return [int(row[0]) for row in rows]


@ensure_main_thread(await_return=True, timeout=60_000)
def _add_filtered(viewer: ViewerModel, layer: Labels, keep: list[int], name: str) -> None:
    data = np.where(np.isin(layer.data, keep), layer.data, 0)
    features = layer.features[layer.features["index"].isin(keep)].reset_index(drop=True)
    if name in viewer.layers:
        viewer.layers.remove(name)
    viewer.add_labels(data, name=name, features=features, scale=layer.scale,
                      translate=layer.translate)


@ensure_main_thread(await_return=True, timeout=10_000)
def _set_scale(layers, scale, unit) -> None:
    for layer in layers:
        layer.scale = scale
        layer.units = (unit,) * len(scale)


@ensure_main_thread(await_return=True, timeout=10_000)
def _set_colormap(layer: Labels, colormap) -> None:
    layer.colormap = colormap


def _labels_layer(viewer: ViewerModel, name: str) -> Labels:
    layers = [layer for layer in viewer.layers if isinstance(layer, Labels)]
    if not layers:
        raise ValueError("napari has no labels layer. Segment an image first.")
    if not name:
        return layers[-1]
    # The LLM often names the image ("nuclei") for its labels ("nuclei labels").
    if found := find_layer(layers, name) or find_layer(layers, f"{name} labels"):
        return found
    raise ValueError(f"No labels layer named {name!r}. Available: {[l.name for l in layers]}.")


@ensure_main_thread(await_return=True, timeout=10_000)
def _focus(viewer: ViewerModel, layer: Labels, label: int) -> None:
    focus_label(viewer, layer, label)

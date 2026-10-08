"""Lumen data source actions that read from and write to a live napari viewer.

No `from __future__ import annotations` here: Lumen rebuilds the action signatures and needs
real annotation objects, not strings.
"""

import re
from typing import Literal

import numpy as np
import pandas as pd
import param
from lumen.ai.controls import CodeSourceControls
from napari.components import ViewerModel
from napari.layers import Image, Labels, Layer, Points, Shapes, Surface, Tracks, Vectors
from skimage.color import rgb2gray
from superqt.utils import ensure_main_thread

from .measure import measure, to_features
from .segment import segment

FEATURE_LAYERS = (Labels, Points, Shapes, Surface, Tracks, Vectors)


def table_name(layer_name: str) -> str:
    """SQL-safe table name for a layer."""
    return re.sub(r"\W+", "_", layer_name).strip("_").lower() or "layer"


class NapariControls(CodeSourceControls):
    """Expose segmentation and measurement of napari layers as Lumen data sources."""

    viewer = param.ClassSelector(class_=ViewerModel, precedence=-1)

    label = '<span class="material-icons" style="vertical-align: middle;">biotech</span> napari'

    def __init__(self, viewer: ViewerModel, **params):
        functions = {
            "segment_layer": self.segment_layer,
            "measure_layer": self.measure_layer,
            "layer_features": self.layer_features,
        }
        super().__init__(viewer=viewer, functions=functions, **params)

    def segment_layer(
        self,
        image_layer: str,
        method: Literal["otsu", "cellpose"] = "otsu",
        min_size: int = 20,
        split_touching: bool = True,
    ) -> pd.DataFrame:
        """Find the objects (cells, nuclei, spots) in a napari image layer and measure each one.

        Use this to segment an image. It adds a labels layer to napari and returns one row per
        object with its area, shape and intensity.

        Parameters
        ----------
        image_layer : str
            Name of the napari image layer to segment.
        method : str
            'otsu' for a fast threshold, 'cellpose' for a deep learning model.
        min_size : int
            Objects with fewer pixels than this are dropped.
        split_touching : bool
            Split touching objects with a watershed (otsu only).
        """
        layer = self._layer(image_layer, Image)
        image = _intensity(layer)
        labels = segment(image, method=method, min_size=min_size, split_touching=split_touching)
        df = measure(labels, image, spacing=layer.scale[-labels.ndim:])
        name = f"{layer.name} labels"
        self._publish(name, labels, df, layer)
        self.table_name = table_name(name)
        return df

    def measure_layer(self, labels_layer: str, image_layer: str | None = None) -> pd.DataFrame:
        """Measure the objects of a napari labels layer that already exists.

        Only for labels layers, such as ones drawn by hand or made by another plugin. To find
        objects in an image layer, use Segment Layer instead.

        Parameters
        ----------
        labels_layer : str
            Name of the napari labels layer to measure.
        image_layer : str
            Optional image layer to measure intensities from.
        """
        layer = self._layer(labels_layer, Labels)
        labels = np.asarray(layer.data)
        image = _intensity(self._layer(image_layer, Image)) if image_layer else None
        df = measure(labels, image, spacing=layer.scale)
        self._publish(layer.name, labels, df, layer)
        self.table_name = table_name(layer.name)
        return df

    def layer_features(self, layer: str) -> pd.DataFrame:
        """Load the features table of a napari points, shapes, labels or tracks layer.

        Parameters
        ----------
        layer : str
            Name of the napari layer whose features to load.
        """
        source = self._layer(layer, FEATURE_LAYERS)
        df = source.features.copy()
        if isinstance(source, Labels):
            df = df.rename(columns={"index": "label"})
        elif source.data is not None and np.ndim(source.data) == 2:
            for axis, column in enumerate(np.asarray(source.data).T):
                df[f"position_{axis}"] = column
        self.table_name = table_name(source.name)
        return df

    def _layer(self, name: str, kind: type[Layer] | tuple[type[Layer], ...]) -> Layer:
        layers = [layer for layer in self.viewer.layers if isinstance(layer, kind)]
        for layer in layers:
            if layer.name == name:
                return layer
        names = ", ".join(repr(layer.name) for layer in layers) or "none"
        kinds = kind if isinstance(kind, tuple) else (kind,)
        what = " or ".join(k.__name__.lower() for k in kinds)
        raise ValueError(f"No {what} layer named {name!r}. Available: {names}.")

    def _publish(self, name: str, labels: np.ndarray, df: pd.DataFrame, like: Layer) -> None:
        _publish_labels(self.viewer, name, labels, to_features(df), like)


@ensure_main_thread(await_return=True, timeout=60_000)
def _publish_labels(
    viewer: ViewerModel, name: str, labels: np.ndarray, features: pd.DataFrame, like: Layer
) -> None:
    if name in viewer.layers:
        layer = viewer.layers[name]
        layer.data = labels
        layer.features = features
    else:
        viewer.add_labels(
            labels, name=name, features=features, scale=like.scale[-labels.ndim:],
            translate=like.translate[-labels.ndim:],
        )


def _intensity(layer: Image) -> np.ndarray:
    # ponytail: loads the full-resolution array, segment a crop or a lower level if this is too big
    data = np.asarray(layer.data[0] if layer.multiscale else layer.data)
    return rgb2gray(data) if layer.rgb else data

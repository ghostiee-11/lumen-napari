"""Lumen data source actions that read from and write to a live napari viewer.

No `from __future__ import annotations` here: Lumen rebuilds the action signatures and needs
real annotation objects, not strings.
"""

import asyncio
import functools
import re
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import param
from lumen.ai.controls import CodeSourceControls, SourceResult
from napari.components import ViewerModel
from napari.layers import Image, Labels, Layer, Points, Shapes, Surface, Tracks, Vectors
from skimage.color import rgb2gray
from superqt.utils import ensure_main_thread

from .batch import measure_files
from .measure import measure, to_features
from .script import Script
from .segment import segment

# pandas reader and keyword arguments for each table file type.
READERS = {
    ".csv": ("read_csv", {}),
    ".tsv": ("read_csv", {"sep": "\t"}),
    ".xlsx": ("read_excel", {}),
    ".parquet": ("read_parquet", {}),
}

FEATURE_LAYERS = (Labels, Points, Shapes, Surface, Tracks, Vectors)


def unit_of(layer: Layer) -> str | None:
    """SQL-safe physical unit of the layer's axes, or None for pixels or mixed units."""
    units = {f"{u:~}" for u in layer.units}
    if len(units) != 1 or units == {"pixel"}:
        return None
    return re.sub(r"\W", "", units.pop().replace("μ", "u").replace("µ", "u")) or None


def table_name(layer_name: str) -> str:
    """SQL-safe table name for a layer."""
    return re.sub(r"\W+", "_", layer_name).strip("_").lower() or "layer"


class NapariControls(CodeSourceControls):
    """Expose segmentation and measurement of napari layers as Lumen data sources."""

    viewer = param.ClassSelector(class_=ViewerModel, precedence=-1)

    script = param.ClassSelector(class_=Script, precedence=-1, doc="""
        Records each step as Python that reproduces it.""")

    label = '<span class="material-icons" style="vertical-align: middle;">biotech</span> napari'

    def __init__(self, viewer: ViewerModel, **params):
        actions = (
            self.segment_layer, self.measure_layer, self.layer_features, self.segment_folder,
            self.load_table,
        )
        functions = {action.__name__: self._named(action) for action in actions}
        params.setdefault("script", Script())
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
        image = intensity(layer)
        labels = segment(image, method=method, min_size=min_size, split_touching=split_touching)
        spacing = _floats(layer.scale[-labels.ndim:])
        unit = unit_of(layer)
        df = measure(labels, image, spacing=spacing, unit=unit)
        name = f"{layer.name} labels"
        self._publish(name, labels, df, layer)
        self.table_name = table_name(name)
        self.script.load(layer)
        self.script.created(name)
        self.script.add(
            f"image = intensity(viewer.layers[{layer.name!r}])",
            f"labels = segment(image, method={method!r}, min_size={min_size!r}, "
            f"split_touching={split_touching!r})",
            f"table = tables[{self.table_name!r}] = measure(labels, image, spacing={spacing!r}, "
            f"unit={unit!r})",
            f"viewer.add_labels(labels, name={name!r}, features=to_features(table), "
            f"scale={spacing!r}, translate={_floats(layer.translate[-labels.ndim:])!r})",
        )
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
        image_source = self._layer(image_layer, Image) if image_layer else None
        image = intensity(image_source) if image_source else None
        spacing = _floats(layer.scale)
        unit = unit_of(layer)
        df = measure(labels, image, spacing=spacing, unit=unit)
        self._publish(layer.name, labels, df, layer)
        self.table_name = table_name(layer.name)
        self.script.load(layer)
        image_code = "None"
        if image_source:
            self.script.load(image_source)
            image_code = f"intensity(viewer.layers[{image_source.name!r}])"
        self.script.add(
            f"labels = viewer.layers[{layer.name!r}].data",
            f"table = tables[{self.table_name!r}] = measure(labels, {image_code}, "
            f"spacing={spacing!r}, unit={unit!r})",
            f"viewer.layers[{layer.name!r}].features = to_features(table)",
        )
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

    def segment_folder(
        self,
        folder: str,
        pattern: str = "*.tif",
        method: Literal["otsu", "cellpose"] = "otsu",
        min_size: int = 20,
        max_files: int = 500,
    ) -> pd.DataFrame:
        """Segment and measure every image file in a folder into one table, one row per object.

        Use this for many images at once, such as all fields or wells of a plate. Rows are keyed
        by image_id (the file name without extension) and by well when file names contain plate
        wells like B02, so they can be joined with an uploaded plate map. The images are not
        added to napari. Sizes are in pixels.

        Parameters
        ----------
        folder : str
            Path of the folder with the images.
        pattern : str
            Glob pattern for the image files, such as '*.tif' or '*.png'.
        method : str
            'otsu' for a fast threshold, 'cellpose' for a deep learning model.
        min_size : int
            Objects with fewer pixels than this are dropped.
        max_files : int
            Stop after this many files.
        """
        root = Path(folder).expanduser()
        files = sorted(root.glob(pattern))[:max_files]
        if not files:
            raise ValueError(f"No files match {pattern!r} in {str(root)!r}.")
        df = measure_files(files, method=method, min_size=min_size)
        self.table_name = table_name(f"{root.name} objects")
        self.script.add(
            "from pathlib import Path",
            "from lumen_napari.batch import measure_files",
            f"files = sorted(Path({str(root)!r}).glob({pattern!r}))[:{max_files!r}]",
            f"tables[{self.table_name!r}] = measure_files(files, method={method!r}, "
            f"min_size={min_size!r})",
        )
        return df

    def load_table(self, path: str) -> pd.DataFrame:
        """Load a table file, such as a plate map of wells and treatments, to join with
        measurements. Reads .csv, .tsv, .xlsx and .parquet files.

        Parameters
        ----------
        path : str
            Path of the table file.
        """
        file = Path(path).expanduser()
        suffix = file.suffix.lower()
        if suffix not in READERS:
            raise ValueError(f"Cannot read {file.name!r}. Use one of {', '.join(READERS)}.")
        reader, kwargs = READERS[suffix]
        df = getattr(pd, reader)(file, **kwargs)
        self.table_name = table_name(file.stem)
        args = ", ".join([repr(str(file)), *(f"{k}={v!r}" for k, v in kwargs.items())])
        self.script.add(f"tables[{self.table_name!r}] = pd.{reader}({args})")
        return df

    def _named(self, action):
        """Return the action's table under our name. Lumen would otherwise derive one from the
        arguments, which can start with a digit and break SQL."""

        @functools.wraps(action)
        def run(**params) -> SourceResult:
            df = action(**params)
            return SourceResult.from_dataframe(df, self.table_name)

        return run

    async def _fetch_data(self, action_name: str, **params) -> SourceResult:
        try:
            return await asyncio.to_thread(self._actions[action_name], **params)
        except Exception as e:  # noqa: BLE001 - shown to the user and the LLM, as Lumen does
            return SourceResult.empty(f"Error calling {action_name}: {e}")

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


def _floats(values) -> tuple[float, ...]:
    return tuple(float(v) for v in values)


def intensity(layer: Image) -> np.ndarray:
    """The layer's pixels as one intensity channel, full resolution."""
    # ponytail: loads the full-resolution array, segment a crop or a lower level if this is too big
    data = np.asarray(layer.data[0] if layer.multiscale else layer.data)
    return rgb2gray(data) if layer.rgb else data

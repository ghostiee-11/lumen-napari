"""Lumen data source actions that read from and write to a live napari viewer.

No `from __future__ import annotations` here: Lumen rebuilds the action signatures and needs
real annotation objects, not strings.
"""

import asyncio
import re
import threading
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import param
from lumen.ai.controls import CodeSourceControls, SourceResult
from lumen.sources.duckdb import DuckDBSource
from napari.components import ViewerModel
from napari.layers import Image, Labels, Layer, Points, Shapes, Surface, Tracks, Vectors
from skimage.color import rgb2gray
from superqt.utils import ensure_main_thread

from .batch import join_plate_map, measure_files
from .measure import measure, to_features
from .region import choose_level, load_region, visible_region
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
        functions = {action.__name__: action for action in actions}
        params.setdefault("script", Script())
        super().__init__(viewer=viewer, functions=functions, **params)
        self._source = None
        self._lock = threading.Lock()

    def segment_layer(
        self,
        image_layer: str,
        method: Literal["otsu", "cellpose"] = "otsu",
        min_size: int = 20,
        split_touching: bool = True,
        visible_only: bool = False,
        level: int = -1,
        measure_layers: list[str] | None = None,
    ) -> SourceResult:
        """Find the objects (cells, nuclei, spots) in a napari image layer and measure each one.

        Use this to segment an image. It adds a labels layer to napari and returns one row per
        object with its area, shape and intensity. Large and multiscale images (such as
        OME-Zarr) are read at the finest resolution level that fits in memory; set
        visible_only to segment just the part on screen at full detail.

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
        visible_only : bool
            Segment only the region currently visible in napari.
        level : int
            Resolution level of a multiscale image, 0 being full resolution. -1 picks the
            finest level that fits in memory.
        measure_layers : list[str]
            Other image layers (channels such as tubulin or actin) to measure intensity in,
            each giving columns like intensity_mean_tubulin.
        """
        layer = self._layer(image_layer, Image)
        region = visible_region(layer) if visible_only else None
        level = choose_level(layer, region) if level < 0 else level
        image, scale, translate = load_region(layer, level, region)
        labels = segment(image, method=method, min_size=min_size, split_touching=split_touching)
        unit = unit_of(layer)
        channels = {
            table_name(name): load_region(self._layer(name, Image), level, region)[0]
            for name in measure_layers or []
        }
        df = measure(labels, image, spacing=scale, unit=unit, origin=translate, channels=channels)
        name = f"{layer.name} labels"
        _publish_labels(self.viewer, name, labels, to_features(df), scale, translate)
        table = table_name(name)
        self.script.load(layer)
        self.script.created(name)
        for name in measure_layers or []:
            self.script.load(self._layer(name, Image))
        channel_code = ", ".join(
            f"{table_name(name)!r}: load_region(viewer.layers[{name!r}], {level!r}, {region!r})[0]"
            for name in measure_layers or []
        )
        self.script.add(
            f"image, scale, translate = load_region(viewer.layers[{layer.name!r}], "
            f"level={level!r}, region={region!r})",
            f"labels = segment(image, method={method!r}, min_size={min_size!r}, "
            f"split_touching={split_touching!r})",
            f"table = tables[{table!r}] = measure(labels, image, spacing=scale, unit={unit!r}, "
            f"origin=translate, channels={{{channel_code}}})",
            f"viewer.add_labels(labels, name={name!r}, features=to_features(table), "
            "scale=scale, translate=translate)",
        )
        return self._publish_table(table, df)

    def measure_layer(
        self,
        labels_layer: str,
        image_layer: str | None = None,
        measure_layers: list[str] | None = None,
    ) -> SourceResult:
        """Measure the objects of a napari labels layer that already exists.

        Only for labels layers, such as ones drawn by hand or made by another plugin. To find
        objects in an image layer, use Segment Layer instead.

        Parameters
        ----------
        labels_layer : str
            Name of the napari labels layer to measure.
        image_layer : str
            Optional image layer to measure intensities from.
        measure_layers : list[str]
            More image layers (channels) to measure intensity in, each giving columns like
            intensity_mean_actin.
        """
        layer = self._layer(labels_layer, Labels)
        labels = np.asarray(layer.data)
        image_source = self._layer(image_layer, Image) if image_layer else None
        image = intensity(image_source) if image_source else None
        spacing = _floats(layer.scale)
        unit = unit_of(layer)
        channels = {
            table_name(name): intensity(self._layer(name, Image)) for name in measure_layers or []
        }
        df = measure(labels, image, spacing=spacing, unit=unit, channels=channels)
        _publish_labels(
            self.viewer, layer.name, labels, to_features(df), layer.scale, layer.translate
        )
        table = table_name(layer.name)
        self.script.load(layer)
        image_code = "None"
        if image_source:
            self.script.load(image_source)
            image_code = f"intensity(viewer.layers[{image_source.name!r}])"
        for name in measure_layers or []:
            self.script.load(self._layer(name, Image))
        channel_code = ", ".join(
            f"{table_name(name)!r}: intensity(viewer.layers[{name!r}])" for name in measure_layers or []
        )
        self.script.add(
            f"labels = viewer.layers[{layer.name!r}].data",
            f"table = tables[{table!r}] = measure(labels, {image_code}, "
            f"spacing={spacing!r}, unit={unit!r}, channels={{{channel_code}}})",
            f"viewer.layers[{layer.name!r}].features = to_features(table)",
        )
        return self._publish_table(table, df)

    def layer_features(self, layer: str) -> SourceResult:
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
        return self._publish_table(table_name(source.name), df)

    def segment_folder(
        self,
        folder: str,
        pattern: str = "*.tif",
        method: Literal["otsu", "cellpose"] = "otsu",
        min_size: int = 20,
        max_files: int = 500,
        plate_map: str = "",
        channels: dict[str, str] | None = None,
        segment_channel: str = "",
    ) -> SourceResult:
        """Segment and measure every image file in a folder into one table, one row per object.

        Use this for many images at once, such as all fields or wells of a plate. Rows are keyed
        by image_id (the file name without extension) and by well when file names contain plate
        wells like B02. If the user has a plate map file, pass it as plate_map: its columns, such
        as compound or dose, are joined onto every object. The images are not added to napari.
        Sizes are in pixels.

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
        plate_map : str
            Optional path of a .csv, .tsv, .xlsx or .parquet table with a well or image_id column.
        channels : dict[str, str]
            For screens with one file per channel: channel name to the token that marks it in
            file names, such as {"dapi": "_w1", "tubulin": "_w2", "actin": "_w4"}.
        segment_channel : str
            With channels, the channel to segment (usually the nuclear stain). The others are
            measured as intensity_mean_<channel> columns.
        """
        root = Path(folder).expanduser()
        files = sorted(root.glob(pattern))[:max_files]
        if not files:
            raise ValueError(f"No files match {pattern!r} in {str(root)!r}.")
        df = measure_files(files, method=method, min_size=min_size, channels=channels,
                           segment_channel=segment_channel or None)
        table = table_name(f"{root.name} objects")
        lines = [
            "from pathlib import Path",
            "from lumen_napari.batch import join_plate_map, measure_files",
            f"files = sorted(Path({str(root)!r}).glob({pattern!r}))[:{max_files!r}]",
            (
                f"tables[{table!r}] = measure_files(files, method={method!r}, "
                f"min_size={min_size!r}, channels={channels!r}, "
                f"segment_channel={segment_channel or None!r})"
            ),
        ]
        if plate_map:
            plate, code = _read_table(plate_map)
            df = join_plate_map(df, plate)
            lines.append(f"tables[{table!r}] = join_plate_map(tables[{table!r}], {code})")
        self.script.add(*lines)
        return self._publish_table(table, df)

    def load_table(self, path: str) -> SourceResult:
        """Load a table file, such as a plate map of wells and treatments, to join with
        measurements. Reads .csv, .tsv, .xlsx and .parquet files.

        Parameters
        ----------
        path : str
            Path of the table file.
        """
        df, code = _read_table(path)
        table = table_name(Path(path).expanduser().stem)
        self.script.add(f"tables[{table!r}] = {code}")
        return self._publish_table(table, df)

    def _publish_table(self, name: str, df: pd.DataFrame) -> SourceResult:
        """Add the table to this session's one DuckDB source and return that source.

        Lumen keeps only the first result when the LLM calls several actions at once, so every
        table lives in the same source and stays queryable and joinable. Our own names also
        avoid Lumen deriving one from the arguments, which can start with a digit.
        """
        with self._lock:
            if self._source is None:
                self._source = DuckDBSource.from_df(tables={name: df})
            else:
                self._source._connection.from_df(df).to_view(name, replace=True)
            self._source.tables[name] = f"SELECT * FROM {name}"
        return SourceResult.from_source(
            self._source, table=name, message=f"Loaded {len(df):,} rows into '{name}'"
        )

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

@ensure_main_thread(await_return=True, timeout=60_000)
def _publish_labels(viewer: ViewerModel, name: str, labels: np.ndarray, features: pd.DataFrame,
                    scale, translate) -> None:
    if name in viewer.layers:
        layer = viewer.layers[name]
        layer.data = labels
        layer.scale, layer.translate = scale, translate
        layer.features = features
    else:
        viewer.add_labels(labels, name=name, features=features, scale=scale, translate=translate)


def _read_table(path: str) -> tuple[pd.DataFrame, str]:
    """Read a table file, and the pandas code that reads it."""
    file = Path(path).expanduser()
    suffix = file.suffix.lower()
    if suffix not in READERS:
        raise ValueError(f"Cannot read {file.name!r}. Use one of {', '.join(READERS)}.")
    reader, kwargs = READERS[suffix]
    args = ", ".join([repr(str(file)), *(f"{k}={v!r}" for k, v in kwargs.items())])
    return getattr(pd, reader)(file, **kwargs), f"pd.{reader}({args})"


def _floats(values) -> tuple[float, ...]:
    return tuple(float(v) for v in values)


def intensity(layer: Image) -> np.ndarray:
    """The layer's pixels as one intensity channel, full resolution."""
    # ponytail: loads the full-resolution array, segment a crop or a lower level if this is too big
    data = np.asarray(layer.data[0] if layer.multiscale else layer.data)
    return rgb2gray(data) if layer.rgb else data

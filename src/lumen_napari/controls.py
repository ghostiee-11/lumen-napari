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
from superqt.utils import ensure_main_thread, qdebounced

from .batch import join_plate_map, measure_files
from .measure import measure, to_features
from .region import choose_level, load_region, visible_region
from .regions import objects_by_region
from .report import overlay_png, segmentation_report, size_note
from .script import Script
from .segment import segment
from .stats import compare, dose_response
from .tiles import segment_tiled

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
    return re.sub(r"[^0-9A-Za-z]+", "_", layer_name).strip("_").lower() or "layer"


def find_layer(layers, name: str) -> Layer | None:
    """The layer with this name, also matched by its table name, since the LLM often uses the
    table name ("nuclei_labels") for the layer ("nuclei labels")."""
    for layer in layers:
        if layer.name == name:
            return layer
    for layer in layers:
        if table_name(layer.name) == table_name(name):
            return layer
    return None


class NapariControls(CodeSourceControls):
    """Expose segmentation and measurement of napari layers as Lumen data sources."""

    viewer = param.ClassSelector(class_=ViewerModel, precedence=-1)

    script = param.ClassSelector(class_=Script, precedence=-1, doc="""
        Records each step as Python that reproduces it.""")

    chat = param.Callable(default=None, precedence=-1, doc="""
        post(markdown, png=None) that shows what a step did in the chat.""")

    label = '<span class="material-icons" style="vertical-align: middle;">biotech</span> napari'

    def __init__(self, viewer: ViewerModel, **params):
        actions = (
            self.segment_layer, self.measure_layer, self.layer_features, self.segment_folder,
            self.load_table, self.measure_regions, self.segment_whole_slide,
        )
        functions = {action.__name__: action for action in actions}
        params.setdefault("script", Script())
        super().__init__(viewer=viewer, functions=functions, **params)
        self._source = None
        self._warned_pixels: set[str] = set()
        self._segmented: dict[str, tuple] = {}
        self._lock = threading.Lock()

    def segment_layer(
        self,
        image_layer: str,
        method: Literal["otsu", "cellpose", "stardist", "bioimageio"] = "otsu",
        model: str = "",
        reason: str = "",
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
            Segmentation method: 'otsu', 'cellpose', 'stardist' or 'bioimageio'. Call
            segmentation_methods first to see which are installed and when each fits.
        model : str
            For stardist or bioimageio: the model name or BioImage.IO id. Usually empty.
        reason : str
            One sentence on why this method fits the image, shown to the user.
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
        key = (layer.name, method, model, min_size, split_touching, level, region,
               tuple(measure_layers or ()), tuple(layer.scale))
        name = f"{layer.name} labels"
        if self._segmented.get(name) == key and name in self.viewer.layers:
            # Same image, same settings: reuse the result (hand edits keep it current).
            return SourceResult.from_source(self._source, table=table_name(name))
        image, scale, translate = load_region(layer, level, region)
        labels = segment(image, method=method, min_size=min_size, split_touching=split_touching,
                         model=model)
        unit = unit_of(layer)
        channels = {
            table_name(name): load_region(self._layer(name, Image), level, region)[0]
            for name in measure_layers or []
        }
        df = measure(labels, image, spacing=scale, unit=unit, origin=translate, channels=channels)
        _publish_labels(self.viewer, name, labels, to_features(df), scale, translate)
        self._segmented[name] = key
        table = table_name(name)
        self._remeasure_on_edit(name, table, image, scale, unit, translate, channels)
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
            f"split_touching={split_touching!r}, model={model!r})",
            f"table = tables[{table!r}] = measure(labels, image, spacing=scale, unit={unit!r}, "
            f"origin=translate, channels={{{channel_code}}})",
            f"viewer.add_labels(labels, name={name!r}, features=to_features(table), "
            "scale=scale, translate=translate)",
        )
        settings = {"method": method, **({"model": model} if model else {}),
                    "min_size": min_size, "split_touching": split_touching,
                    "level": level, "region": region or "whole image"}
        self._post(
            segmentation_report(layer.name, len(df), settings,
                                self._size_note(unit, scale, layer.name), table)
            + _why(method, reason),
            overlay_png(image, labels),
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
        existing = [layer for layer in self.viewer.layers if isinstance(layer, Labels)]
        images = [layer.name for layer in self.viewer.layers if isinstance(layer, Image)]
        if not existing and (image_layer or images):
            # Nothing is segmented yet: segment the image rather than fail.
            return self.segment_layer(
                image_layer=image_layer or images[0], measure_layers=measure_layers,
                reason="There was no labels layer yet, so the image was segmented first.",
            )
        layer = self._layer(labels_layer, Labels) if labels_layer else existing[-1]
        labels = np.asarray(layer.data)
        if not image_layer and layer.name.removesuffix(" labels") in images:
            # Labels made by segmenting an image keep that image's intensities.
            image_layer = layer.name.removesuffix(" labels")
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
        self._remeasure_on_edit(layer.name, table, image, spacing, unit, None, channels)
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
        self._post(
            f"**Measured `{layer.name}`: {len(df):,} objects** into table `{table}`"
            f"{f', with intensities from `{image_layer}`' if image_layer else ''}.\n\n"
            f"{self._size_note(unit, spacing, layer.name)}",
            overlay_png(image, labels) if image is not None else None,
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
        table = table_name(source.name)
        if not isinstance(source, Labels):
            _watch(source, "data", lambda: self._publish_table(table, features_table(source)))
        return self._publish_table(table, features_table(source))

    def segment_folder(
        self,
        folder: str,
        pattern: str = "*.tif",
        method: Literal["otsu", "cellpose", "stardist", "bioimageio"] = "otsu",
        model: str = "",
        reason: str = "",
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
        OME-TIFF, OME-Zarr and CZI files supply their own channel names, pixel size (sizes are
        then in micrometers) and plate well; other files are measured in pixels.

        Parameters
        ----------
        folder : str
            Path of the folder with the images.
        pattern : str
            Glob pattern for the image files, such as '*.tif' or '*.png'.
        method : str
            Segmentation method: 'otsu', 'cellpose', 'stardist' or 'bioimageio'. Call
            segmentation_methods first to see which are installed and when each fits.
        model : str
            For stardist or bioimageio: the model name or BioImage.IO id. Usually empty.
        reason : str
            One sentence on why this method fits the image, shown to the user.
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
            The channel to segment, usually the nuclear stain: one of the channels names, or
            for multi-channel files (OME-TIFF, OME-Zarr, CZI) a channel name stored in the file
            such as 'dapi'. Defaults to the first channel. The others are measured as
            intensity_mean_<channel> columns.
        """
        root = Path(folder).expanduser()
        files = sorted(root.glob(pattern))[:max_files]
        if not files:
            raise ValueError(f"No files match {pattern!r} in {str(root)!r}.")
        df = measure_files(files, method=method, min_size=min_size, model=model, channels=channels,
                           segment_channel=segment_channel or None)
        table = table_name(f"{root.name} objects")
        lines = [
            "from pathlib import Path",
            "from lumen_napari.batch import join_plate_map, measure_files",
            f"files = sorted(Path({str(root)!r}).glob({pattern!r}))[:{max_files!r}]",
            (
                f"tables[{table!r}] = measure_files(files, method={method!r}, "
                f"min_size={min_size!r}, model={model!r}, channels={channels!r}, "
                f"segment_channel={segment_channel or None!r})"
            ),
        ]
        if plate_map:
            plate, code = _read_table(plate_map)
            df = join_plate_map(df, plate)
            lines.append(f"tables[{table!r}] = join_plate_map(tables[{table!r}], {code})")
        self.script.add(*lines)
        counts = df.groupby("image_id").size()
        unit_cols = [c for c in df.columns if c.startswith(("area_", "volume_"))]
        self._post(
            f"**Segmented {len(counts)} images from `{root}`: {len(df):,} objects** into table "
            f"`{table}`.\n\nSettings: method={method!r}, min_size={min_size!r}"
            f"{f', segmenting channel {segment_channel!r}' if segment_channel else ''}"
            f"{f', joined with plate map `{Path(plate_map).name}`' if plate_map else ''}.\n\n"
            f"Objects per image: median {counts.median():g}, fewest {counts.min()} "
            f"(`{counts.idxmin()}`), most {counts.max()} (`{counts.idxmax()}`). Check the "
            "extremes in napari by asking me to show an object from them.\n\n"
            + ("Sizes come from the files' pixel size." if unit_cols else
               "⚠️ **Sizes are in pixels**: these files carry no pixel size.")
            + _why(method, reason)
        )
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

    def measure_regions(self, labels_layer: str, shapes_layer: str) -> SourceResult:
        """Assign every object of a labels layer to the drawn shape it lies in, to compare
        regions: density, counts or intensity inside versus outside a drawn area.

        Returns one row per object with its measurements, a `region` column (the shape's name,
        "region 1", "region 2"..., or "outside") and `region_area`, the region's area. Density
        is COUNT(*) / region_area per region.

        Parameters
        ----------
        labels_layer : str
            Name of the napari labels layer with the objects.
        shapes_layer : str
            Name of the napari shapes layer with the drawn regions.
        """
        labels = self._layer(labels_layer, Labels)
        shapes = self._layer(shapes_layer, Shapes)
        df = objects_by_region(labels, shapes)
        unit = unit_of(labels)
        if unit:
            df = df.rename(columns={"region_area": f"region_area_{unit}2"})
        table = table_name(f"{labels.name} by region")
        self.script.add(f"# Regions from {shapes.name!r} are not replayed by this script.")
        return self._publish_table(table, df)

    def _remeasure_on_edit(self, name, table, image, spacing, unit, origin, channels) -> None:
        """Measure a labels layer again whenever it is painted, filled or erased by hand, and
        update both its napari features and its Lumen table."""

        def remeasure():
            if name not in self.viewer.layers:
                return
            layer = self.viewer.layers[name]
            df = measure(np.asarray(layer.data), image, spacing=spacing, unit=unit,
                         origin=origin, channels=channels)
            layer.features = to_features(df)
            self._publish_table(table, df)
            self.script.edited(name)

        _watch(self.viewer.layers[name], "paint", remeasure)

    def segment_whole_slide(
        self,
        image_layer: str,
        tile_size: int = 2048,
        method: Literal["otsu", "cellpose", "stardist", "bioimageio"] = "otsu",
        model: str = "",
        reason: str = "",
        min_size: int = 20,
        split_touching: bool = True,
    ) -> SourceResult:
        """Segment and measure every object of a whole-slide or other very large 2D image at
        full resolution, tile by tile, without loading it all. Use this instead of Segment
        Layer when the image is too big to segment at once. Objects are added to napari as a
        points layer at their centroids, and measured in one table.

        Parameters
        ----------
        image_layer : str
            Name of the napari image layer.
        tile_size : int
            Tile side in pixels. Smaller tiles use less memory.
        method : str
            Segmentation method: 'otsu', 'cellpose', 'stardist' or 'bioimageio'. Call
            segmentation_methods first to see which are installed and when each fits.
        model : str
            For stardist or bioimageio: the model name or BioImage.IO id. Usually empty.
        reason : str
            One sentence on why this method fits the image, shown to the user.
        min_size : int
            Objects with fewer pixels than this are dropped.
        split_touching : bool
            Split touching objects with a watershed (otsu only).
        """
        layer = self._layer(image_layer, Image)
        unit = unit_of(layer)
        df, count = segment_tiled(layer, tile=tile_size, method=method, model=model,
                                  min_size=min_size,
                                  split_touching=split_touching, unit=unit)
        name = f"{layer.name} objects"
        suffix = f"_{unit}" if unit else ""
        positions = df[[f"centroid_0{suffix}", f"centroid_1{suffix}"]].to_numpy()
        _publish_points(self.viewer, name, positions, df)
        table = table_name(name)
        self.script.load(layer)
        self.script.add(
            "from lumen_napari.tiles import segment_tiled",
            f"tables[{table!r}], _ = segment_tiled(viewer.layers[{layer.name!r}], "
            f"tile={tile_size!r}, method={method!r}, model={model!r}, min_size={min_size!r}, "
            f"split_touching={split_touching!r}, unit={unit!r})",
        )
        self._post(
            f"**Segmented `{layer.name}` in {count} tiles of {tile_size} px: {len(df):,} objects** "
            f"into table `{table}`, shown in napari as the points layer `{name}`.\n\n"
            f"Settings: method={method!r}, min_size={min_size!r}, split_touching="
            f"{split_touching!r}, one threshold for the whole slide.\n\n"
            f"{self._size_note(unit, layer.scale, layer.name)}" + _why(method, reason)
        )
        return self._publish_table(table, df)

    def compare_conditions(
        self,
        table: str,
        measurement: str,
        condition: str,
        control: str,
        replicate: str = "well",
        dose: str = "",
    ) -> str:
        """Compare conditions (compounds, treatments) against a control the statistically sound
        way. Use this, not a plain average over cells, for questions like "which compounds
        change nuclear size compared to DMSO?".

        Objects are first summarised per replicate (the median per well), so wells, not cells,
        are the replicates. Returns per condition: replicates, objects, mean and sd of the well
        medians, fold change and z-score against the control wells, and a Welch t-test p-value.
        With a dose column it also fits a dose-response curve per condition (EC50, hill).

        Parameters
        ----------
        table : str
            A measurement table with one row per object, such as plate1_objects.
        measurement : str
            The column to compare, such as area or intensity_mean_tubulin.
        condition : str
            The column holding the condition, such as compound.
        control : str
            The control condition, such as DMSO.
        replicate : str
            The column identifying a replicate, usually well.
        dose : str
            Optional dose or concentration column for a dose-response fit.
        """
        if self._source is None or table not in self._source.tables:
            known = list(self._source.tables) if self._source else []
            raise ValueError(f"No table {table!r}. Tables: {known}.")
        df = self._source.execute(f"SELECT * FROM {table}")
        for column in (measurement, condition, replicate, *([dose] if dose else [])):
            if column not in df.columns:
                raise ValueError(f"{table!r} has no {column!r} column. Columns: {list(df.columns)}.")
        result = compare(df, measurement, condition, control, replicate)
        if dose:
            result = result.merge(dose_response(df, measurement, condition, dose, replicate),
                                  on=condition, how="left")
        name = table_name(f"{table} vs {control}")
        self.script.add(
            "from lumen_napari.stats import compare, dose_response",
            f"tables[{name!r}] = compare(tables[{table!r}], {measurement!r}, {condition!r}, "
            f"{control!r}, {replicate!r})",
        )
        text = (
            f"**Compared `{measurement}` across `{condition}` against `{control}`** into table "
            f"`{name}`.\n\nMethod: each {replicate} is one replicate, summarised by the median "
            f"of its objects, so wells with many cells do not outweigh wells with few. Means, "
            f"z-scores and Welch t-tests use the {replicate} medians "
            f"({int(result['replicates'].sum())} {replicate}s, "
            f"{int(result['objects'].sum()):,} objects)."
            + (f" Dose-response: four-parameter logistic fit against `{dose}`." if dose else "")
            + "\n\n" + _verdicts(result, condition, control)
        )
        self._post(text)
        self._publish_table(name, result)
        return f"{text}\n\n{_markdown_table(result)}"

    def current_table(self) -> str | None:
        """The measurement table of the most recent labels layer, if it has one."""
        if self._source is None:
            return None
        for layer in reversed(self.viewer.layers):
            if isinstance(layer, Labels) and table_name(layer.name) in self._source.tables:
                return table_name(layer.name)
        return None

    def _post(self, text: str, png: bytes | None = None) -> None:
        self.script.cards.append((text, png))
        if self.chat is not None:
            self.chat(text, png)

    def _size_note(self, unit, spacing, layer: str) -> str:
        """The units sentence, with the pixel warning only the first time for each layer."""
        if unit or layer not in self._warned_pixels:
            self._warned_pixels.add(layer)
            return size_note(unit, spacing)
        return "Sizes are in pixels."

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
                self._source.clear_cache()  # Lumen caches table data; drop the old version
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
        if found := find_layer(layers, name):
            return found
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


def _why(method: str, reason: str) -> str:
    """The method choice, explained."""
    return f"\n\n**Why {method}:** {reason}" if reason else ""


def _markdown_table(df: pd.DataFrame) -> str:
    """A small table as markdown, numbers rounded."""
    rows = [[f"{v:.3g}" if isinstance(v, float) else str(v) for v in row] for row in df.to_numpy()]
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    return "\n".join(lines + ["| " + " | ".join(row) + " |" for row in rows])


def _verdicts(result: pd.DataFrame, condition: str, control: str) -> str:
    """One plain sentence per condition, flagging too few replicates for a test."""
    lines = []
    for row in result.itertuples(index=False):
        name = getattr(row, condition)
        if name == control:
            continue
        if row.replicates < 2:
            lines.append(f"- `{name}`: only {row.replicates} replicate, no test possible.")
        elif np.isnan(row.p_value):
            lines.append(f"- `{name}`: fold change {row.fold_change:.2f}; no test possible "
                         "because the replicates do not vary.")
        else:
            z = "undefined (control wells do not vary)" if np.isnan(row.z_score) \
                else f"{row.z_score:.1f}"
            lines.append(f"- `{name}`: fold change {row.fold_change:.2f}, z = {z}, "
                         f"p = {row.p_value:.3g} ({row.replicates} replicates).")
    return "\n".join(lines)


def features_table(layer: Layer) -> pd.DataFrame:
    """A layer's features as a table: labels keyed by `label`, points and other 2D-data layers
    with their positions as position_0, position_1..."""
    df = layer.features.copy()
    if isinstance(layer, Labels):
        return df.rename(columns={"index": "label"})
    if layer.data is not None and np.ndim(layer.data) == 2:
        for axis, column in enumerate(np.asarray(layer.data).T):
            df[f"position_{axis}"] = column
    return df


@ensure_main_thread
def _watch(layer: Layer, event: str, callback) -> None:
    """Call back half a second after the last `event`, replacing any earlier watcher, so a
    brush stroke re-measures once rather than per pixel."""
    emitter = getattr(layer.events, event)
    key = f"lumen_napari_{event}"
    if previous := layer.metadata.get(key):
        emitter.disconnect(previous)
    debounced = qdebounced(lambda _event=None: callback(), timeout=500)
    layer.metadata[key] = debounced
    emitter.connect(debounced)


@ensure_main_thread(await_return=True, timeout=60_000)
def _publish_points(viewer: ViewerModel, name: str, positions, features: pd.DataFrame) -> None:
    if name in viewer.layers:
        viewer.layers.remove(name)
    viewer.add_points(positions, name=name, features=features, size=6, face_color="orange")


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

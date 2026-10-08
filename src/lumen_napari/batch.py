"""Segment and measure many image files into one table, without opening them in napari."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
from napari.components import ViewerModel
from napari.layers import Labels
from superqt.utils import ensure_main_thread

from .files import ImageFile, read_file
from .measure import measure, to_features
from .segment import read_image, segment

# Plate well ids such as A01 or P24, delimited by non-alphanumerics in a file name.
WELL = re.compile(r"(?<![A-Za-z0-9])([A-P])(\d{1,2})(?![0-9])")

# How each measured file was segmented, so a clicked object can be segmented again identically.
SEGMENTED_WITH: dict[str, dict] = {}


def well_of(name: str) -> str | None:
    """The plate well in a file name, zero padded (B2 -> B02), or None."""
    match = WELL.search(name)
    return f"{match[1]}{int(match[2]):02d}" if match else None


def group_channels(paths: Iterable[Path], channels: dict[str, str]) -> dict[str, dict[str, Path]]:
    """Group per-channel files into sites. `channels` maps a channel name to the token that
    marks it in file names (`{"dapi": "_w1", "actin": "_w4"}`); a site is the name before the
    token. Sites missing a channel are left out."""
    sites: dict[str, dict[str, Path]] = {}
    for path in paths:
        for name, token in channels.items():
            if (i := Path(path).name.find(token)) >= 0:
                sites.setdefault(Path(path).name[:i], {})[name] = Path(path)
                break
    return {site: files for site, files in sites.items() if len(files) == len(channels)}


def measure_files(
    paths: Iterable[Path],
    method: str = "otsu",
    min_size: int = 20,
    model: str = "",
    channels: dict[str, str] | None = None,
    segment_channel: str | None = None,
) -> pd.DataFrame:
    """One row per object across all files, keyed by image_id (the file name without extension).

    With `channels`, files are grouped into sites (see `group_channels`): `segment_channel`
    is segmented and every other channel adds intensity columns such as intensity_mean_actin.
    A `well` column is added when every image_id contains a plate well id.
    """
    if channels and segment_channel not in channels:
        raise ValueError(f"segment_channel must be one of {list(channels)}.")
    tables = []
    for site, path, channel, image, others, file in _sites(paths, channels, segment_channel):
        labels = segment(image, method=method, min_size=min_size, model=model)
        df = measure(labels, image, spacing=file.spacing, unit=file.unit, channels=others or None)
        resolved = str(path.resolve())
        df.insert(0, "image_id", site)
        df["well"] = file.well or well_of(site)
        df["path"] = resolved
        SEGMENTED_WITH[resolved] = {
            "image_id": site, "method": method, "min_size": min_size, "model": model,
            "channel": channel,
        }
        tables.append(df)
    if not tables:
        raise ValueError("No complete sites found: every channel token must match a file.")
    df = pd.concat(tables, ignore_index=True)
    wells = df.pop("well")
    if wells.notna().all():
        df.insert(1, "well", wells)
    return df


def _sites(paths, channels, segment_channel):
    """Yield (image_id, path of the segmented channel, the channel's name inside that file or
    None for single-channel files, its pixels, the other channels, the file's metadata)."""
    if channels:
        for site, files in group_channels(paths, channels).items():
            path = files[segment_channel]
            others = {n: read_image(f) for n, f in files.items() if n != segment_channel}
            yield site.rstrip("_-. ") or path.stem, path, None, read_image(path), others, ImageFile({})
        return
    for path in map(Path, paths):
        file = read_file(path)
        name = segment_channel or next(iter(file.channels))
        if name not in file.channels:
            raise ValueError(f"{path.name} has channels {list(file.channels)}, not {name!r}.")
        others = {n: data for n, data in file.channels.items() if n != name}
        yield _stem(path), path, name, file.channels[name], others, file


def _stem(path: Path) -> str:
    """File name without its extensions, so plate.ome.tiff gives plate."""
    return path.name.split(".")[0] or path.stem


def path_of(image_id: str) -> str:
    """The file a batch-measured image_id came from."""
    for path, settings in SEGMENTED_WITH.items():
        if settings["image_id"] == image_id:
            return path
    raise ValueError(f"No measured image {image_id!r}. Segment a folder first.")


def open_in_viewer(viewer: ViewerModel, image_id: str) -> Labels:
    """Open a batch-measured image and its labels in napari, segmented exactly as before."""
    name = f"{image_id} labels"
    if name in viewer.layers:
        return viewer.layers[name]
    path = path_of(image_id)
    settings = dict(SEGMENTED_WITH[path])
    channel = settings.pop("channel")
    settings.pop("image_id")
    file = read_file(path) if channel else ImageFile({"image": read_image(path)})
    image = file.channels[channel or "image"]
    labels = segment(image, **settings)
    features = to_features(measure(labels, image, spacing=file.spacing, unit=file.unit))
    _add(viewer, image, labels, image_id, name, features, file.spacing or (1,) * image.ndim)
    return viewer.layers[name]


@ensure_main_thread(await_return=True, timeout=60_000)
def _add(viewer, image, labels, image_id, name, features, scale) -> None:
    viewer.add_image(image, name=image_id, scale=scale)
    viewer.add_labels(labels, name=name, features=features, scale=scale)


def join_plate_map(objects: pd.DataFrame, plate_map: pd.DataFrame) -> pd.DataFrame:
    """Add the plate map's columns (compound, dose...) to every object, matched on well, or on
    image_id when the map has no well column."""
    key = next((k for k in ("well", "image_id") if k in objects and k in plate_map), None)
    if key is None:
        raise ValueError(
            f"The plate map needs a 'well' or 'image_id' column. It has: {list(plate_map.columns)}."
        )
    plate_map = plate_map.assign(**{key: plate_map[key].astype(str).str.strip()})
    if key == "well":
        plate_map["well"] = plate_map["well"].map(lambda w: well_of(w) or w)
    return objects.merge(plate_map, on=key, how="left")

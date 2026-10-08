"""Segment and measure many image files into one table, without opening them in napari."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
from napari.components import ViewerModel
from napari.layers import Labels
from superqt.utils import ensure_main_thread

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
    channels: dict[str, str] | None = None,
    segment_channel: str | None = None,
) -> pd.DataFrame:
    """One row per object across all files, keyed by image_id (the file name without extension).

    With `channels`, files are grouped into sites (see `group_channels`): `segment_channel`
    is segmented and every other channel adds intensity columns such as intensity_mean_actin.
    A `well` column is added when every image_id contains a plate well id.
    """
    if channels:
        if segment_channel not in channels:
            raise ValueError(f"segment_channel must be one of {list(channels)}.")
        sites = group_channels(paths, channels)
    else:
        sites = {Path(p).stem: {None: Path(p)} for p in paths}
    tables = []
    for site, files in sites.items():
        path = files[segment_channel if channels else None]
        image = read_image(path)
        others = {name: read_image(f) for name, f in files.items() if name != segment_channel}
        labels = segment(image, method=method, min_size=min_size)
        df = measure(labels, image, channels=others or None)
        resolved = str(path.resolve())
        df.insert(0, "image_id", site.rstrip("_-. ") or path.stem)
        df["path"] = resolved
        SEGMENTED_WITH[resolved] = {"method": method, "min_size": min_size}
        tables.append(df)
    if not tables:
        raise ValueError("No complete sites found: every channel token must match a file.")
    df = pd.concat(tables, ignore_index=True)
    wells = df["image_id"].map(well_of)
    if wells.notna().all():
        df.insert(1, "well", wells)
    return df


def path_of(image_id: str) -> str:
    """The file a batch-measured image_id came from."""
    for path in SEGMENTED_WITH:
        if Path(path).stem == image_id:
            return path
    raise ValueError(f"No measured image {image_id!r}. Segment a folder first.")


def open_in_viewer(viewer: ViewerModel, image_id: str) -> Labels:
    """Open a batch-measured image and its labels in napari, segmented exactly as before."""
    name = f"{image_id} labels"
    if name in viewer.layers:
        return viewer.layers[name]
    path = path_of(image_id)
    image = read_image(path)
    labels = segment(image, **SEGMENTED_WITH[path])
    _add(viewer, image, labels, image_id, name, to_features(measure(labels, image)))
    return viewer.layers[name]


@ensure_main_thread(await_return=True, timeout=60_000)
def _add(viewer, image, labels, image_id, name, features) -> None:
    viewer.add_image(image, name=image_id)
    viewer.add_labels(labels, name=name, features=features)


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

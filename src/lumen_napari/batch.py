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


def measure_files(paths: Iterable[Path], method: str = "otsu", min_size: int = 20) -> pd.DataFrame:
    """One row per object across all files, keyed by image_id (the file name without extension).

    A `well` column is added when every file name contains a plate well id.
    """
    tables = []
    for path in paths:
        image = read_image(path)
        df = measure(segment(image, method=method, min_size=min_size), image)
        resolved = str(Path(path).resolve())
        df.insert(0, "image_id", Path(path).stem)
        df["path"] = resolved
        SEGMENTED_WITH[resolved] = {"method": method, "min_size": min_size}
        tables.append(df)
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

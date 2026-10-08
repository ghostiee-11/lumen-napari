"""Segment and measure many image files into one table, without opening them in napari."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from .measure import measure
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

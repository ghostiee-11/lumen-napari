"""Measure every object in a label image as one table row."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

SHAPE = ("label", "area", "centroid", "bbox", "equivalent_diameter_area", "extent")
SHAPE_2D = ("eccentricity", "perimeter", "solidity")
INTENSITY = ("intensity_mean", "intensity_min", "intensity_max")


LENGTHS = ("centroid", "equivalent_diameter_area", "perimeter")


def measure(
    labels: np.ndarray,
    intensity: np.ndarray | None = None,
    spacing: Sequence[float] | None = None,
    unit: str | None = None,
    origin: Sequence[float] | None = None,
    channels: dict[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    """Return one row per label with shape and, if an image is given, intensity columns.

    In 3D `area` is called `volume`. With a `unit` (the physical unit of `spacing`), size
    columns get it as a suffix, such as `area_um2` or `centroid_0_um`. `bbox` stays in pixels.
    `origin` is added to the centroids, to place objects of a cropped image in world space.
    `channels` maps a name to another image of the same shape; each adds its own intensity
    columns, such as `intensity_mean_tubulin`.
    """
    labels = np.asarray(labels)
    properties = SHAPE + (SHAPE_2D if labels.ndim == 2 else ())
    if intensity is not None:
        properties += INTENSITY
    table = regionprops_table(
        labels, intensity_image=intensity, properties=properties, spacing=spacing
    )
    df = pd.DataFrame(table)
    df.columns = [c.replace("-", "_") for c in df.columns]
    for name, image in (channels or {}).items():
        extra = regionprops_table(
            labels, intensity_image=np.asarray(image), properties=("label",) + INTENSITY
        )
        df = df.merge(
            pd.DataFrame(extra).rename(columns={p: f"{p}_{name}" for p in INTENSITY}), on="label"
        )
    for axis, offset in enumerate(origin or ()):
        df[f"centroid_{axis}"] += offset
    size = "area" if labels.ndim == 2 else "volume"
    df = df.rename(columns={"area": size})
    if unit:
        df = df.rename(columns={
            c: f"{c}_{unit}{labels.ndim}" if c == size else f"{c}_{unit}"
            for c in df.columns
            if c == size or c.startswith(LENGTHS)
        })
    return df


def to_features(df: pd.DataFrame) -> pd.DataFrame:
    """Key a measurement table by label value, the way napari Labels features expect."""
    return df.rename(columns={"label": "index"})

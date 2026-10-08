"""Measure every object in a label image as one table row."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

SHAPE = ("label", "area", "centroid", "bbox", "equivalent_diameter_area", "extent")
SHAPE_2D = ("eccentricity", "perimeter", "solidity")
INTENSITY = ("intensity_mean", "intensity_min", "intensity_max")


def measure(
    labels: np.ndarray,
    intensity: np.ndarray | None = None,
    spacing: Sequence[float] | None = None,
) -> pd.DataFrame:
    """Return one row per label with shape and, if an image is given, intensity columns."""
    labels = np.asarray(labels)
    properties = SHAPE + (SHAPE_2D if labels.ndim == 2 else ())
    if intensity is not None:
        properties += INTENSITY
    table = regionprops_table(
        labels, intensity_image=intensity, properties=properties, spacing=spacing
    )
    df = pd.DataFrame(table)
    df.columns = [c.replace("-", "_") for c in df.columns]
    return df


def to_features(df: pd.DataFrame) -> pd.DataFrame:
    """Key a measurement table by label value, the way napari Labels features expect."""
    return df.rename(columns={"label": "index"})

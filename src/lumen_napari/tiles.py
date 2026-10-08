"""Segment a whole-slide image tile by tile, keeping only the measurements in memory."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from napari.layers import Image
from skimage.color import rgb2gray
from skimage.filters import threshold_otsu

from .measure import measure
from .region import levels
from .segment import segment

# Pixels sampled from the image to estimate one global threshold.
SAMPLE_PIXELS = 4_000_000


def _gray(data: np.ndarray, rgb: bool) -> np.ndarray:
    data = np.asarray(data)
    return rgb2gray(data[..., :3]) if rgb else data


def global_threshold(layer: Image) -> float:
    """Otsu's threshold of a coarse view of the whole image: the coarsest pyramid level, or
    every n-th pixel of a single-level image."""
    data = levels(layer)[-1]
    step = max(1, math.isqrt(math.prod(data.shape[:2]) // SAMPLE_PIXELS))
    return float(threshold_otsu(_gray(data[::step, ::step], layer.rgb)))


def tiles(shape: tuple[int, int], tile: int, overlap: int):
    """Yield (core, crop) slices: the core owns objects whose centroid lies in it, the crop
    adds `overlap` pixels on each side so objects on the seam are seen whole."""
    height, width = shape
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            core = (slice(y, min(y + tile, height)), slice(x, min(x + tile, width)))
            crop = (slice(max(0, y - overlap), min(height, y + tile + overlap)),
                    slice(max(0, x - overlap), min(width, x + tile + overlap)))
            yield core, crop


def segment_tiled(layer: Image, tile: int = 2048, overlap: int = 64, method: str = "otsu",
                  min_size: int = 20, split_touching: bool = True, model: str = "",
                  unit: str | None = None) -> tuple[pd.DataFrame, int]:
    """Measure every object of a 2D image, tile by tile. Returns the table, in world units,
    and the number of tiles. Labels are renumbered to be unique across the image."""
    if layer.ndim != 2:
        raise ValueError("Tiled segmentation works on 2D images.")
    full = levels(layer)[0]
    shape = full.shape[:2]
    threshold = global_threshold(layer) if method == "otsu" else None
    scale = tuple(float(s) for s in layer.scale)
    tables, count, next_label = [], 0, 1
    for core, crop in tiles(shape, tile, overlap):
        count += 1
        image = _gray(full[crop], layer.rgb)
        labels = segment(image, method=method, min_size=min_size, model=model,
                         split_touching=split_touching, threshold=threshold)
        if not labels.max():
            continue
        df = measure(labels, image)
        pixel_y = df["centroid_0"] + crop[0].start
        pixel_x = df["centroid_1"] + crop[1].start
        owned = ((pixel_y >= core[0].start) & (pixel_y < core[0].stop)
                 & (pixel_x >= core[1].start) & (pixel_x < core[1].stop))
        labels_owned = df.loc[owned, "label"].to_numpy()
        df = measure(labels, image, spacing=scale, unit=unit,
                     origin=tuple(t + c.start * s for t, c, s in
                                  zip(layer.translate, crop, scale, strict=True)))
        df = df[df["label"].isin(labels_owned)].copy()
        df["label"] = np.arange(next_label, next_label + len(df))
        next_label += len(df)
        tables.append(df)
    if not tables:
        return measure(np.zeros((1, 1), int)), count
    return pd.concat(tables, ignore_index=True), count

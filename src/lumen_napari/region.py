"""Read only part of a large image: one pyramid level, optionally cropped to a region."""

from __future__ import annotations

import math

import numpy as np
from napari.layers import Image
from skimage.color import rgb2gray

# ponytail: fixed budget, make it a setting if machines need more or less
MAX_PIXELS = 50_000_000

Region = tuple[tuple[int, int], ...]


def levels(layer: Image) -> list:
    return list(layer.data) if layer.multiscale else [layer.data]


def factors(layer: Image) -> np.ndarray:
    """Downsample factor of every level along every spatial axis."""
    shapes = [np.array(level.shape[: layer.ndim]) for level in levels(layer)]
    return np.array([shapes[0] / shape for shape in shapes])


def visible_region(layer: Image) -> Region:
    """The part of the layer on screen, in full-resolution pixels. Axes that are not displayed
    (such as z in a 2D view of a volume) are kept whole."""
    level = layer.data_level if layer.multiscale else 0
    f = factors(layer)[level]
    first, last = layer.corner_pixels  # inclusive pixel indices at the viewed level
    full = levels(layer)[0].shape
    return tuple(
        (int(a * s), min(int((b + 1) * s), full[axis])) if b > a else (0, full[axis])
        for axis, (a, b, s) in enumerate(zip(first, last, f, strict=True))
    )


def pixels(layer: Image, level: int, region: Region | None) -> int:
    shape = levels(layer)[level].shape[: layer.ndim]
    if region is None:
        return math.prod(shape)
    f = factors(layer)[level]
    return math.prod(math.ceil((b - a) / s) for (a, b), s in zip(region, f, strict=True))


def choose_level(layer: Image, region: Region | None = None, budget: int | None = None) -> int:
    """The finest level that fits the pixel budget."""
    budget = budget or MAX_PIXELS
    for level in range(len(levels(layer))):
        if pixels(layer, level, region) <= budget:
            return level
    coarsest = pixels(layer, len(levels(layer)) - 1, region)
    raise ValueError(
        f"Even the coarsest level has {coarsest:,} pixels, over the {budget:,} budget. "
        "Zoom in and segment only the visible region."
    )


def load_region(
    layer: Image, level: int = 0, region: Region | None = None, gray: bool = True
) -> tuple[np.ndarray, tuple[float, ...], tuple[float, ...]]:
    """Read one level of the layer, cropped to a full-resolution region, as one intensity
    channel (or, with gray=False, RGB images as they are). Returns the pixels and the world
    scale and translate that place them."""
    f = factors(layer)[level]
    region = region or tuple((0, n) for n in levels(layer)[0].shape[: layer.ndim])
    starts = [int(a // s) for (a, _), s in zip(region, f, strict=True)]
    stops = [math.ceil(b / s) for (_, b), s in zip(region, f, strict=True)]
    # ponytail: ignores the half-pixel shift of downsampled pyramid levels
    crop = tuple(slice(a, b) for a, b in zip(starts, stops, strict=True))
    image = np.asarray(levels(layer)[level][crop])
    if layer.rgb and gray:
        image = rgb2gray(image[..., :3])
    scale = tuple(float(s) for s in np.asarray(layer.scale) * f)
    translate = tuple(
        float(t + a * s) for t, a, s in zip(layer.translate, starts, scale, strict=True)
    )
    return image, scale, translate


def rgb_channels(image: np.ndarray) -> dict[str, np.ndarray]:
    """The red, green and blue planes of an RGB image, to measure each color."""
    return {name: image[..., i] for i, name in enumerate(("red", "green", "blue"))}

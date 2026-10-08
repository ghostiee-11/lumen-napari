"""Turn an intensity image into a label image."""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy import ndimage as ndi
from skimage import feature, filters, morphology, segmentation
from skimage.color import rgb2gray
from skimage.io import imread

Method = Literal["otsu", "cellpose"]


def read_image(path) -> np.ndarray:
    """Read an image file as one intensity channel; RGB images are converted to gray."""
    image = imread(path)
    if image.ndim == 3 and image.shape[-1] in (3, 4):
        image = rgb2gray(image[..., :3])
    return image


def segment(
    image: np.ndarray,
    method: Method = "otsu",
    min_size: int = 0,
    split_touching: bool = True,
    diameter: float | None = None,
) -> np.ndarray:
    """Segment bright objects in a 2D or 3D image and return a label image."""
    image = np.asarray(image)
    if method == "cellpose":
        return _cellpose(image, diameter)
    if method != "otsu":
        raise ValueError(f"Unknown method {method!r}, expected 'otsu' or 'cellpose'.")
    if image.ndim == 3:
        # Volumes are noisy and nuclei textured; unsmoothed they shatter into thousands of
        # pieces. 2D stays unsmoothed, since smoothing shifts edges by about a pixel.
        image = filters.gaussian(image.astype(float), sigma=2)
    mask = ndi.binary_fill_holes(image > filters.threshold_otsu(image))
    if min_size:
        mask = morphology.remove_small_objects(mask, max_size=min_size - 1)
    objects = ndi.label(mask)[0]
    if not split_touching or not objects.max():
        return objects.astype(np.int32)
    distance = ndi.distance_transform_edt(mask)
    peaks = feature.peak_local_max(
        distance, min_distance=_peak_distance(objects), labels=objects, exclude_border=False
    )
    markers = np.zeros(mask.shape, dtype=np.int32)
    markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    return segmentation.watershed(-distance, markers, mask=mask).astype(np.int32)


def _peak_distance(objects: np.ndarray) -> int:
    """Keep watershed seeds at least 0.8 of a typical object radius apart, so objects split
    where they touch but do not shatter."""
    sizes = np.bincount(objects.ravel())[1:]
    radius = np.median(sizes) ** (1 / objects.ndim) / 2
    return max(2, int(0.8 * radius))


def _cellpose(image: np.ndarray, diameter: float | None) -> np.ndarray:
    try:
        from cellpose import models
    except ImportError as e:
        raise ImportError("Install the cellpose extra: pip install 'lumen-napari[cellpose]'") from e
    masks = models.CellposeModel(gpu=False).eval(image, diameter=diameter)[0]
    return np.asarray(masks, dtype=np.int32)

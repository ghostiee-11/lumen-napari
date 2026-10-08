"""Turn an intensity image into a label image."""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy import ndimage as ndi
from skimage import feature, filters, morphology, segmentation

Method = Literal["otsu", "cellpose"]


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
    mask = image > filters.threshold_otsu(image)
    if min_size:
        mask = morphology.remove_small_objects(mask, max_size=min_size - 1)
    if not split_touching:
        return ndi.label(mask)[0].astype(np.int32)
    distance = ndi.distance_transform_edt(mask)
    peaks = feature.peak_local_max(distance, min_distance=3, labels=ndi.label(mask)[0])
    markers = np.zeros(mask.shape, dtype=np.int32)
    markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    return segmentation.watershed(-distance, markers, mask=mask).astype(np.int32)


def _cellpose(image: np.ndarray, diameter: float | None) -> np.ndarray:
    try:
        from cellpose import models
    except ImportError as e:
        raise ImportError("Install the cellpose extra: pip install 'lumen-napari[cellpose]'") from e
    masks = models.CellposeModel(gpu=False).eval(image, diameter=diameter)[0]
    return np.asarray(masks, dtype=np.int32)

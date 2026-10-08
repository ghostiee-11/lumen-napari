"""Turn an intensity image into a label image."""

from __future__ import annotations

import functools
import importlib.util
from typing import Literal

import numpy as np
from scipy import ndimage as ndi
from skimage import feature, filters, morphology, segmentation
from skimage.color import rgb2gray
from skimage.io import imread

Method = Literal["auto", "otsu", "cellpose", "stardist", "bioimageio"]

# When each method fits, shown to the LLM so it can pick and explain its choice.
METHODS = {
    "otsu": "Fast global threshold with watershed splitting. Good for bright, well separated "
            "nuclei on a dark background. Fails on tissue, uneven illumination or crowding.",
    "cellpose": "Deep learning generalist (Cellpose 4), no diameter needed. Best default for "
                "cells and nuclei in tissue, crowded or unevenly lit images.",
    "stardist": "Deep learning for star-convex shapes (nuclei). Fast and accurate on round "
                "nuclei in fluorescence images, 2D or 3D.",
    "bioimageio": "A BioImage.IO model zoo model given by id, for specialised data such as "
                  "a particular stain or organism.",
}

INSTALL = {
    "cellpose": "pip install 'lumen-napari[cellpose]'",
    "stardist": "pip install 'lumen-napari[stardist]'",
    "bioimageio": "pip install 'lumen-napari[bioimageio]'",
}


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
    split_touching: bool | None = None,
    diameter: float | None = None,
    threshold: float | None = None,
    model: str = "",
    dark_objects: bool | None = None,
) -> np.ndarray:
    """Segment the objects of a 2D or 3D image and return a label image. `threshold`
    replaces Otsu's, so tiles of one large image share a single cut-off. `model` names the
    StarDist or BioImage.IO model.

    With Otsu, `dark_objects` and `split_touching` are worked out from the image when left
    as None (see `polarity`): bright objects on a dark background are split where they
    touch; dark objects on a bright background (brightfield) are found by inverting; cells
    inside a network of bright walls or membranes are found without splitting, since the
    walls already separate them."""
    image = _fill_nan(np.asarray(image))
    if method == "auto":
        method = choose_method(image)[0]
    if method == "otsu" and threshold is None and (dark_objects is None or split_touching is None):
        dark, walls = polarity(image)
        dark_objects = dark if dark_objects is None else dark_objects
        split_touching = (not walls) if split_touching is None else split_touching
    split_touching = True if split_touching is None else split_touching
    if dark_objects and method == "otsu":
        image = image.max() - image.astype(float)
    if method in ("cellpose", "stardist", "bioimageio"):
        backend = {"cellpose": lambda: _cellpose(image, diameter),
                   "stardist": lambda: _stardist(image, model),
                   "bioimageio": lambda: _bioimageio(image, model)}[method]
        labels = backend()
        if min_size:
            labels = morphology.remove_small_objects(labels, max_size=min_size - 1)
        return labels.astype(np.int32)
    if method != "otsu":
        raise ValueError(f"Unknown method {method!r}, expected one of {list(METHODS)}.")
    if image.ndim == 3:
        # Volumes are noisy and nuclei textured; unsmoothed they shatter into thousands of
        # pieces. 2D stays unsmoothed, since smoothing shifts edges by about a pixel.
        image = filters.gaussian(image.astype(float), sigma=2)
    cut = filters.threshold_otsu(image) if threshold is None else threshold
    mask = ndi.binary_fill_holes(image > cut)
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


def choose_method(image: np.ndarray) -> tuple[str, str]:
    """The method for an image and why: Cellpose for objects on a bright background (stained
    tissue, brightfield), where a threshold fails, when it is installed; Otsu otherwise."""
    dark, walls = polarity(image)
    if not dark or walls:
        return "otsu", "the objects stand out from the background, so a threshold finds them."
    if available()["cellpose"]:
        return "cellpose", "this looks like stained tissue or brightfield, where a threshold fails."
    return "otsu", ("this looks like stained tissue or brightfield, which Cellpose segments much "
                    f"better; install it with {INSTALL['cellpose']}.")


def polarity(image: np.ndarray) -> tuple[bool, bool]:
    """(dark objects, inside walls) for an intensity image. Above Otsu's threshold, most of
    the image means a bright background (brightfield), and one bright component spanning the
    image means walls or membranes around dark cells. Otherwise the objects are bright."""
    image = _fill_nan(np.asarray(image, dtype=float))
    if image.ndim == 3:
        image = filters.gaussian(image, sigma=2)
    if image.min() == image.max():
        return False, False
    mask = image > filters.threshold_otsu(image)
    labels, count = ndi.label(mask)
    if not count:
        return False, False
    sizes = np.bincount(labels.ravel())[1:]
    largest = ndi.find_objects((labels == sizes.argmax() + 1).astype(np.int8))[0]
    span = min((s.stop - s.start) / n for s, n in zip(largest, mask.shape, strict=True))
    background = mask.mean() > 0.5
    walls = not background and sizes.max() >= 0.6 * mask.sum() and span >= 0.8
    return bool(walls or background), bool(walls)


def _fill_nan(image: np.ndarray) -> np.ndarray:
    """Missing (NaN) pixels become background, the image's minimum."""
    if np.issubdtype(image.dtype, np.floating) and np.isnan(image).any():
        return np.where(np.isnan(image), np.nanmin(image), image)
    return image


def _peak_distance(objects: np.ndarray) -> int:
    """Keep watershed seeds at least 0.8 of a typical object radius apart, so objects split
    where they touch but do not shatter."""
    sizes = np.bincount(objects.ravel())[1:]
    radius = np.median(sizes) ** (1 / objects.ndim) / 2
    return max(2, int(0.8 * radius))


def available() -> dict[str, bool]:
    """Which methods can run here."""
    found = {"otsu": True}
    for method, module in (("cellpose", "cellpose"), ("stardist", "stardist"),
                           ("bioimageio", "bioimageio.core")):
        found[method] = importlib.util.find_spec(module.split(".")[0]) is not None
    return found


def _missing(method: str) -> ImportError:
    return ImportError(f"The {method} method is not installed: {INSTALL[method]}")


def _cellpose(image: np.ndarray, diameter: float | None) -> np.ndarray:
    masks = _cellpose_model().eval(image, diameter=diameter)[0]
    return np.asarray(masks, dtype=np.int32)


@functools.cache
def _cellpose_model():
    """The Cellpose model, loaded once (its weights are about a gigabyte), on the GPU (CUDA or
    Apple MPS) when there is one, else the CPU."""
    try:
        from cellpose import models
    except ImportError as e:
        raise _missing("cellpose") from e
    return models.CellposeModel(gpu=True)


def _stardist(image: np.ndarray, model: str) -> np.ndarray:
    try:
        from csbdeep.utils import normalize
        from stardist.models import StarDist2D, StarDist3D
    except ImportError as e:
        raise _missing("stardist") from e
    if image.ndim == 3:
        net = StarDist3D.from_pretrained(model or "3D_demo")
    else:
        net = StarDist2D.from_pretrained(model or "2D_versatile_fluo")
    labels, _ = net.predict_instances(normalize(image, 1, 99.8))
    return np.asarray(labels, dtype=np.int32)


def _bioimageio(image: np.ndarray, model: str) -> np.ndarray:
    """Run a BioImage.IO model and turn its output into instances: label images are kept,
    foreground probabilities are thresholded at 0.5 and split with a watershed."""
    if not model:
        raise ValueError("Give the BioImage.IO model id, such as 'affable-shark'.")
    try:
        from bioimageio.core import predict
    except ImportError as e:
        raise _missing("bioimageio") from e
    sample = predict(model=model, inputs=image)
    output = np.squeeze(np.asarray(next(iter(sample.members.values())).data))
    if output.ndim == image.ndim + 1:  # channels first, foreground in channel 0
        output = output[0]
    if np.issubdtype(output.dtype, np.integer):
        return output.astype(np.int32)
    return segment(output, threshold=0.5)

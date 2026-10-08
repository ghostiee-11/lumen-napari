"""What a napari step did, shown in the chat: settings, counts, units and an overlay to check."""

from __future__ import annotations

import io

import numpy as np
from skimage import exposure, segmentation, transform
from skimage.io import imsave

MAX_SIDE = 600


def overlay_png(image: np.ndarray, labels: np.ndarray) -> bytes:
    """A PNG of the image with object outlines, to check a segmentation at a glance. Volumes
    show the slice with the most objects."""
    image, labels = np.asarray(image, dtype=float), np.asarray(labels)
    if labels.ndim == 3:
        z = int(np.argmax([len(np.unique(plane)) for plane in labels]))
        image, labels = image[z], labels[z]
    scale = min(1.0, MAX_SIDE / max(labels.shape))
    if scale < 1:
        shape = tuple(int(n * scale) for n in labels.shape)
        image = transform.resize(image, shape, anti_aliasing=True)
        labels = transform.resize(labels, shape, order=0, preserve_range=True, anti_aliasing=False)
    low, high = np.percentile(image, (1, 99.5))
    gray = exposure.rescale_intensity(image, in_range=(low, high if high > low else low + 1),
                                      out_range=(0, 1))
    outlined = segmentation.mark_boundaries(gray, labels.astype(int), color=(1, 0.55, 0))
    buffer = io.BytesIO()
    imsave(buffer, (outlined * 255).astype(np.uint8), extension=".png", check_contrast=False)
    return buffer.getvalue()


def size_note(unit: str | None, spacing) -> str:
    """How sizes are expressed, with a warning when they are in pixels."""
    if unit:
        return f"Sizes are in {unit} (pixel size {', '.join(f'{s:g}' for s in spacing)} {unit})."
    return (
        "⚠️ **Sizes are in pixels**: this image has no pixel size, so areas cannot be compared "
        "across instruments. Tell me the pixel size, for example *\"the pixel size is "
        "0.65 µm\"*, and I will measure in micrometers."
    )


def segmentation_report(
    source: str, count: int, settings: dict, unit: str | None, spacing, table: str
) -> str:
    """Markdown describing one segmentation, ending with the check question."""
    shown = ", ".join(f"{k}={v!r}" for k, v in settings.items())
    return (
        f"**Segmented `{source}`: {count:,} objects** into table `{table}`.\n\n"
        f"Settings: {shown}.\n\n{size_note(unit, spacing)}\n\n"
        "**Does the outline look right?** If not, ask me to segment again with other settings "
        "(for example a larger min_size, or method='cellpose'), or fix objects by hand in "
        "napari: they are measured again automatically."
    )

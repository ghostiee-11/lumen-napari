"""Images uploaded in the Lumen chat open in napari, segmented and measured."""

from __future__ import annotations

import functools
import re
import tempfile
from pathlib import Path

from superqt.utils import ensure_main_thread

from .files import read_file

IMAGE_EXTENSIONS = ("png", "tif", "tiff", "jpg", "jpeg", "czi", "nd2", "lif")

# ponytail: uploads stay in one temp folder for the session; clean it up if disk matters
_FOLDER = Path(tempfile.mkdtemp(prefix="lumen-napari-uploads-"))


def image_upload_handlers(controls) -> dict:
    """Lumen upload handlers, one per image extension, bound to the session's controls."""
    return {ext: functools.partial(upload_image, controls, ext) for ext in IMAGE_EXTENSIONS}


def upload_image(controls, extension: str, context, file_obj, alias: str, filename: str):
    """Save the upload, open each channel as a napari image layer with the file's pixel size,
    segment the first channel and measure the others. Returns the measurement source, so
    Lumen can query it straight away."""
    stem = re.sub(r"\.ome$", "", filename, flags=re.IGNORECASE)
    suffix = (".ome" if filename.lower().endswith(".ome") else "") + f".{extension}"
    path = _FOLDER / f"{stem}{suffix}"
    file_obj.seek(0)
    path.write_bytes(file_obj.read())
    file = read_file(path)
    names = _add_channels(controls.viewer, stem, file)
    controls.segment_layer(
        image_layer=names[0], measure_layers=names[1:],
        reason=f"Uploaded {path.name}: segmented on its first channel.",
    )
    return controls._source


@ensure_main_thread(await_return=True, timeout=60_000)
def _add_channels(viewer, stem: str, file) -> list[str]:
    """Add each channel as an image layer, to the right of what is already open, so uploads
    sit side by side instead of hiding each other."""
    offset = _right_edge(viewer)
    names = []
    for channel, data in file.channels.items():
        name = stem if len(file.channels) == 1 else f"{stem} {channel}"
        kwargs = {"scale": file.spacing, "units": (file.unit,) * len(file.spacing)} \
            if file.spacing else {}
        translate = (0.0,) * (data.ndim - 1) + (offset,)
        viewer.add_image(data, name=name, translate=translate, **kwargs)
        names.append(viewer.layers[-1].name)
    viewer.fit_to_view()
    return names


def _right_edge(viewer) -> float:
    """Where the next image goes along x: past the open layers, with a 5% gap."""
    if not len(viewer.layers):
        return 0.0
    right = max(layer.extent.world[1][-1] for layer in viewer.layers)
    return float(right + 0.05 * abs(right))

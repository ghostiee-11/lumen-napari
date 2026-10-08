"""Read image files with their metadata: channel names, pixel size and plate well."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .segment import read_image

# Formats read through bioio, which carries the metadata; the rest go through scikit-image.
BIOIO_SUFFIXES = (".ome.tif", ".ome.tiff", ".zarr", ".czi", ".nd2", ".lif")


@dataclass
class ImageFile:
    channels: dict[str, np.ndarray]
    spacing: tuple[float, ...] | None = None
    unit: str | None = None
    well: str | None = None


def read_file(path: str | Path) -> ImageFile:
    """The file's channels by name, its physical pixel size and, from OME plate metadata, its
    well. Plain image files have one channel called "image" and no metadata."""
    if str(path).lower().rstrip("/").endswith(BIOIO_SUFFIXES):
        return _read_bioio(path)
    return ImageFile({"image": read_image(path)})


def _read_bioio(path) -> ImageFile:
    try:
        from bioio import BioImage
    except ImportError as e:
        raise ImportError(
            f"Reading {Path(path).name} needs bioio: pip install 'lumen-napari[bioio]'"
        ) from e
    image = BioImage(path)
    order = "ZYX" if image.dims.Z > 1 else "YX"
    channels = {
        channel_name(name, i): image.get_image_data(order, C=i, T=0)
        for i, name in enumerate(image.channel_names)
    }
    sizes = image.physical_pixel_sizes
    spacing = (sizes.Z, sizes.Y, sizes.X) if order == "ZYX" else (sizes.Y, sizes.X)
    has_spacing = all(spacing)
    return ImageFile(
        channels,
        spacing=tuple(float(s) for s in spacing) if has_spacing else None,
        unit="um" if has_spacing else None,
        well=well_from_ome(image.metadata, image.current_scene_index),
    )


def channel_name(name, index: int) -> str:
    """SQL-safe channel name, or c<index> when the file has none."""
    return re.sub(r"[^0-9A-Za-z]+", "_", str(name)).strip("_").lower() or f"c{index}"


def well_from_ome(ome, image_index: int) -> str | None:
    """The plate well holding an OME image, as A01, or None outside a plate."""
    try:
        image_id = ome.images[image_index].id
        plates = ome.plates
    except (AttributeError, IndexError):
        return None
    for plate in plates:
        for well in plate.wells:
            for sample in well.well_samples:
                if sample.image_ref is not None and sample.image_ref.id == image_id:
                    return f"{chr(ord('A') + well.row)}{well.column + 1:02d}"
    return None

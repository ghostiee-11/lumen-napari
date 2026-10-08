"""Which drawn shape each object lies in."""

from __future__ import annotations

import numpy as np
import pandas as pd
from napari.layers import Labels, Shapes
from skimage.measure import regionprops_table


def region_masks(labels: Labels, shapes: Shapes) -> list[np.ndarray]:
    """Each shape rasterized onto the labels layer's pixel grid."""
    if labels.ndim != 2:
        raise ValueError("Regions work on 2D labels layers.")
    # Move the vertices into the labels layer's pixel space, so layers with different
    # scale or translate still line up.
    # data_to_world only takes one point; the composite transforms map whole vertex arrays.
    to_labels = labels._data_to_world.inverse
    data = [to_labels(shapes._data_to_world(vertices)) for vertices in shapes.data]
    on_grid = Shapes(data, shape_type=shapes.shape_type)
    return list(on_grid.to_masks(mask_shape=labels.data.shape))


def objects_by_region(labels: Labels, shapes: Shapes) -> pd.DataFrame:
    """One row per object: its measurements, its region and the region's area in world units."""
    masks = region_masks(labels, shapes)
    names = _names(shapes)
    pixel_area = float(np.prod(np.abs(labels.scale)))
    props = regionprops_table(np.asarray(labels.data), properties=("label", "centroid"))
    rows = np.clip(np.round(props["centroid-0"]).astype(int), 0, labels.data.shape[0] - 1)
    cols = np.clip(np.round(props["centroid-1"]).astype(int), 0, labels.data.shape[1] - 1)
    region = np.full(len(rows), "outside", dtype=object)
    for name, mask in zip(reversed(names), reversed(masks), strict=True):
        region[mask[rows, cols]] = name  # earlier shapes win where shapes overlap
    areas = {name: mask.sum() * pixel_area for name, mask in zip(names, masks, strict=True)}
    union = np.logical_or.reduce(masks) if masks else np.zeros(labels.data.shape, bool)
    areas["outside"] = (~union).sum() * pixel_area
    df = pd.DataFrame({"label": props["label"], "region": region})
    df["region_area"] = df["region"].map(areas)
    features = labels.features.rename(columns={"index": "label"})
    if "label" in features:
        df = df.merge(features, on="label", how="left")
    return df


def _names(shapes: Shapes) -> list[str]:
    if "name" in shapes.features:
        return [str(name) for name in shapes.features["name"]]
    return [f"region {i + 1}" for i in range(len(shapes.data))]

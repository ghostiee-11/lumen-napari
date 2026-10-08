"""Sample images to try lumen-napari on."""

from skimage import data


def mitosis():
    """Human HeLa nuclei, 2D."""
    return [(data.human_mitosis(), {"name": "nuclei"}, "image")]


def cells3d():
    """Mouse embryo nuclei, 3D, with physical voxel size in micrometers."""
    nuclei = data.cells3d()[:, 1]
    meta = {"name": "nuclei", "scale": (0.29, 0.26, 0.26), "units": ("um", "um", "um")}
    return [(nuclei, meta, "image")]

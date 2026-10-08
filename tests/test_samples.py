from lumen_napari.samples import cells3d, mitosis


def test_mitosis():
    [(image, meta, kind)] = mitosis()
    assert image.ndim == 2
    assert meta["name"] == "nuclei"
    assert kind == "image"


def test_cells3d():
    [(image, meta, _)] = cells3d()
    assert image.ndim == 3
    assert meta["scale"] == (0.29, 0.26, 0.26)
    assert meta["units"] == ("um", "um", "um")

from lumen_napari.samples import cells3d, lily, mitosis


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


def test_lily_has_one_layer_per_channel():
    layers = lily()
    assert [meta["name"] for _, meta, _ in layers] == [
        "lily-magenta", "lily-green", "lily-yellow", "lily-blue"]
    assert all(image.shape == (922, 922) for image, _, _ in layers)

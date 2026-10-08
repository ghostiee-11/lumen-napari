import numpy as np
import pytest

from lumen_napari.segment import segment


def blobs():
    image = np.zeros((40, 40))
    image[5:12, 5:12] = 1
    image[25:35, 25:35] = 1
    image[2, 30] = 1
    return image


def test_otsu_finds_each_object():
    labels = segment(blobs(), split_touching=False)
    assert labels.max() == 3


def test_min_size_drops_specks():
    labels = segment(blobs(), min_size=4, split_touching=False)
    assert labels.max() == 2


def test_min_size_keeps_objects_of_exactly_that_size():
    assert segment(blobs(), min_size=49, split_touching=False).max() == 2


def test_split_touching_separates_two_disks():
    yy, xx = np.mgrid[:40, :60]
    image = ((yy - 20) ** 2 + (xx - 20) ** 2 < 100) | ((yy - 20) ** 2 + (xx - 37) ** 2 < 100)
    assert segment(image.astype(float), split_touching=False).max() == 1
    assert segment(image.astype(float)).max() == 2


def test_works_in_3d():
    image = np.zeros((10, 20, 20))
    image[2:6, 3:8, 3:8] = 1
    assert segment(image, split_touching=False).max() == 1


def test_unknown_method():
    with pytest.raises(ValueError, match="Unknown method"):
        segment(blobs(), method="magic")


def test_textured_3d_nuclei_do_not_shatter():
    from skimage import data

    nuclei = segment(data.cells3d()[:, 1], min_size=20)
    # About thirty nuclei are in view; the old seeding found over a thousand pieces.
    assert 20 <= nuclei.max() <= 45


def test_cellpose_is_called_on_cpu(monkeypatch):
    import sys
    import types

    calls = {}

    class CellposeModel:
        def __init__(self, gpu):
            calls["gpu"] = gpu

        def eval(self, image, diameter=None):
            calls["diameter"] = diameter
            return np.ones(image.shape, np.uint16), None, None

    models = types.SimpleNamespace(CellposeModel=CellposeModel)
    monkeypatch.setitem(sys.modules, "cellpose", types.SimpleNamespace(models=models))
    labels = segment(blobs(), method="cellpose", diameter=12)
    assert calls == {"gpu": False, "diameter": 12}
    assert labels.dtype == np.int32


def test_cellpose_missing_explains_the_extra(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "cellpose", None)
    with pytest.raises(ImportError, match=r"lumen-napari\[cellpose\]"):
        segment(blobs(), method="cellpose")


def test_read_image_converts_rgb_to_gray(tmp_path):
    from skimage.io import imsave

    from lumen_napari.segment import read_image

    imsave(tmp_path / "rgb.png", np.zeros((6, 6, 3), np.uint8), check_contrast=False)
    imsave(tmp_path / "gray.png", np.zeros((6, 6), np.uint8), check_contrast=False)
    assert read_image(tmp_path / "rgb.png").shape == (6, 6)
    assert read_image(tmp_path / "gray.png").shape == (6, 6)


def test_a_fixed_threshold_replaces_otsu():
    image = np.zeros((20, 20))
    image[2:6, 2:6] = 10
    image[10:14, 10:14] = 3
    assert segment(image, split_touching=False).max() == 2
    assert segment(image, split_touching=False, threshold=5).max() == 1


def fake_module(monkeypatch, name, **attrs):
    import sys
    import types

    module = types.SimpleNamespace(**attrs)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def test_stardist_uses_the_pretrained_model_for_the_dimension(monkeypatch):
    used = {}

    class Model:
        @classmethod
        def from_pretrained(cls, name):
            used["model"] = name
            return cls()

        def predict_instances(self, image):
            used["max"] = float(image.max())
            labels = np.zeros(image.shape, int)
            labels[0:2, 0:2] = 1
            labels[5:15, 5:15] = 2
            return labels, {}

    fake_module(monkeypatch, "stardist")
    fake_module(monkeypatch, "stardist.models", StarDist2D=Model, StarDist3D=Model)
    fake_module(monkeypatch, "csbdeep")
    fake_module(monkeypatch, "csbdeep.utils", normalize=lambda image, low, high: image / image.max())
    labels = segment(blobs(), method="stardist", min_size=10)
    assert used == {"model": "2D_versatile_fluo", "max": 1.0}
    assert np.unique(labels).tolist() == [0, 2]


def test_bioimageio_turns_probabilities_into_instances(monkeypatch):
    import types

    probability = np.zeros((1, 40, 40))
    probability[0, 5:12, 5:12] = 0.9
    probability[0, 25:35, 25:35] = 0.8
    sample = types.SimpleNamespace(members={"output": types.SimpleNamespace(data=probability)})
    calls = {}

    def predict(model, inputs):
        calls["model"] = model
        return sample

    fake_module(monkeypatch, "bioimageio")
    fake_module(monkeypatch, "bioimageio.core", predict=predict)
    labels = segment(blobs(), method="bioimageio", model="affable-shark")
    assert calls == {"model": "affable-shark"}
    assert labels.max() == 2


def test_bioimageio_needs_a_model_id():
    with pytest.raises(ValueError, match="model id"):
        segment(blobs(), method="bioimageio")


def test_available_methods():
    from lumen_napari.segment import METHODS, available

    found = available()
    assert found["otsu"] is True
    assert set(found) == set(METHODS)


def test_dark_objects_inside_bright_walls():
    walls = np.zeros((60, 60))
    walls[::20, :] = walls[:, ::20] = 1  # a grid of walls, 9 cells
    walls[-1, :] = walls[:, -1] = 1
    labels = segment(walls, dark_objects=True, split_touching=False)
    assert labels.max() == 9
    assert labels[10, 10] and not labels[0, 10]


def grid_of_walls():
    walls = np.zeros((60, 60))
    walls[::20, :] = walls[:, ::20] = 1
    walls[-1, :] = walls[:, -1] = 1
    return walls


def test_dark_objects_are_detected():
    from lumen_napari.segment import polarity

    assert polarity(grid_of_walls()) == (True, True)  # dark cells inside a wall network
    spots = np.zeros((60, 60))
    spots[10:20, 10:20] = spots[40:50, 40:50] = 1
    assert polarity(spots) == (False, False)  # bright objects
    assert polarity(1 - spots) == (True, False)  # brightfield: dark objects, bright background
    assert segment(grid_of_walls()).max() == 9  # automatic, without settings


def test_blank_image_has_no_objects():
    assert segment(np.zeros((20, 20))).max() == 0
    assert segment(np.full((20, 20), 7.0)).max() == 0


def test_nan_pixels_are_background():
    image = np.zeros((30, 30))
    image[5:12, 5:12] = 1
    image[0, :] = np.nan
    assert segment(image).max() == 1

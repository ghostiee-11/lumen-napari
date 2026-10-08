import numpy as np
import pytest
from skimage.io import imsave

from lumen_napari.batch import SEGMENTED_WITH, measure_files, well_of


@pytest.mark.parametrize(("name", "well"), [
    ("A01", "A01"),
    ("Week1_150607_B02_s1_w1", "B02"),
    ("plate1-c7-field2", None),
    ("P24_DAPI", "P24"),
    ("img_C3", "C03"),
    ("cells", None),
])
def test_well_of(name, well):
    assert well_of(name) == well


def write(folder, name, count):
    image = np.zeros((30, 70), np.uint8)
    for i in range(count):
        image[5:15, 5 + 20 * i:15 + 20 * i] = 200
    path = folder / name
    imsave(path, image, check_contrast=False)
    return path


def test_measure_files_keys_rows_by_image(tmp_path):
    paths = [write(tmp_path, "plate_A01.png", 1), write(tmp_path, "plate_B03.png", 3)]
    df = measure_files(paths, min_size=0)
    assert list(df.columns[:2]) == ["image_id", "well"]
    assert df.groupby("well").size().to_dict() == {"A01": 1, "B03": 3}
    assert df.path.iloc[0] == str(paths[0].resolve())
    assert SEGMENTED_WITH[str(paths[0].resolve())] == {"method": "otsu", "min_size": 0}


def test_no_well_column_without_wells(tmp_path):
    df = measure_files([write(tmp_path, "cells.png", 2)], min_size=0)
    assert "well" not in df.columns
    assert list(df.image_id) == ["cells", "cells"]

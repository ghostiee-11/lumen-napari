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
    assert SEGMENTED_WITH[str(paths[0].resolve())] == {
        "image_id": "plate_A01", "method": "otsu", "min_size": 0, "channel": "image",
    }


def test_no_well_column_without_wells(tmp_path):
    df = measure_files([write(tmp_path, "cells.png", 2)], min_size=0)
    assert "well" not in df.columns
    assert list(df.image_id) == ["cells", "cells"]


def test_open_in_viewer_resegments_identically(tmp_path, qapp):
    from napari.components import ViewerModel

    from lumen_napari.batch import open_in_viewer

    path = write(tmp_path, "plate_C04.png", 3)
    df = measure_files([path], min_size=0)
    viewer = ViewerModel()
    layer = open_in_viewer(viewer, "plate_C04")
    assert [l.name for l in viewer.layers] == ["plate_C04", "plate_C04 labels"]
    assert layer.data.max() == len(df) == 3
    assert list(layer.features["area"]) == list(df["area"])
    assert open_in_viewer(viewer, "plate_C04") is layer


def test_open_unknown_image():
    from lumen_napari.batch import path_of

    with pytest.raises(ValueError, match="Segment a folder first"):
        path_of("nope")


def test_join_plate_map_on_well():
    import pandas as pd

    from lumen_napari.batch import join_plate_map

    objects = pd.DataFrame({"image_id": ["p_A01", "p_B02"], "well": ["A01", "B02"], "area": [1, 2]})
    plate = pd.DataFrame({"well": ["A1", " B02 "], "compound": ["DMSO", "taxol"]})
    joined = join_plate_map(objects, plate)
    assert list(joined.compound) == ["DMSO", "taxol"]


def test_join_plate_map_on_image_id_and_bad_maps():
    import pandas as pd

    from lumen_napari.batch import join_plate_map

    objects = pd.DataFrame({"image_id": ["a", "b"], "area": [1, 2]})
    joined = join_plate_map(objects, pd.DataFrame({"image_id": ["b"], "dose": [10]}))
    assert joined.dose.isna().tolist() == [True, False]
    with pytest.raises(ValueError, match="needs a 'well' or 'image_id' column"):
        join_plate_map(objects, pd.DataFrame({"plate": [1]}))


def test_per_channel_files_are_grouped_into_sites(tmp_path):
    from lumen_napari.batch import group_channels

    for name in ("A01_s1_w1x.png", "A01_s1_w2y.png", "B02_s1_w1z.png"):
        write(tmp_path, name, 1)
    sites = group_channels(sorted(tmp_path.glob("*.png")), {"dapi": "_w1", "tubulin": "_w2"})
    assert list(sites) == ["A01_s1"]
    assert sites["A01_s1"]["tubulin"].name == "A01_s1_w2y.png"


def test_measure_files_with_channels(tmp_path):
    nuclei = write(tmp_path, "P_C03_s1_w1.png", 2)
    from skimage.io import imread
    imsave(tmp_path / "P_C03_s1_w2.png", (imread(nuclei) // 2).astype(np.uint8), check_contrast=False)
    df = measure_files(sorted(tmp_path.glob("*.png")), min_size=0,
                       channels={"dapi": "_w1", "tubulin": "_w2"}, segment_channel="dapi")
    assert list(df.image_id) == ["P_C03_s1", "P_C03_s1"]
    assert list(df.well) == ["C03", "C03"]
    assert list(df.intensity_mean_tubulin) == list(df.intensity_mean // 2)
    assert df.path.iloc[0].endswith("_w1.png")


def test_channels_need_a_valid_segment_channel(tmp_path):
    with pytest.raises(ValueError, match="segment_channel must be one of"):
        measure_files([], channels={"dapi": "_w1"}, segment_channel="nuclei")


def test_ome_tiff_folders_use_file_metadata(tmp_path, qapp):
    pytest.importorskip("bioio_ome_tiff")
    from bioio.writers import OmeTiffWriter
    from bioio_base.types import PhysicalPixelSizes
    from napari.components import ViewerModel

    from lumen_napari.batch import open_in_viewer

    data = np.zeros((2, 40, 40), np.uint16)
    data[0, 5:15, 5:15] = 900
    data[1, 5:15, 5:15] = 300
    path = tmp_path / "screen_D05.ome.tiff"
    OmeTiffWriter.save(data, str(path), dim_order="CYX", channel_names=["DAPI", "Actin"],
                       physical_pixel_sizes=PhysicalPixelSizes(None, 0.5, 0.5))
    df = measure_files([path], min_size=0)
    assert list(df.image_id) == ["screen_D05"]
    assert list(df.well) == ["D05"]
    assert list(df.area_um2) == [25.0]
    assert list(df.intensity_mean_actin) == [300]

    viewer = ViewerModel()
    layer = open_in_viewer(viewer, "screen_D05")
    assert tuple(layer.scale) == (0.5, 0.5)
    assert viewer.layers["screen_D05"].data.max() == 900


def test_channel_sites_reopen_by_site_id(tmp_path, qapp):
    from napari.components import ViewerModel

    from lumen_napari.batch import open_in_viewer

    write(tmp_path, "E01_s2_w1abc.png", 2)
    write(tmp_path, "E01_s2_w2def.png", 2)
    measure_files(sorted(tmp_path.glob("*.png")), min_size=0,
                  channels={"dapi": "_w1", "actin": "_w2"}, segment_channel="dapi")
    viewer = ViewerModel()
    assert open_in_viewer(viewer, "E01_s2").data.max() == 2

import numpy as np
import pytest
from skimage.io import imsave

from lumen_napari.files import channel_name, read_file, well_from_ome


@pytest.fixture
def ome_tiff(tmp_path):
    pytest.importorskip("bioio_ome_tiff")
    from bioio.writers import OmeTiffWriter
    from bioio_base.types import PhysicalPixelSizes

    data = np.zeros((2, 32, 32), np.uint16)
    data[0, 5:10, 5:10] = 500
    data[1, 5:10, 5:10] = 100
    path = tmp_path / "site.ome.tiff"
    OmeTiffWriter.save(data, str(path), dim_order="CYX", channel_names=["DAPI", "Tubulin β"],
                       physical_pixel_sizes=PhysicalPixelSizes(None, 0.65, 0.65))
    return path


def test_ome_tiff_metadata(ome_tiff):
    file = read_file(ome_tiff)
    assert list(file.channels) == ["dapi", "tubulin"]
    assert file.channels["tubulin"].max() == 100
    assert file.spacing == (0.65, 0.65)
    assert file.unit == "um"
    assert file.well is None


def test_plain_files_have_one_channel(tmp_path):
    imsave(tmp_path / "a.png", np.zeros((4, 4), np.uint8), check_contrast=False)
    file = read_file(tmp_path / "a.png")
    assert list(file.channels) == ["image"]
    assert file.spacing is None


def test_channel_name():
    assert channel_name("Alexa Fluor 488", 0) == "alexa_fluor_488"
    assert channel_name("", 2) == "c2"


def test_well_from_ome_plate():
    from ome_types.model import OME, Image, ImageRef, Pixels, Plate, Well, WellSample

    pixels = Pixels(dimension_order="XYZCT", size_x=1, size_y=1, size_z=1, size_c=1, size_t=1,
                    type="uint8")
    image = Image(id="Image:0", pixels=pixels)
    well = Well(row=1, column=2, well_samples=[WellSample(index=0, image_ref=ImageRef(id="Image:0"))])
    ome = OME(images=[image], plates=[Plate(wells=[well])])
    assert well_from_ome(ome, 0) == "B03"
    assert well_from_ome(OME(images=[image]), 0) is None
    assert well_from_ome(object(), 0) is None

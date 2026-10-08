import io
import threading

import numpy as np
import pytest
from napari.components import ViewerModel
from skimage.io import imsave

from lumen_napari.controls import NapariControls
from lumen_napari.upload import IMAGE_EXTENSIONS, image_upload_handlers


def run(qtbot, handler, *args):
    out = {}
    thread = threading.Thread(target=lambda: out.update(source=handler(*args)))
    thread.start()
    qtbot.waitUntil(lambda: not thread.is_alive(), timeout=60_000)
    return out["source"]


@pytest.fixture
def controls(qapp):
    return NapariControls(viewer=ViewerModel())


def png_bytes():
    image = np.zeros((40, 40), np.uint8)
    image[5:15, 5:15] = 200
    image[25:35, 25:35] = 200
    buffer = io.BytesIO()
    imsave(buffer, image, extension=".png", check_contrast=False)
    buffer.seek(0)
    return buffer


def test_every_image_extension_has_a_handler(controls):
    assert set(image_upload_handlers(controls)) == set(IMAGE_EXTENSIONS)


def test_uploaded_png_opens_in_napari_segmented(qtbot, controls):
    handler = image_upload_handlers(controls)["png"]
    source = run(qtbot, handler, {}, png_bytes(), "cells", "cells")
    viewer = controls.viewer
    assert [layer.name for layer in viewer.layers] == ["cells", "cells labels"]
    assert source.execute("SELECT COUNT(*) AS n FROM cells_labels").n[0] == 2


def test_uploaded_ome_tiff_keeps_channels_and_pixel_size(qtbot, controls, tmp_path):
    pytest.importorskip("bioio_ome_tiff")
    from bioio.writers import OmeTiffWriter
    from bioio_base.types import PhysicalPixelSizes

    data = np.zeros((2, 40, 40), np.uint16)
    data[0, 5:15, 5:15] = 900
    data[1, 5:15, 5:15] = 300
    path = tmp_path / "site.ome.tiff"
    OmeTiffWriter.save(data, str(path), dim_order="CYX", channel_names=["DAPI", "Actin"],
                       physical_pixel_sizes=PhysicalPixelSizes(None, 0.5, 0.5))
    upload = io.BytesIO(path.read_bytes())
    source = run(qtbot, image_upload_handlers(controls)["tiff"], {}, upload, "site", "site.ome")
    viewer = controls.viewer
    assert [layer.name for layer in viewer.layers] == ["site dapi", "site actin", "site dapi labels"]
    assert tuple(viewer.layers["site dapi"].scale) == (0.5, 0.5)
    df = source.execute("SELECT area_um2, intensity_mean_site_actin FROM site_dapi_labels")
    assert df.area_um2[0] == 25 and df.intensity_mean_site_actin[0] == 300


def test_lumen_uploader_sends_images_to_napari(qapp):
    from lumen.ai.controls import UploadSourceControls
    from lumen.ai.llm import OpenAI

    from lumen_napari.app import build_ui

    viewer = ViewerModel()
    ui = build_ui(viewer, llm=OpenAI(api_key="sk-test"))
    [uploader] = [c for c in ui.context["source_controls"] if isinstance(c, UploadSourceControls)]
    uploader._file_input.value = {"cells.png": png_bytes().getvalue()}
    uploader.param.trigger("add")
    assert [layer.name for layer in viewer.layers] == ["cells", "cells labels"]
    sources = uploader.outputs.get("sources", [])
    assert any("cells_labels" in source.get_tables() for source in sources)

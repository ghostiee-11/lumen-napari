import urllib.request

import pytest
from lumen.ai.llm import OpenAI
from napari.components import ViewerModel

from lumen_napari.app import LumenServer, build_ui
from lumen_napari.controls import NapariControls


@pytest.fixture
def llm():
    return OpenAI(api_key="sk-test")


def test_build_ui_wires_napari(qapp, llm):
    ui = build_ui(ViewerModel(), llm=llm)
    assert isinstance(ui.source_controls[0], NapariControls)
    assert [tool.name for tool in ui.tools] == ["list_napari_layers", "show_object_in_napari"]
    assert ui.title == "Lumen for napari"


def test_server_serves_and_stops(qapp, llm):
    server = LumenServer(ViewerModel(), llm=llm)
    assert not server.running
    url = server.start()
    try:
        html = urllib.request.urlopen(url, timeout=60).read().decode()
        assert "Lumen for napari" in html
    finally:
        server.stop()
    assert not server.running


def test_sessions_share_the_server_script(qapp, llm):
    server = LumenServer(ViewerModel(), llm=llm)
    ui = build_ui(server.viewer, server.script, llm=llm)
    assert ui.source_controls[0].script is server.script


def test_object_explorer_is_available(qapp, llm):
    viewer = ViewerModel()
    ui = build_ui(viewer, llm=llm)
    explorer, plate = ui.analyses
    assert explorer.name == "ObjectExplorer"
    assert plate.name == "PlateHeatmap"
    assert explorer.instance().viewer is viewer

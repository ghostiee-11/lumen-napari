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
    assert [tool.name for tool in ui.tools] == [
        "list_napari_layers", "show_object_in_napari", "color_objects_by", "filter_objects",
        "set_pixel_size", "segmentation_methods", "compare_conditions",
    ]
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


def test_page_shows_the_app_once(qapp, llm):
    from bokeh.client import pull_session

    server = LumenServer(ViewerModel(), llm=llm)
    server.start()
    try:
        with pull_session(url=server.url) as session:
            roots = session.document.roots
            # The whole page, header included, is one React root; serving it twice made two.
            assert [type(r).__name__ for r in roots].count("ReactComponent") == 1
    finally:
        server.stop()


def test_reports_reach_the_chat(qapp, llm):
    ui = build_ui(ViewerModel(), llm=llm)
    before = len(ui.interface.objects)
    import numpy as np

    from lumen_napari.report import overlay_png

    png = overlay_png(np.zeros((8, 8)), np.ones((8, 8), int))
    ui.source_controls[0].chat("**Segmented**", png)
    message = ui.interface.objects[-1]
    assert len(ui.interface.objects) == before + 1
    assert message.user == "napari"
    assert message.object.objects[0].object == "**Segmented**"
    assert message.object.objects[1].object == png


def test_tools_post_failures_to_the_chat(qapp, llm):
    ui = build_ui(ViewerModel(), llm=llm)
    assert all(tool.chat is ui.source_controls[0].chat for tool in ui.tools)


def test_questions_and_cards_are_kept_for_the_report(qapp, llm):
    viewer = ViewerModel()
    ui = build_ui(viewer, llm=llm)
    script = ui.source_controls[0].script
    ui.interface.send("How many nuclei?", user=ui.interface.user, respond=False)
    ui.interface.send("not a question", user="napari", respond=False)
    assert script.questions == ["How many nuclei?"]
    ui.source_controls[0]._post("**card**")
    assert script.cards[-1] == ("**card**", None)

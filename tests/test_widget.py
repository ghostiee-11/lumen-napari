import urllib.request

from lumen.ai.llm import OpenAI
from napari.components import ViewerModel

from lumen_napari.widget import LumenWidget


def test_start_and_stop(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    widget = LumenWidget(ViewerModel())
    widget.server.params["llm"] = OpenAI(api_key="sk-test")
    qtbot.addWidget(widget)
    assert widget.toggle.text() == "Start Lumen"
    assert not widget.open.isEnabled()

    widget.toggle.click()
    try:
        assert opened == [widget.server.url]
        assert widget.toggle.text() == "Stop Lumen"
        assert widget.server.url in widget.status.text()
        assert urllib.request.urlopen(widget.server.url, timeout=60).status == 200
    finally:
        widget.toggle.click()
    assert widget.toggle.text() == "Start Lumen"
    assert not widget.server.running


def test_reopening_reuses_the_server_and_quit_stops_it(qtbot, qapp):
    viewer = ViewerModel()
    first, second = LumenWidget(viewer), LumenWidget(viewer)
    qtbot.addWidget(first)
    qtbot.addWidget(second)
    assert first.server is second.server
    first.server.params["llm"] = OpenAI(api_key="sk-test")
    first.server.start()
    qapp.aboutToQuit.emit()
    assert not first.server.running


def test_export_script(qtbot, tmp_path):
    widget = LumenWidget(ViewerModel())
    qtbot.addWidget(widget)
    widget._export(str(tmp_path / "a.py"))
    assert "Nothing to export yet" in widget.status.text()
    assert not (tmp_path / "a.py").exists()

    widget.server.script.add("labels = None")
    widget._export(str(tmp_path / "a.py"))
    assert "labels = None" in (tmp_path / "a.py").read_text()
    assert "Saved the analysis script" in widget.status.text()


def test_napari_plugin_proxy_is_unwrapped(qtbot, qapp):
    import warnings

    from napari.utils._proxies import PublicOnlyProxy

    from lumen_napari.app import build_ui

    viewer = ViewerModel()
    widget = LumenWidget(PublicOnlyProxy(viewer))
    qtbot.addWidget(widget)
    assert widget.server.viewer is viewer
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message="Private attribute access")
        build_ui(widget.server.viewer, llm=OpenAI(api_key="sk-test"))

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

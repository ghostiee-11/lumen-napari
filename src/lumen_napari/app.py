"""Serve a Lumen chat app bound to a live napari viewer."""

from __future__ import annotations

import socket
import time

import panel as pn
from lumen.ai.controls import UploadSourceControls
from lumen.ai.ui import ExplorerUI
from napari.components import ViewerModel

from .clickable import make_charts_clickable
from .controls import NapariControls
from .explorer import explorer_for
from .plate import plate_for
from .script import Script
from .tools import make_tools

SUGGESTIONS = [
    ("biotech", "Segment the nuclei layer and plot the distribution of object area"),
    ("search", "Which objects are the brightest? Show the top one in napari"),
    ("scatter_plot", "Plot area against mean intensity for every object"),
    ("touch_app", "Explore the objects and click one to see it in napari"),
    ("grid_on", "Show a plate heatmap of the mean nuclear area per well"),
]


def build_ui(viewer: ViewerModel, script: Script | None = None, **params) -> ExplorerUI:
    """A Lumen ExplorerUI whose data comes from the napari viewer."""
    script = script or Script()
    controls = NapariControls(viewer=viewer, script=script)
    make_charts_clickable(viewer, on_chart=script.chart)
    params.setdefault("title", "Lumen for napari")
    params.setdefault("suggestions", SUGGESTIONS)
    ui = ExplorerUI(
        source_controls=[controls, UploadSourceControls],
        tools=make_tools(viewer),
        analyses=[explorer_for(viewer), plate_for(viewer)],
        **params,
    )
    controls.chat = chat_poster(ui.interface)
    ui.interface.param.watch(lambda event: _record_questions(script, ui.interface, event),
                             "objects")
    for tool in ui.tools:
        tool.chat = controls.chat
    return ui


def _record_questions(script: Script, interface, event) -> None:
    """Keep each new question typed in the chat, for the report."""
    for message in event.new[len(event.old):]:
        question = message.object
        if message.user == interface.user and isinstance(question, str) \
                and question not in script.questions:
            script.questions.append(question)


def chat_poster(interface):
    """post(markdown, png=None) adding a "napari" message to the chat. Steps run on worker
    threads, so in a served session the message is added on the document's next tick."""
    doc = pn.state.curdoc

    def post(text: str, png: bytes | None = None) -> None:
        def send():
            parts = [pn.pane.Markdown(text, sizing_mode="stretch_width")]
            if png:
                parts.append(pn.pane.PNG(png, width=360))
            interface.send(pn.Column(*parts), user="napari", respond=False)

        if doc is not None and doc.session_context is not None:
            doc.add_next_tick_callback(send)
        else:
            send()

    return post


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError(f"Lumen server did not start on port {port}.")


class LumenServer:
    """Run the Lumen app for a viewer in a background thread, reachable only from this machine."""

    def __init__(self, viewer: ViewerModel, port: int | None = None, **params):
        self.viewer = viewer
        self.port = port or free_port()
        self.params = params
        self.script = Script()
        self._thread = None

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}"

    @property
    def running(self) -> bool:
        return self._thread is not None

    def _page(self):
        # The full page (header, sidebar, JS extensions) is what ExplorerUI.servable() adds to
        # the document; returning it, and not also calling servable(), renders it once.
        return build_ui(self.viewer, self.script, **self.params)._create_view(server=True)

    def start(self) -> str:
        if not self.running:
            self._thread = pn.serve(
                self._page,
                port=self.port,
                address="127.0.0.1",
                websocket_origin=[f"localhost:{self.port}", f"127.0.0.1:{self.port}"],
                threaded=True,
                show=False,
                verbose=False,
                title="Lumen for napari",
            )
            _wait_for_port(self.port)
        return self.url

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread = None

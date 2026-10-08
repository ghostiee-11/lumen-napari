"""Serve a Lumen chat app bound to a live napari viewer."""

from __future__ import annotations

import socket
import time

import panel as pn
from lumen.ai.controls import UploadSourceControls
from lumen.ai.ui import ExplorerUI
from napari.components import ViewerModel

from .controls import NapariControls
from .tools import make_tools

SUGGESTIONS = [
    ("biotech", "Segment the nuclei layer and plot the distribution of object area"),
    ("search", "Which objects are the brightest? Show the top one in napari"),
    ("scatter_plot", "Plot area against mean intensity for every object"),
]


def build_ui(viewer: ViewerModel, **params) -> ExplorerUI:
    """A Lumen ExplorerUI whose data comes from the napari viewer."""
    params.setdefault("title", "Lumen for napari")
    params.setdefault("suggestions", SUGGESTIONS)
    return ExplorerUI(
        source_controls=[NapariControls(viewer=viewer), UploadSourceControls],
        tools=make_tools(viewer),
        **params,
    )


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
        self._thread = None

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}"

    @property
    def running(self) -> bool:
        return self._thread is not None

    def start(self) -> str:
        if not self.running:
            self._thread = pn.serve(
                lambda: build_ui(self.viewer, **self.params).servable(),
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

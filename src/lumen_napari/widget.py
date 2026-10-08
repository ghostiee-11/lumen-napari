"""napari dock widget that starts the Lumen app for the current viewer."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from weakref import WeakKeyDictionary

import napari
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .app import LumenServer

_servers: WeakKeyDictionary = WeakKeyDictionary()


def server_for(viewer) -> LumenServer:
    """One server per viewer, so closing and reopening the dock keeps the same chat."""
    if viewer not in _servers:
        _servers[viewer] = server = LumenServer(viewer)
        QApplication.instance().aboutToQuit.connect(server.stop)
    return _servers[viewer]


class LumenWidget(QWidget):
    def __init__(self, napari_viewer: napari.Viewer, parent: QWidget | None = None):
        super().__init__(parent)
        # napari hands plugins a proxy that warns on private attribute access, which param
        # does when it stores the viewer. Lumen gets the viewer itself.
        self.server = server_for(getattr(napari_viewer, "__wrapped__", napari_viewer))
        self.toggle = QPushButton("Start Lumen")
        self.open = QPushButton("Open in browser")
        self.export = QPushButton("Export script")
        self.export.setToolTip("Save the segmentation and measurement steps as a Python script.")
        self.status = QLabel("Ask questions about your layers in plain language.")
        self.status.setWordWrap(True)
        self.status.setOpenExternalLinks(True)
        self.toggle.clicked.connect(self._toggle)
        self.open.clicked.connect(lambda: webbrowser.open(self.server.url))
        self.export.clicked.connect(self._export)
        layout = QVBoxLayout(self)
        for widget in (self.toggle, self.open, self.export, self.status):
            layout.addWidget(widget)
        layout.addStretch()
        self._refresh()

    def _toggle(self) -> None:
        if self.server.running:
            self.server.stop()
        else:
            self.status.setText("Starting Lumen...")
            QApplication.processEvents()
            webbrowser.open(self.server.start())
        self._refresh()

    def _export(self, path: str | None = None) -> None:
        if not self.server.script.lines:
            self.status.setText("Nothing to export yet. Ask Lumen to segment or measure a layer.")
            return
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Export script", "analysis.py", "Python (*.py)")
        if path:
            Path(path).write_text(self.server.script.render())
            self.status.setText(f"Saved the analysis script to {path}")

    def _refresh(self) -> None:
        running = self.server.running
        self.toggle.setText("Stop Lumen" if running else "Start Lumen")
        self.open.setEnabled(running)
        if running:
            url = self.server.url
            self.status.setText(f'Lumen is running at <a href="{url}">{url}</a>')
        else:
            self.status.setText("Ask questions about your layers in plain language.")

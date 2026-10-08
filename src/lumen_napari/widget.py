"""napari dock widget that starts the Lumen app for the current viewer."""

from __future__ import annotations

import webbrowser

import napari
from qtpy.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from .app import LumenServer


class LumenWidget(QWidget):
    def __init__(self, napari_viewer: napari.Viewer, parent: QWidget | None = None):
        super().__init__(parent)
        self.server = LumenServer(napari_viewer)
        self.toggle = QPushButton("Start Lumen")
        self.open = QPushButton("Open in browser")
        self.status = QLabel("Ask questions about your layers in plain language.")
        self.status.setWordWrap(True)
        self.status.setOpenExternalLinks(True)
        self.toggle.clicked.connect(self._toggle)
        self.open.clicked.connect(lambda: webbrowser.open(self.server.url))
        layout = QVBoxLayout(self)
        for widget in (self.toggle, self.open, self.status):
            layout.addWidget(widget)
        layout.addStretch()
        QApplication.instance().aboutToQuit.connect(self.server.stop)
        self._refresh()

    def _toggle(self) -> None:
        if self.server.running:
            self.server.stop()
        else:
            self.status.setText("Starting Lumen...")
            QApplication.processEvents()
            webbrowser.open(self.server.start())
        self._refresh()

    def _refresh(self) -> None:
        running = self.server.running
        self.toggle.setText("Stop Lumen" if running else "Start Lumen")
        self.open.setEnabled(running)
        if running:
            url = self.server.url
            self.status.setText(f'Lumen is running at <a href="{url}">{url}</a>')
        else:
            self.status.setText("Ask questions about your layers in plain language.")

"""Record the napari steps Lumen ran as a Python script that reproduces them."""

from __future__ import annotations

from napari.layers import Layer

HEADER = '''"""Reproduces the lumen-napari steps run on this viewer."""

import napari
import pandas as pd

from lumen_napari.controls import intensity
from lumen_napari.measure import measure, to_features
from lumen_napari.segment import segment

viewer = napari.Viewer()
tables = {}
'''

FOOTER = "\nnapari.run()\n"


class Script:
    def __init__(self):
        self.lines: list[str] = []
        self._loaded: set[str] = set()

    def load(self, layer: Layer) -> None:
        """Add the line that loads a layer, once per layer."""
        if layer.name in self._loaded:
            return
        self._loaded.add(layer.name)
        path = layer.source.path
        if path:
            self.lines.append(f"viewer.open({path!r})[0].name = {layer.name!r}")
        else:
            self.lines.append(f"# Load the {layer.name!r} layer into the viewer here.")

    def created(self, name: str) -> None:
        """Mark a layer the script itself creates, so it is never loaded from disk."""
        self._loaded.add(name)

    def add(self, *lines: str) -> None:
        self.lines.extend(lines)
        self.lines.append("")

    def body(self) -> str:
        return "\n".join(self.lines)

    def render(self) -> str:
        return HEADER + "\n" + self.body() + FOOTER

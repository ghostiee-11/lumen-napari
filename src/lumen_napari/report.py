"""What a napari step did, shown in the chat: settings, counts, units and an overlay to check."""

from __future__ import annotations

import base64
import html
import io
import json
from datetime import datetime

import imageio.v3 as iio
import numpy as np
from markdown_it import MarkdownIt
from skimage import exposure, segmentation, transform

MAX_SIDE = 600


def overlay_png(image: np.ndarray, labels: np.ndarray) -> bytes:
    """A PNG of the image with object outlines, to check a segmentation at a glance. Volumes
    show the slice with the most objects."""
    image, labels = np.asarray(image, dtype=float), np.asarray(labels)
    if labels.ndim == 3:
        z = int(np.argmax([len(np.unique(plane)) for plane in labels]))
        image, labels = image[z], labels[z]
    scale = min(1.0, MAX_SIDE / max(labels.shape))
    if scale < 1:
        shape = tuple(int(n * scale) for n in labels.shape)
        image = transform.resize(image, shape, anti_aliasing=True)
        labels = transform.resize(labels, shape, order=0, preserve_range=True, anti_aliasing=False)
    low, high = np.percentile(image, (1, 99.5))
    gray = exposure.rescale_intensity(image, in_range=(low, high if high > low else low + 1),
                                      out_range=(0, 1))
    outlined = segmentation.mark_boundaries(gray, labels.astype(int), color=(1, 0.55, 0))
    buffer = io.BytesIO()
    iio.imwrite(buffer, (outlined * 255).astype(np.uint8), extension=".png")
    return buffer.getvalue()


def size_note(unit: str | None, spacing) -> str:
    """How sizes are expressed, with a warning when they are in pixels."""
    if unit:
        return f"Sizes are in {unit} (pixel size {', '.join(f'{s:g}' for s in spacing)} {unit})."
    return (
        "⚠️ **Sizes are in pixels**: this image has no pixel size, so areas cannot be compared "
        "across instruments. Tell me the pixel size, for example *\"the pixel size is "
        "0.65 µm\"*, and I will measure in micrometers."
    )


def segmentation_report(source: str, count: int, settings: dict, units: str, table: str) -> str:
    """Markdown describing one segmentation, ending with the check question. `units` is the
    sentence from `size_note`."""
    shown = ", ".join(f"{k}={v!r}" for k, v in settings.items())
    if not count:
        return (
            f"**No objects found in `{source}`** (settings: {shown}).\n\n"
            "The image may be blank or out of focus, or the objects smaller than min_size. "
            "Ask me to try a smaller min_size, or method='cellpose' for tissue and crowded cells."
        )
    return (
        f"**Segmented `{source}`: {count:,} objects** into table `{table}`.\n\n"
        f"Settings: {shown}.\n\n{units}\n\n"
        "**Does the outline look right?** If not, ask me to segment again with other settings "
        "(for example a larger min_size, or method='cellpose'), or fix objects by hand in "
        "napari: they are measured again automatically."
    )


def report_html(script, snapshot: bytes | None = None, title: str = "lumen-napari report") -> str:
    """One standalone HTML page: questions, napari snapshot, report cards with overlays, the
    charts (rendered by vega-embed) and the Python that reproduces the analysis."""
    md = MarkdownIt()
    sections = [f"<h1>{html.escape(title)}</h1>",
                f"<p class=muted>Exported {datetime.now().astimezone():%Y-%m-%d %H:%M %Z} from lumen-napari.</p>"]
    if script.questions:
        items = "".join(f"<li>{html.escape(q)}</li>" for q in script.questions)
        sections.append(f"<h2>Questions</h2><ol>{items}</ol>")
    if snapshot:
        sections.append(f"<h2>napari</h2>{_img(snapshot, 'napari viewer')}")
    if script.cards:
        cards = "".join(f"<div class=card>{md.render(text)}{_img(png, 'overlay') if png else ''}</div>"
                        for text, png in script.cards)
        sections.append(f"<h2>Steps and checks</h2>{cards}")
    if script.charts:
        divs = "".join(f"<div class=chart id=chart{i}></div>" for i in range(len(script.charts)))
        calls = "".join(f"vegaEmbed('#chart{i}', {_script_json(spec)});"
                        for i, spec in enumerate(script.charts))
        sections.append(f"<h2>Charts</h2>{divs}<script>{calls}</script>")
    sections.append(f"<h2>Methods: reproduce this analysis</h2><pre>{html.escape(script.render())}</pre>")
    return REPORT.format(title=html.escape(title), body="\n".join(sections))


def _script_json(value) -> str:
    """JSON safe inside a script tag: "</" is escaped so data cannot close the tag."""
    return json.dumps(value, default=str).replace("</", "<\\/")


def _img(png: bytes, alt: str) -> str:
    return f"<img alt='{alt}' src='data:image/png;base64,{base64.b64encode(png).decode()}'>"


REPORT = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 16px;
       color: #1f2328; line-height: 1.5; }}
h1 {{ margin-bottom: 0; }} .muted {{ color: #656d76; }}
.card {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 0 16px 16px; margin: 16px 0; }}
img {{ max-width: 100%; border-radius: 4px; }} .chart {{ margin: 16px 0; }}
pre {{ background: #f6f8fa; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; }}
</style></head><body>
{body}
</body></html>
"""

"""Deterministic PIL-based speech bubble renderer.

The Fabric.js editor and this module share a tiny JSON schema so any layout
saved from the browser can be re-rendered server-side identically. That keeps
generated panels reproducible without depending on the editor's raster export.

Schema
------
::

    {
      "bubbles": [
        {
          "shape": "rounded" | "ellipse" | "shout" | "thought",
          "x": 100, "y": 50, "width": 300, "height": 150,
          "text": "Hello!",
          "font_size": 28,
          "tail": {"x": 220, "y": 320}   // point the tail aims at (optional)
        }
      ]
    }
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

_DEFAULT_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _DEFAULT_FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


@dataclass
class Bubble:
    shape: str
    x: int
    y: int
    width: int
    height: int
    text: str = ""
    font_size: int = 28
    tail: tuple[int, int] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Bubble":
        tail = None
        tail_data = d.get("tail")
        if isinstance(tail_data, dict) and "x" in tail_data and "y" in tail_data:
            tail = (int(tail_data["x"]), int(tail_data["y"]))
        return cls(
            shape=str(d.get("shape", "rounded")),
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
            width=int(d.get("width", 200)),
            height=int(d.get("height", 100)),
            text=str(d.get("text", "")),
            font_size=int(d.get("font_size", 28)),
            tail=tail,
        )


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_tail(draw: ImageDraw.ImageDraw, bubble: Bubble, fill, outline, width: int) -> None:
    if bubble.tail is None:
        return
    cx = bubble.x + bubble.width // 2
    cy = bubble.y + bubble.height // 2
    tx, ty = bubble.tail
    # Base of the tail sits on the edge of the bubble closest to (tx, ty).
    dx = tx - cx
    dy = ty - cy
    norm = math.hypot(dx, dy) or 1.0
    # Scale to the ellipse/rectangle's edge.
    ex = cx + (dx / norm) * bubble.width * 0.5
    ey = cy + (dy / norm) * bubble.height * 0.5
    base_width = max(16, min(bubble.width, bubble.height) // 5)
    # Perpendicular offset for base points.
    px = -dy / norm * base_width / 2
    py = dx / norm * base_width / 2
    poly = [
        (ex + px, ey + py),
        (ex - px, ey - py),
        (tx, ty),
    ]
    draw.polygon(poly, fill=fill, outline=outline)


def _draw_shout(draw: ImageDraw.ImageDraw, bubble: Bubble, fill, outline, width: int) -> None:
    cx = bubble.x + bubble.width / 2
    cy = bubble.y + bubble.height / 2
    spikes = 16
    rx_out = bubble.width / 2
    ry_out = bubble.height / 2
    rx_in = rx_out * 0.82
    ry_in = ry_out * 0.82
    pts: list[tuple[float, float]] = []
    for i in range(spikes * 2):
        angle = (math.pi * i) / spikes
        rx = rx_out if i % 2 == 0 else rx_in
        ry = ry_out if i % 2 == 0 else ry_in
        pts.append((cx + math.cos(angle) * rx, cy + math.sin(angle) * ry))
    draw.polygon(pts, fill=fill, outline=outline)


def _draw_thought(draw: ImageDraw.ImageDraw, bubble: Bubble, fill, outline, width: int) -> None:
    # Cloud of overlapping circles around the bubble perimeter.
    cx = bubble.x + bubble.width / 2
    cy = bubble.y + bubble.height / 2
    rx = bubble.width / 2
    ry = bubble.height / 2
    bumps = 14
    radius = min(bubble.width, bubble.height) * 0.12
    for i in range(bumps):
        a = (2 * math.pi * i) / bumps
        x = cx + math.cos(a) * (rx - radius * 0.4)
        y = cy + math.sin(a) * (ry - radius * 0.4)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=fill,
            outline=outline,
            width=width,
        )
    # Also fill the centre so text sits on a solid area.
    draw.ellipse(
        (bubble.x + bubble.width * 0.15, bubble.y + bubble.height * 0.15,
         bubble.x + bubble.width * 0.85, bubble.y + bubble.height * 0.85),
        fill=fill,
        outline=None,
    )


def _draw_bubble_background(draw: ImageDraw.ImageDraw, bubble: Bubble, fill, outline, width: int) -> None:
    bbox = (bubble.x, bubble.y, bubble.x + bubble.width, bubble.y + bubble.height)
    if bubble.shape == "ellipse":
        draw.ellipse(bbox, fill=fill, outline=outline, width=width)
    elif bubble.shape == "shout":
        _draw_shout(draw, bubble, fill, outline, width)
    elif bubble.shape == "thought":
        _draw_thought(draw, bubble, fill, outline, width)
    else:
        # Rounded rectangle (default).
        radius = int(min(bubble.width, bubble.height) * 0.25)
        draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def render_bubble(image: Image.Image, bubble: Bubble) -> None:
    """Draw a single bubble onto ``image`` in place."""
    draw = ImageDraw.Draw(image, mode="RGBA")
    fill = (255, 255, 255, 255)
    outline = (0, 0, 0, 255)
    stroke_width = max(2, min(bubble.width, bubble.height) // 60)

    # Tail first (so bubble body covers its base).
    _draw_tail(draw, bubble, fill, outline, stroke_width)
    _draw_bubble_background(draw, bubble, fill, outline, stroke_width)

    # Text.
    font = _load_font(bubble.font_size)
    padding = int(min(bubble.width, bubble.height) * 0.12)
    max_text_width = max(10, bubble.width - 2 * padding)
    lines = _wrap_text(bubble.text, font, max_text_width, draw)
    if hasattr(font, "getbbox"):
        line_height = font.getbbox("Ag")[3] + 4
    else:
        line_height = bubble.font_size + 4
    total_h = line_height * len(lines)
    start_y = bubble.y + (bubble.height - total_h) // 2
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        draw.text(
            (bubble.x + (bubble.width - w) / 2, start_y + i * line_height),
            line,
            fill=(0, 0, 0, 255),
            font=font,
        )


def render(image: Image.Image, layout: dict[str, Any]) -> Image.Image:
    """Non-destructive: returns a copy with all bubbles drawn on top."""
    out = image.convert("RGBA").copy()
    bubbles = [Bubble.from_dict(d) for d in layout.get("bubbles", [])]
    for b in bubbles:
        render_bubble(out, b)
    return out.convert("RGB")

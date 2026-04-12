"""Build a multi-character OpenPose skeleton image at correct relative scale.

The comic pipeline enforces character height by rendering a deterministic
OpenPose skeleton where each character's skeleton is scaled by
``char.height_cm / tallest.height_cm``. Feeding that skeleton to ControlNet
OpenPose forces the diffusion model to respect the heights regardless of how
the prompt describes each character.

The keypoint layout follows the standard OpenPose body-18 scheme as rendered
by ``lllyasviel/ControlNet-v1-1``; colors match the reference implementation
so the ControlNet preprocessor and the target LoRA recognise it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from PIL import Image

# --- Standard OpenPose body-18 keypoints (normalised 0..1, head-at-top) -----
# Coordinates describe a neutral standing pose, 1.0 = full body height.
# x is centred on 0.5; y grows downward.
_TEMPLATE: dict[int, tuple[float, float]] = {
    0: (0.50, 0.055),   # nose
    1: (0.50, 0.15),    # neck
    2: (0.57, 0.18),    # right shoulder
    3: (0.60, 0.33),    # right elbow
    4: (0.62, 0.46),    # right wrist
    5: (0.43, 0.18),    # left shoulder
    6: (0.40, 0.33),    # left elbow
    7: (0.38, 0.46),    # left wrist
    8: (0.54, 0.52),    # right hip
    9: (0.55, 0.73),    # right knee
    10: (0.56, 0.96),   # right ankle
    11: (0.46, 0.52),   # left hip
    12: (0.45, 0.73),   # left knee
    13: (0.44, 0.96),   # left ankle
    14: (0.52, 0.045),  # right eye
    15: (0.48, 0.045),  # left eye
    16: (0.54, 0.055),  # right ear
    17: (0.46, 0.055),  # left ear
}

# Limb connections, as (start_kp, end_kp).
_LIMBS: list[tuple[int, int]] = [
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
    (1, 0), (0, 14), (14, 16), (0, 15), (15, 17),
]

# Colours taken from the canonical ControlNet OpenPose renderer (BGR in that
# codebase; expressed here as RGB tuples).
_LIMB_COLORS: list[tuple[int, int, int]] = [
    (153, 0, 0), (153, 51, 0), (153, 102, 0), (153, 153, 0), (102, 153, 0),
    (51, 153, 0), (0, 153, 0), (0, 153, 51), (0, 153, 102), (0, 153, 153),
    (0, 102, 153), (0, 51, 153), (0, 0, 153), (51, 0, 153), (102, 0, 153),
    (153, 0, 153), (153, 0, 102),
]

_KEYPOINT_COLORS: list[tuple[int, int, int]] = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
    (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
    (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
    (255, 0, 255), (255, 0, 170), (255, 0, 85),
]


@dataclass
class CharacterSlot:
    """One character to place in the composed skeleton image."""
    name: str
    height_cm: float
    # Horizontal centre of the character in 0..1 (0=left edge, 1=right edge).
    # If None, auto-distribute across the frame.
    x_center: float | None = None


def _draw_line(canvas: np.ndarray, p1: tuple[float, float], p2: tuple[float, float], color: tuple[int, int, int], thickness: int) -> None:
    """Draw a thick line by stamping discs along the interpolation. Keeps the
    module dependency-light; OpenCV would work too but we avoid it for parity
    with the rest of this file."""
    x1, y1 = p1
    x2, y2 = p2
    length = max(abs(x2 - x1), abs(y2 - y1))
    steps = int(max(length * 1.5, 2))
    h, w = canvas.shape[:2]
    r = thickness // 2
    rr, cc = np.ogrid[-r:r + 1, -r:r + 1]
    mask = rr * rr + cc * cc <= r * r
    for i in range(steps + 1):
        t = i / steps
        x = int(round(x1 + t * (x2 - x1)))
        y = int(round(y1 + t * (y2 - y1)))
        y0, y1_ = max(0, y - r), min(h, y + r + 1)
        x0, x1_ = max(0, x - r), min(w, x + r + 1)
        if y0 >= y1_ or x0 >= x1_:
            continue
        sub_mask = mask[
            (y0 - (y - r)):(mask.shape[0] - ((y + r + 1) - y1_)),
            (x0 - (x - r)):(mask.shape[1] - ((x + r + 1) - x1_)),
        ]
        canvas[y0:y1_, x0:x1_][sub_mask] = color


def _draw_circle(canvas: np.ndarray, center: tuple[float, float], radius: int, color: tuple[int, int, int]) -> None:
    h, w = canvas.shape[:2]
    cx, cy = int(round(center[0])), int(round(center[1]))
    y0, y1_ = max(0, cy - radius), min(h, cy + radius + 1)
    x0, x1_ = max(0, cx - radius), min(w, cx + radius + 1)
    if y0 >= y1_ or x0 >= x1_:
        return
    rr, cc = np.ogrid[y0 - cy:y1_ - cy, x0 - cx:x1_ - cx]
    mask = rr * rr + cc * cc <= radius * radius
    canvas[y0:y1_, x0:x1_][mask] = color


def build_skeleton(
    characters: Sequence[CharacterSlot],
    *,
    width: int = 1536,
    height: int = 1024,
    bottom_margin: float = 0.02,
    horizontal_padding: float = 0.05,
) -> Image.Image:
    """Render a black-background OpenPose image with one scaled skeleton per
    character. Y is aligned so that everyone's *ankles* share the same
    baseline — that's what makes heights visually correct."""
    if not characters:
        raise ValueError("Pass at least one CharacterSlot.")

    canvas = np.zeros((height, width, 3), dtype=np.uint8)

    tallest = max(c.height_cm for c in characters if c.height_cm > 0) or 1.0
    # Space between characters when auto-distributing.
    n = len(characters)
    inner = 1.0 - 2 * horizontal_padding
    default_centres = [
        horizontal_padding + inner * (i + 0.5) / n for i in range(n)
    ]
    baseline_y = (1.0 - bottom_margin) * height

    for idx, slot in enumerate(characters):
        scale = (slot.height_cm / tallest) if tallest else 1.0
        char_px_height = scale * (1.0 - bottom_margin - 0.02) * height
        cx = (slot.x_center if slot.x_center is not None else default_centres[idx]) * width
        # Template y=0 → head top; y=1 → ankles. We anchor ankles to baseline_y.
        def to_px(kp: tuple[float, float]) -> tuple[float, float]:
            nx, ny = kp
            # Horizontal spread scales with the character's height too, so
            # narrow characters stay narrow.
            dx = (nx - 0.5) * char_px_height * 0.45  # typical body width ~ 0.45H
            dy = (ny - 1.0) * char_px_height         # ankle-aligned
            return (cx + dx, baseline_y + dy)

        points = {i: to_px(p) for i, p in _TEMPLATE.items()}
        limb_thickness = max(3, int(round(char_px_height * 0.012)))
        joint_radius = max(3, int(round(char_px_height * 0.008)))

        for i, (a, b) in enumerate(_LIMBS):
            color = _LIMB_COLORS[i % len(_LIMB_COLORS)]
            _draw_line(canvas, points[a], points[b], color, limb_thickness)
        for i, (x, y) in points.items():
            _draw_circle(canvas, (x, y), joint_radius, _KEYPOINT_COLORS[i % len(_KEYPOINT_COLORS)])

    return Image.fromarray(canvas, mode="RGB")

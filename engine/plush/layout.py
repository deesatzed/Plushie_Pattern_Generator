"""Cutting layout: every copy of every piece laid on its fabric, grain along the fabric's length.

Pieces are never rotated (their grain arrow runs along the fabric), mirrored copies are
flipped, and pieces are packed in rows across the fabric width.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from plush.finishing import Pattern
from plush.settings import Settings

SPACING_IN = 0.125  # gap between neighbouring cut lines


class LayoutError(ValueError):
    """A piece is wider than the fabric."""


@dataclass
class Placement:
    piece: str
    copy: int  # 1-based
    mirrored: bool
    outline: np.ndarray  # cut line on the fabric, inches; x across the width, y along the length


@dataclass
class FabricLayout:
    colour: str
    width_in: float
    length_in: float
    placements: list[Placement]


def cutting_layout(pattern: Pattern, settings: Settings) -> list[FabricLayout]:
    by_colour: dict[str, list[tuple[str, int, bool, np.ndarray]]] = {}
    for piece in pattern.pieces.values():
        for copy in range(1, piece.cut_count + 1):
            mirrored = copy > piece.cut_count - piece.mirrored
            outline = piece.cut * ([-1, 1] if mirrored else [1, 1])
            by_colour.setdefault(piece.colour, []).append((piece.name, copy, mirrored, outline))

    width = settings.fabric_width_in
    layouts = []
    for colour, copies in by_colour.items():
        copies.sort(key=lambda c: -np.ptp(c[3][:, 1]))  # tallest first
        x = y = row_height = 0.0
        placements = []
        for name, copy, mirrored, outline in copies:
            w, h = np.ptp(outline, axis=0)
            if w > width:
                raise LayoutError(f"piece {name!r} is {w:.2f} in wide; the fabric is {width} in")
            if x > 0 and x + w > width:  # next row
                x, y, row_height = 0.0, y + row_height + SPACING_IN, 0.0
            placed = outline - outline.min(axis=0) + [x, y]
            placements.append(Placement(name, copy, mirrored, placed))
            x += w + SPACING_IN
            row_height = max(row_height, h)
        layouts.append(FabricLayout(colour, width, y + row_height, placements))
    return layouts

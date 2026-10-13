"""Materials list: fabric per colour (from the cutting layout), stuffed volume, safety eyes, thread."""

from __future__ import annotations

from dataclasses import dataclass

import igl
import numpy as np

from plush.geometry.assemble import Placed
from plush.layout import FabricLayout
from plush.parts import FeatureMethod, Kit
from plush.stuffing import StuffingResult


@dataclass
class Materials:
    fabric: list[tuple[str, float, float]]  # (colour, width in, length in)
    stuffed_volume_cuin: float
    safety_eyes: list[tuple[str, float, int]]  # (feature name, diameter in, count)
    thread: str


def closed_volume(positions: np.ndarray, faces: np.ndarray) -> float:
    """Volume enclosed by a surface; an open end (a limb's sewn-on opening) is closed by a flat cap."""
    loops = igl.boundary_loop(faces)
    caps = []
    if len(loops):
        centre_index = len(positions)
        positions = np.vstack([positions, positions[loops].mean(axis=0)])
        caps = [[loops[i], centre_index, loops[(i + 1) % len(loops)]] for i in range(len(loops))]
    F = np.vstack([faces, caps]) if caps else faces
    a, b, c = positions[F[:, 0]], positions[F[:, 1]], positions[F[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6))


def materials(kit: Kit, placed: dict[str, Placed], layouts: list[FabricLayout],
              stuffing: dict[str, StuffingResult | None]) -> Materials:
    copies = {p.id: (2 if p.pair else 1) for p in kit.parts}
    volume = sum(closed_volume(r.inflated.positions, r.inflated.faces) * copies[part]
                 for part, r in stuffing.items() if r is not None)
    eyes = []
    for p in kit.parts:
        if p.kind == "surface_feature" and p.method is FeatureMethod.SAFETY_EYE:
            scale = next(pl.scale_in for pl in placed.values() if pl.part_id == p.id)
            eyes.append((p.name, p.width * scale, copies[p.id]))
    return Materials([(f.colour, f.width_in, f.length_in) for f in layouts], volume, eyes,
                     "Polyester thread to match each fabric colour")

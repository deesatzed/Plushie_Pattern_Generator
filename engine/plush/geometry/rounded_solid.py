"""Rounded solids (body, head, muzzle): a deformed sphere at finished size."""

from __future__ import annotations

import numpy as np
import trimesh

from plush.parts import RoundedSolid

SUBDIVISIONS = 4  # icosphere with 2562 vertices
FLAT_BOTTOM_CUT = 0.85  # unit-sphere depth at which a flat bottom is cut


def rounded_solid_mesh(part: RoundedSolid, scale_in: float) -> trimesh.Trimesh:
    """Mesh centred on its bounding box, sized exactly width x height x depth."""
    unit = trimesh.creation.icosphere(subdivisions=SUBDIVISIONS, radius=1.0)
    v = unit.vertices.copy()
    if part.flat_bottom:
        v[:, 1] = np.maximum(v[:, 1], -FLAT_BOTTOM_CUT)
    # +taper widens the lower half and narrows the upper half
    v[:, [0, 2]] *= (1.0 - part.taper * v[:, 1])[:, None]
    size = np.array([part.width, part.height, part.depth]) * scale_in
    lo, hi = v.min(axis=0), v.max(axis=0)
    v = (v - (lo + hi) / 2) / (hi - lo) * size
    return trimesh.Trimesh(vertices=v, faces=unit.faces, process=False)

"""Rounded solids (body, head, muzzle): a deformed sphere at finished size."""

from __future__ import annotations

import numpy as np
import trimesh

from plush.parts import RoundedSolid

SUBDIVISIONS = 4  # icosphere with 2562 vertices
FLAT_BOTTOM_CUT = 0.85  # unit-sphere depth at which a flat bottom is cut
_PROFILE_SAMPLES = 20001


def unit_direction(theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """Point on the unit sphere. theta from the top (0) down; phi around, 0 = front, pi/2 = left."""
    theta, phi = np.broadcast_arrays(theta, phi)
    return np.stack([np.sin(theta) * np.sin(phi), np.cos(theta), np.sin(theta) * np.cos(phi)], axis=-1)


def bottom_theta(part: RoundedSolid) -> float:
    """Polar angle where the surface ends: the bottom pole, or the rim of a flat bottom."""
    return float(np.arccos(-FLAT_BOTTOM_CUT)) if part.flat_bottom else float(np.pi)


def _normaliser(part: RoundedSolid) -> tuple[float, float, float]:
    """Vertical centre, widest radius and vertical half-height of the deformed unit sphere."""
    y_min = -FLAT_BOTTOM_CUT if part.flat_bottom else -1.0
    y = np.linspace(y_min, 1.0, _PROFILE_SAMPLES)
    radius = np.sqrt(np.clip(1 - y**2, 0, None)) * (1 - part.taper * y)
    return (1.0 + y_min) / 2, float(radius.max()), (1.0 - y_min) / 2


def deform(unit: np.ndarray, part: RoundedSolid, scale_in: float) -> np.ndarray:
    """Map unit-sphere points onto the part's surface (centred on its bounding box), in inches."""
    v = np.array(unit, dtype=float)
    if part.flat_bottom:
        v[..., 1] = np.maximum(v[..., 1], -FLAT_BOTTOM_CUT)
    # +taper widens the lower half and narrows the upper half
    v[..., 0] *= 1.0 - part.taper * v[..., 1]
    v[..., 2] *= 1.0 - part.taper * v[..., 1]
    y_mid, r_max, y_half = _normaliser(part)
    half = np.array([part.width, part.height, part.depth]) * scale_in / 2
    out = np.empty_like(v)
    out[..., 0] = v[..., 0] / r_max * half[0]
    out[..., 1] = (v[..., 1] - y_mid) / y_half * half[1]
    out[..., 2] = v[..., 2] / r_max * half[2]
    return out


def rounded_solid_mesh(part: RoundedSolid, scale_in: float) -> trimesh.Trimesh:
    """Mesh centred on its bounding box, sized width x height x depth."""
    unit = trimesh.creation.icosphere(subdivisions=SUBDIVISIONS, radius=1.0)
    return trimesh.Trimesh(vertices=deform(unit.vertices, part, scale_in), faces=unit.faces, process=False)

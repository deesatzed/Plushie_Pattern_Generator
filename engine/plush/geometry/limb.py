"""Limbs (arms, legs, tails, horns): a tapered tube along a bent centreline.

Local frame: the limb starts at the origin, where it is sewn on and left
open, grows along +y and bends toward +z.
"""

from __future__ import annotations

import numpy as np
import trimesh

from plush.parts import EndShape, Limb

RINGS = 40
SEGMENTS = 48
CAP_RINGS = 12
POINT_LENGTH = 1.5  # length of a pointed end, in end radii


def limb_centreline(part: Limb, scale_in: float, n: int = RINGS) -> tuple[np.ndarray, np.ndarray]:
    """Points and unit tangents along the centreline, from start to end."""
    length = part.length * scale_in
    t = np.linspace(0.0, 1.0, n)
    theta = np.radians(part.bend_deg)
    zeros = np.zeros(n)
    if theta < 1e-9:
        points = np.column_stack([zeros, length * t, zeros])
        tangents = np.tile([0.0, 1.0, 0.0], (n, 1))
    else:
        radius = length / theta
        a = theta * t
        points = np.column_stack([zeros, radius * np.sin(a), radius * (1 - np.cos(a))])
        tangents = np.column_stack([zeros, np.cos(a), np.sin(a)])
    return points, tangents


def ring_frame(tangent: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two unit axes across the tube at a ring; angle 0 points along local +x."""
    x_axis = np.array([1.0, 0.0, 0.0])
    return x_axis, np.cross(x_axis, tangent)


def ring_points(centre: np.ndarray, tangent: np.ndarray, radius: float, phi: np.ndarray) -> np.ndarray:
    x_axis, b_axis = ring_frame(tangent)
    return centre + radius * (np.outer(np.cos(phi), x_axis) + np.outer(np.sin(phi), b_axis))


def limb_rings(part: Limb, scale_in: float) -> tuple[list[tuple[np.ndarray, np.ndarray, float]], np.ndarray | None]:
    """(centre, tangent, radius) of every ring from the open start to the end cap, and the tip.

    The tip is None for a flat sole, whose last ring is closed by a flat disc.
    """
    points, tangents = limb_centreline(part, scale_in)
    t = np.linspace(0.0, 1.0, len(points))
    radii = ((1 - t) * part.start_thickness + t * part.end_thickness) / 2 * scale_in
    rings = [(p, d, float(r)) for p, d, r in zip(points, tangents, radii)]
    end, tan, r_end = points[-1], tangents[-1], float(radii[-1])
    if part.end_shape is EndShape.ROUND:
        alpha = np.linspace(0, np.pi / 2, CAP_RINGS + 1)[1:-1]
        rings += [(end + tan * r_end * np.sin(a), tan, r_end * np.cos(a)) for a in alpha]
        return rings, end + tan * r_end
    if part.end_shape is EndShape.POINT:
        k = np.arange(1, CAP_RINGS) / CAP_RINGS
        rings += [(end + tan * POINT_LENGTH * r_end * f, tan, r_end * (1 - f)) for f in k]
        return rings, end + tan * POINT_LENGTH * r_end
    return rings, None


def limb_mesh(part: Limb, scale_in: float) -> trimesh.Trimesh:
    rings, tip = limb_rings(part, scale_in)
    if tip is None:  # flat sole: a disc closing the end
        tip = rings[-1][0]
    phi = np.linspace(0.0, 2 * np.pi, SEGMENTS, endpoint=False)
    vertices = np.vstack([ring_points(c, d, r, phi) for c, d, r in rings] + [tip[None, :]])
    s = SEGMENTS
    faces = []
    for i in range(len(rings) - 1):
        for j in range(s):
            a, b = i * s + j, i * s + (j + 1) % s
            c, d = a + s, b + s
            faces += [[a, c, b], [b, c, d]]
    tip_index = len(vertices) - 1
    last = (len(rings) - 1) * s
    faces += [[last + j, tip_index, last + (j + 1) % s] for j in range(s)]
    return trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=False)

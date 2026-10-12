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


def _ring(centre: np.ndarray, tangent: np.ndarray, radius: float) -> np.ndarray:
    x_axis = np.array([1.0, 0.0, 0.0])
    b_axis = np.cross(x_axis, tangent)
    phi = np.linspace(0.0, 2 * np.pi, SEGMENTS, endpoint=False)
    return centre + radius * (np.outer(np.cos(phi), x_axis) + np.outer(np.sin(phi), b_axis))


def limb_mesh(part: Limb, scale_in: float) -> trimesh.Trimesh:
    points, tangents = limb_centreline(part, scale_in)
    t = np.linspace(0.0, 1.0, len(points))
    radii = ((1 - t) * part.start_thickness + t * part.end_thickness) / 2 * scale_in
    rings = [_ring(p, d, r) for p, d, r in zip(points, tangents, radii)]

    end, tan, r_end = points[-1], tangents[-1], radii[-1]
    if part.end_shape is EndShape.ROUND:
        alpha = np.linspace(0, np.pi / 2, CAP_RINGS + 1)[1:-1]
        rings += [_ring(end + tan * r_end * np.sin(a), tan, r_end * np.cos(a)) for a in alpha]
        tip = end + tan * r_end
    elif part.end_shape is EndShape.POINT:
        k = np.arange(1, CAP_RINGS) / CAP_RINGS
        rings += [_ring(end + tan * POINT_LENGTH * r_end * f, tan, r_end * (1 - f)) for f in k]
        tip = end + tan * POINT_LENGTH * r_end
    else:  # flat sole: a disc closing the end
        tip = end

    vertices = np.vstack(rings + [tip[None, :]])
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

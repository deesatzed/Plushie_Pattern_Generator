"""Flat parts (ears, wings, fins): an outline sewn as a lightly stuffed pillow.

Local frame: the straight base edge lies on y = 0 (where the part is sewn
on), the tip points along +y and the front face looks along +z.
"""

from __future__ import annotations

import numpy as np
import shapely
import trimesh
from scipy.spatial import Delaunay
from shapely.geometry import Polygon

from plush.parts import FlatPart, Outline

PROFILE_SAMPLES = 96
GRID = 24


def _half_width(outline: Outline, t: np.ndarray) -> np.ndarray:
    """Half-width at height fraction t (0 = base, 1 = tip), as a fraction of half the width."""
    if outline is Outline.ROUND:
        return np.sqrt(np.clip(1 - t**2, 0, None))
    if outline is Outline.POINTED:
        return 1 - t
    if outline is Outline.LONG_OVAL:
        return np.clip(1 - t**4, 0, None) ** 0.25
    return np.clip(np.sin(np.pi * (0.25 + 0.75 * t)), 0, None)  # leaf


def outline_polygon(part: FlatPart, scale_in: float) -> Polygon:
    w, h = part.width * scale_in, part.height * scale_in
    t = np.sin(np.linspace(0, np.pi / 2, PROFILE_SAMPLES))  # dense near the tip
    hw = _half_width(part.outline, t) * w / 2
    right = np.column_stack([hw, t * h])
    left = np.column_stack([-hw[-2::-1], t[-2::-1] * h])
    return Polygon(np.vstack([right, left]))


def flat_part_mesh(part: FlatPart, scale_in: float) -> trimesh.Trimesh:
    poly = outline_polygon(part, scale_in)
    w, h = part.width * scale_in, part.height * scale_in
    boundary = np.asarray(poly.exterior.coords)[:-1]
    gx, gy = np.meshgrid(np.linspace(-w / 2, w / 2, GRID), np.linspace(0, h, GRID))
    grid = np.column_stack([gx.ravel(), gy.ravel()])
    inner = poly.buffer(-0.02 * min(w, h))
    grid = grid[shapely.contains_xy(inner, grid[:, 0], grid[:, 1])]
    pts = np.vstack([boundary, grid])

    tri = Delaunay(pts).simplices
    centroids = pts[tri].mean(axis=1)
    tri = tri[shapely.contains_xy(poly, centroids[:, 0], centroids[:, 1])]
    e1, e2 = pts[tri[:, 1]] - pts[tri[:, 0]], pts[tri[:, 2]] - pts[tri[:, 0]]
    flip = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0
    tri[flip] = tri[flip][:, ::-1]  # all counter-clockwise, so the front faces +z

    dist = shapely.distance(poly.exterior, shapely.points(pts))
    thickness = part.puffiness * 0.5 * min(w, h)
    puff = thickness / 2 * np.sin(np.pi / 2 * dist / dist.max())
    cup = part.cupping * (w / 4) * (pts[:, 0] / (w / 2)) ** 2

    n, nb = len(pts), len(boundary)
    top = np.column_stack([pts, cup + puff])
    back = np.column_stack([pts[nb:], cup[nb:] - puff[nb:]])
    vertices = np.vstack([top, back])
    back_index = np.concatenate([np.arange(nb), n + np.arange(n - nb)])  # rim shared
    faces = np.vstack([tri, back_index[tri][:, ::-1]])
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

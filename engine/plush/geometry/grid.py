"""Triangulated grids of surface points, shared by the panel builders."""

from __future__ import annotations

import numpy as np


def grid_mesh(points: np.ndarray, collapse_top: bool, collapse_bottom: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Triangulate a (rows, cols, 3) grid; a collapsed row becomes a single tip vertex."""
    rows, cols = points.shape[:2]
    index = np.zeros((rows, cols), dtype=np.int64)
    vertices = []
    for j in range(rows):
        for i in range(cols):
            tip = (j == 0 and collapse_top) or (j == rows - 1 and collapse_bottom)
            if tip and i > 0:
                index[j, i] = index[j, 0]
                continue
            index[j, i] = len(vertices)
            vertices.append(points[j, i])
    faces = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a, b, c, d = index[j, i], index[j, i + 1], index[j + 1, i], index[j + 1, i + 1]
            faces += [t for t in ([a, c, b], [b, c, d]) if len(set(t)) == 3]
    return np.array(vertices), np.array(faces, dtype=np.int64), index

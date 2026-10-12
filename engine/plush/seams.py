"""Seam measurements: side lengths, matching notches."""

from __future__ import annotations

import numpy as np

from plush.panels import PanelSet, Seam


def side_points(ps: PanelSet, side: tuple[str, int]) -> np.ndarray:
    """Flattened points along one side of a seam, in order."""
    panel, edge = side
    p = ps.panels[panel]
    return p.uv[p.edges[edge].vertices]


def side_points_3d(ps: PanelSet, side: tuple[str, int]) -> np.ndarray:
    panel, edge = side
    p = ps.panels[panel]
    return p.vertices[p.edges[edge].vertices]


def polyline_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def side_lengths(ps: PanelSet, seam: Seam) -> list[float]:
    return [polyline_length(side_points(ps, s)) for s in seam.sides]


def point_at_fraction(points: np.ndarray, fractions: np.ndarray) -> np.ndarray:
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.r_[0.0, np.cumsum(seg)]
    target = np.asarray(fractions) * s[-1]
    return np.column_stack([np.interp(target, s, points[:, k]) for k in range(points.shape[1])])


def notches(ps: PanelSet, seam: Seam, spacing_in: float) -> list[np.ndarray]:
    """Matching notch points on each side, evenly spaced no more than spacing_in apart."""
    length = float(np.mean(side_lengths(ps, seam)))
    intervals = max(1, int(np.ceil(length / spacing_in)))
    fractions = np.arange(1, intervals) / intervals
    return [point_at_fraction(side_points(ps, s), fractions) for s in seam.sides]

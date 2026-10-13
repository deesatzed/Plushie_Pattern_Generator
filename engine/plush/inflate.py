"""Stuffing simulation: sewn panels inflated by internal pressure.

Fabric is modelled as a tension-field membrane (as in Skouras et al.,
"Designing Inflatable Structures", 2014): each triangle resists stretching
beyond its flat pattern shape in any direction, but wrinkles freely when
compressed. Inflation minimises stretch energy minus pressure x volume.
Validated against the Mylar balloon (two discs sewn at the rim).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh
from scipy.optimize import minimize

from plush.panels import Panel, weld

STIFFNESS = (1e2, 1e3, 1e4)  # fabric stiffness per unit pressure, relative to part size; raised in stages


@dataclass
class Membrane:
    positions: np.ndarray  # (n, 3) start positions: the target surface
    faces: np.ndarray  # (t, 3) welded across seams
    rest_inverse: np.ndarray  # (t, 2, 2) inverse of each triangle's flat edge matrix
    rest_area: np.ndarray  # (t,)
    fixed: np.ndarray  # (n,) bool: vertices held in place (where the part is sewn on)
    index: np.ndarray  # membrane vertex for each panel vertex, panels taken in order


@dataclass
class Inflated:
    positions: np.ndarray
    iterations: int
    max_stretch: float  # largest principal stretch beyond the flat pattern, as a fraction
    faces: np.ndarray | None = None  # the welded faces the positions belong to


def membrane_from_panels(panels: list[Panel]) -> Membrane:
    """Weld a part's panels along their seams. Attachment edges are held fixed."""
    V, F, welded = weld(panels)
    starts = np.cumsum([0] + [len(p.vertices) for p in panels])
    fixed = np.zeros(len(V), bool)
    for p, start in zip(panels, starts):
        for e in p.edges:
            if e.kind == "attachment":
                fixed[welded[e.vertices + start]] = True
    raw = np.vstack([p.faces + start for p, start in zip(panels, starts)])
    U = np.vstack([p.uv for p in panels])
    u0, u1, u2 = U[raw[:, 0]], U[raw[:, 1]], U[raw[:, 2]]
    rest = np.stack([u1 - u0, u2 - u0], axis=2)
    return Membrane(V, F, np.linalg.inv(rest), np.abs(np.linalg.det(rest)) / 2, fixed, welded)


def _stretch_energy(X, m: Membrane, k: float):
    """Energy and per-triangle gradient (t, 3, 2) of stretch beyond the flat shape."""
    F = m.faces
    x0, x1, x2 = X[F[:, 0]], X[F[:, 1]], X[F[:, 2]]
    Fd = np.stack([x1 - x0, x2 - x0], axis=2) @ m.rest_inverse  # deformation gradient (t, 3, 2)
    C = np.transpose(Fd, (0, 2, 1)) @ Fd
    a, b, d = C[:, 0, 0], C[:, 0, 1], C[:, 1, 1]
    centre, radius = (a + d) / 2, np.sqrt(((a - d) / 2) ** 2 + b**2)
    stretch = np.sqrt(np.stack([centre + radius, np.maximum(centre - radius, 0.0)], axis=1))
    over = np.maximum(stretch - 1.0, 0.0)
    energy = float(np.sum(m.rest_area * k * (over**2).sum(axis=1)))

    v1 = np.stack([b, stretch[:, 0] ** 2 - a], axis=1)
    other = np.stack([stretch[:, 0] ** 2 - d, b], axis=1)
    small = np.linalg.norm(v1, axis=1) < 1e-14
    v1[small] = other[small]
    norm = np.linalg.norm(v1, axis=1)
    v1[norm < 1e-14] = [1.0, 0.0]
    v1 /= np.linalg.norm(v1, axis=1)[:, None]
    v2 = np.stack([-v1[:, 1], v1[:, 0]], axis=1)
    grad = np.zeros_like(Fd)
    for i, v in ((0, v1), (1, v2)):
        coef = np.where(stretch[:, i] > 1e-14, 2 * m.rest_area * k * over[:, i] / np.maximum(stretch[:, i], 1e-14), 0.0)
        Fv = np.einsum("tij,tj->ti", Fd, v)
        grad += coef[:, None, None] * np.einsum("ti,tj->tij", Fv, v)
    return energy, grad @ np.transpose(m.rest_inverse, (0, 2, 1)), float(over.max())


def _scatter(F: np.ndarray, per_corner: list[np.ndarray], n: int) -> np.ndarray:
    g = np.zeros((n, 3))
    for corner, values in enumerate(per_corner):
        for axis in range(3):
            g[:, axis] += np.bincount(F[:, corner], weights=values[:, axis], minlength=n)
    return g


def inflate(m: Membrane, stiffness: tuple[float, ...] = STIFFNESS) -> Inflated:
    X = m.positions.copy()
    free = ~m.fixed
    size = float(np.ptp(X, axis=0).max())
    iterations, n, F = 0, len(X), m.faces
    for K in stiffness:
        k = K / size

        def objective(z):
            Xc = X.copy()
            Xc[free] = z.reshape(-1, 3)
            energy, dDs, _ = _stretch_energy(Xc, m, k)
            a, b, c = Xc[F[:, 0]], Xc[F[:, 1]], Xc[F[:, 2]]
            volume = np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6
            g = _scatter(F, [-dDs[:, :, 0] - dDs[:, :, 1] - np.cross(b, c) / 6,
                             dDs[:, :, 0] - np.cross(c, a) / 6,
                             dDs[:, :, 1] - np.cross(a, b) / 6], n)
            return energy - volume, g[free].ravel()

        result = minimize(objective, X[free].ravel(), jac=True, method="L-BFGS-B",
                          options={"maxiter": 30000, "maxcor": 30, "gtol": 1e-10, "ftol": 1e-15})
        X[free] = result.x.reshape(-1, 3)
        iterations += int(result.nit)
    _, _, worst = _stretch_energy(X, m, 1.0)
    return Inflated(X, iterations, worst, m.faces)


def deviation(inflated: np.ndarray, target: trimesh.Trimesh) -> np.ndarray:
    """Signed distance of each inflated vertex from the target surface (+ = outside)."""
    closest, distance, tri = trimesh.proximity.closest_point(target, inflated)
    side = np.sign(np.einsum("ij,ij->i", inflated - closest, target.face_normals[tri]))
    return side * distance

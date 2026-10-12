"""Flatten 3D panels onto the plane with as little stretch as possible.

All panels of one part are flattened together. Each starts from a
least-squares conformal map (libigl); then a sparse Levenberg-Marquardt
solve moves every flat edge toward its 3D length, while holding each pair
of matching seam edges to the same flat length. Seam sides may ease a
little along with the fabric, but they always match each other, which is
what sewing needs. Stretch is reported per mesh edge.
"""

from __future__ import annotations

from dataclasses import dataclass

import igl
import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import spsolve

SEAM_WEIGHT = 100.0
MAX_ITERATIONS = 200


@dataclass
class Flattened:
    uv: np.ndarray  # (n, 2) inches
    edges: np.ndarray  # (m, 2) vertex indices
    stretch: np.ndarray  # (m,) |flat length / 3D length - 1|


@dataclass
class SeamLink:
    """Two chains of vertices (panel index, vertex indices) that are sewn together, in matching order."""

    a_panel: int
    a_chain: np.ndarray
    b_panel: int
    b_chain: np.ndarray


def flatten(vertices: np.ndarray, faces: np.ndarray) -> Flattened:
    """Flatten a single panel."""
    return flatten_together([(vertices, faces)], [])[0]


def flatten_together(
    meshes: list[tuple[np.ndarray, np.ndarray]],
    links: list[SeamLink],
    lengths: list[np.ndarray] | None = None,
) -> list[Flattened]:
    """Flatten several panels at once. `lengths` (optional, per panel, in igl.edges order) replaces
    the 3D edge lengths as the target, which the stuffing correction uses."""
    starts, x0, edge_sets, targets = [], [], [], []
    offset = 0
    for i, (V, F) in enumerate(meshes):
        V, F = np.asarray(V, float), np.asarray(F, np.int64)
        E = igl.edges(F)
        L = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1) if lengths is None else np.asarray(lengths[i], float)
        x0.append(_initial_uv(V, F, E, L))
        starts.append(offset)
        edge_sets.append(E + offset)
        targets.append(L)
        offset += len(V)

    E_all = np.vstack(edge_sets)
    L_all = np.concatenate(targets)
    pairs_a, pairs_b, pair_len = [], [], []
    for link in links:
        ga, gb = link.a_chain + starts[link.a_panel], link.b_chain + starts[link.b_panel]
        pairs_a.append(np.column_stack([ga[:-1], ga[1:]]))
        pairs_b.append(np.column_stack([gb[:-1], gb[1:]]))
        V = np.asarray(meshes[link.a_panel][0], float)
        pair_len.append(np.linalg.norm(V[link.a_chain[1:]] - V[link.a_chain[:-1]], axis=1))
    A = np.vstack(pairs_a) if pairs_a else np.zeros((0, 2), np.int64)
    B = np.vstack(pairs_b) if pairs_b else np.zeros((0, 2), np.int64)
    P = np.concatenate(pair_len) if pair_len else np.zeros(0)

    x = _solve(np.concatenate([u.ravel() for u in x0]), E_all, L_all, A, B, P)
    uv_all = x.reshape(-1, 2)

    out = []
    for (V, F), start, E, L in zip(meshes, starts, edge_sets, targets):
        uv = uv_all[start : start + len(V)].copy()
        F = np.asarray(F, np.int64)
        if _signed_area(uv, F) < 0:  # keep the outside of the fabric facing up
            uv[:, 0] *= -1
        local_E = E - start
        flat = np.linalg.norm(uv[local_E[:, 0]] - uv[local_E[:, 1]], axis=1)
        out.append(Flattened(uv=uv, edges=local_E, stretch=np.abs(flat / L - 1)))
    return out


def _initial_uv(V: np.ndarray, F: np.ndarray, E: np.ndarray, L: np.ndarray) -> np.ndarray:
    if np.ptp(V, axis=0).min() < 1e-12:  # already flat: use the plane's own coordinates
        keep = np.sort(np.argsort(np.ptp(V, axis=0))[1:])
        return V[:, keep]
    loop = igl.boundary_loop(F)
    pins = np.array([loop[0], loop[len(loop) // 2]], dtype=np.int64)
    uv, _ = igl.lscm(V, F, pins, np.array([[0.0, 0.0], [1.0, 0.0]]))
    flat = np.linalg.norm(uv[E[:, 0]] - uv[E[:, 1]], axis=1)
    return uv * (L @ flat) / (flat @ flat)


def _signed_area(uv: np.ndarray, F: np.ndarray) -> float:
    a, b, c = uv[F[:, 0]], uv[F[:, 1]], uv[F[:, 2]]
    return float(np.sum((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])))


def _solve(x, E, L, A, B, P) -> np.ndarray:
    """Least squares: edges toward 3D length; matching seam edges toward equal flat length."""
    m, k, n = len(E), len(A), len(x)

    def cols(idx):
        return np.column_stack([2 * idx[:, 0], 2 * idx[:, 0] + 1, 2 * idx[:, 1], 2 * idx[:, 1] + 1])

    rows_e = np.repeat(np.arange(m), 4)
    cols_e = cols(E).ravel()
    rows_s = np.repeat(np.arange(m, m + k), 8)
    cols_s = np.column_stack([cols(A), cols(B)]).ravel()

    def evaluate(x):
        X = x.reshape(-1, 2)
        de, da, db = X[E[:, 0]] - X[E[:, 1]], X[A[:, 0]] - X[A[:, 1]], X[B[:, 0]] - X[B[:, 1]]
        le, la, lb = (np.linalg.norm(d, axis=1) for d in (de, da, db))
        r = np.concatenate([(le - L) / L, SEAM_WEIGHT * (la - lb) / P])
        return r, (de, da, db, le, la, lb)

    def jacobian(parts):
        de, da, db, le, la, lb = parts
        ge = de / (L * le)[:, None]
        ga = SEAM_WEIGHT * da / (P * la)[:, None]
        gb = -SEAM_WEIGHT * db / (P * lb)[:, None]
        data = np.concatenate([np.column_stack([ge, -ge]).ravel(), np.column_stack([ga, -ga, gb, -gb]).ravel()])
        return csr_matrix((data, (np.r_[rows_e, rows_s], np.r_[cols_e, cols_s])), shape=(m + k, n))

    r, parts = evaluate(x)
    cost, damping = r @ r, 1e-3
    for _ in range(MAX_ITERATIONS):
        J = jacobian(parts)
        H, g = (J.T @ J).tocsc(), -(J.T @ r)
        while damping <= 1e8:
            step = spsolve(H + damping * identity(n, format="csc"), g)
            r_new, parts_new = evaluate(x + step)
            new_cost = r_new @ r_new
            if new_cost < cost:
                break
            damping *= 4
        if damping > 1e8:
            break
        improvement = cost - new_cost
        x, r, parts, cost = x + step, r_new, parts_new, new_cost
        damping = max(damping / 3, 1e-12)
        if improvement < 1e-14 * max(cost, 1e-30):
            break
    return x

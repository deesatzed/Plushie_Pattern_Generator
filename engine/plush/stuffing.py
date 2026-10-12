"""Stuffing correction: adjust the flat panels until the stuffed part matches its 3D model."""

from __future__ import annotations

from dataclasses import dataclass, field

import igl
import numpy as np
import trimesh

from plush.flatten import SeamLink, flatten_together
from plush.inflate import Inflated, deviation, inflate, membrane_from_panels
from plush.panels import Panel

MAX_ROUNDS = 4
STEP = 1.0  # fraction of the measured bulge removed per round


@dataclass
class StuffingResult:
    panels: list[Panel]
    inflated: Inflated
    mean_deviation: float  # fraction of the part's largest dimension
    worst_deviation: float
    converged: bool
    history: list[tuple[float, float]] = field(default_factory=list)  # (mean, worst) per round


def _target(panels: list[Panel]) -> trimesh.Trimesh:
    m = membrane_from_panels(panels)
    return trimesh.Trimesh(m.positions, m.faces, process=False)


def _measure(panels: list[Panel], target: trimesh.Trimesh, size: float):
    inflated = inflate(membrane_from_panels(panels))
    signed = deviation(inflated.positions, target)
    return inflated, signed, float(np.abs(signed).mean() / size), float(np.abs(signed).max() / size)


def stuff(panels: list[Panel], mean_limit: float, worst_limit: float, rounds: int = MAX_ROUNDS) -> StuffingResult:
    """Simulate stuffing; while the result is off the model, shrink fabric where it bulges and grow it where it sinks."""
    target = _target(panels)
    size = float(np.ptp(target.vertices, axis=0).max())
    centre = target.vertices.mean(axis=0)
    inflated, signed, mean, worst = _measure(panels, target, size)
    history = [(mean, worst)]
    best = (panels, inflated, mean, worst)

    for _ in range(rounds):
        if mean <= mean_limit and worst <= worst_limit:
            break
        panels = _adjusted(best[0], best[1], target, centre)
        inflated, signed, mean, worst = _measure(panels, target, size)
        history.append((mean, worst))
        if mean < best[2]:
            best = (panels, inflated, mean, worst)

    panels, inflated, mean, worst = best
    return StuffingResult(panels, inflated, mean, worst, mean <= mean_limit and worst <= worst_limit, history)


def _adjusted(panels: list[Panel], inflated: Inflated, target: trimesh.Trimesh, centre: np.ndarray) -> list[Panel]:
    """Re-flatten with each edge scaled by how far the stuffed surface bulged (or sank) near it."""
    m = membrane_from_panels(panels)
    signed = deviation(inflated.positions, target)
    radius = np.linalg.norm(m.positions - centre, axis=1)
    factor = 1.0 - STEP * signed / np.maximum(radius, 1e-9)  # per welded vertex

    starts = np.cumsum([0] + [len(p.vertices) for p in panels])
    welded = m.index
    meshes, lengths, new_panels = [], [], []
    for i, p in enumerate(panels):
        E = igl.edges(p.faces)
        flat = np.linalg.norm(p.uv[E[:, 0]] - p.uv[E[:, 1]], axis=1)
        f = factor[welded[starts[i] + E[:, 0]]] * factor[welded[starts[i] + E[:, 1]]]
        meshes.append((p.vertices, p.faces))
        lengths.append(flat * np.sqrt(f))
    chains: dict[str, list[tuple[int, np.ndarray]]] = {}
    for i, p in enumerate(panels):
        for e in p.edges:
            if e.kind == "seam":
                chains.setdefault(e.seam, []).append((i, e.vertices))
    links = [SeamLink(a[0], a[1], b[0], b[1]) for a, b in (c for c in chains.values() if len(c) == 2)]
    flats = flatten_together(meshes, links, lengths=lengths)
    for p, flat in zip(panels, flats):
        # stretch keeps meaning "how far the fabric stretches to match the model", from the first flattening
        new_panels.append(Panel(p.name, p.part, p.colour, p.vertices, p.faces, flat.uv - flat.uv.mean(axis=0),
                                p.stretch, p.edges, p.cut, p.mirrored, p.upright))
    return new_panels

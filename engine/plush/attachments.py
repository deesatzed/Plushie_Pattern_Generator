"""Where each part is sewn onto its parent: placement marks and matching notches on both pieces.

The child's opening is found in 3D: a limb's open end, a flat part's base, or,
for a rounded part such as a head, the ring where it sinks into its parent
(it is ladder-stitched on there). Each notch is one 3D point on that opening,
projected onto both the child's and the parent's pieces, so the marks meet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from plush.geometry.assemble import Placed
from plush.geometry.rounded_solid import deform, unit_direction
from plush.panels import PanelSet, closed_surface
from plush.parts import Kit, RoundedSolid

RING_NOTCHES = (0.0, 0.25, 0.5, 0.75)  # quarter marks around a closed opening
LINE_NOTCHES = (0.5,)  # the middle of a flat part's base
SAMPLES = 48
MERIDIAN_SAMPLES = 241
SPACING_IN = 0.02


@dataclass
class AttachmentMark:
    child: str  # placed name, e.g. "arm_left"
    parent: str  # placed name of the parent
    outline: list[tuple[str, np.ndarray]]  # (parent panel, flat polyline) where the child is sewn on
    child_outline: list[tuple[str, np.ndarray]]  # (child panel, flat polyline) of the same line on the child
    parent_notches: list[tuple[str, np.ndarray]]  # (parent panel, flat point)
    child_notches: list[tuple[str, np.ndarray]]  # (child panel, flat point), matching parent_notches in order
    gap_in: float  # largest distance from the child's opening to the parent's surface


class _Surface:
    """A part's 3D panels, for projecting points onto them and reading the flat position."""

    def __init__(self, ps: PanelSet, part_id: str):
        self.panels = [p for p in ps.panels.values() if p.part == part_id]
        if self.panels[0].name.endswith(("/front", "/back")):
            self.panels = self.panels[:1]  # front and back lie on top of each other; marks go on the front
        vstart = np.cumsum([0] + [len(p.vertices) for p in self.panels])
        self.face_start = np.cumsum([0] + [len(p.faces) for p in self.panels])
        self.mesh = trimesh.Trimesh(np.vstack([p.vertices for p in self.panels]),
                                    np.vstack([p.faces + s for p, s in zip(self.panels, vstart[:-1])]),
                                    process=False)

    def flat(self, points: np.ndarray) -> tuple[list[tuple[str, np.ndarray]], np.ndarray]:
        closest, distance, tri = trimesh.proximity.closest_point(self.mesh, points)
        out = []
        for c, t in zip(closest, tri):
            k = int(np.searchsorted(self.face_start, t, side="right") - 1)
            p = self.panels[k]
            corners = p.faces[t - self.face_start[k]]
            w = trimesh.triangles.points_to_barycentric(p.vertices[corners][None], c[None])[0]
            out.append((p.name, w @ p.uv[corners]))
        return out, distance


def _opening(ps: PanelSet, part, child: Placed, parent: Placed) -> tuple[np.ndarray, bool]:
    """Points along the child's opening in its own frame, and whether the opening is a closed ring."""
    if isinstance(part, RoundedSolid):
        # the line where the part's surface enters its parent: walk down each meridian
        theta = np.linspace(0.0, np.pi, MERIDIAN_SAMPLES)
        phi = np.linspace(0.0, 2 * np.pi, SAMPLES, endpoint=False)
        local = deform(unit_direction(theta[:, None], phi[None, :]), part, child.scale_in)
        surface = closed_surface([p for p in ps.panels.values() if p.part == parent.part_id])
        in_parent = (local.reshape(-1, 3) @ child.rotation.T + child.translation - parent.translation) @ parent.rotation
        depth = trimesh.proximity.signed_distance(surface, in_parent).reshape(len(theta), len(phi))
        ring = []
        for i in range(len(phi)):
            # first change between outside and inside, whichever end of the part is in the parent
            crossing = np.nonzero(np.sign(depth[:, i]) != np.sign(depth[0, i]))[0]
            if len(crossing) == 0:
                raise ValueError(f"part {part.id!r} does not meet its parent {parent.part_id!r}")
            j = int(crossing[0])
            a, b = depth[j - 1, i], depth[j, i]
            t = a / (a - b)
            ring.append(local[j - 1, i] + t * (local[j, i] - local[j - 1, i]))
        return np.array(ring), True
    panels = [p for p in ps.panels.values() if p.part == part.id]
    runs = [(p, e.vertices) for p in panels for e in p.edges if e.kind == "attachment"]
    if part.kind == "flat_part":
        a, b = runs[0][0].vertices[runs[0][1][0]], runs[0][0].vertices[runs[0][1][-1]]
        return a + np.linspace(0, 1, 9)[:, None] * (b - a), False
    pts = []
    for p, chain in runs:
        for v in chain:
            if not pts or not np.allclose(p.vertices[v], pts[-1]):
                pts.append(p.vertices[v])
    if np.allclose(pts[0], pts[-1]):
        pts.pop()
    return np.array(pts), True


def _point_at(points: np.ndarray, ring: bool, f: float) -> np.ndarray:
    path = np.vstack([points, points[:1]]) if ring else points
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    return np.array([np.interp(f * s[-1], s, path[:, k]) for k in range(3)])


def _dense(points: np.ndarray, ring: bool) -> np.ndarray:
    """The opening resampled every SPACING_IN or so, so the bit of line lost where it crosses
    from one piece to the next is negligible."""
    path = np.vstack([points, points[:1]]) if ring else points
    length = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
    count = max(len(path), int(np.ceil(length / SPACING_IN)) + 1)
    return np.array([_point_at(points, ring, f) for f in np.linspace(0.0, 1.0, count)])


def _runs(mapped: list[tuple[str, np.ndarray]]) -> list[tuple[str, np.ndarray]]:
    """Split a mapped polyline into one run per panel it crosses."""
    runs, name, run = [], None, []
    for panel, uv in mapped:
        if panel != name and run:
            runs.append((name, np.array(run)))
            run = []
        name = panel
        run.append(uv)
    if run:
        runs.append((name, np.array(run)))
    return runs


def attachment_marks(kit: Kit, ps: PanelSet, placed: dict[str, Placed]) -> list[AttachmentMark]:
    by_id = {p.id: p for p in kit.parts}
    marks = []
    for name, child in placed.items():
        if child.parent is None or child.kind == "surface_feature":
            continue
        parent = placed[child.parent]
        parent_surface, child_surface = _Surface(ps, parent.part_id), _Surface(ps, child.part_id)
        points, ring = _opening(ps, by_id[child.part_id], child, parent)

        def to_parent(p):
            return (p @ child.rotation.T + child.translation - parent.translation) @ parent.rotation

        path = _dense(points, ring)
        mapped, distance = parent_surface.flat(to_parent(path))
        on_child, _ = child_surface.flat(path)
        notches = np.array([_point_at(points, ring, f) for f in (RING_NOTCHES if ring else LINE_NOTCHES)])
        parent_notches, _ = parent_surface.flat(to_parent(notches))
        child_notches, _ = child_surface.flat(notches)
        marks.append(AttachmentMark(name, child.parent, _runs(mapped), _runs(on_child), parent_notches,
                                    child_notches, float(distance.max())))
    return marks

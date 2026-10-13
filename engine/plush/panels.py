"""Sewing panels: each part's surface cut along seams into flat pieces of fabric.

Constructions (version 1, low-stretch fabrics):
- rounded solid: gores from top to bottom, plus a flat base if the part has a flat bottom;
- limb: strips along its length (one strip = a tube with one seam), plus a sole for a flat end;
- flat part: a front and a back piece cut from the outline.
The engine uses the fewest gores or strips whose panels flatten within the
stretch limit. Surface features become templates in a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import shapely
import trimesh
from scipy.spatial import Delaunay
from shapely.geometry import Polygon

from plush.flatten import SeamLink, flatten_together
from plush.geometry.assemble import Placed
from plush.geometry.flat_part import outline_triangulation
from plush.geometry.grid import grid_mesh
from plush.geometry.limb import RINGS as RINGS_IN_TUBE
from plush.geometry.limb import limb_rings, ring_frame, ring_points, tube_points
from plush.geometry.rounded_solid import bottom_theta, deform, unit_direction
from plush.parts import FlatPart, Kit, Limb, RoundedSolid
from plush.settings import Settings

ALONG = 40  # grid rows from top to bottom of a gore
AROUND = 48  # grid columns around the whole part
MAX_PANELS = 12
FIRST_TRY = 8
GAP = (1 / 3, 2 / 3)  # the middle third of the back seam is left open for turning and stuffing
TRIM_BACK = 1.0  # how far (in limb lengths) the tube is extended back into its parent when trimming
TRIM_SAMPLES = 161


class PanelError(ValueError):
    """No construction of a part meets the stretch limit."""


@dataclass
class Edge:
    kind: Literal["seam", "attachment"]
    seam: str | None
    vertices: np.ndarray  # panel vertex indices along the edge


@dataclass
class Panel:
    name: str
    part: str
    colour: str
    vertices: np.ndarray  # 3D, in the part's own frame, inches
    faces: np.ndarray
    uv: np.ndarray  # flattened, inches; the panel's top is toward +y
    stretch: np.ndarray  # per mesh edge
    edges: list[Edge]
    cut: int = 1  # how many to cut
    mirrored: int = 0  # how many of those are cut as a mirror image
    upright: tuple[np.ndarray, np.ndarray] | None = None  # (top, bottom) vertices; the flat piece stands top-up

    @property
    def max_stretch(self) -> float:
        return float(self.stretch.max()) if len(self.stretch) else 0.0


@dataclass
class Seam:
    id: str
    part: str
    sides: list[tuple[str, int]]  # (panel name, index into that panel's edges)
    gap: tuple[float, float] | None = None  # fraction of the seam left open


@dataclass
class PanelSet:
    panels: dict[str, Panel] = field(default_factory=dict)
    seams: dict[str, Seam] = field(default_factory=dict)

    def add(self, panels: list[Panel]) -> None:
        for p in panels:
            self.panels[p.name] = p
            for i, e in enumerate(p.edges):
                if e.kind == "seam":
                    self.seams.setdefault(e.seam, Seam(e.seam, p.part, [])).sides.append((p.name, i))


def _unflattened(name, part, colour, vertices, faces, edges, top=None, bottom=None) -> Panel:
    upright = None if top is None else (np.asarray(top), np.asarray(bottom))
    return Panel(name, part, colour, np.asarray(vertices, float), np.asarray(faces, np.int64),
                 np.zeros((len(vertices), 2)), np.zeros(0), edges, upright=upright)


def flatten_part(panels: list[Panel]) -> list[Panel]:
    """Flatten a part's panels together so the sides of every seam match, then stand each upright."""
    chains: dict[str, list[tuple[int, np.ndarray]]] = {}
    for i, p in enumerate(panels):
        for e in p.edges:
            if e.kind == "seam":
                chains.setdefault(e.seam, []).append((i, e.vertices))
    links = [SeamLink(a[0], a[1], b[0], b[1]) for a, b in (c for c in chains.values() if len(c) == 2)]
    flats = flatten_together([(p.vertices, p.faces) for p in panels], links)
    for p, flat in zip(panels, flats):
        uv = flat.uv - flat.uv.mean(axis=0)
        if p.upright is not None:
            top, bottom = p.upright
            up = uv[top].mean(axis=0) - uv[bottom].mean(axis=0)
            angle = np.pi / 2 - np.arctan2(up[1], up[0])
            c, s = np.cos(angle), np.sin(angle)
            uv = uv @ np.array([[c, s], [-s, c]])
        p.uv, p.stretch = uv, flat.stretch
    return panels


def _flat_disc(name, part, colour, ring: np.ndarray, origin, ax_u, ax_v, outward, edges_by_segment) -> Panel:
    """A flat panel (base or sole) whose outline is `ring`, lying in the plane origin + (u, v).

    Its triangles face `outward`, like every other panel.
    """
    flat_ring = np.column_stack([(ring - origin) @ ax_u, (ring - origin) @ ax_v])
    outline = Polygon(flat_ring)
    lo, hi = flat_ring.min(axis=0), flat_ring.max(axis=0)
    gu, gv = np.meshgrid(np.linspace(lo[0], hi[0], 16)[1:-1], np.linspace(lo[1], hi[1], 16)[1:-1])
    inner = np.column_stack([gu.ravel(), gv.ravel()])
    inside = outline.buffer(-0.02 * float(np.ptp(flat_ring, axis=0).min()))
    inner = inner[shapely.contains_xy(inside, inner[:, 0], inner[:, 1])]
    uv = np.vstack([flat_ring, inner])
    faces = Delaunay(uv).simplices
    centroids = uv[faces].mean(axis=1)
    faces = faces[shapely.contains_xy(outline, centroids[:, 0], centroids[:, 1])]
    e1, e2 = uv[faces[:, 1]] - uv[faces[:, 0]], uv[faces[:, 2]] - uv[faces[:, 0]]
    clockwise = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0
    faces[clockwise] = faces[clockwise][:, ::-1]  # all counter-clockwise in (u, v) ...
    if np.dot(np.cross(ax_u, ax_v), outward) < 0:
        faces = faces[:, ::-1]  # ... then turned to face outward
    vertices = origin + np.outer(uv[:, 0], ax_u) + np.outer(uv[:, 1], ax_v)
    return _unflattened(name, part, colour, vertices, faces, edges_by_segment)


def gore_panels(part: RoundedSolid, scale_in: float, n: int, name: str | None = None) -> list[Panel]:
    """n gores from the top down, seams on meridians starting at the back; plus a base if flat-bottomed."""
    name = name or part.id
    theta = np.linspace(0.0, bottom_theta(part), ALONG + 1)
    cols = max(4, int(np.ceil(AROUND / n)))
    seam_phi = np.pi + 2 * np.pi * np.arange(n + 1) / n
    panels, ring = [], []
    for k in range(n):
        phi = np.linspace(seam_phi[k], seam_phi[k + 1], cols + 1)
        grid = deform(unit_direction(theta[:, None], phi[None, :]), part, scale_in)
        V, F, idx = grid_mesh(grid, collapse_top=True, collapse_bottom=not part.flat_bottom)
        edges = [Edge("seam", f"{name}:m{k}", idx[:, 0]), Edge("seam", f"{name}:m{(k + 1) % n}", idx[:, -1])]
        if part.flat_bottom:
            edges.append(Edge("seam", f"{name}:b{k}", idx[-1, :]))
            ring.append(grid[-1, :-1])
        panels.append(_unflattened(f"{name}/gore{k + 1}", part.id, part.colour, V, F, edges, idx[0, :], idx[-1, :]))
    if part.flat_bottom:
        ring = np.vstack(ring)
        segs = [np.r_[np.arange(k * cols, (k + 1) * cols), ((k + 1) * cols) % len(ring)] for k in range(n)]
        base_edges = [Edge("seam", f"{name}:b{k}", segs[k]) for k in range(n)]
        origin = np.array([0.0, ring[0, 1], 0.0])
        panels.append(_flat_disc(f"{name}/base", part.id, part.colour, ring, origin,
                                 np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([0, -1.0, 0]),
                                 base_edges))
    return flatten_part(panels)


def trim_start(part: Limb, scale_in: float, phi: np.ndarray, inside) -> np.ndarray:
    """For each ring angle, the length fraction where the tube leaves its parent.

    `inside(points)` gives the signed distance of limb-frame points into the parent
    (positive inside). The tube is extended straight back into the parent and cut
    where it crosses the parent's surface, so the opening lies on that surface.
    """
    s = np.linspace(-TRIM_BACK, 1.0, TRIM_SAMPLES)
    pts = tube_points(part, scale_in, s[:, None], phi[None, :])  # (samples, cols, 3)
    depth = inside(pts.reshape(-1, 3)).reshape(len(s), len(phi))
    start = np.zeros(len(phi))
    for i in range(len(phi)):
        out = np.nonzero(depth[:, i] <= 0)[0]
        if len(out) == 0 or out[0] == 0:
            continue  # never inside, or already outside at the far end: keep the plain start
        j = out[0]
        a, b = depth[j - 1, i], depth[j, i]
        start[i] = s[j - 1] + (s[j] - s[j - 1]) * a / (a - b)
    return start


def strip_panels(part: Limb, scale_in: float, n: int, name: str | None = None, inside=None) -> list[Panel]:
    """n strips along the limb (n = 1 is a tube with one back seam), plus a sole for a flat end.

    With `inside` (see trim_start), the open end is cut where the limb meets its parent.
    """
    name = name or part.id
    rings, tip = limb_rings(part, scale_in)
    cols = max(4, int(np.ceil(AROUND / n)))
    seam_phi = -np.pi / 2 + 2 * np.pi * np.arange(n + 1) / n
    panels, end_ring = [], []
    for k in range(n):
        phi = np.linspace(seam_phi[k], seam_phi[k + 1], cols + 1)
        rows = [ring_points(c, d, r, phi) for c, d, r in rings]
        if inside is not None:
            start = trim_start(part, scale_in, phi, inside)
            t = np.linspace(0.0, 1.0, RINGS_IN_TUBE)
            tube = tube_points(part, scale_in, start[None, :] + (1 - start[None, :]) * t[:, None], phi[None, :])
            rows = list(tube) + rows[RINGS_IN_TUBE:]
        if tip is not None:
            rows.append(np.repeat(tip[None, :], cols + 1, axis=0))
        grid = np.stack(rows)
        V, F, idx = grid_mesh(grid, collapse_top=False, collapse_bottom=tip is not None)
        edges = [Edge("attachment", None, idx[0, :]),
                 Edge("seam", f"{name}:s{k}", idx[:, 0]),
                 Edge("seam", f"{name}:s{(k + 1) % n}", idx[:, -1])]
        if tip is None:
            edges.append(Edge("seam", f"{name}:sole{k}", idx[-1, :]))
            end_ring.append(grid[-1, :-1])
        panels.append(_unflattened(f"{name}/strip{k + 1}", part.id, part.colour, V, F, edges, idx[-1, :], idx[0, :]))
    if tip is None:
        ring = np.vstack(end_ring)
        segs = [np.r_[np.arange(k * cols, (k + 1) * cols), ((k + 1) * cols) % len(ring)] for k in range(n)]
        centre, tangent, _ = rings[-1]
        ax_u, ax_v = ring_frame(tangent)
        panels.append(_flat_disc(f"{name}/sole", part.id, part.colour, ring, centre, ax_u, ax_v, tangent,
                                 [Edge("seam", f"{name}:sole{k}", segs[k]) for k in range(n)]))
    return flatten_part(panels)


def flat_part_panels(part: FlatPart, scale_in: float, name: str | None = None) -> list[Panel]:
    """Front and back pieces cut from the outline; the front uses the inner colour if there is one."""
    name = name or part.id
    pts, tri, nb = outline_triangulation(part, scale_in)
    vertices = np.column_stack([pts, np.zeros(len(pts))])
    outline, base = np.arange(nb), np.array([nb - 1, 0])
    edges = [Edge("seam", f"{name}:outline", outline), Edge("attachment", None, base)]
    zero = np.zeros(0)
    front = Panel(f"{name}/front", part.id, part.inner_colour or part.colour, vertices, tri, pts.copy(),
                  zero, edges)
    back = Panel(f"{name}/back", part.id, part.colour, vertices, tri[:, ::-1], pts * [-1, 1],
                 zero, [Edge(e.kind, e.seam, e.vertices.copy()) for e in edges])
    return [front, back]


def _fewest(build, lowest: int, limit: float, label: str) -> tuple[list[Panel], int]:
    """Smallest panel count whose panels all flatten within `limit`; the count below it must fail.

    Stretch falls roughly with the square of the panel count, so one trial at
    FIRST_TRY predicts the answer; the search then steps to the exact smallest
    passing count. This avoids slow, hopeless trials with very few panels.
    """
    built: dict[int, list[Panel]] = {}

    def worst(n: int) -> float:
        if n not in built:
            built[n] = build(n)
        return max(p.max_stretch for p in built[n])

    first = min(max(FIRST_TRY, lowest), MAX_PANELS)
    guess = int(np.ceil(first * np.sqrt(worst(first) / limit)))
    n = min(max(guess, lowest), MAX_PANELS)
    while worst(n) > limit:
        if n == MAX_PANELS:
            raise PanelError(
                f"part {label!r}: no construction meets the {limit:.1%} stretch limit "
                f"(best was {worst(n):.2%} with {n} panels)"
            )
        n += 1
    while n > lowest and worst(n - 1) <= limit:
        n -= 1
    return built[n], n


def choose_gores(part: RoundedSolid, scale_in: float, limit: float) -> tuple[list[Panel], int]:
    return _fewest(lambda n: gore_panels(part, scale_in, n), 2, limit, part.id)


def choose_strips(part: Limb, scale_in: float, limit: float, inside=None) -> tuple[list[Panel], int]:
    return _fewest(lambda n: strip_panels(part, scale_in, n, inside=inside), 1, limit, part.id)


def weld(panels: list[Panel]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Join a part's panels along their seams into one surface.

    Returns positions, faces and, for every panel vertex (panels taken in order), its welded vertex.
    """
    ps = PanelSet()
    ps.add(panels)
    start, offset = {}, 0
    for p in panels:
        start[p.name] = offset
        offset += len(p.vertices)
    V = np.vstack([p.vertices for p in panels])
    F = np.vstack([p.faces + start[p.name] for p in panels])
    parent = np.arange(len(V))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for seam in ps.seams.values():
        (pa, ea), (pb, eb) = seam.sides
        for i, j in zip(ps.panels[pa].edges[ea].vertices + start[pa], ps.panels[pb].edges[eb].vertices + start[pb]):
            ri, rj = root(i), root(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([root(i) for i in range(len(V))])
    kept, welded = np.unique(roots, return_inverse=True)
    return V[kept], welded[F], welded


def closed_surface(panels: list[Panel]) -> trimesh.Trimesh:
    V, F, _ = weld(panels)
    return trimesh.Trimesh(V, F, process=False)


def _inside_parent(child: Placed, parent: Placed, parent_panels: list[Panel]):
    """Signed depth (positive inside) of child-frame points in the parent's sewn shape."""
    surface = closed_surface(parent_panels)

    def inside(points: np.ndarray) -> np.ndarray:
        local = (points @ child.rotation.T + child.translation - parent.translation) @ parent.rotation
        return trimesh.proximity.signed_distance(surface, local)
    return inside


def build_panels(kit: Kit, placed: dict[str, Placed], settings: Settings) -> PanelSet:
    """Panels and seams for every part. A pair is built once and cut twice (once mirrored)."""
    by_id = {p.id: p for p in kit.parts}
    result = PanelSet()
    for name, pl in placed.items():
        if name.endswith("_right") or pl.kind == "surface_feature":
            continue
        part = by_id[pl.part_id]
        if pl.kind == "rounded_solid":
            panels, _ = choose_gores(part, pl.scale_in, settings.max_flatten_stretch)
        elif pl.kind == "limb":
            parent = placed[pl.parent]
            parent_panels = [p for p in result.panels.values() if p.part == parent.part_id]
            inside = _inside_parent(pl, parent, parent_panels) if parent.kind == "rounded_solid" else None
            panels, _ = choose_strips(part, pl.scale_in, settings.max_flatten_stretch, inside)
        else:
            panels = flat_part_panels(part, pl.scale_in)
        if name.endswith("_left"):
            for p in panels:
                p.cut, p.mirrored = 2, 1
        result.add(panels)
        if pl.kind == "rounded_solid":
            result.seams[f"{part.id}:m0"].gap = GAP
    return result

"""Stuffing simulation, checked against the Mylar balloon (Paulsen 1994).

Reference constants from Wikipedia, "Mylar balloon (geometry)": a disc of
radius a inflates to rim radius r = a / 1.3110287771 and thickness
2 * 0.5990701173 * r.
"""

import numpy as np
import pytest
from scipy.spatial import Delaunay

from plush.inflate import inflate, membrane_from_panels
from plush.panels import Edge, Panel, gore_panels, strip_panels
from plush.parts import Limb, RoundedSolid

A = 3.0  # disc radius, inches


def disc_panel(name: str, flip: bool, rings: int = 10) -> Panel:
    pts = [[0.0, 0.0]]
    for k in range(1, rings + 1):
        n = 6 * k
        a = np.linspace(0, 2 * np.pi, n, endpoint=False) + (0.5 * np.pi / n if k % 2 else 0)
        pts += list(np.column_stack([A * k / rings * np.cos(a), A * k / rings * np.sin(a)]))
    pts = np.array(pts)
    F = Delaunay(pts).simplices
    e1, e2 = pts[F[:, 1]] - pts[F[:, 0]], pts[F[:, 2]] - pts[F[:, 0]]
    cw = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0
    F[cw] = F[cw][:, ::-1]
    rim = np.arange(len(pts) - 6 * rings, len(pts))
    dome = (-1 if flip else 1) * 0.05 * (A**2 - (pts**2).sum(axis=1)) / A  # start slightly inflated
    return Panel(name, "balloon", "#FFFFFF", np.column_stack([pts, dome]), F[:, ::-1] if flip else F,
                 pts * ([-1, 1] if flip else [1, 1]), np.zeros(0), [Edge("seam", "rim", np.r_[rim, rim[0]])])


@pytest.fixture(scope="module")
def balloon():
    return inflate(membrane_from_panels([disc_panel("top", False), disc_panel("bottom", True)]))


@pytest.fixture(scope="module")
def ball():
    part = RoundedSolid(kind="rounded_solid", id="ball", name="Ball", colour="#000000",
                        width=0.5, height=0.5, depth=0.5)
    panels = gore_panels(part, 12.0, 8)
    m = membrane_from_panels(panels)
    return panels, m, inflate(m)


def test_mylar_balloon_matches_published_shape(balloon):
    r = A / 1.3110287771
    rim = np.linalg.norm(balloon.positions[:, :2], axis=1).max()
    thickness = np.ptp(balloon.positions[:, 2])
    assert rim == pytest.approx(r, rel=0.03)
    assert thickness == pytest.approx(2 * 0.5990701173 * r, rel=0.03)


def test_fabric_barely_stretches(balloon):
    assert balloon.max_stretch < 0.005


def test_identical_gores_inflate_identically(ball):
    panels, m, result = ball
    starts = np.cumsum([0] + [len(p.vertices) for p in panels])
    reach = []
    for i, p in enumerate(panels):
        X = result.positions[m.index[starts[i]:starts[i] + len(p.vertices)]]
        reach.append(np.linalg.norm(X[:, [0, 2]], axis=1).max())  # furthest from the vertical axis
    assert max(reach) - min(reach) < 1e-3


def test_attachment_ring_stays_put():
    leg = Limb(kind="limb", id="leg", name="Leg", colour="#000000", length=0.3, start_thickness=0.1,
               end_thickness=0.1, end_shape="flat_sole",
               attach={"parent": "body", "azimuth_deg": 90, "elevation_deg": 0})
    m = membrane_from_panels(strip_panels(leg, 10.0, 1))
    result = inflate(m)
    assert m.fixed.sum() > 0
    assert np.array_equal(result.positions[m.fixed], m.positions[m.fixed])
    assert np.abs(result.positions[~m.fixed] - m.positions[~m.fixed]).max() > 1e-3

import numpy as np
import pytest

from plush.geometry.limb import POINT_LENGTH, limb_centreline, limb_mesh
from plush.parts import Limb

SCALE = 10.0  # inches per unit of finished height


def limb(**kw):
    base = {"kind": "limb", "id": "l", "name": "L", "colour": "#000000", "length": 0.3,
            "start_thickness": 0.1, "end_thickness": 0.1, "end_shape": "flat_sole",
            "attach": {"parent": "body", "azimuth_deg": 90, "elevation_deg": 0}}
    return Limb(**{**base, **kw})


def test_straight_limb_area_matches_cylinder_plus_sole():
    mesh = limb_mesh(limb(), SCALE)
    d, length = 0.1 * SCALE, 0.3 * SCALE
    assert mesh.area == pytest.approx(np.pi * d * length + np.pi * (d / 2) ** 2, rel=0.01)


def test_bent_limb_centreline_length_and_end_angle():
    points, tangents = limb_centreline(limb(bend_deg=60), SCALE)
    length = np.linalg.norm(np.diff(points, axis=0), axis=1).sum()
    assert length == pytest.approx(0.3 * SCALE, rel=0.005)
    assert np.dot(tangents[0], tangents[-1]) == pytest.approx(np.cos(np.radians(60)), abs=1e-9)


def test_point_limb_ends_in_single_tip():
    part = limb(end_shape="point", bend_deg=30)
    mesh = limb_mesh(part, SCALE)
    points, tangents = limb_centreline(part, SCALE)
    tip = points[-1] + tangents[-1] * POINT_LENGTH * (0.1 * SCALE / 2)
    assert np.linalg.norm(mesh.vertices - tip, axis=1).min() < 1e-9

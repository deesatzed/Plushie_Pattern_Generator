import numpy as np
import pytest
import shapely

from plush.geometry.rounded_solid import rounded_solid_mesh
from plush.parts import RoundedSolid

SCALE = 10.0  # inches per unit of finished height


def solid(**kw):
    base = {"kind": "rounded_solid", "id": "s", "name": "S", "colour": "#000000",
            "width": 0.5, "height": 0.5, "depth": 0.5}
    return RoundedSolid(**{**base, **kw})


def test_round_solid_volume_matches_sphere():
    mesh = rounded_solid_mesh(solid(), SCALE)
    r = 0.25 * SCALE
    assert mesh.volume == pytest.approx(4 / 3 * np.pi * r**3, rel=0.01)


def test_rounded_solid_bounding_box_matches_size():
    mesh = rounded_solid_mesh(solid(width=0.4, height=0.6, depth=0.3, taper=0.3, flat_bottom=True), SCALE)
    assert mesh.extents == pytest.approx([4.0, 6.0, 3.0], rel=0.005)


def test_taper_puts_widest_section_below_centre():
    mesh = rounded_solid_mesh(solid(taper=0.3), SCALE)
    widest = mesh.vertices[np.argmax(np.abs(mesh.vertices[:, 0]))]
    assert widest[1] < 0


def test_flat_bottom_has_flat_base():
    v = rounded_solid_mesh(solid(flat_bottom=True), SCALE).vertices
    base = v[v[:, 1] < v[:, 1].min() + 1e-6]
    assert len(base) >= 3
    assert shapely.MultiPoint(base[:, [0, 2]]).convex_hull.area > 0

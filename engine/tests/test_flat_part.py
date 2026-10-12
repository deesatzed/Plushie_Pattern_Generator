import numpy as np
import pytest

from plush.geometry.flat_part import flat_part_mesh, outline_polygon
from plush.parts import FlatPart

SCALE = 10.0  # inches per unit of finished height


def flat(**kw):
    base = {"kind": "flat_part", "id": "f", "name": "F", "colour": "#000000", "outline": "round",
            "width": 0.2, "height": 0.3,
            "attach": {"parent": "body", "azimuth_deg": 0, "elevation_deg": 90}}
    return FlatPart(**{**base, **kw})


def test_round_outline_area_is_half_ellipse():
    poly = outline_polygon(flat(), SCALE)
    w, h = 0.2 * SCALE, 0.3 * SCALE
    assert poly.area == pytest.approx(np.pi * w * h / 4, rel=0.01)


@pytest.mark.parametrize("outline", ["round", "pointed", "long_oval", "leaf"])
def test_outlines_are_valid_and_fill_their_box(outline):
    poly = outline_polygon(flat(outline=outline), SCALE)
    assert poly.is_valid
    minx, miny, maxx, maxy = poly.bounds
    assert (maxx - minx, maxy - miny) == pytest.approx((0.2 * SCALE, 0.3 * SCALE), rel=0.005)


def test_zero_puffiness_is_flat():
    mesh = flat_part_mesh(flat(puffiness=0.0), SCALE)
    assert mesh.extents[2] <= 0.01
    assert flat_part_mesh(flat(puffiness=0.5), SCALE).extents[2] > 0.1

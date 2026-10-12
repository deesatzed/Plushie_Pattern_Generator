import json

import numpy as np
import pytest
import shapely

from plush.geometry.assemble import assemble
from plush.panels import build_panels
from plush.parts import parse_kit
from plush.seams import notches, polyline_length, side_lengths, side_points, side_points_3d
from plush.settings import load_settings

from kits import bear

SETTINGS = load_settings()


@pytest.fixture(scope="module")
def panels():
    kit = parse_kit(json.dumps(bear()))
    return build_panels(kit, assemble(kit, 12.0), SETTINGS)


def test_every_seam_joins_two_matching_sides(panels):
    for seam in panels.seams.values():
        assert len(seam.sides) == 2, seam.id
        a, b = (side_points_3d(panels, s) for s in seam.sides)
        assert np.abs(a - b).max() < 1e-9, seam.id


def test_seam_sides_have_equal_length(panels):
    for seam in panels.seams.values():
        a, b = side_lengths(panels, seam)
        assert abs(a - b) <= SETTINGS.seam_length_diff_in, seam.id


def test_notches_match_and_are_close_enough(panels):
    for seam in panels.seams.values():
        sides = notches(panels, seam, SETTINGS.notch_spacing_in)
        assert len(sides[0]) == len(sides[1]), seam.id
        intervals = len(sides[0]) + 1
        for side, marks in zip(seam.sides, sides):
            pts = side_points(panels, side)
            assert polyline_length(pts) / intervals <= SETTINGS.notch_spacing_in + 1e-9, seam.id
            line = shapely.LineString(pts)
            assert all(line.distance(shapely.Point(m)) < 1e-9 for m in marks), seam.id


def test_each_closed_part_has_one_stuffing_gap_on_its_back_seam(panels):
    gaps = {s.id for s in panels.seams.values() if s.gap is not None}
    assert gaps == {"body:m0", "head:m0"}

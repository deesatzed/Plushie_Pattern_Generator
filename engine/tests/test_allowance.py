import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from plush.allowance import cut_outline


def test_square_grows_by_exactly_the_allowance():
    square = np.array([[0, 0], [2, 0], [2, 2], [0, 2]], float)
    assert Polygon(cut_outline(square, 0.25)).area == pytest.approx(2.5**2, abs=1e-9)


def test_circle_grows_by_the_allowance():
    a = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    circle = np.column_stack([np.cos(a), np.sin(a)])
    assert Polygon(cut_outline(circle, 0.25)).area == pytest.approx(np.pi * 1.25**2, rel=0.005)


def test_cut_line_is_never_closer_than_the_allowance():
    gore_tip = np.array([[0, 0], [0.6, 2.0], [0, 4.0], [-0.6, 2.0]], float)  # sharp ends, like a gore
    cut = cut_outline(gore_tip, 0.25)
    stitch = Polygon(gore_tip)
    assert min(stitch.exterior.distance(Point(p)) for p in cut) >= 0.25 - 1e-6

import itertools

import numpy as np
import pytest
from shapely.geometry import Polygon

from plush.layout import cutting_layout
from plush.settings import load_settings

SETTINGS = load_settings()


@pytest.fixture(scope="module")
def fabric(bear_stuffed):
    _, _, pattern, _ = bear_stuffed
    return pattern, cutting_layout(pattern, SETTINGS)


def test_every_copy_fits_across_the_fabric(fabric):
    _, layouts = fabric
    for f in layouts:
        for p in f.placements:
            assert p.outline[:, 0].min() >= -1e-9 and p.outline[:, 0].max() <= f.width_in + 1e-9, p.piece


def test_no_copies_overlap(fabric):
    _, layouts = fabric
    for f in layouts:
        shapes = [Polygon(p.outline) for p in f.placements]
        for a, b in itertools.combinations(shapes, 2):
            assert a.intersection(b).area < 1e-9


def test_pieces_are_never_rotated_only_mirrored(fabric):
    pattern, layouts = fabric
    for f in layouts:
        for p in f.placements:
            cut = pattern.pieces[p.piece].cut * ([-1, 1] if p.mirrored else [1, 1])
            assert np.abs((p.outline - p.outline.min(axis=0)) - (cut - cut.min(axis=0))).max() < 1e-9, p.piece


def test_every_copy_is_laid_out_and_lengths_are_reported(fabric):
    pattern, layouts = fabric
    assert {f.colour for f in layouts} == {p.colour for p in pattern.pieces.values()}
    copies = sum(len(f.placements) for f in layouts)
    assert copies == sum(p.cut_count for p in pattern.pieces.values())
    for f in layouts:
        assert f.length_in == pytest.approx(max(p.outline[:, 1].max() for p in f.placements))

import json

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from plush.finishing import finish
from plush.geometry.assemble import assemble
from plush.panels import build_panels
from plush.parts import parse_kit
from plush.settings import load_settings

from kits import bear

SETTINGS = load_settings()


@pytest.fixture(scope="module")
def pattern():
    kit = parse_kit(json.dumps(bear()))
    placed = assemble(kit, 12.0)
    return finish(kit, placed, build_panels(kit, placed, SETTINGS), SETTINGS)


def test_labels_name_the_part_and_how_many_to_cut(pattern):
    assert pattern.pieces["ear/front"].label == "Ear — front — cut 2 (1 mirrored)"
    head = [p for p in pattern.pieces.values() if p.part == "head"]
    assert pattern.pieces["head/gore1"].label == f"Head — gore 1 of {len(head)} — cut 1"


def test_limb_grain_runs_along_the_limb(pattern):
    ps = pattern.panels
    for p in (p for p in ps.panels.values() if p.part == "arm" and "/strip" in p.name):
        start = next(e for e in p.edges if e.kind == "attachment").vertices
        top = p.upright[0]
        along = p.uv[top].mean(axis=0) - p.uv[start].mean(axis=0)
        grain = np.diff(pattern.pieces[p.name].grain, axis=0)[0]
        cos = along @ grain / np.linalg.norm(along) / np.linalg.norm(grain)
        assert cos > np.cos(np.radians(1.0)), p.name


def test_every_cut_line_clears_the_stitch_line_by_the_allowance(pattern):
    for piece in pattern.pieces.values():
        stitch = Polygon(piece.stitch)
        assert Polygon(piece.cut).contains(stitch), piece.name
        assert min(stitch.exterior.distance(Point(p)) for p in piece.cut) >= SETTINGS.seam_allowance_in - 1e-6


def test_notches_carry_matching_seam_letters_and_gaps_sit_on_back_seams(pattern):
    for sid, seam in pattern.panels.seams.items():
        letter = pattern.seam_letters[sid]
        counts = [sum(1 for _, label in pattern.pieces[side[0]].notches if label == letter) for side in seam.sides]
        if seam.sides[0][0] == seam.sides[1][0]:  # a seam closing a single piece carries both sides' notches
            assert counts[0] % 2 == 0 and counts[0] > 0, sid
        else:
            assert counts[0] == counts[1] > 0, sid
    with_gaps = sorted(name for name, p in pattern.pieces.items() if p.gaps)
    assert {n.split("/")[0] for n in with_gaps} == {"body", "head"}
    assert len(with_gaps) == 4  # both sides of each back seam

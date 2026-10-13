import copy
import dataclasses
import json

import numpy as np
import pytest

from plush.checks import check_flattening_stretch, check_seams_match, check_sewable, check_stuffed_shape
from plush.finishing import finish
from plush.geometry.assemble import assemble
from plush.panels import build_panels, gore_panels
from plush.parts import parse_kit
from plush.settings import load_settings
from plush.stuffing import stuff_all

from kits import bear, part

SETTINGS = load_settings()


def build(kit_dict):
    kit = parse_kit(json.dumps(kit_dict))
    placed = assemble(kit, 12.0)
    ps = build_panels(kit, placed, SETTINGS)
    return kit, placed, ps


@pytest.fixture(scope="module")
def bear_pattern():
    kit, placed, ps = build(bear())
    stuffing = stuff_all(ps, SETTINGS)
    return kit, placed, finish(kit, placed, ps, SETTINGS), stuffing


def test_check_1_passes_for_the_bear(bear_pattern):
    _, _, pattern, _ = bear_pattern
    assert check_seams_match(pattern, SETTINGS).passed


def test_check_1_fails_when_one_side_of_a_seam_is_shorter(bear_pattern):
    kit, placed, pattern, _ = bear_pattern
    broken = copy.deepcopy(pattern)
    seam = broken.panels.seams["head:m1"]
    panel_name, edge = seam.sides[0]
    panel = broken.panels.panels[panel_name]
    chain = panel.edges[edge].vertices
    end, before = panel.uv[chain[-1]], panel.uv[chain[-2]]
    panel.uv[chain[-1]] = end + (before - end) / np.linalg.norm(before - end) * 0.1  # 0.1 in shorter
    result = check_seams_match(broken, SETTINGS)
    assert not result.passed and any("head:m1" in w for w in result.where)


def test_check_3_passes_for_the_bear(bear_pattern):
    *_, stuffing = bear_pattern
    result = check_stuffed_shape(stuffing, SETTINGS)
    assert result.passed and "ear" in result.measured  # flat ears are reported as not simulated


def test_check_3_fails_against_a_tighter_limit(bear_pattern):
    *_, stuffing = bear_pattern
    tight = dataclasses.replace(SETTINGS, stuffed_mean_deviation=0.0001, stuffed_max_deviation=0.0001)
    result = check_stuffed_shape(stuffing, tight)
    assert not result.passed and any(w.startswith("head") for w in result.where)


def test_check_4_passes_for_the_bear(bear_pattern):
    _, _, pattern, _ = bear_pattern
    assert check_flattening_stretch(pattern, SETTINGS).passed


def test_check_4_fails_with_too_few_gores(bear_pattern):
    kit, placed, pattern, _ = bear_pattern
    broken = copy.deepcopy(pattern)
    head = next(p for p in kit.parts if p.id == "head")
    for p in [n for n in broken.panels.panels if n.startswith("head/")]:
        del broken.panels.panels[p]
    for p in gore_panels(head, placed["head"].scale_in, 2):
        broken.panels.panels[p.name] = p
    result = check_flattening_stretch(broken, SETTINGS)
    assert not result.passed and all(w.startswith("head/") for w in result.where)


def test_check_5_passes_for_the_bear(bear_pattern):
    kit, placed, pattern, _ = bear_pattern
    result = check_sewable(kit, placed, pattern, SETTINGS)
    assert result.passed, result.where


def test_check_5_fails_for_an_arm_too_thin_to_turn():
    thin = bear()
    part(thin, "arm").update(start_thickness=0.04, end_thickness=0.04)  # about 0.5 in across at 12 in tall
    kit, placed, ps = build(thin)
    pattern = finish(kit, placed, ps, SETTINGS)
    result = check_sewable(kit, placed, pattern, SETTINGS)
    assert not result.passed and any(w.startswith("arm:") for w in result.where)

import json

import numpy as np
import pytest

from plush.geometry.assemble import assemble
from plush.panels import (PanelError, build_panels, choose_gores, flat_part_panels, gore_panels,
                          strip_panels)
from plush.parts import FlatPart, Limb, RoundedSolid, parse_kit
from plush.settings import load_settings

from kits import bear

LIMIT = load_settings().max_flatten_stretch


def ball(**kw):
    base = {"kind": "rounded_solid", "id": "ball", "name": "Ball", "colour": "#000000",
            "width": 0.5, "height": 0.5, "depth": 0.5}
    return RoundedSolid(**{**base, **kw})


def limb(**kw):
    base = {"kind": "limb", "id": "leg", "name": "Leg", "colour": "#000000", "length": 0.3,
            "start_thickness": 0.1, "end_thickness": 0.1, "end_shape": "flat_sole",
            "attach": {"parent": "body", "azimuth_deg": 90, "elevation_deg": 0}}
    return Limb(**{**base, **kw})


def uv_area(p):
    a, b, c = (p.uv[p.faces[:, k]] for k in range(3))
    return float(((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])).sum() / 2)


@pytest.fixture(scope="module")
def bear_panels():
    kit = parse_kit(json.dumps(bear()))
    return build_panels(kit, assemble(kit, 12.0), load_settings())


def test_sphere_gores_are_equal_and_stand_upright():
    panels = gore_panels(ball(), 12.0, 10)
    assert len(panels) == 10
    areas = [uv_area(p) for p in panels]
    assert max(areas) == pytest.approx(min(areas), rel=0.005)
    for p in panels:
        top, bottom = p.uv[p.upright[0]].mean(axis=0), p.uv[p.upright[1]].mean(axis=0)
        assert top[1] > bottom[1] and abs(top[0] - bottom[0]) < 1e-6 * np.ptp(p.uv[:, 1])


def test_flat_bottom_adds_a_base_sewn_to_every_gore():
    panels = gore_panels(ball(flat_bottom=True), 12.0, 8)
    names = [p.name for p in panels]
    assert names[-1] == "ball/base" and len(names) == 9
    base_seams = {e.seam for e in panels[-1].edges}
    assert base_seams == {f"ball:b{k}" for k in range(8)}


def test_straight_limb_is_one_strip_and_a_sole_without_stretch():
    panels = strip_panels(limb(), 10.0, 1)
    assert [p.name for p in panels] == ["leg/strip1", "leg/sole"]
    assert panels[0].max_stretch < 1e-3  # a straight tube unrolls exactly
    for end in ("round", "point"):  # no sole on a rounded or pointed end
        assert [p.name for p in strip_panels(limb(end_shape=end), 10.0, 8)] == [f"leg/strip{k}" for k in range(1, 9)]


def test_flat_part_is_a_front_and_a_mirrored_back():
    ear = FlatPart(kind="flat_part", id="ear", name="Ear", colour="#C8A27A", inner_colour="#F2D0D9",
                   outline="round", width=0.12, height=0.12,
                   attach={"parent": "head", "azimuth_deg": 50, "elevation_deg": 60})
    front, back = flat_part_panels(ear, 12.0)
    assert (front.colour, back.colour) == ("#F2D0D9", "#C8A27A")
    assert np.allclose(back.uv, front.uv * [-1, 1])
    assert front.max_stretch == back.max_stretch == 0.0


def test_pairs_are_built_once_and_cut_twice(bear_panels):
    names = list(bear_panels.panels)
    assert not any("_left" in n or "_right" in n for n in names)
    for p in bear_panels.panels.values():
        expected = (2, 1) if p.part in ("ear", "arm") else (1, 0)
        assert (p.cut, p.mirrored) == expected, p.name


def test_fewest_gores_that_meet_the_stretch_limit():
    panels, n = choose_gores(ball(), 12.0, LIMIT)
    assert max(p.max_stretch for p in panels) <= LIMIT
    assert max(p.max_stretch for p in gore_panels(ball(), 12.0, n - 1)) > LIMIT


def test_unreachable_limit_names_the_part():
    with pytest.raises(PanelError, match="part 'ball'"):
        choose_gores(ball(), 12.0, 1e-6)


def test_every_3d_panel_faces_outward(bear_panels):
    by_part: dict[str, list] = {}
    for p in bear_panels.panels.values():
        by_part.setdefault(p.part, []).append(p)
    for part, panels in by_part.items():
        if part == "ear":  # flat pieces: checked by the front/back test
            continue
        centre = np.vstack([p.vertices for p in panels]).mean(axis=0)
        for p in panels:
            tri = p.vertices[p.faces]
            normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            outward = np.einsum("ij,ij->i", normals, tri.mean(axis=1) - centre)
            assert (outward > 0).mean() > 0.99, p.name

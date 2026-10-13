import json

import numpy as np
import pytest
import trimesh
from shapely.geometry import LineString

from plush.attachments import attachment_marks
from plush.geometry.assemble import assemble
from plush.panels import build_panels
from plush.parts import parse_kit
from plush.settings import load_settings

from kits import bear

SETTINGS = load_settings()


@pytest.fixture(scope="module")
def bear_build():
    kit = parse_kit(json.dumps(bear()))
    placed = assemble(kit, 12.0)
    ps = build_panels(kit, placed, SETTINGS)
    return kit, placed, ps, attachment_marks(kit, ps, placed)


def test_every_part_is_marked_on_its_parent_with_matching_notches(bear_build):
    _, _, _, marks = bear_build
    assert {m.child for m in marks} == {"head", "ear_left", "ear_right", "arm_left", "arm_right"}
    for m in marks:
        assert len(m.parent_notches) == len(m.child_notches) > 0, m.child
        assert all(n.split("/")[0] == m.parent.split("_")[0] for n, _ in m.parent_notches), m.child


def test_limb_openings_and_head_ring_lie_on_the_parent(bear_build):
    _, placed, ps, marks = bear_build
    for m in marks:
        if m.child.startswith(("arm", "head")):
            assert m.gap_in < 0.01, m.child
    # the arm's open end itself was cut where the arm meets the body
    arm, body = placed["arm_left"], placed["body"]
    ends = np.vstack([p.vertices[e.vertices] for p in ps.panels.values() if p.part == "arm"
                      for e in p.edges if e.kind == "attachment"])
    depth = trimesh.proximity.signed_distance(body.mesh, ends @ arm.rotation.T + arm.translation)
    assert np.abs(depth).max() < 0.01


def test_opening_and_its_line_on_the_parent_have_matching_lengths(bear_build):
    *_, marks = bear_build
    for m in marks:
        on_parent = sum(LineString(line).length for _, line in m.outline if len(line) > 1)
        on_child = sum(LineString(line).length for _, line in m.child_outline if len(line) > 1)
        assert on_parent == pytest.approx(on_child, rel=SETTINGS.max_flatten_stretch), m.child


def test_a_rounded_part_below_its_parent_is_marked_where_they_meet():
    kit = bear()
    kit["parts"].append({"kind": "rounded_solid", "id": "foot", "name": "Foot", "colour": "#C8A27A",
                         "width": 0.2, "height": 0.12, "depth": 0.25,
                         "attach": {"parent": "body", "azimuth_deg": 0, "elevation_deg": -60}})
    kit = parse_kit(json.dumps(kit))
    placed = assemble(kit, 12.0)
    ps = build_panels(kit, placed, SETTINGS)
    mark = next(m for m in attachment_marks(kit, ps, placed) if m.child == "foot")
    assert mark.gap_in < 0.01 and len(mark.parent_notches) == 4

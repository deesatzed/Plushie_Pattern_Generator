import json

import numpy as np
import pytest
from shapely.geometry import Polygon

from plush.finishing import finish
from plush.geometry.assemble import assemble
from plush.panels import build_panels
from plush.parts import parse_kit
from plush.settings import load_settings

from kits import bear


def test_safety_eyes_are_marked_on_the_head(bear_stuffed):
    _, _, pattern, _ = bear_stuffed
    marks = {name: (panel, label) for name, panel, label, _ in pattern.features}
    assert set(marks) == {"eye_left", "eye_right"}
    assert all(panel.startswith("head/") for panel, _ in marks.values())
    assert marks["eye_left"][1] == "Eye (left) — safety eye"


def test_applique_feature_becomes_a_felt_template_without_allowance():
    kit = bear()
    kit["parts"].append({"kind": "surface_feature", "id": "nose", "name": "Nose", "colour": "#4A3020",
                         "shape": "oval", "method": "applique", "width": 0.06, "height": 0.04,
                         "attach": {"parent": "head", "azimuth_deg": 0, "elevation_deg": -5}})
    kit = parse_kit(json.dumps(kit))
    placed = assemble(kit, 12.0)
    settings = load_settings()
    pattern = finish(kit, placed, build_panels(kit, placed, settings), settings)
    template = pattern.pieces["nose/template"]
    scale = placed["nose"].scale_in
    assert np.array_equal(template.cut, template.stitch)
    assert Polygon(template.cut).area == pytest.approx(np.pi * 0.06 * 0.04 * scale**2 / 4, rel=0.01)
    assert "felt appliqué" in template.label

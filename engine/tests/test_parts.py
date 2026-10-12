"""Validation rules for the part kit.

The kits below are hand-written inputs that exercise each rule. They live
only in this test file and are never loaded by the app.
"""

import copy
import json

import pytest
from pydantic import ValidationError

from plush.parts import Kit, kit_json_schema, parse_kit

BODY = {"kind": "rounded_solid", "id": "body", "name": "Body", "colour": "#C8A27A",
        "width": 0.5, "height": 0.55, "depth": 0.45, "flat_bottom": True}

BEAR = {
    "character_name": "Rule-check bear",
    "parts": [
        BODY,
        {"kind": "rounded_solid", "id": "head", "name": "Head", "colour": "#C8A27A",
         "width": 0.45, "height": 0.4, "depth": 0.4,
         "attach": {"parent": "body", "azimuth_deg": 0, "elevation_deg": 90}},
        {"kind": "flat_part", "id": "ear", "name": "Ear", "colour": "#C8A27A", "pair": True,
         "outline": "round", "width": 0.12, "height": 0.12, "inner_colour": "#F2D0D9",
         "attach": {"parent": "head", "azimuth_deg": 50, "elevation_deg": 60}},
        {"kind": "limb", "id": "arm", "name": "Arm", "colour": "#C8A27A", "pair": True,
         "length": 0.25, "start_thickness": 0.12, "end_thickness": 0.1, "end_shape": "round",
         "attach": {"parent": "body", "azimuth_deg": 80, "elevation_deg": 30, "pitch_deg": -40}},
        {"kind": "surface_feature", "id": "eye", "name": "Eye", "colour": "#1A1A1A", "pair": True,
         "shape": "circle", "method": "safety_eye", "width": 0.04, "height": 0.04,
         "attach": {"parent": "head", "azimuth_deg": 20, "elevation_deg": 10}},
    ],
}


def bear():
    return copy.deepcopy(BEAR)


def part(kit, part_id):
    return next(p for p in kit["parts"] if p["id"] == part_id)


def test_minimal_kit_with_only_a_body_is_valid():
    kit = parse_kit(json.dumps({"character_name": "Blob", "parts": [BODY]}))
    assert kit.parts[0].kind == "rounded_solid"


def test_bear_kit_is_valid():
    kit = parse_kit(json.dumps(bear()))
    assert [p.id for p in kit.parts] == ["body", "head", "ear", "arm", "eye"]


def test_rejects_unknown_part_kind():
    kit = bear()
    part(kit, "arm")["kind"] = "tentacle"
    with pytest.raises(ValidationError):
        parse_kit(json.dumps(kit))


def test_rejects_value_outside_fixed_list():
    kit = bear()
    part(kit, "arm")["end_shape"] = "claw"
    with pytest.raises(ValidationError, match="end_shape"):
        parse_kit(json.dumps(kit))


def test_rejects_unexpected_field():
    kit = bear()
    part(kit, "head")["sparkle"] = True
    with pytest.raises(ValidationError, match="sparkle"):
        parse_kit(json.dumps(kit))


def test_rejects_bad_colour():
    kit = bear()
    part(kit, "body")["colour"] = "brown"
    with pytest.raises(ValidationError, match="colour"):
        parse_kit(json.dumps(kit))


def test_json_schema_carries_the_fixed_lists():
    schema = json.dumps(kit_json_schema())
    for value in ("flat_sole", "long_oval", "safety_eye", "rounded_solid", "surface_feature"):
        assert f'"{value}"' in schema
    assert Kit.model_json_schema()["additionalProperties"] is False

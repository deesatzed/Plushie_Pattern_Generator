"""The test bear, fully built and stuffed once per test run (stuffing takes most of a minute)."""

import json

import pytest

from plush.finishing import finish
from plush.geometry.assemble import assemble
from plush.panels import build_panels
from plush.parts import parse_kit
from plush.settings import load_settings
from plush.stuffing import stuff_all

from kits import bear


@pytest.fixture(scope="session")
def bear_stuffed():
    settings = load_settings()
    kit = parse_kit(json.dumps(bear()))
    placed = assemble(kit, 12.0)
    ps = build_panels(kit, placed, settings)
    stuffing = stuff_all(ps, settings)
    return kit, placed, finish(kit, placed, ps, settings), stuffing

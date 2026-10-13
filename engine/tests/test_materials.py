import pytest
import trimesh

from plush.materials import closed_volume
from plush.panels import gore_panels
from plush.parts import RoundedSolid
from plush.settings import load_settings
from plush.stuffing import stuff

SETTINGS = load_settings()


def test_stuffed_volume_is_the_volume_of_the_inflated_shape():
    ball = RoundedSolid(kind="rounded_solid", id="ball", name="Ball", colour="#000000",
                        width=0.5, height=0.5, depth=0.5)
    result = stuff(gore_panels(ball, 12.0, 8), SETTINGS.stuffed_mean_deviation, SETTINGS.stuffed_max_deviation)
    inflated = trimesh.Trimesh(result.inflated.positions, result.inflated.faces, process=False)
    assert inflated.is_watertight
    assert closed_volume(result.inflated.positions, result.inflated.faces) == pytest.approx(inflated.volume, rel=1e-9)

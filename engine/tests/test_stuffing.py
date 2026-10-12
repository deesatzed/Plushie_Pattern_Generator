import pytest

from plush.panels import gore_panels
from plush.parts import RoundedSolid
from plush.settings import load_settings
from plush.stuffing import stuff

SETTINGS = load_settings()


def ball():
    return RoundedSolid(kind="rounded_solid", id="ball", name="Ball", colour="#000000",
                        width=0.5, height=0.5, depth=0.5)


@pytest.fixture(scope="module")
def tight():
    # a target far tighter than the settings, so the correction loop has to work (and cannot finish)
    return stuff(gore_panels(ball(), 12.0, 6), mean_limit=0.001, worst_limit=0.005, rounds=1)


def test_eight_gore_ball_stuffs_close_to_its_model():
    result = stuff(gore_panels(ball(), 12.0, 8), SETTINGS.stuffed_mean_deviation, SETTINGS.stuffed_max_deviation)
    assert result.converged
    assert result.mean_deviation <= SETTINGS.stuffed_mean_deviation
    assert result.worst_deviation <= SETTINGS.stuffed_max_deviation
    assert len(result.history) == 1  # no correction needed


def test_correction_reduces_deviation(tight):
    start_mean, _ = tight.history[0]
    assert len(tight.history) == 2
    assert tight.mean_deviation < start_mean


def test_unreachable_target_reports_measured_values(tight):
    assert tight.converged is False
    assert tight.mean_deviation > 0.001
    assert (tight.mean_deviation, tight.worst_deviation) in tight.history

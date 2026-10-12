import pytest

from plush.settings import SETTINGS_PATH, load_settings


def test_settings_file_loads_with_positive_values():
    s = load_settings()
    assert s.approved_by_owner is True  # owner approved the values (gate G2, 2026-10-12)
    for name in (
        "seam_allowance_in", "min_turnable_width_in", "fabric_width_in",
        "notch_spacing_in", "seam_length_diff_in", "max_flatten_stretch",
        "stuffed_mean_deviation", "stuffed_max_deviation",
        "test_square_in", "tile_overlap_in",
    ):
        assert getattr(s, name) > 0, name


def test_missing_key_is_reported_by_name(tmp_path):
    text = SETTINGS_PATH.read_text().replace("fabric_width_in = 44.0\n", "")
    broken = tmp_path / "settings.toml"
    broken.write_text(text)
    with pytest.raises(KeyError, match="fabric_width_in"):
        load_settings(broken)

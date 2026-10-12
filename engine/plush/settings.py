"""Pattern settings and check tolerances, read from engine/settings.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.toml"


@dataclass(frozen=True)
class Settings:
    approved_by_owner: bool
    seam_allowance_in: float
    min_turnable_width_in: float
    fabric_width_in: float
    notch_spacing_in: float
    seam_length_diff_in: float
    max_flatten_stretch: float
    stuffed_mean_deviation: float
    stuffed_max_deviation: float
    test_square_in: float
    tile_overlap_in: float


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read settings; a missing key raises KeyError naming it."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    pattern, tol, pdf = raw["pattern"], raw["tolerances"], raw["pdf"]
    return Settings(
        approved_by_owner=bool(raw["status"]["approved_by_owner"]),
        seam_allowance_in=float(pattern["seam_allowance_in"]),
        min_turnable_width_in=float(pattern["min_turnable_width_in"]),
        fabric_width_in=float(pattern["fabric_width_in"]),
        notch_spacing_in=float(pattern["notch_spacing_in"]),
        seam_length_diff_in=float(tol["seam_length_diff_in"]),
        max_flatten_stretch=float(tol["max_flatten_stretch"]),
        stuffed_mean_deviation=float(tol["stuffed_mean_deviation"]),
        stuffed_max_deviation=float(tol["stuffed_max_deviation"]),
        test_square_in=float(pdf["test_square_in"]),
        tile_overlap_in=float(pdf["tile_overlap_in"]),
    )

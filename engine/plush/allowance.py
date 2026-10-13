"""Seam allowance: the cut line is the stitch line pushed outward by an even margin."""

from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon

MITRE_LIMIT = 2.0  # sharp tips (gore points) are bevelled instead of drawn as long spikes


def cut_outline(stitch: np.ndarray, allowance_in: float) -> np.ndarray:
    """Closed cut line (counter-clockwise, first point not repeated) around a closed stitch line."""
    shape = Polygon(stitch).buffer(allowance_in, join_style="mitre", mitre_limit=MITRE_LIMIT)
    return np.asarray(shape.exterior.coords)[:-1]

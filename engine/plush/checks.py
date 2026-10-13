"""The automatic checks that decide whether a pattern may be printed (design section 4).

Checks 1, 3, 4 and 5 live here; check 2 (true scale) reads the PDF and check 6
(complete directions) needs the directions, so they come with those outputs;
check 7 (matches the approved model) comes with project versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from plush.finishing import Pattern
from plush.geometry.assemble import Placed
from plush.parts import Kit
from plush.seams import polyline_length, side_lengths
from plush.settings import Settings
from plush.stuffing import StuffingResult


@dataclass
class CheckResult:
    number: int
    name: str
    passed: bool
    measured: str
    limit: str
    where: list[str] = field(default_factory=list)  # what failed, one line each


def check_seams_match(pattern: Pattern, settings: Settings) -> CheckResult:
    worst, where = 0.0, []
    for sid, seam in pattern.panels.seams.items():
        a, b = side_lengths(pattern.panels, seam)
        worst = max(worst, abs(a - b))
        if abs(a - b) > settings.seam_length_diff_in:
            where.append(f"seam {pattern.seam_letters[sid]} ({sid}): sides differ by {abs(a - b):.4f} in")
    return CheckResult(1, "Seams match", not where, f"{worst:.4f} in", f"{settings.seam_length_diff_in:.4f} in", where)


def check_stuffed_shape(results: dict[str, StuffingResult | None], settings: Settings) -> CheckResult:
    worst_mean = worst_worst = 0.0
    where = []
    for part, r in results.items():
        if r is None:
            continue  # flat parts: the outline is cut exactly; stuffing is not simulated
        worst_mean, worst_worst = max(worst_mean, r.mean_deviation), max(worst_worst, r.worst_deviation)
        if r.mean_deviation > settings.stuffed_mean_deviation or r.worst_deviation > settings.stuffed_max_deviation:
            where.append(f"{part}: stuffed shape off the model by {r.mean_deviation:.2%} on average, "
                         f"{r.worst_deviation:.2%} at worst")
    not_simulated = sorted(p for p, r in results.items() if r is None)
    measured = f"mean {worst_mean:.2%}, worst {worst_worst:.2%}"
    if not_simulated:
        measured += f"; not simulated (flat, outline exact): {', '.join(not_simulated)}"
    return CheckResult(3, "Stuffed shape matches the model", not where, measured,
                       f"mean {settings.stuffed_mean_deviation:.0%}, worst {settings.stuffed_max_deviation:.0%}", where)


def check_flattening_stretch(pattern: Pattern, settings: Settings) -> CheckResult:
    worst, where = 0.0, []
    for p in pattern.panels.panels.values():
        worst = max(worst, p.max_stretch)
        if p.max_stretch > settings.max_flatten_stretch:
            where.append(f"{p.name}: needs {p.max_stretch:.2%} stretch to lie flat")
    return CheckResult(4, "Flattening stretch", not where, f"{worst:.2%}", f"{settings.max_flatten_stretch:.0%}", where)


def check_sewable(kit: Kit, placed: dict[str, Placed], pattern: Pattern, settings: Settings) -> CheckResult:
    where = []
    minimum = settings.min_turnable_width_in
    scale = {pl.part_id: pl.scale_in for pl in placed.values()}
    ps = pattern.panels
    for part in kit.parts:
        if part.kind == "limb":
            narrowest = min(part.start_thickness, part.end_thickness) * scale[part.id]
            if narrowest < minimum:
                where.append(f"{part.id}: narrowest tube {narrowest:.3f} in is too thin to turn ({minimum} in)")
        elif part.kind == "flat_part":
            front = ps.panels[f"{part.id}/front"]
            base = next(e for e in front.edges if e.kind == "attachment")
            width = polyline_length(front.uv[base.vertices])
            if width < minimum:
                where.append(f"{part.id}: base opening {width:.3f} in is too narrow to turn ({minimum} in)")
        elif part.kind == "rounded_solid":
            seam = ps.seams.get(f"{part.id}:m0")
            if seam is None or seam.gap is None:
                where.append(f"{part.id}: no stuffing gap")
            else:
                gap = (seam.gap[1] - seam.gap[0]) * min(side_lengths(ps, seam))
                if gap < minimum:
                    where.append(f"{part.id}: stuffing gap {gap:.3f} in is too short to turn ({minimum} in)")
    for piece in pattern.pieces.values():
        stitch, cut = Polygon(piece.stitch), Polygon(piece.cut)
        margin = min(stitch.exterior.distance(Point(p)) for p in piece.cut)
        if not cut.contains(stitch) or margin < settings.seam_allowance_in - 1e-6:
            where.append(f"{piece.name}: seam allowance {margin:.3f} in is less than {settings.seam_allowance_in} in")
    for m in pattern.attachments:
        if not m.parent_notches or len(m.parent_notches) != len(m.child_notches):
            where.append(f"{m.child}: notches on {m.parent} and on the part do not match")
        if m.gap_in > settings.seam_allowance_in:
            where.append(f"{m.child}: opening sits {m.gap_in:.3f} in off {m.parent} (more than the seam allowance)")
        on_parent = sum(LineString(line).length for _, line in m.outline if len(line) > 1)
        on_child = sum(LineString(line).length for _, line in m.child_outline if len(line) > 1)
        if abs(on_parent / on_child - 1) > settings.max_flatten_stretch:
            where.append(f"{m.child}: opening {on_child:.3f} in vs its line on {m.parent} {on_parent:.3f} in")
    return CheckResult(5, "Sewable", not where, "all pass" if not where else f"{len(where)} problem(s)",
                       f"turnable ≥ {minimum} in; allowance {settings.seam_allowance_in} in", where)

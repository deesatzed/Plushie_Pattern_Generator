"""The whole pipeline: approved part kit -> pieces -> stuffing -> outputs -> the seven checks.

The PDF is written to a working file, checked (check 2), and only moved to `pdf_path`
when all seven checks pass. A failed pattern never leaves a printable PDF behind.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from plush.checks import CheckResult, check_flattening_stretch, check_seams_match, check_sewable, check_stuffed_shape
from plush.directions import check_directions, directions
from plush.finishing import Pattern, finish
from plush.geometry.assemble import assemble
from plush.layout import cutting_layout
from plush.materials import materials
from plush.panels import build_panels
from plush.parts import Kit
from plush.pdf import check_true_scale, sheet_layout, write_pdf
from plush.settings import Settings
from plush.stuffing import stuff_all


@dataclass
class PatternResult:
    checks: list[CheckResult]  # all seven, in order
    pattern: Pattern
    pdf: Path | None  # set only when every check passed

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def build_pattern(kit: Kit, finished_height_in: float, settings: Settings, pdf_path: Path,
                  version_check: CheckResult) -> PatternResult:
    placed = assemble(kit, finished_height_in)
    ps = build_panels(kit, placed, settings)
    stuffing = stuff_all(ps, settings)
    pattern = finish(kit, placed, ps, settings)
    fabric = cutting_layout(pattern, settings)
    steps = directions(kit, placed, pattern)
    mats = materials(kit, placed, fabric, stuffing)
    sheet = sheet_layout(pattern, settings)
    checks = [
        check_seams_match(pattern, settings),
        check_stuffed_shape(stuffing, settings),
        check_flattening_stretch(pattern, settings),
        check_sewable(kit, placed, pattern, settings),
        check_directions(pattern, steps),
        version_check,
    ]
    title = f"{kit.character_name}, {finished_height_in:g} in tall"
    working = pdf_path.with_suffix(".checking.pdf")
    write_pdf(str(working), pattern, sheet, fabric, steps, mats, settings, title, checks)
    checks.insert(1, check_true_scale(str(working), pattern, sheet, settings))
    checks.sort(key=lambda c: c.number)
    if all(c.passed for c in checks):
        # write again so the cover lists check 2 as well; the drawing is identical
        write_pdf(str(working), pattern, sheet, fabric, steps, mats, settings, title, checks)
        os.replace(working, pdf_path)
        return PatternResult(checks, pattern, pdf_path)
    working.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)
    return PatternResult(checks, pattern, None)

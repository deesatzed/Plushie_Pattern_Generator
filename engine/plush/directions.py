"""Step-by-step directions, written from the actual pieces, seams and attachments.

The order is fixed: cut, mark, add surface features while pieces are flat, sew each part
(closed parts leave their back-seam gap open), turn and stuff, close gaps, then attach
parts to each other by hand. Check 6 confirms every piece, seam and attachment appears
in exactly one step of the right kind, and that features come before their part is sewn.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from plush.checks import CheckResult
from plush.finishing import Pattern
from plush.geometry.assemble import Placed
from plush.parts import FeatureMethod, Kit
from plush.seams import side_points


@dataclass
class Step:
    number: int
    kind: str  # "cut", "mark", "feature", "sew", "stuff", "close", "attach"
    text: str
    part: str | None = None  # the part this step works on
    pieces: list[str] = field(default_factory=list)  # pieces cut in a "cut" step
    seams: list[str] = field(default_factory=list)  # seams sewn in a "sew" step
    attachments: list[str] = field(default_factory=list)  # placed child names in an "attach" step
    highlight: list[tuple[str, np.ndarray]] = field(default_factory=list)  # (piece, flat line) to draw in red


def _sewing_order(seam_id: str, has_gap: bool) -> tuple:
    """Panels joined to each other first, then bases and soles, and the seam with the stuffing gap last."""
    kind = seam_id.split(":")[1]
    stem = kind.rstrip("0123456789")
    number = int(kind[len(stem):] or 0)
    return (has_gap, stem in ("b", "sole"), stem, number)


def _labels(pattern: Pattern, names: list[str]) -> str:
    return "; ".join(pattern.pieces[n].label for n in names)


def directions(kit: Kit, placed: dict[str, Placed], pattern: Pattern) -> list[Step]:
    steps: list[Step] = []
    names = {p.id: p.name for p in kit.parts}

    def add(kind: str, text: str, **kw) -> None:
        steps.append(Step(len(steps) + 1, kind, text, **kw))

    by_colour: dict[str, list[str]] = {}
    for piece in pattern.pieces.values():
        by_colour.setdefault(piece.colour, []).append(piece.name)
    for colour, pieces in by_colour.items():
        add("cut", f"From the fabric in colour {colour}, cut: {_labels(pattern, pieces)}. "
                   "Cut on the solid line. Copies marked 'mirrored' are cut with the pattern turned over.",
            pieces=pieces)
    add("mark", "Transfer every notch, the stuffing gaps and all placement marks to the wrong side of each piece.")

    for name, panel, label, line in pattern.features:
        feature = next(p for p in kit.parts if p.id == placed[name].part_id)
        parent_part = placed[placed[name].parent].part_id
        where = pattern.pieces[panel].label
        if feature.method is FeatureMethod.SAFETY_EYE:
            text = f"{label}: push the safety eye through a small hole at the centre of the marked circle on {where}, then fix the washer on the wrong side."
        elif feature.method is FeatureMethod.EMBROIDERY:
            text = f"{label}: embroider inside the marked outline on {where}."
        else:
            text = f"{label}: stitch the felt template inside the marked outline on {where}."
        add("feature", text, part=parent_part, highlight=[(panel, line)])

    parts_in_order = list(dict.fromkeys(p.part for p in pattern.panels.panels.values()))
    for part in parts_in_order:
        seams = sorted((sid for sid, s in pattern.panels.seams.items() if s.part == part),
                       key=lambda sid: _sewing_order(sid, pattern.panels.seams[sid].gap is not None))
        for sid in seams:
            seam = pattern.panels.seams[sid]
            letter = pattern.seam_letters[sid]
            (a, _), (b, _) = seam.sides
            if a == b:
                text = f"Seam {letter}: fold {pattern.pieces[a].label} right sides together and sew seam {letter}, matching the {letter} notches."
            else:
                text = (f"Seam {letter}: place {pattern.pieces[a].label} and {pattern.pieces[b].label} right sides "
                        f"together, match the {letter} notches and sew along the stitch line.")
            if seam.gap is not None:
                text += " Leave the marked gap open for turning and stuffing."
            if pattern.pieces[a].mirrored:
                text += f" Do the same for the second {names[part]}."
            add("sew", text, part=part, seams=[sid],
                highlight=[(side[0], side_points(pattern.panels, side)) for side in seam.sides])

    for part in parts_in_order:
        kind = next(p.kind for p in kit.parts if p.id == part)
        each = "each " if any(p.mirrored for p in pattern.pieces.values() if p.part == part) else ""
        if kind == "rounded_solid":
            add("stuff", f"Turn {names[part]} right side out through the gap and stuff it firmly.", part=part)
            add("close", f"Close the gap in {names[part]} with a ladder stitch.", part=part)
        elif kind == "limb":
            add("stuff", f"Turn {each}{names[part]} right side out through its open end and stuff it firmly, "
                         "leaving the last half inch unstuffed.", part=part)
        else:
            amount = next(p.puffiness for p in kit.parts if p.id == part)
            how = "stuff it lightly" if amount > 0 else "do not stuff it"
            add("stuff", f"Turn {each}{names[part]} right side out through its open base; {how}.", part=part)

    for m in pattern.attachments:
        child = placed[m.child]
        side = " (left)" if m.child.endswith("_left") else " (right)" if m.child.endswith("_right") else ""
        child_name, parent_name = names[child.part_id] + side, names[placed[m.parent].part_id]
        if child.kind == "rounded_solid":
            text = (f"Place {child_name} on {parent_name}, matching the notches on both, and ladder-stitch around "
                    "the marked lines.")
        else:
            text = (f"Turn under the open edge of {child_name}, place it on the marked line on {parent_name} with the "
                    "notches matching, and ladder-stitch it on.")
        add("attach", text, part=child.part_id, attachments=[m.child], highlight=list(m.outline))
    return steps


def check_directions(pattern: Pattern, steps: list[Step]) -> CheckResult:
    """Check 6: every piece cut once, every seam sewn once, every attachment made once, features first."""
    where = []

    def count(items, kind, attr):
        seen: dict[str, int] = {}
        for s in steps:
            if s.kind == kind:
                for x in getattr(s, attr):
                    seen[x] = seen.get(x, 0) + 1
        for x in items:
            if seen.get(x, 0) != 1:
                where.append(f"{x}: in {seen.get(x, 0)} {kind} steps (should be 1)")

    count(pattern.pieces, "cut", "pieces")
    count(pattern.panels.seams, "sew", "seams")
    count([m.child for m in pattern.attachments], "attach", "attachments")
    for f in (s for s in steps if s.kind == "feature"):
        first_sew = min((s.number for s in steps if s.kind == "sew" and s.part == f.part), default=None)
        if first_sew is not None and f.number > first_sew:
            where.append(f"step {f.number}: feature comes after {f.part} is sewn (step {first_sew})")
    return CheckResult(6, "Directions complete", not where,
                       f"{len(steps)} steps" if not where else f"{len(where)} problem(s)",
                       "each piece, seam and attachment exactly once; features first", where)

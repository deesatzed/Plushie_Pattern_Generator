"""Finished pattern pieces: stitch and cut lines, label, arrows, notches, stuffing gaps, placement marks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import igl
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from plush.allowance import cut_outline
from plush.attachments import AttachmentMark, attachment_marks
from plush.features import applique_templates, feature_marks
from plush.geometry.assemble import Placed
from plush.panels import Panel, PanelSet
from plush.parts import Kit
from plush.seams import notches, point_at_fraction, side_points
from plush.settings import Settings

ARROW = 0.4  # arrow length as a fraction of the piece's height


@dataclass
class Piece:
    name: str  # panel name, e.g. "head/gore3"
    part: str  # part id
    label: str
    colour: str
    cut_count: int
    mirrored: int
    stitch: np.ndarray  # (k, 2) closed stitch line, counter-clockwise, inches
    cut: np.ndarray  # (m, 2) closed cut line
    grain: np.ndarray  # (2, 2) arrow tail and head
    nap: np.ndarray | None  # (2, 2) direction the fur runs, if the piece has one
    notches: list[tuple[np.ndarray, str]] = field(default_factory=list)  # point, label
    gaps: list[np.ndarray] = field(default_factory=list)  # stretches of stitch line left open
    marks: list[tuple[np.ndarray, str]] = field(default_factory=list)  # placement lines, label


@dataclass
class Pattern:
    pieces: dict[str, Piece]
    seam_letters: dict[str, str]
    attachments: list[AttachmentMark]
    panels: PanelSet
    features: list[tuple[str, str, str, np.ndarray]] = field(default_factory=list)  # see feature_marks


def seam_letter(i: int) -> str:
    """A, B, ... Z, AA, AB, ..."""
    letters = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        letters = chr(65 + r) + letters
    return letters


def _role(panel: Panel, siblings: list[Panel]) -> str:
    kind = panel.name.split("/")[1]
    match = re.fullmatch(r"(gore|strip)(\d+)", kind)
    if match:
        total = sum(1 for p in siblings if p.name.split("/")[1].startswith(match.group(1)))
        return f"{match.group(1)} {match.group(2)} of {total}"
    return kind


def _label(panel: Panel, part_name: str, siblings: list[Panel]) -> str:
    text = f"{part_name} — {_role(panel, siblings)} — cut {panel.cut}"
    return text + (f" ({panel.mirrored} mirrored)" if panel.mirrored else "")


def _arrows(panel: Panel, stitch: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    """Grain runs along the piece (+y, as the piece stands); fur runs down the toy."""
    centre = np.array([stitch[:, 0].mean(), (stitch[:, 1].min() + stitch[:, 1].max()) / 2])
    half = ARROW * np.ptp(stitch[:, 1]) / 2
    up = np.array([centre - [0, half], centre + [0, half]])
    kind = panel.name.split("/")[1]
    if kind.startswith("gore"):
        return up, up[::-1]  # top of the toy at the top of the gore: fur runs down
    if kind.startswith("strip") or kind in ("front", "back"):
        return up, up  # fur runs from where the part is sewn on toward its tip
    return up, None  # bases and soles


def _stretch_between(points: np.ndarray, start: float, end: float) -> np.ndarray:
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))] / max(
        np.linalg.norm(np.diff(points, axis=0), axis=1).sum(), 1e-12)
    inner = points[(s > start) & (s < end)]
    return np.vstack([point_at_fraction(points, [start]), inner, point_at_fraction(points, [end])])


def finish(kit: Kit, placed: dict[str, Placed], ps: PanelSet, settings: Settings) -> Pattern:
    names = {p.id: p.name for p in kit.parts}
    letters = {sid: seam_letter(i) for i, sid in enumerate(sorted(ps.seams))}
    pieces: dict[str, Piece] = {}
    for panel in ps.panels.values():
        siblings = [p for p in ps.panels.values() if p.part == panel.part]
        loop = igl.boundary_loop(panel.faces)
        stitch = np.asarray(orient(Polygon(panel.uv[loop]), sign=1.0).exterior.coords)[:-1]
        grain, nap = _arrows(panel, stitch)
        pieces[panel.name] = Piece(panel.name, panel.part, _label(panel, names[panel.part], siblings),
                                   panel.colour, panel.cut, panel.mirrored, stitch,
                                   cut_outline(stitch, settings.seam_allowance_in), grain, nap)

    for sid, seam in ps.seams.items():
        for side, marks in zip(seam.sides, notches(ps, seam, settings.notch_spacing_in)):
            pieces[side[0]].notches += [(m, letters[sid]) for m in marks]
        if seam.gap is not None:
            for side in seam.sides:
                pieces[side[0]].gaps.append(_stretch_between(side_points(ps, side), *seam.gap))

    marks = attachment_marks(kit, ps, placed)
    for m in marks:
        child = placed[m.child]
        side = " (left)" if m.child.endswith("_left") else " (right)" if m.child.endswith("_right") else ""
        label = f"{names[child.part_id]}{side}"
        for panel_name, line in m.outline:
            pieces[panel_name].marks.append((line, label))
        for panel_name, point in m.parent_notches:
            pieces[panel_name].notches.append((point, label))
        if not m.child.endswith("_right"):  # a pair's pieces are cut twice from one pattern
            on = names[placed[m.parent].part_id]
            for panel_name, line in m.child_outline:
                pieces[panel_name].marks.append((line, f"sew to {on}"))
            for panel_name, point in m.child_notches:
                pieces[panel_name].notches.append((point, f"to {on}"))

    features = feature_marks(kit, ps, placed)
    for _, panel_name, label, line in features:
        pieces[panel_name].marks.append((line, label))
    for part_id, label, outline, cut, mirrored in applique_templates(kit, placed):
        part = next(p for p in kit.parts if p.id == part_id)
        centre = outline.mean(axis=0)
        half = 0.4 * np.ptp(outline[:, 1]) / 2
        pieces[f"{part_id}/template"] = Piece(f"{part_id}/template", part_id, label, part.colour, cut, mirrored,
                                               outline, outline.copy(),  # felt: cut on the line, no allowance
                                               np.array([centre - [0, half], centre + [0, half]]), None)
    return Pattern(pieces, letters, marks, ps, features)

"""Surface features (eyes, noses, mouths, patches): marks on the pieces they sit on, and felt templates.

A feature's outline is placed on the 3D model and projected onto its parent's pieces.
Appliqué features also become a template piece, cut from felt with no seam allowance.
"""

from __future__ import annotations

import numpy as np

from plush.attachments import PartSurface
from plush.geometry.assemble import Placed
from plush.geometry.feature import feature_outline
from plush.panels import PanelSet
from plush.parts import FeatureMethod, Kit

METHOD_WORDS = {
    FeatureMethod.SAFETY_EYE: "safety eye",
    FeatureMethod.EMBROIDERY: "embroider",
    FeatureMethod.APPLIQUE: "felt appliqué",
}


def feature_marks(kit: Kit, ps: PanelSet, placed: dict[str, Placed]) -> list[tuple[str, str, str, np.ndarray]]:
    """(placed feature name, parent panel, label, flat polyline) for every feature on the model."""
    by_id = {p.id: p for p in kit.parts}
    marks = []
    for name, pl in placed.items():
        if pl.kind != "surface_feature":
            continue
        part = by_id[pl.part_id]
        parent = placed[pl.parent]
        outline = feature_outline(part, pl.scale_in)
        closed = np.vstack([outline, outline[:1]])
        local = np.column_stack([closed, np.zeros(len(closed))])
        in_parent = (local @ pl.rotation.T + pl.translation - parent.translation) @ parent.rotation
        mapped, _ = PartSurface(ps, parent.part_id).flat(in_parent)
        side = " (left)" if name.endswith("_left") else " (right)" if name.endswith("_right") else ""
        label = f"{part.name}{side} — {METHOD_WORDS[part.method]}"
        run_panel, run = None, []
        for panel, uv in mapped:
            if panel != run_panel and run:
                marks.append((name, run_panel, label, np.array(run)))
                run = []
            run_panel = panel
            run.append(uv)
        marks.append((name, run_panel, label, np.array(run)))
    return marks


def applique_templates(kit: Kit, placed: dict[str, Placed]) -> list[tuple[str, str, np.ndarray, int, int]]:
    """(part id, label, outline, cut count, mirrored) for each appliqué feature, at true size."""
    templates, seen = [], set()
    for name, pl in placed.items():
        part = next(p for p in kit.parts if p.id == pl.part_id)
        if pl.kind != "surface_feature" or part.method is not FeatureMethod.APPLIQUE or part.id in seen:
            continue
        seen.add(part.id)
        cut, mirrored = (2, 1) if part.pair else (1, 0)
        templates.append((part.id, f"{part.name} — felt appliqué — cut {cut}" + (f" ({mirrored} mirrored)" if mirrored else ""),
                          feature_outline(part, pl.scale_in), cut, mirrored))
    return templates

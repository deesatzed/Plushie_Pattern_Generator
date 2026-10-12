"""Surface features (eyes, nose, mouth, patches): flat shapes laid on a part.

Local frame: the shape lies in the x-y plane, centred on the origin, facing +z.
They are drawn for the 3D view only; their sewing templates come later.
"""

from __future__ import annotations

import numpy as np
import trimesh

from plush.parts import FeatureShape, SurfaceFeature

SEGMENTS = 32


def feature_outline(part: SurfaceFeature, scale_in: float) -> np.ndarray:
    w, h = part.width * scale_in, part.height * scale_in
    if part.shape in (FeatureShape.CIRCLE, FeatureShape.OVAL):
        a = np.linspace(0, 2 * np.pi, SEGMENTS, endpoint=False)
        return np.column_stack([w / 2 * np.cos(a), h / 2 * np.sin(a)])
    if part.shape is FeatureShape.TRIANGLE:
        return np.array([[-w / 2, h / 2], [0, -h / 2], [w / 2, h / 2]])  # points down, like a nose
    return np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]])


def feature_mesh(part: SurfaceFeature, scale_in: float) -> trimesh.Trimesh:
    outline = feature_outline(part, scale_in)
    k = len(outline)
    vertices = np.vstack([np.column_stack([outline, np.zeros(k)]), [[0.0, 0.0, 0.0]]])
    faces = [[i, (i + 1) % k, k] for i in range(k)]  # fan from the centre, facing +z
    return trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=False)

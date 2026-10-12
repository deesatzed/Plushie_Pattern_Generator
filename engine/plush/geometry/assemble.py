"""Place every part on its parent at finished size; pairs become left/right copies."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from plush.geometry.feature import feature_mesh
from plush.geometry.flat_part import flat_part_mesh
from plush.geometry.limb import limb_mesh
from plush.geometry.rounded_solid import rounded_solid_mesh
from plush.parts import Kit

SINK = 0.25  # fraction of a rounded child's height sunk into its parent
FEATURE_LIFT_IN = 0.01  # gap between a surface feature and the surface (3D view only)
UP = np.array([0.0, 1.0, 0.0])
FRONT = np.array([0.0, 0.0, 1.0])


@dataclass
class Placed:
    """One part in character space (inches)."""

    part_id: str
    kind: str
    mesh: trimesh.Trimesh
    rotation: np.ndarray  # local -> world
    anchor: np.ndarray | None  # point on the parent's surface where it attaches
    parent: str | None  # name of the placed parent
    scale_in: float = 0.0  # inches per kit unit after scaling to the finished height


def _rotation(axis: np.ndarray, angle_deg: float) -> np.ndarray:
    return trimesh.transformations.rotation_matrix(np.radians(angle_deg), axis)[:3, :3]


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def _perpendicular(v: np.ndarray, n: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    p = v - np.dot(v, n) * n
    if np.linalg.norm(p) < 1e-6:
        p = fallback - np.dot(fallback, n) * n
    return _unit(p)


def _local_mesh(part, scale_in: float) -> trimesh.Trimesh:
    builders = {
        "rounded_solid": rounded_solid_mesh,
        "limb": limb_mesh,
        "flat_part": flat_part_mesh,
        "surface_feature": feature_mesh,
    }
    return builders[part.kind](part, scale_in)


def _surface_hit(parent: Placed, direction: np.ndarray, name: str) -> tuple[np.ndarray, np.ndarray]:
    origin = parent.mesh.bounds.mean(axis=0)
    locations, _, tri = parent.mesh.ray.intersects_location(
        origin[None, :], direction[None, :], multiple_hits=False
    )
    if len(locations) == 0:
        raise ValueError(f"part {name!r}: no surface found on {parent.part_id!r} in that direction")
    # blend the corner normals so a hit on a vertex or edge gives a symmetric, smooth normal
    corners = parent.mesh.faces[tri[0]]
    weights = trimesh.triangles.points_to_barycentric(
        parent.mesh.vertices[corners][None, :, :], locations[:1]
    )[0]
    normal = _unit(weights @ parent.mesh.vertex_normals[corners])
    return locations[0], normal


def _place(part, parent: Placed | None, scale_in: float, name: str, parent_name: str | None) -> Placed:
    local = _local_mesh(part, scale_in)
    if parent is None:
        return Placed(part.id, part.kind, local, np.eye(3), None, None)

    a = part.attach
    az, el = np.radians(a.azimuth_deg), np.radians(a.elevation_deg)
    direction = parent.rotation @ np.array([np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)])
    anchor, normal = _surface_hit(parent, _unit(direction), name)
    up, front = parent.rotation @ UP, parent.rotation @ FRONT

    if part.kind == "surface_feature":
        z = normal
        y = _perpendicular(up, z, front)
        rotation = _rotation(z, a.yaw_deg) @ np.column_stack([np.cross(y, z), y, z])
        position = anchor + normal * FEATURE_LIFT_IN
    else:
        y = normal
        z = _perpendicular(front, y, up)
        rotation = np.column_stack([np.cross(y, z), y, z])
        rotation = _rotation(up, a.yaw_deg) @ rotation
        grow = rotation[:, 1]
        pitch_axis = np.cross(grow, up)
        if np.linalg.norm(pitch_axis) < 1e-6:
            pitch_axis = rotation[:, 0]
        rotation = _rotation(_unit(pitch_axis), a.pitch_deg) @ rotation
        if part.kind == "rounded_solid":
            position = anchor + rotation[:, 1] * part.height * scale_in * (0.5 - SINK)
        else:
            position = anchor

    mesh = local.copy()
    mesh.vertices = mesh.vertices @ rotation.T + position
    return Placed(part.id, part.kind, mesh, rotation, anchor, parent_name)


def _mirror(placed: Placed, renames: dict[str, str]) -> Placed:
    flip = np.diag([-1.0, 1.0, 1.0])
    mesh = trimesh.Trimesh(
        vertices=placed.mesh.vertices @ flip, faces=placed.mesh.faces[:, ::-1], process=False
    )
    anchor = None if placed.anchor is None else placed.anchor @ flip
    parent = renames.get(placed.parent, placed.parent)
    return Placed(placed.part_id, placed.kind, mesh, flip @ placed.rotation, anchor, parent)


def assemble(kit: Kit, finished_height_in: float) -> dict[str, Placed]:
    """All parts placed in character space, scaled so the toy is exactly finished_height_in tall.

    A paired part (and everything attached to it) appears twice, named
    '<id>_left' and '<id>_right'; the right copy is the mirror of the left.
    """
    children: dict[str, list] = {p.id: [] for p in kit.parts}
    root = next(p for p in kit.parts if p.attach is None)
    for p in kit.parts:
        if p.attach is not None:
            children[p.attach.parent].append(p)

    placed: dict[str, Placed] = {}

    def build(part, parent_name: str | None, suffix: str, out: dict[str, Placed]) -> None:
        name = part.id + suffix
        parent = None if parent_name is None else out.get(parent_name) or placed[parent_name]
        out[name] = _place(part, parent, finished_height_in, name, parent_name)
        for child in children[part.id]:
            if not child.pair:
                build(child, name, suffix, out)
                continue
            # pairs only hang from symmetric, unpaired parts (enforced in parts.py)
            side, other = ("_left", "_right") if child.attach.azimuth_deg > 0 else ("_right", "_left")
            subtree: dict[str, Placed] = {}
            build(child, name, side, subtree)
            renames = {n: n[: -len(side)] + other for n in subtree}
            for sub_name, sub in subtree.items():
                out[sub_name] = sub
                out[renames[sub_name]] = _mirror(sub, renames)

    build(root, None, "", placed)

    lo = np.min([p.mesh.bounds[0] for p in placed.values()], axis=0)
    hi = np.max([p.mesh.bounds[1] for p in placed.values()], axis=0)
    k = finished_height_in / (hi[1] - lo[1])
    shift = np.array([0.0, -lo[1] * k, 0.0])  # toy stands on y = 0
    for p in placed.values():
        p.mesh.vertices = p.mesh.vertices * k + shift
        p.scale_in = finished_height_in * k
        if p.anchor is not None:
            p.anchor = p.anchor * k + shift
    return placed

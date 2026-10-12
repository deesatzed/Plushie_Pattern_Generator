import json

import numpy as np
import pytest
import trimesh

from plush.geometry.assemble import assemble
from plush.geometry.rounded_solid import rounded_solid_mesh
from plush.parts import RoundedSolid, parse_kit

from kits import BODY, bear


@pytest.fixture(scope="module")
def placed():
    return assemble(parse_kit(json.dumps(bear())), finished_height_in=12.0)


def test_part_meshes_face_outward(placed):
    for name, p in placed.items():
        if p.kind == "surface_feature":
            continue
        m = p.mesh
        outward = np.einsum("ij,ij->i", m.face_normals, m.triangles_center - m.vertices.mean(axis=0))
        assert outward.mean() > 0, name


def test_pair_copies_mirror_each_other(placed):
    for pid in ("ear", "arm", "eye"):
        left, right = placed[f"{pid}_left"].mesh.vertices, placed[f"{pid}_right"].mesh.vertices
        assert np.abs(left * [-1, 1, 1] - right).max() < 1e-9
        assert left[:, 0].mean() > 0  # the left copy is on the character's left (+x)


def test_children_attach_on_parent_surface(placed):
    for name, p in placed.items():
        if p.parent is None:
            continue
        _, distance, _ = trimesh.proximity.closest_point(placed[p.parent].mesh, p.anchor[None, :])
        assert distance[0] < 0.01, name


def test_assembly_height_equals_finished_height(placed):
    lo = np.min([p.mesh.bounds[0] for p in placed.values()], axis=0)
    hi = np.max([p.mesh.bounds[1] for p in placed.values()], axis=0)
    assert hi[1] - lo[1] == pytest.approx(12.0, abs=1e-6)
    assert lo[1] == pytest.approx(0.0, abs=1e-9)


def test_scale_rebuilds_parts_at_finished_size(placed):
    rebuilt = rounded_solid_mesh(RoundedSolid(**BODY), placed["body"].scale_in)
    assert rebuilt.extents == pytest.approx(placed["body"].mesh.extents, rel=1e-9)

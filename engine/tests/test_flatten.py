import numpy as np
import pytest

from plush.flatten import SeamLink, flatten, flatten_together
from plush.geometry.rounded_solid import deform, unit_direction
from plush.geometry.grid import grid_mesh
from plush.parts import RoundedSolid


def uv_area(uv, faces):
    a, b, c = uv[faces[:, 0]], uv[faces[:, 1]], uv[faces[:, 2]]
    return float(np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])).sum() / 2)


def test_cylinder_cut_along_a_line_unrolls_to_a_rectangle():
    cols, length = 48, 3.0
    phi = np.linspace(0, 2 * np.pi, cols + 1)
    y = np.linspace(0, length, 31)
    grid = np.stack([np.column_stack([np.cos(phi), np.full_like(phi, yy), np.sin(phi)]) for yy in y])
    V, F, _ = grid_mesh(grid, collapse_top=False, collapse_bottom=False)
    flat = flatten(V, F)
    perimeter = cols * 2 * np.sin(np.pi / cols)  # the mesh's polygon, radius 1
    assert flat.stretch.max() < 1e-3
    assert uv_area(flat.uv, F) == pytest.approx(perimeter * length, rel=1e-3)


def test_flat_input_stays_flat():
    gx, gy = np.meshgrid(np.linspace(0, 2, 9), np.linspace(0, 1, 5))
    grid = np.stack([gx, gy, np.zeros_like(gx)], axis=-1)
    V, F, _ = grid_mesh(grid, collapse_top=False, collapse_bottom=False)
    assert flatten(V, F).stretch.max() < 1e-9


def test_linked_seam_edges_get_equal_flat_lengths():
    # a gore of an oval solid: its two side edges differ in 3D, so linking them is a real test
    part = RoundedSolid(kind="rounded_solid", id="o", name="O", colour="#000000",
                        width=0.6, height=0.5, depth=0.3)
    theta, phi = np.linspace(0, np.pi, 31), np.linspace(0.3, 1.1, 9)
    V, F, idx = grid_mesh(deform(unit_direction(theta[:, None], phi[None, :]), part, 10.0), True, True)
    left, right = idx[:, 0], idx[:, -1]

    def edge_lengths(uv, chain):
        return np.linalg.norm(np.diff(uv[chain], axis=0), axis=1)

    free = flatten(V, F).uv
    assert np.abs(edge_lengths(free, left) / edge_lengths(free, right) - 1).max() > 1e-3
    linked = flatten_together([(V, F)], [SeamLink(0, left, 0, right)])[0].uv
    assert np.abs(edge_lengths(linked, left) / edge_lengths(linked, right) - 1).max() < 1e-4

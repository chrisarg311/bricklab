"""mesh_voxel: GLB -> stud/plate occupancy grid. Meshes are generated here,
so no downloaded models are needed."""
from pathlib import Path

import numpy as np
import trimesh

from ptb_ml.mesh_voxel import MeshVoxelReq, MeshVoxelSettings, run_mesh_voxelization

STUD = 0.008
PLATE = 0.0032


def _voxelize(tmp_path: Path, mesh: trimesh.Trimesh, **kw):
    path = tmp_path / "in.glb"
    mesh.export(path)
    settings = MeshVoxelSettings(**kw)
    result = run_mesh_voxelization(
        MeshVoxelReq(job_id="t", mesh_path=path, output_dir=tmp_path / "out"),
        settings,
    )
    assert result.ok, result.error
    data = np.load(result.voxel_path)
    return result, data["occupancy"], data["colors"]


def _box(x, y, z):
    """Box with its min corner at the origin."""
    m = trimesh.creation.box(extents=(x, y, z))
    m.apply_translation(m.extents / 2)
    return m


def test_anisotropic_scale(tmp_path):
    # 1 stud wide, 3 plates tall, 2 studs deep; target 2 studs on the long side
    mesh = _box(STUD, 3 * PLATE, 2 * STUD)
    result, occ, _ = _voxelize(tmp_path, mesh, target_studs=2, hollow_wall_studs=None)
    assert result.grid_shape == (1, 3, 2)
    assert occ.all()


def test_z_up_input(tmp_path):
    # Same box authored Z-up: its height is along z
    mesh = _box(STUD, 2 * STUD, 3 * PLATE)
    result, occ, _ = _voxelize(
        tmp_path, mesh, target_studs=2, up_axis="z", hollow_wall_studs=None
    )
    assert result.grid_shape == (1, 3, 2)
    assert occ.all()


def test_scale_ignores_mesh_units(tmp_path):
    # A 10 x 10 x 10 metre cube becomes 8 x 20 x 8 at target 8 studs
    result, occ, _ = _voxelize(
        tmp_path, _box(10, 10, 10), target_studs=8, hollow_wall_studs=None
    )
    assert result.grid_shape == (8, 20, 8)
    assert occ.all()


def test_hollow_walls(tmp_path):
    result, occ, _ = _voxelize(
        tmp_path, _box(10, 4, 10), target_studs=10, hollow_wall_studs=1
    )
    X, Y, Z = result.grid_shape
    assert (X, Y, Z) == (10, 10, 10)
    # 1 stud = 2.5 plates, so the floor and top keep 3 plates (within 1.5
    # studs of air); the layers between are 1-stud rings
    assert occ[:, :3, :].all() and occ[:, -3:, :].all()
    for y in range(3, Y - 3):
        layer = occ[:, y, :]
        assert layer[0, :].all() and layer[-1, :].all()
        assert layer[:, 0].all() and layer[:, -1].all()
        assert not layer[1:-1, 1:-1].any()


def test_open_floor(tmp_path):
    _, occ, _ = _voxelize(
        tmp_path, _box(10, 4, 10), target_studs=10, hollow_wall_studs=1, floor=False
    )
    assert not occ[1:-1, 0, 1:-1].any()
    assert occ[0, 0, :].all()


def test_snap_to_courses(tmp_path):
    # 3.5 plates tall rounds to 3; 4.6 plates rounds up to 6
    for plates, expected in [(3.5, 3), (4.6, 6)]:
        result, occ, _ = _voxelize(
            tmp_path, _box(2 * STUD, plates * PLATE, 2 * STUD),
            target_studs=2, hollow_wall_studs=None, snap_to_courses=True,
        )
        assert result.grid_shape[1] % 3 == 0
        assert occ.any(axis=(0, 2)).sum() == expected


def test_open_bottom_falls_back_to_slices(tmp_path):
    # Remove the bottom faces: a house shell with no floor
    mesh = _box(10, 4, 10)
    keep = mesh.face_normals[:, 1] > -0.5
    mesh.update_faces(keep)
    mesh.remove_unreferenced_vertices()
    result, occ, _ = _voxelize(tmp_path, mesh, target_studs=10, hollow_wall_studs=None)
    assert occ.all()


def test_face_colors(tmp_path):
    mesh = _box(10, 4, 10)
    mesh.visual.face_colors = [200, 30, 30, 255]
    _, occ, colors = _voxelize(tmp_path, mesh, target_studs=10, hollow_wall_studs=None)
    assert np.abs(colors[occ].astype(int) - [200, 30, 30]).max() <= 2


def test_uncolored_mesh_gets_a_color(tmp_path):
    _, occ, colors = _voxelize(tmp_path, _box(10, 4, 10), target_studs=10)
    assert occ.any()
    assert (colors[occ] > 0).any(axis=1).all()


def test_missing_file_is_not_ok(tmp_path):
    result = run_mesh_voxelization(
        MeshVoxelReq(job_id="t", mesh_path=tmp_path / "nope.glb", output_dir=tmp_path),
        MeshVoxelSettings(),
    )
    assert not result.ok

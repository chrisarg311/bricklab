"""Brick placement on small hand-made grids."""
from pathlib import Path

import numpy as np

from ptb_ml.brickification import BrickificationReq, BrickificationSettings, run_brickification
from ptb_ml.brickification.settings import BRICK_SHAPES


def _bricks(tmp_path: Path, occ: np.ndarray, shapes=None) -> list[list[int]]:
    """Returns [x, y, z, w, d, h] per brick."""
    np.savez(tmp_path / "occ.npz", occupancy=occ,
             colors=np.full(occ.shape + (3,), 200, np.uint8))
    settings = BrickificationSettings() if shapes is None else BrickificationSettings(
        brick_shapes=tuple(sorted(shapes, key=lambda s: -(s[0] * s[1] * s[2]))))
    res = run_brickification(
        BrickificationReq(job_id="t", voxel_path=tmp_path / "occ.npz", output_dir=tmp_path / "out"),
        settings,
    )
    assert res.ok, res.error
    return np.load(res.bricks_path)["bricks"][:, :6].tolist()


def test_block_becomes_one_2x4_brick(tmp_path):
    # 2 studs (x) x 3 plates (y) x 4 studs (z)
    assert _bricks(tmp_path, np.ones((2, 3, 4), bool)) == [[0, 0, 0, 2, 4, 3]]


def test_column_is_brick_plus_plate(tmp_path):
    assert _bricks(tmp_path, np.ones((1, 4, 1), bool)) == [
        [0, 0, 0, 1, 1, 3],
        [0, 3, 0, 1, 1, 1],
    ]


def test_bricks_stay_inside_occupancy(tmp_path):
    rng = np.random.default_rng(0)
    occ = rng.random((8, 9, 8)) > 0.3
    covered = np.zeros_like(occ, dtype=int)
    for x, y, z, w, d, h in _bricks(tmp_path, occ):
        covered[x:x + w, y:y + h, z:z + d] += 1
    assert (covered == occ).all()


def test_wall_along_x_needs_rotated_shapes(tmp_path):
    occ = np.ones((4, 3, 1), bool)              # 4 studs along x, 1 deep
    rotated = list(BRICK_SHAPES) + [(d, w, h) for w, d, h in BRICK_SHAPES]
    assert len(_bricks(tmp_path, occ)) > 1      # listed shapes only run along z
    assert _bricks(tmp_path, occ, rotated) == [[0, 0, 0, 4, 1, 3]]

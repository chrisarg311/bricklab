"""brick_optimizer on small hand-made grids."""
from pathlib import Path

import numpy as np

from ptb_ml.brick_optimizer import BrickOptReq, BrickOptSettings, run_brick_optimization
from ptb_ml.brickification import BrickificationReq, BrickificationSettings, run_brickification

WHITE, RED = (255, 255, 255), (196, 40, 28)


def _run(tmp_path: Path, occ, colors=None, solid=None, **kw):
    kw.setdefault("base_plate", False)
    kw.setdefault("color_smoothing", 0)
    colors = np.full(occ.shape + (3,), WHITE, np.uint8) if colors is None else colors
    extra = {} if solid is None else {"solid": solid}
    np.savez(tmp_path / "occ.npz", occupancy=occ, colors=colors, **extra)
    res = run_brick_optimization(
        BrickOptReq(job_id="t", voxel_path=tmp_path / "occ.npz", output_dir=tmp_path / "out"),
        BrickOptSettings(**kw),
    )
    assert res.ok, res.error
    return res, np.load(res.bricks_path)["bricks"]


def test_block_becomes_one_2x4_brick(tmp_path):
    _, b = _run(tmp_path, np.ones((2, 3, 4), bool))
    assert b[:, :6].tolist() == [[0, 0, 0, 2, 4, 3]]


def test_exact_cover_and_one_color_per_piece(tmp_path):
    rng = np.random.default_rng(1)
    occ = rng.random((8, 6, 8)) > 0.25
    colors = np.where(rng.random((8, 6, 8, 1)) > 0.5, WHITE, RED).astype(np.uint8)
    _, b = _run(tmp_path, occ, colors, drop_loose=False)
    covered = np.zeros(occ.shape, int)
    for x, y, z, w, d, h, *rgb in b:
        covered[x:x + w, y:y + h, z:z + d] += 1
        cells = colors[x:x + w, y:y + h, z:z + d][occ[x:x + w, y:y + h, z:z + d]]
        assert (cells == rgb).all()
    assert (covered == occ).all()


def test_only_kit_colors_and_catalog_parts(tmp_path):
    occ = np.ones((6, 6, 6), bool)
    colors = np.full(occ.shape + (3,), (40, 120, 200), np.uint8)    # blue
    res, b = _run(tmp_path, occ, colors)
    assert {tuple(c) for c in b[:, 6:9]} <= {WHITE, (33, 33, 33), RED}
    catalog = {(min(w, d), max(w, d), h) for w, d, h in BrickOptSettings().catalog}
    assert all((min(w, d), max(w, d), h) in catalog for w, d, h in b[:, 3:6])


def test_fewer_pieces_than_greedy(tmp_path):
    rng = np.random.default_rng(2)
    occ = np.repeat(rng.random((12, 4, 12)) > 0.2, 3, axis=1)     # whole courses
    _, b = _run(tmp_path, occ)
    np.savez(tmp_path / "g.npz", occupancy=occ,
             colors=np.full(occ.shape + (3,), WHITE, np.uint8))
    greedy = run_brickification(
        BrickificationReq(job_id="g", voxel_path=tmp_path / "g.npz", output_dir=tmp_path / "g"),
        BrickificationSettings(),
    )
    assert len(b) < greedy.num_bricks


def test_running_bond_locks_courses(tmp_path):
    # Wall 8 long, 2 courses: the top course should not repeat the joints
    # of the bottom one, so the wall holds together as one piece
    occ = np.ones((8, 6, 1), bool)
    res, b = _run(tmp_path, occ, catalog=((1, 1, 3), (1, 2, 3), (1, 4, 3), (1, 1, 1)))
    assert res.num_loose == 0
    joints = [{x for x, y, _, w, *_ in b if y == yy} for yy in (0, 3)]
    assert not (joints[0] & joints[1] - {0})


def test_floating_piece_gets_support(tmp_path):
    # A course floating one course above the ground, with solid material
    # below it: support is filled in and nothing is loose or dropped
    occ = np.zeros((4, 9, 2), bool)
    occ[:, 0:3] = True
    occ[:, 6:9] = True
    solid = np.ones_like(occ)
    res, _ = _run(tmp_path, occ, solid=solid)
    assert res.num_support_cells > 0
    assert res.num_loose == 0 and res.num_dropped == 0


def test_unsupportable_piece_is_dropped(tmp_path):
    occ = np.zeros((4, 9, 2), bool)
    occ[:, 0:3] = True
    occ[:, 6:9] = True
    res, b = _run(tmp_path, occ, solid=occ.copy())                  # air between
    assert res.num_dropped > 0
    assert (b[:, 1] == 0).all()


def test_base_plate_under_centered_model(tmp_path):
    res, b = _run(tmp_path, np.ones((2, 3, 4), bool), base_plate=True)
    assert res.base_plate_size == 16
    assert b[0, :6].tolist() == [0, 0, 0, 16, 16, 1]
    # Model lifted one plate and centered on the 16x16 plate
    assert b[1, :6].tolist() == [7, 1, 6, 2, 4, 3]
    # Green base plate; the bricks stay in the kit colors
    assert tuple(b[0, 6:9]) == (75, 151, 74)
    assert tuple(b[1, 6:9]) == WHITE


def test_rank_colors_keeps_a_dark_model_apart(tmp_path):
    # Three dark colors (blue-grey wall, dark green roof, near-black trim):
    # nearest matching makes them all black; ranking keeps three colors
    occ = np.ones((6, 9, 6), bool)
    colors = np.zeros(occ.shape + (3,), np.uint8)
    colors[:, 0:3] = (60, 70, 90)        # wall, lightest
    colors[:, 3:6] = (10, 15, 12)        # trim, darkest
    colors[:, 6:9] = (0, 90, 40)         # roof, most saturated
    _, b = _run(tmp_path, occ, colors)
    by_y = {int(y): tuple(rgb) for _, y, _, _, _, _, *rgb in b}
    assert by_y[0] == WHITE and by_y[3] == (33, 33, 33) and by_y[6] == RED
    _, b = _run(tmp_path, occ, colors, color_mapping="nearest")
    assert {tuple(c) for c in b[:, 6:9]} == {(33, 33, 33)}


def test_rank_colors_single_color_model(tmp_path):
    # One light grey (Carlos's untextured mesh) -> white, not split
    occ = np.ones((4, 3, 4), bool)
    colors = np.full(occ.shape + (3,), (160, 165, 169), np.uint8)
    _, b = _run(tmp_path, occ, colors)
    assert {tuple(c) for c in b[:, 6:9]} == {WHITE}


def test_smoothing_removes_speckles(tmp_path):
    # A white wall with scattered single red cells becomes all white
    occ = np.ones((8, 6, 8), bool)
    colors = np.full(occ.shape + (3,), WHITE, np.uint8)
    for x, z in [(1, 1), (5, 2), (3, 6)]:
        colors[x, :, z] = RED
    _, b = _run(tmp_path, occ, colors, color_smoothing=0)
    assert any(tuple(c) == RED for c in b[:, 6:9])
    _, b = _run(tmp_path, occ, colors, color_smoothing=1)
    assert {tuple(c) for c in b[:, 6:9]} == {WHITE}

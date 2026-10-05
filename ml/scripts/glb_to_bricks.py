"""
GLB -> LEGO voxel grid -> bricks, once per brick catalog, with a report.

Used to decide which pieces belong in our catalog: run a model through each
greedy catalog and through the optimizer (20-part catalog, kit colors,
heights rounded to brick courses), and compare piece counts, unique parts
and how many cells fall back to 1x1 plates.

    PYTHONPATH=ml/src python ml/scripts/glb_to_bricks.py model.glb \
        --studs 32 --up y --hollow 2 --out ml/tmp/bricks/model
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from ptb_ml.brickification import (
    BrickificationReq,
    BrickificationSettings,
    run_brickification,
)
from ptb_ml.brickification.settings import BRICK_SHAPES
from ptb_ml.brick_optimizer import BrickOptReq, BrickOptSettings, run_brick_optimization
from ptb_ml.instructions.glb_builder import build_glb
from ptb_ml.instructions.settings import InstructionsSettings
from ptb_ml.mesh_voxel import MeshVoxelReq, MeshVoxelSettings, run_mesh_voxelization


def _with_rotations(shapes) -> list[tuple[int, int, int]]:
    """Add the 90-degree twin (d, w, h) of every shape. The engine only
    places a shape in the orientation it is listed in."""
    out = []
    for w, d, h in shapes:
        for s in ((w, d, h), (d, w, h)):
            if s not in out:
                out.append(s)
    return out


EXTRA_SHAPES = [(1, 6, 1), (1, 8, 1), (1, 6, 3), (1, 8, 3)]

CATALOGS: dict[str, list[tuple[int, int, int]]] = {
    "current": list(BRICK_SHAPES),
    "rotated": _with_rotations(BRICK_SHAPES),
    "rotated+1x6/1x8": _with_rotations(list(BRICK_SHAPES) + EXTRA_SHAPES),
}


def _settings(shapes) -> BrickificationSettings:
    return BrickificationSettings(
        brick_shapes=tuple(sorted(shapes, key=lambda s: -(s[0] * s[1] * s[2])))
    )


def part_name(w: int, d: int, h: int) -> str:
    """Rotations are the same physical part: 1x6 and 6x1 are both '1x6'."""
    a, b = sorted((w, d))
    return f"{a}x{b} {'brick' if h == 3 else 'plate'}"


def _report(bricks: np.ndarray, seconds: float) -> dict:
    parts = Counter(part_name(*map(int, b[3:6])) for b in bricks)
    colored = {(part_name(*map(int, b[3:6])), tuple(map(int, b[6:9]))) for b in bricks}
    cells = int((bricks[:, 3] * bricks[:, 4] * bricks[:, 5]).sum()) if len(bricks) else 0
    ones = parts.get("1x1 plate", 0)
    return {
        "total_pieces": int(len(bricks)),
        "unique_parts": len(parts),
        "unique_part_colors": len(colored),
        "colors": len({c for _, c in colored}),
        "one_by_one_plates": ones,
        "one_by_one_share": round(ones / len(bricks), 3) if len(bricks) else 0.0,
        "cells_per_piece": round(cells / len(bricks), 2) if len(bricks) else 0.0,
        "seconds": round(seconds, 2),
        "parts": dict(parts.most_common()),
    }


def _bricks_glb(bricks: np.ndarray, grid_y: int, path: Path) -> None:
    """build_glb negates y (the old TSDF grids were y-down). Ours is y-up,
    so mirror first to keep the model upright."""
    flipped = bricks.copy()
    flipped[:, 1] = grid_y - bricks[:, 1] - bricks[:, 5]
    build_glb(flipped, InstructionsSettings(), path)


OPTIMIZED = "optimized-20"


def _optimized(args, out: Path) -> dict:
    """Voxelize in whole brick courses with an open floor, then tile with
    the CP-SAT optimizer (20-part catalog, white/black/red)."""
    vox = run_mesh_voxelization(
        MeshVoxelReq(job_id=args.mesh.stem, mesh_path=args.mesh, output_dir=out),
        MeshVoxelSettings(
            target_studs=args.studs,
            up_axis=args.up,
            hollow_wall_studs=args.hollow or None,
            snap_to_courses=True,
            floor=False,
        ),
    )
    if not vox.ok:
        raise SystemExit(vox.error)
    t = time.perf_counter()
    res = run_brick_optimization(
        BrickOptReq(job_id=OPTIMIZED, voxel_path=vox.voxel_path, output_dir=out),
        BrickOptSettings(),
    )
    if not res.ok:
        raise SystemExit(res.error)
    bricks = np.load(res.bricks_path)["bricks"]
    report = _report(bricks, time.perf_counter() - t)
    report["dropped_loose"] = res.num_dropped
    report["support_cells"] = res.num_support_cells
    (out / "report.json").write_text(json.dumps(report, indent=2))
    _bricks_glb(bricks, vox.grid_shape[1], out / "bricks.glb")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("mesh", type=Path)
    ap.add_argument("--studs", type=int, default=32)
    ap.add_argument("--up", choices=["y", "z"], default="y")
    ap.add_argument("--hollow", type=int, default=2, help="wall studs; 0 = solid")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--catalog", choices=list(CATALOGS) + [OPTIMIZED], action="append")
    args = ap.parse_args()
    chosen = args.catalog or list(CATALOGS) + [OPTIMIZED]

    out = args.out or Path("ml/tmp/bricks") / args.mesh.stem
    vox = run_mesh_voxelization(
        MeshVoxelReq(job_id=args.mesh.stem, mesh_path=args.mesh, output_dir=out),
        MeshVoxelSettings(
            target_studs=args.studs,
            up_axis=args.up,
            hollow_wall_studs=args.hollow or None,
        ),
    )
    if not vox.ok:
        raise SystemExit(vox.error)
    X, Y, Z = vox.grid_shape
    print(f"grid {X}x{Y}x{Z} (studs x plates x studs), {vox.num_occupied} cells")

    summary = {}
    for name in [c for c in chosen if c in CATALOGS]:
        cat_dir = out / name.replace("/", "_").replace("+", "_")
        t = time.perf_counter()
        res = run_brickification(
            BrickificationReq(job_id=name, voxel_path=vox.voxel_path, output_dir=cat_dir),
            _settings(CATALOGS[name]),
        )
        if not res.ok:
            raise SystemExit(res.error)
        bricks = np.load(res.bricks_path)["bricks"]
        report = _report(bricks, time.perf_counter() - t)
        (cat_dir / "report.json").write_text(json.dumps(report, indent=2))
        _bricks_glb(bricks, Y, cat_dir / "bricks.glb")
        summary[name] = report

    if OPTIMIZED in chosen:
        summary[OPTIMIZED] = _optimized(args, out / "optimized")

    cols = ["total_pieces", "unique_parts", "unique_part_colors", "one_by_one_share",
            "cells_per_piece", "seconds"]
    print(f"\n{'catalog':<18}" + "".join(f"{c:>20}" for c in cols))
    for name, r in summary.items():
        print(f"{name:<18}" + "".join(f"{r[c]:>20}" for c in cols))
    for name, r in summary.items():
        print(f"\n{name}: " + ", ".join(f"{k} x{v}" for k, v in r["parts"].items()))


if __name__ == "__main__":
    main()

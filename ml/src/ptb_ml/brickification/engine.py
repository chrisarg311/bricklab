from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
import numpy as np

from .colors import snap_to_lego_color
from .models import Brick, BomEntry, BrickificationReq, BrickificationResult
from .settings import BrickificationSettings


log = logging.getLogger(__name__)

def _load_voxels(
    voxel_path: Path,
) -> tuple[np.ndarray, np.ndarray]:
    """Load occupancy and color grids form npz"""
    data= np.load(voxel_path)
    occupancy= data["occupancy"].astype(bool)
    colors= data["colors"].astype(np.uint8)
    return occupancy, colors


def _can_plce(
    brick: tuple[int, int, int, int, int, int],
    occupancy: np.ndarray,
    placed: np.ndarray,
    settings: BrickificationSettings,
) -> bool:
    """
    Check if a brick can be placed at (x, y, z) with shape (w, h, d).
    Rules: 
        - All voxels must be occupied
        - No voxels already covered by placed bricks
        - Sufficient support from layer below(except ground)
    """

    x, y, z, w, h, d = brick
    X, Y, Z = occupancy.shape

    if x + w > X or y + h > Y or z + d > Z:
        return False
    
    region= occupancy[x:x+w, y:y+h, z:z+d]
    if not region.all():
        return False
    
    if placed[x:x+w, y:y+h, z:z+d].any():
        return False
    
    """if y > 0:
        support_region= placed[x:x+w, y-1:y, z:z+d]
        support_ratio= support_region.mean()
        if support_ratio < settings.min_support_ratio:
            return False"""

    return True

def _check_stagger(
        x: int, z: int, y: int,
        w: int, d: int,
        placed_bricks: list[Brick],
        settings: BrickificationSettings,
) -> bool:
   """Ensure brick is staggered relative to the bricks directly below
   Returns True if stagger is satisfied or no bricks below
   """
   if y == 0:
       return True
   
   for b in placed_bricks:
       # check if there is a brick directly below
       if b.y + b.h != y:
           continue
       
       """x_overlap = min(x + w, b.x + b.w) - max(x, b.x)
       z_overlap = min(z + d, b.z + b.d) - max(z, b.z)

       if x_overlap <=0 or z_overlap <= 0:
           continue"""
       
       if x == b.x and z == b.z and w == b.w and d == b.d:
            return False
       


   return True


def _get_region_color(
    x: int, y: int, z: int,
    w: int, h: int, d: int,
    colors: np.ndarray,
    snap: bool,
) -> tuple[int, int, int]:
    """Aveage color over brick region, optionally snap to Lego color"""

    region = colors[x:x+w, y:y+h, z:z+d]
    avg = region.mean(axis=(0, 1, 2))
    r, g, b = int(avg[0]), int(avg[1]), int(avg[2])
    if snap:
        r,g,b = snap_to_lego_color(r, g, b)

    return r, g, b

def _brickify_layer(
    y: int,
    h: int,
    occupancy: np.ndarray,
    colors: np.ndarray,
    placed: np.ndarray,
    placed_bricks: list[Brick],
    settings: BrickificationSettings,
) -> list[Brick]:
    """
    Greedily place bricks in a single layer (y to y+h)
    Tries largist bricks first, enforces stagger
    """

    X, _, Z = occupancy.shape
    layer_bricks: list[Brick] = []

    shapes= [s for s in settings.brick_shapes if s[2]==h]

    for x in range(X):
        for z in range(Z):
            if placed[x,y,z]:
                continue
            if not occupancy[x,y,z]:
                continue
        
            placed_here= False
            for w,d,bh in shapes:
                if _can_plce((x, y, z, w, d, bh), occupancy, placed, settings):
                    if _check_stagger(x, z, y,w, d, placed_bricks, settings):
                        r, g, b = _get_region_color(
                            x, y, z, w, bh, d, colors,
                            settings.snap_to_lego_colors
                        )
                        brick= Brick(
                            x=x, y=y, z=z,
                            w=w, h=bh, d=d,
                            color_r=r, color_g=g, color_b=b,
                        )
                        placed[x:x+w, y:y+bh, z:z+d]= True
                        layer_bricks.append(brick)
                        placed_bricks.append(brick)
                        placed_here= True
                        break


            if not placed_here and not placed[x, y, z]:
                r, g, b = _get_region_color(
                    x, y, z, 1, 1, 1, colors,
                    settings.snap_to_lego_colors
                )
                brick = Brick(
                    x=x, y=y, z=z,
                    w=1, d=1, h=1,
                    color_r=r, color_g=g, color_b=b,
                    )
                placed[x:x+1, y:y+1, z:z+1] = True
                layer_bricks.append(brick)
                placed_bricks.append(brick)

    return layer_bricks


def _build_bom(bricks: list[Brick]) -> list[BomEntry]:
    """Aggregate bricks into a bill of materials."""
    counts: dict[tuple, int] = defaultdict(int)
    for b in bricks:
        key = (b.w, b.d, b.h, b.color_r, b.color_g, b.color_b)
        counts[key] += 1

    return [
        BomEntry(
            shape=(w, d, h),
            color_r=r,
            color_g=g,
            color_b=b,
            quantity=qty,
        )
        for (w, d, h, r, g, b), qty in sorted(
            counts.items(), key=lambda x: -x[1]
        )
    ]


def run_brickification(
    req: BrickificationReq,
    settings: BrickificationSettings,
) -> BrickificationResult:
    req.output_dir.mkdir(parents=True, exist_ok=True)
    bricks_path = req.output_dir / "bricks.npz"
    bom_path = req.output_dir / "bom.json"

    if not req.voxel_path.exists():
        return BrickificationResult(
            job_id=req.job_id,
            ok=False,
            bricks_path=bricks_path,
            bom_path=bom_path,
            output_dir=req.output_dir,
            num_bricks=0,
            num_bom_entries=0,
            error=f"voxel_path does not exist: {req.voxel_path}",
        )

    log.info("Loading occupancy grid...")
    occupancy, colors = _load_voxels(req.voxel_path)
    X, Y, Z = occupancy.shape
    log.info(f"Grid: {X}x{Y}x{Z}, occupied: {occupancy.sum()}")

    placed = np.zeros((X, Y, Z), dtype=bool)
    all_bricks: list[Brick] = []

    # Process layer by layer bottom-up
    # Try brick height (3 plates) first, then plate height (1 plate)
    y = 0
    while y < Y:
        # Try to place 3-plate bricks first
        if y + 3 <= Y and occupancy[:, y:y+3, :].any():
            layer_bricks = _brickify_layer(
                y, 3, occupancy, colors, placed, all_bricks, settings
            )
            all_bricks.extend(
                [b for b in layer_bricks if b not in all_bricks]
            )

        # Then fill remaining with plates
        if occupancy[:, y:y+1, :].any():
            layer_bricks = _brickify_layer(
                y, 1, occupancy, colors, placed, all_bricks, settings
            )
            all_bricks.extend(
                [b for b in layer_bricks if b not in all_bricks]
            )

        y += 1

    log.info(f"Placed {len(all_bricks)} bricks")

    # Build BOM
    bom = _build_bom(all_bricks)
    log.info(f"BOM: {len(bom)} unique entries")

    # Save bricks as npz
    if all_bricks:
        brick_array = np.array([
            [b.x, b.y, b.z, b.w, b.d, b.h, b.color_r, b.color_g, b.color_b]
            for b in all_bricks
        ], dtype=np.int32)
    else:
        brick_array = np.zeros((0, 9), dtype=np.int32)

    np.savez_compressed(bricks_path, bricks=brick_array)

    # Save BOM as JSON
    bom_payload = {
        "job_id": req.job_id,
        "total_bricks": len(all_bricks),
        "unique_entries": len(bom),
        "entries": [
            {
                "shape": list(e.shape),
                "color": [e.color_r, e.color_g, e.color_b],
                "quantity": e.quantity,
            }
            for e in bom
        ],
    }
    bom_path.write_text(
        json.dumps(bom_payload, indent=2), encoding="utf-8"
    )

    return BrickificationResult(
        job_id=req.job_id,
        ok=True,
        bricks_path=bricks_path,
        bom_path=bom_path,
        output_dir=req.output_dir,
        num_bricks=len(all_bricks),
        num_bom_entries=len(bom),
    )
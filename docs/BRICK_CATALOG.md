# Brick catalog

The bricks the optimizer (`ml/src/ptb_ml/brick_optimizer`) is allowed to use. The list is defined in code as
`CATALOG_20` in `brick_optimizer/settings.py`; this page explains it and shows how often each shape is used.

## Sizes

| Unit | Size | In the grid |
|---|---|---|
| Stud (width and depth) | 8 mm | 1 cell |
| Plate (height) | 3.2 mm | 1 cell |
| Brick (height) | 9.6 mm | 3 cells (one "course") |

A shape written W×D is W studs by D studs. A turned brick (2×4 vs 4×2) is the same part.

## The 20 shapes

| Shape | Kind | Used in tests so far |
|---|---|---|
| 1×1, 1×2, 1×3, 1×4, 1×6, 1×8 | Brick (3 plates tall) | Yes |
| 2×2, 2×3, 2×4, 2×6, 2×8 | Brick (3 plates tall) | Yes |
| 1×1, 1×2, 1×4, 1×6, 1×8 | Plate (1 plate tall) | Not yet (see below) |
| 2×2, 2×4, 2×6, 2×8 | Plate (1 plate tall) | Not yet (see below) |

Plus one **base plate** under every model, counted as one part: the smallest of 16×16, 32×32 or 48×48 studs that
fits the model.

The plates are unused because the voxel step rounds every height to whole brick courses, so every layer is filled
with full-height bricks. Those 9 plate slots are free for other parts later, for example roof slopes or corner bricks.

## Colors

Bricks come in **white, black and red** only. The base plate is **green**. Each model's own colors are mapped onto
these by rank: its most saturated color becomes red, and the rest go by lightness (lightest white, darkest black).

## How often each shape is used

Totals over four test houses at 16 studs wide (570 bricks, base plates not counted). "Share of volume" is how much
of the house each shape builds.

| Brick | Count | Share of bricks | Share of volume |
|---|---|---|---|
| 2×8 | 92 | 16% | 37% |
| 2×6 | 58 | 10% | 17% |
| 2×4 | 44 | 8% | 9% |
| 1×8 | 40 | 7% | 8% |
| 2×3 | 50 | 9% | 7% |
| 1×3 | 82 | 14% | 6% |
| 1×4 | 54 | 9% | 5% |
| 1×6 | 26 | 5% | 4% |
| 2×2 | 27 | 5% | 3% |
| 1×2 | 45 | 8% | 2% |
| 1×1 | 52 | 9% | 1% |

The large bricks (2×8, 2×6, 2×4, 1×8) build about 70% of the volume across the test houses. Small bricks (1×1, 1×2, 1×3) are many in
number but fill gaps at windows, doors, color edges and roof steps.

Pieces per house, including the base plate:

| House | 16 studs | 20 studs | 24 studs |
|---|---|---|---|
| Simple low-poly house | 120 | 209 | 329 |
| House (Fishboe) | 173 | 319 | 348 |
| Halloween house | 233 | 418 | 549 |
| Carlos's photo-to-model output | 48 | 75 | 118 |

Larger sizes keep more detail (window frames, door trim, steps) but use more bricks; 16 studs keeps every test
house under 300 pieces.

## Reference

Shapes and sizes follow the standard parts listed in the public BrickLink catalog
(https://www.bricklink.com/v2/search.page?q=brick#T=P). It was used only as a reference for which shapes are
common; no data from it is copied into this repo. The catalog itself is not open source.

## Changing the catalog

Edit `CATALOG_20` in `ml/src/ptb_ml/brick_optimizer/settings.py`. Each entry is `(width, depth, height)` with height
in plates: 3 for a brick, 1 for a plate. The catalog must keep a 1×1 plate so every cell can always be covered.
To see how a change affects piece counts, run:

```
PYTHONPATH=ml/src python ml/scripts/glb_to_bricks.py <model.glb> --studs 16 --hollow 2 --catalog optimized-20
```

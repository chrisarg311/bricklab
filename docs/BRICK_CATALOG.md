# Brick catalog

The bricks the optimizer (`ml/src/ptb_ml/brick_optimizer`) is allowed to use. The list is defined in code as
`CATALOG_20` in `brick_optimizer/settings.py`; this page explains it, shows how often each shape is used, and
lists the store part numbers and prices used to price a kit.

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
| 1×1, 1×2, 1×4, 1×6, 1×8 | Plate (1 plate tall), mosaic style | Not in 3D builds (see below) |
| 2×2, 2×4, 2×6, 2×8 | Plate (1 plate tall), mosaic style | Not in 3D builds (see below) |

Plus one **base plate** under every model, counted as one part: 16×16 or 32×32 studs, whichever is the smallest
that fits the model (48×48 is used only if neither fits, and isn't sold in the store).

The 9 plates are for the mosaic style: a flat picture, one plate tall, laid on the base plate. 3D builds don't use
them, because the voxel step rounds every height to whole brick courses, so every layer is filled with full-height
bricks.

## Colors

Bricks come in **white, black and red** only. The base plate is **green**. Each model's own colors are mapped onto
these by rank: its most saturated color becomes red, and the rest go by lightness (lightest white, darkest black).
Small specks of color are cleaned up, but any brick you can see from outside keeps its color unless it is a lone
speck; only bricks hidden inside the walls change color, so they can join into larger bricks.

## How often each shape is used

Totals over four test houses at 16 studs wide (644 bricks, base plates not counted). "Share of volume" is how much
of the house each shape builds.

| Brick | Count | Share of bricks | Share of volume |
|---|---|---|---|
| 2×8 | 91 | 14% | 36% |
| 2×6 | 50 | 8% | 15% |
| 2×4 | 43 | 7% | 9% |
| 1×8 | 39 | 6% | 8% |
| 1×3 | 92 | 14% | 7% |
| 1×4 | 67 | 10% | 7% |
| 1×6 | 34 | 5% | 5% |
| 2×3 | 33 | 5% | 5% |
| 1×2 | 83 | 13% | 4% |
| 2×2 | 30 | 5% | 3% |
| 1×1 | 82 | 13% | 2% |

The large bricks (2×8, 2×6, 2×4, 1×8) build about two thirds of the volume across the test houses. Small bricks
(1×1, 1×2, 1×3) are many in number but fill gaps at windows, doors, color edges and roof steps.

Pieces per house, including the base plate:

| House | 16 studs | 20 studs | 24 studs |
|---|---|---|---|
| Simple low-poly house | 135 | 224 | 297 |
| House (Fishboe) | 196 | 349 | 484 |
| Halloween house | 267 | 462 | 592 |
| Carlos's photo-to-model output | 50 | 77 | 118 |

Larger sizes keep more detail (window frames, door trim, steps) but use more bricks; 16 studs keeps every test
house under 300 pieces.

## Ordering from the store

Every part maps to the Pick a Brick store (https://www.lego.com/en-us/pick-and-build/pick-a-brick), so a kit can
be ordered part by part. The **store ID** (design ID) is the shape: searching it in the store finds the part. The
**element ID** is the shape in one color, which is the item that is actually ordered. The data lives in
`ml/src/ptb_ml/brick_optimizer/store_parts.py`, and each `bom.json` line carries the store ID, element ID, unit
price and line total, plus an order total.

Prices are US dollars each and stock is as read from the US store on **2026-10-16**; both change over time.

| Part | Store ID | White | Black | Red (Bright Red) | Price each |
|---|---|---|---|---|---|
| Brick 1×1 | 3005 | 300501 | 300526 | 300521 | $0.07 |
| Brick 1×2 | 3004 | 300401 | 300426 | 300421 | $0.10 |
| Brick 1×3 | 3622 | 362201 | 362226 | 362221 | $0.14 |
| Brick 1×4 | 3010 | 301001 | 301026 | 301021 | $0.15 |
| Brick 1×6 | 3009 | 300901 | 300926 | 300921 | $0.24 |
| Brick 1×8 | 3008 | 300801 | 300826 | 300821 | $0.26 |
| Brick 2×2 | 3003 | 300301 | 300326 | 300321 | $0.13 |
| Brick 2×3 | 3002 | 300201 | 300226 | 300221 | $0.17 |
| Brick 2×4 | 3001 | 300101 | 300126 | 300121 | $0.21 |
| Brick 2×6 | 44237 | 4181142 | 4181144 | 4181138 | $0.31 |
| Brick 2×8 | 93888 | 6033776 | 6037390 | 6036408 (out of stock) | $0.39 |
| Plate 1×1 | 3024 | 302401 | 302426 | 302421 | $0.06 |
| Plate 1×2 | 3023 | 302301 | 302326 | 302321 | $0.08 |
| Plate 1×4 | 3710 | 371001 | 371026 | 371021 | $0.11 |
| Plate 1×6 | 3666 | 366601 | 366626 | 366621 | $0.16 |
| Plate 1×8 | 3460 | 346001 | 346026 | 346021 | $0.18 |
| Plate 2×2 | 3022 | 302201 | 302226 | 302221 | $0.09 |
| Plate 2×4 | 3020 | 302001 | 302026 | 302021 | $0.14 |
| Plate 2×6 | 3795 | 379501 | 379526 | 379521 | $0.19 |
| Plate 2×8 | 3034 | 303401 | 303426 | 303421 | $0.28 |

| Base plate (green) | Store ID | Element ID | Color in store | Price each |
|---|---|---|---|---|
| 16×16 (PLATE 16X16) | 91405 | 4611777 | Bright Green | $3.29 |
| 32×32 (BASE PLATE 32X32) | 3811 | 4219692 | Dark Green | $10.35 |

Out-of-stock parts are kept in the layout and flagged in the parts list, so the layout doesn't depend on that
day's stock.

## Reference

Shapes and sizes follow the standard parts listed in the public BrickLink catalog
(https://www.bricklink.com/v2/search.page?q=brick#T=P), used only as a reference for which shapes are common.
Store IDs, element IDs and prices come from the Pick a Brick store as listed above.

## Changing the catalog

Edit `CATALOG_20` in `ml/src/ptb_ml/brick_optimizer/settings.py`. Each entry is `(width, depth, height)` with height
in plates: 3 for a brick, 1 for a plate. The catalog must keep a 1×1 plate so every cell can always be covered.
To see how a change affects piece counts, run:

```
PYTHONPATH=ml/src python ml/scripts/glb_to_bricks.py <model.glb> --studs 16 --hollow 2 --catalog optimized-20
```

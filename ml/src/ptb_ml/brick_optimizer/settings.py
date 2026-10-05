from __future__ import annotations
from dataclasses import dataclass, field

## The 20-part catalog: (w, d, h) with h in plates (3 = brick, 1 = plate).
## Rotations are the same part and are added by the engine.
CATALOG_20: tuple[tuple[int, int, int], ...] = (
    # Bricks
    (1, 1, 3), (1, 2, 3), (1, 3, 3), (1, 4, 3), (1, 6, 3), (1, 8, 3),
    (2, 2, 3), (2, 3, 3), (2, 4, 3), (2, 6, 3), (2, 8, 3),
    # Plates
    (1, 1, 1), (1, 2, 1), (1, 4, 1), (1, 6, 1), (1, 8, 1),
    (2, 2, 1), (2, 4, 1), (2, 6, 1), (2, 8, 1),
)

## The kit's colors, as names in brickification/colors.py::LEGO_COLORS
KIT_COLORS: tuple[str, ...] = ("White", "Black", "Red")


@dataclass(frozen=True)
class BrickOptSettings:
    """
    Per-layer exact cover with OR-Tools CP-SAT. Each layer is tiled with
    catalog parts so every occupied cell is covered once, by a part whose
    cells all have the same kit color, at the lowest total cost.
    """
    catalog: tuple[tuple[int, int, int], ...]= CATALOG_20
    colors: tuple[str, ...]= KIT_COLORS

    ## Cost per part; the main term, so fewer parts always wins
    piece_cost: int= 100
    ## Reward per extra part underneath that this part locks together
    ## (a running-bond wall), capped at link_cap
    link_bonus: int= 10
    link_cap: int= 2
    ## Extra cost for 1x1 parts, and for parts with nothing underneath.
    ## Unsupported costs more than a whole part, so the solver adds a part
    ## to bridge an overhang rather than leave it floating
    one_by_one_cost: int= 20
    unsupported_cost: int= 250
    ## Extra cost for sitting exactly on a part of the same footprint: the
    ## joints line up and the wall splits into separate towers. More than a
    ## part, so the solver staggers joints even when that adds a part
    stacked_cost: int= 150

    ## Rounds of "add support under loose pieces, re-solve". Needs the
    ## `solid` grid saved by mesh_voxel; support only goes inside it
    repair_rounds: int= 3
    ## Support only fills gaps down to material at most this deep (6 = two
    ## brick courses), so it never builds pillars through a hollow house
    max_support_plates: int= 6
    ## Leave out pieces that are still loose after repair
    drop_loose: bool= True

    time_limit_s: float= 2.0
    workers: int= 8

    def __post_init__(self):
        if not self.catalog:
            raise ValueError("catalog must not be empty")
        if (1, 1, 1) not in self.catalog:
            raise ValueError("catalog needs a 1x1 plate so every cell can be covered")
        if any(h not in (1, 3) for _, _, h in self.catalog):
            raise ValueError("part heights must be 1 (plate) or 3 (brick)")
        if not self.colors:
            raise ValueError("colors must not be empty")
        if self.time_limit_s <= 0:
            raise ValueError("time_limit_s must be positive")

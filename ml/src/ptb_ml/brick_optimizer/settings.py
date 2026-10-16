from __future__ import annotations
from dataclasses import dataclass, field

from ..brickification.colors import BRICK_COLORS

## (w, d, h), h in plates. Rotations are added by the engine
CATALOG_20: tuple[tuple[int, int, int], ...] = (
    # Bricks
    (1, 1, 3), (1, 2, 3), (1, 3, 3), (1, 4, 3), (1, 6, 3), (1, 8, 3),
    (2, 2, 3), (2, 3, 3), (2, 4, 3), (2, 6, 3), (2, 8, 3),
    # Plates, for the flat mosaic style
    (1, 1, 1), (1, 2, 1), (1, 4, 1), (1, 6, 1), (1, 8, 1),
    (2, 2, 1), (2, 4, 1), (2, 6, 1), (2, 8, 1),
)

KIT_COLORS: tuple[str, ...] = ("White", "Black", "Red")


@dataclass(frozen=True)
class BrickOptSettings:
    """
    Per-layer exact cover with OR-Tools CP-SAT: every occupied cell is
    covered once, by a one-color catalog part, at the lowest total cost.
    """
    catalog: tuple[tuple[int, int, int], ...]= CATALOG_20
    colors: tuple[str, ...]= KIT_COLORS

    ## "rank": lightest -> white, darkest -> black, most saturated -> red.
    ## "nearest": closest kit color
    color_mapping: str= "rank"
    accent_min_saturation: float= 0.35
    merge_color_distance: float= 40.0
    color_smoothing: int= 2

    ## Solver costs. A part costs more than any bonus, so fewer parts wins
    piece_cost: int= 100
    link_bonus: int= 10            # per extra part locked underneath, up to link_cap
    link_cap: int= 2
    one_by_one_cost: int= 20
    unsupported_cost: int= 250     # more than a part: bridge overhangs
    stacked_cost: int= 150         # same footprint right below: stagger joints

    ## Support under loose pieces, at most max_support_plates deep
    repair_rounds: int= 3
    max_support_plates: int= 6
    drop_loose: bool= True

    ## Smallest size that fits the footprint; color is outside the kit colors
    base_plate: bool= True
    base_plate_sizes: tuple[int, ...]= (16, 32, 48)
    base_plate_color: str= "Green"

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
        if self.base_plate and self.base_plate_color not in {c[0] for c in BRICK_COLORS}:
            raise ValueError(f"unknown base_plate_color: {self.base_plate_color}")
        if self.color_mapping not in ("rank", "nearest"):
            raise ValueError("color_mapping must be 'rank' or 'nearest'")
        if self.time_limit_s <= 0:
            raise ValueError("time_limit_s must be positive")

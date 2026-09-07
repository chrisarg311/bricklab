from __future__ import annotations
from dataclasses import dataclass, field

BRICK_SHAPES: list[tuple[int,int,int]] = [
    # Plates
    (1, 1, 1), (1, 2, 1), (1, 3, 1), (1, 4, 1),
    (2, 2, 1), (2, 3, 1), (2, 4, 1), (2, 6, 1), (2, 8, 1),
    # Bricks (3 plates tall)
    (1, 1, 3), (1, 2, 3), (1, 3, 3), (1, 4, 3),
    (2, 2, 3), (2, 3, 3), (2, 4, 3), (2, 6, 3), (2, 8, 3),
]

@dataclass(frozen=True)
class BrickificationSettings:
    brick_shapes: tuple[tuple, ...] = field(
        default_factory=lambda: tuple(
            sorted(BRICK_SHAPES, key=lambda s: - (s[0] * s[1] * s[2]))
        )
    )

    min_stagger_overlap: int= 1
    min_support_ratio: float= 0.5

    min_wall_thickness: int= 2
    max_overhand_studs: int= 2

    snap_to_lego_colors: bool= True

    def __post_init__(self):
        if self.min_stagger_overlap < 1:
            raise ValueError(
                "min_stagger_overlap must be at least >=1"
            )
        if not (0.0 <= self.min_support_ratio <= 1.0):
            raise ValueError(
                "min_support_ratio must be in [0, 1]"
            )
        if self.min_wall_thickness < 1:
            raise ValueError(
                "min_wall_thickness must be at least >=1"
            )
        if self.max_overhand_studs < 1:
            raise ValueError(
                "max_overhand_studs must be at least >=1"
            )
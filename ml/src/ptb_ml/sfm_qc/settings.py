from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SfmQcSettings:
    # Hard minimums — if below these score is forced to 0.0
    min_registered_images: int = 5
    min_points3d: int = 100
    max_reprojection_error: float = 2.0  # pixels

    # Target values — hitting these gives full score for that metric
    target_registered_images: int = 20
    target_points3d: int = 2000
    target_reprojection_error: float = 0.5  # pixels — lower is better

    # Metric weights — must sum to 1.0
    weight_registered_images: float = 0.35
    weight_points3d: float = 0.40
    weight_reprojection_error: float = 0.25

    # Score threshold for Blue vs Orange routing
    blue_threshold: float = 0.5

    colmap_bin: str = "colmap"

    def __post_init__(self) -> None:
        weights = (
            self.weight_registered_images
            + self.weight_points3d
            + self.weight_reprojection_error
        )
        if not abs(weights - 1.0) < 1e-6:
            raise ValueError(
                f"SfmQcSettings weights must sum to 1.0, got {weights}"
            )
        if self.blue_threshold < 0.0 or self.blue_threshold > 1.0:
            raise ValueError(
                f"blue_threshold must be in [0, 1], got {self.blue_threshold}"
            )
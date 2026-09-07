from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from .models import SfmInputMode


@dataclass(frozen=True)
class SfmSettings:
    enabled: bool = True

    # Executable
    colmap_bin: str = "colmap"

    # Camera / feature extraction
    camera_model: str = "SIMPLE_RADIAL"
    single_camera: bool = True
    use_gpu: bool = True
    gpu_index: str = "-1"  # "-1" lets COLMAP choose

    max_image_size: int = 3200
    max_num_features: int = 8192
    max_num_matches: int = 32768

    # Sequential matching knobs
    sequential_overlap: int = 10
    sequential_quadratic_overlap: bool = True
    sequential_loop_detection: bool = False
    sequential_loop_detection_period: int = 10
    sequential_loop_detection_num_images: int = 50

    # Mapper / BA knobs
    mapper_ba_use_gpu: bool = False
    mapper_ba_global_max_num_iterations: int | None = None
    mapper_ba_global_function_tolerance: float | None = None
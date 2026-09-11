# Settings for preprocessing 

from __future__ import annotations
from dataclasses import dataclass, field



@dataclass(frozen=True)
class MaskingSettings:
    enabled: bool = True
    backend: str = "sky_hsv"   # "sky_hsv" or "sky_hsv+deeplabv3" or "none"
    dilation_px: int = 6
    min_unmasked_ratio: float = 0.15

    # sky heuristic knobs
    sky_top_fraction: float = 0.55
    sky_blue_strength: float = 0.12
    sky_low_sat: float = 0.25
    sky_high_val: float = 0.78

    # semantic (only if backend includes deeplabv3)
    semantic_classes_to_mask: tuple[str, ...] = (
        "person", "car", "bus", "truck", "motorcycle", "bicycle"
    )
    device: str = "auto"  # auto|cpu|cuda

    def __post_init__(self) -> None:
        allowed_backends = {"none", "sky_hsv", "sky_hsv+deeplabv3"}
        if self.backend.strip().lower() not in allowed_backends:
            raise ValueError(
                f"Invalid masking backend '{self.backend}'. "
                f"Expected one of {sorted(allowed_backends)}"
            )

        if self.dilation_px < 0:
            raise ValueError(f"dilation_px must be >= 0, got {self.dilation_px}")

        if not (0.0 <= self.min_unmasked_ratio <= 1.0):
            raise ValueError(
                f"min_unmasked_ratio must be in [0, 1], got {self.min_unmasked_ratio}"
            )

        if not (0.0 <= self.sky_top_fraction <= 1.0):
            raise ValueError(
                f"sky_top_fraction must be in [0, 1], got {self.sky_top_fraction}"
            )

        if not (0.0 <= self.sky_blue_strength <= 1.0):
            raise ValueError(
                f"sky_blue_strength must be in [0, 1], got {self.sky_blue_strength}"
            )

        if not (0.0 <= self.sky_low_sat <= 1.0):
            raise ValueError(
                f"sky_low_sat must be in [0, 1], got {self.sky_low_sat}"
            )

        if not (0.0 <= self.sky_high_val <= 1.0):
            raise ValueError(
                f"sky_high_val must be in [0, 1], got {self.sky_high_val}"
            )

        if not isinstance(self.semantic_classes_to_mask, tuple):
            raise TypeError("semantic_classes_to_mask must be a tuple[str, ...]")

        if any(not isinstance(x, str) or not x.strip() for x in self.semantic_classes_to_mask):
            raise ValueError(
                "semantic_classes_to_mask must contain only non-empty strings"
            )

        if self.device.strip().lower() not in {"auto", "cpu", "cuda"}:
            raise ValueError(
                f"device must be one of auto|cpu|cuda, got '{self.device}'"
            )


@dataclass(frozen=True)
class PreprocessSettings:
    fps: float = 2.0
    max_video_frames: int = 500
    source_type: str = "image_set"

    min_sharpness: float = 80.0
    min_brightness: float = 0.12
    max_brightness: float = 0.88
    max_clip_high: float = 0.02
    max_clip_low: float = 0.02

    dedupe_phash_size: int = 16
    dedupe_hamming_threshold: int = 6

    masking: MaskingSettings = field(default_factory=MaskingSettings)

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError(f"fps must be > 0, got {self.fps}")

        if self.max_video_frames <= 0:
            raise ValueError(
                f"max_video_frames must be > 0, got {self.max_video_frames}"
            )

        if self.min_sharpness < 0:
            raise ValueError(
                f"min_sharpness must be >= 0, got {self.min_sharpness}"
            )

        if not (0.0 <= self.min_brightness <= 1.0):
            raise ValueError(
                f"min_brightness must be in [0, 1], got {self.min_brightness}"
            )

        if not (0.0 <= self.max_brightness <= 1.0):
            raise ValueError(
                f"max_brightness must be in [0, 1], got {self.max_brightness}"
            )

        if self.min_brightness > self.max_brightness:
            raise ValueError(
                "min_brightness cannot be greater than max_brightness"
            )

        if not (0.0 <= self.max_clip_high <= 1.0):
            raise ValueError(
                f"max_clip_high must be in [0, 1], got {self.max_clip_high}"
            )

        if not (0.0 <= self.max_clip_low <= 1.0):
            raise ValueError(
                f"max_clip_low must be in [0, 1], got {self.max_clip_low}"
            )

        if self.dedupe_phash_size <= 0:
            raise ValueError(
                f"dedupe_phash_size must be > 0, got {self.dedupe_phash_size}"
            )

        if self.dedupe_hamming_threshold < 0:
            raise ValueError(
                f"dedupe_hamming_threshold must be >= 0, got {self.dedupe_hamming_threshold}"
            )
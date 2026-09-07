from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PriorsSettings:
    device: str = "cpu"  # auto|cpu|cuda

    # Depth Anything V2
    depth_model_id: str = "depth-anything/Depth-Anything-V2-Small-hf"

    # DSINE
    dsine_local_weights: str | None = None  # None = download from HuggingFace

    # DeepLabv3 — reuse from preprocess
    semantic_classes_to_mask: tuple[str, ...] = (
        "person", "car", "bus", "truck", "motorcycle", "bicycle"
    )

    # Output
    depth_png_max_val: int = 65535  # 16-bit PNG for depth precision

    def __post_init__(self) -> None:
        if self.device.strip().lower() not in {"auto", "cpu", "cuda"}:
            raise ValueError(
                f"device must be one of auto|cpu|cuda, got '{self.device}'"
            )
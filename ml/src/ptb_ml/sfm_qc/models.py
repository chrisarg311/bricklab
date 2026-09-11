from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PipelinePath = Literal["blue", "orange"]


@dataclass(frozen=True)
class SfmQcReq:
    job_id: str
    sparse_model_dir: Path  # path to sparse/0
    num_input_images: int   # total frames passed to SfM

    def __post_init__(self) -> None:
        if self.sparse_model_dir is not None:
            object.__setattr__(self, "sparse_model_dir", Path(self.sparse_model_dir))


@dataclass(frozen=True)
class SfmQcMetrics:
    registered_images: int
    points3d: int
    reprojection_error: float
    pct_registered: float   # registered_images / num_input_images


@dataclass(frozen=True)
class SfmQcResult:
    job_id: str
    ok: bool                # False means QC itself failed to run
    route: PipelinePath     # "blue" or "orange"
    score: float            # 0.0 - 1.0
    metrics: SfmQcMetrics | None = None
    error: str | None = None
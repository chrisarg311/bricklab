from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SfmInputMode = Literal["sequential", "unordered"]


@dataclass(frozen=True)
class SfmReq:
    job_id: str
    image_dir: Path
    output_dir: Path

    # "sequential" for video-derived frames, "unordered" for normal image sets
    input_mode: SfmInputMode

    # Optional preprocessing outputs
    database_path: Path | None = None
    sparse_dir: Path | None = None
    logs_dir: Path | None = None


    mask_dir: Path | None = None
    manifest_path: Path | None = None
    image_list_path: Path | None = None


    def __post_init__(self):
        object.__setattr__(self, "image_dir", Path(self.image_dir))
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.mask_dir is not None:
            object.__setattr__(self, "mask_dir", Path(self.mask_dir))
        if self.manifest_path is not None:
            object.__setattr__(self, "manifest_path", Path(self.manifest_path))
        if self.image_list_path is not None:
            object.__setattr__(self, "image_list_path", Path(self.image_list_path))


@dataclass(frozen=True)
class SfmResult:
    ok: bool
    job_id: str
    input_mode: SfmInputMode

    image_dir: Path
    output_dir: Path
    database_path: Path
    sparse_dir: Path
    best_model_dir: Path | None

    commands: tuple[str, ...] = field(default_factory=tuple)
    log_paths: tuple[Path, ...] = field(default_factory=tuple)

    num_sparse_models: int = 0
    error: str | None = None
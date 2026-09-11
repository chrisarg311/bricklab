from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PriorsReq:
    job_id: str
    frames_dir: Path
    output_dir: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames_dir", Path(self.frames_dir))
        object.__setattr__(self, "output_dir", Path(self.output_dir))


@dataclass(frozen=True)
class PriorsFrameResult:
    frame: str          # frame filename
    depth_path: str
    normals_path: str
    segmentation_path: str


@dataclass(frozen=True)
class PriorsResult:
    job_id: str
    ok: bool
    frames: tuple[PriorsFrameResult, ...]
    depth_dir: Path
    normals_dir: Path
    segmentation_dir: Path
    manifest_path: Path
    error: str | None = None
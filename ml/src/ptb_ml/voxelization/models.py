from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class VoxelizationReq:
    job_id: str
    tsdf_path: Path
    output_dir: Path

    def __post_init__(self):
        object.__setattr__(self, "tsdf_path", Path(self.tsdf_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))

@dataclass(frozen=True)
class VoxelizationResult:
    job_id: str
    ok: bool
    voxel_path: Path
    output_dir: Path
    num_occupied_voxels: int
    grid_shape: tuple[int, int, int]
    error: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "voxel_path", Path(self.voxel_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))

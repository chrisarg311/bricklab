from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MeshVoxelReq:
    job_id: str
    mesh_path: Path
    output_dir: Path

    def __post_init__(self):
        object.__setattr__(self, "mesh_path", Path(self.mesh_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))


@dataclass(frozen=True)
class MeshVoxelResult:
    job_id: str
    ok: bool
    voxel_path: Path
    grid_shape: tuple[int, int, int]
    num_occupied: int
    num_surface: int
    error: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "voxel_path", Path(self.voxel_path))

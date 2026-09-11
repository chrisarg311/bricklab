from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ShapeCompletionReq:
    job_id: str
    frames_dir: Path
    depth_dir: Path
    normals_dir: Path
    segmentation_dir: Path
    output_dir: Path
    sparse_model_dir: Path | None = None  # None = Orange path, use identity
    colmap_bin: str = "colmap"


    def __post_init__(self) -> None:
        for field_name in ("frames_dir", "depth_dir", "normals_dir",
                           "segmentation_dir", "output_dir"):
            object.__setattr__(
                self, field_name, Path(getattr(self, field_name))
            )
        if self.sparse_model_dir is not None:
            object.__setattr__(
                self, "sparse_model_dir", Path(self.sparse_model_dir)
            )


@dataclass(frozen=True)
class ShapeCompletionResult:
    job_id: str
    ok: bool
    tsdf_path: Path
    mesh_path: Path
    alignment_matrix: tuple[float, ...]
    num_frames_integrated: int
    output_dir: Path
    error: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "tsdf_path", Path(self.tsdf_path))
        object.__setattr__(self, "mesh_path", Path(self.mesh_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))


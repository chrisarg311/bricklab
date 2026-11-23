from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrickOptReq:
    job_id: str
    voxel_path: Path
    output_dir: Path

    def __post_init__(self):
        object.__setattr__(self, "voxel_path", Path(self.voxel_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))


@dataclass(frozen=True)
class BrickOptResult:
    job_id: str
    ok: bool
    bricks_path: Path
    bom_path: Path
    output_dir: Path
    num_bricks: int
    num_bom_entries: int
    ## Pieces not connected to the ground through the pieces above/below
    ## them: they would fall off when built
    num_loose: int= 0
    ## Loose pieces left out of the model because nothing could hold them
    num_dropped: int= 0
    ## Side of the square base plate (0 = none)
    base_plate_size: int= 0
    ## Cells added under loose pieces to hold them up
    num_support_cells: int= 0
    ## Layers where the solver hit its time limit before proving optimal
    num_layers_not_optimal: int= 0
    error: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "bricks_path", Path(self.bricks_path))
        object.__setattr__(self, "bom_path", Path(self.bom_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))

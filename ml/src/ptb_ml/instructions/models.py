from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BuildStep:
    step_number: int
    brick_indices: tuple[int, ...]      
    section_x: int                      
    section_z: int
    layer_min: int                      
    layer_max: int


@dataclass(frozen=True)
class InstructionsReq:
    job_id: str
    bricks_path: Path
    bom_path: Path
    output_dir: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "bricks_path", Path(self.bricks_path))
        object.__setattr__(self, "bom_path", Path(self.bom_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))


@dataclass(frozen=True)
class InstructionsResult:
    job_id: str
    ok: bool
    glb_path: Path
    steps_path: Path        
    output_dir: Path
    num_steps: int
    num_bricks: int
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "glb_path", Path(self.glb_path))
        object.__setattr__(self, "steps_path", Path(self.steps_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))
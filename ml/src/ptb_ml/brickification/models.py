from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Brick:
    """A Brick"""
    x: int
    y: int
    z: int
    w: int
    h: int
    d: int
    color_r: int
    color_g: int
    color_b: int

    @property
    def shape(self) -> tuple[int,int,int]:
        return self.w, self.h, self.d
    @property
    def volume(self) -> int:
        return self.w * self.h * self.d
    
@dataclass(frozen=True)
class BomEntry:
    """Bill of materials entry"""
    shape: tuple[int,int,int]
    color_r: int
    color_g: int
    color_b: int
    quantity: int


@dataclass(frozen=True)
class BrickificationReq:
    job_id: str
    voxel_path: Path
    output_dir: Path

    def __post_init__(self):
        object.__setattr__(self, "voxel_path", Path(self.voxel_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))

@dataclass(frozen=True)
class BrickificationResult:
    job_id: str
    ok: bool
    bricks_path: Path
    bom_path: Path
    output_dir: Path
    num_bricks: int
    num_bom_entries: int
    error: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "bricks_path", Path(self.bricks_path))
        object.__setattr__(self, "bom_path", Path(self.bom_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))

    

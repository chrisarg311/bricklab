from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class InstructionsSettings:
    # GLB appearance
    stud_radius_ratio: float = 0.35     
    stud_height_m: float = 0.0018       
    bevel_size_ratio: float = 0.05      
    
    # Build steps — spatial sectioning
    section_size_studs: int = 8         
    max_bricks_per_step: int = 50       

    # GLB scale — metres per unit
    stud_size_m: float = 0.008
    plate_size_m: float = 0.0032

    def __post_init__(self) -> None:
        if not (0.0 < self.stud_radius_ratio < 0.5):
            raise ValueError("stud_radius_ratio must be in (0, 0.5)")
        if self.section_size_studs < 1:
            raise ValueError("section_size_studs must be >= 1")
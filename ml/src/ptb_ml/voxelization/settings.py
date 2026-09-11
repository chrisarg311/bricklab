from __future__ import annotations
from dataclasses import dataclass

LEGO_STUD_M= 0.008
LEGO_PLATE_M= 0.0032
LEGO_BRICK_M= 0.0096


@dataclass(frozen=True)
class VoxelizationSettings:
    ## Grid resolution
    stud_size_m: float= LEGO_STUD_M
    plate_size_m: float= LEGO_PLATE_M


    ## Dimensions of the voxel grid 
    ## WIRE INTO API FOR 
    ## this controls the size of the recreation, so a user could
    ## select an option to scale the model (small/ medium/ large)
    max_studs_x: int= 64
    max_studs_z: int= 64
    max_plates_y: int= 96

    ## Occupancy threshold
    occupancy_threshold: float= 0.0 #occupy all points may change later 

    # Normal smoothing
    normal_smoothing: bool=True

    def __post_init__(self):
        if self.stud_size_m <= 0:
            raise ValueError("Stud size must be positive")
        if self.plate_size_m <= 0:
            raise ValueError("Plate size must be positive")
        if self.max_studs_x <= 0 or self.max_studs_z <= 0 or self.max_plates_y <= 0:
            raise ValueError("Max studs must be positive")
        if not (0.0 <= self.occupancy_threshold <= 1.0):
            raise ValueError("Occupancy threshold must be in [0, 1]")



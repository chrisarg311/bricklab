from __future__ import annotations
from dataclasses import dataclass

STUD_M= 0.008
PLATE_M= 0.0032


@dataclass(frozen=True)
class MeshVoxelSettings:
    """
    Mesh -> brick grid. One cell is 1 stud x 1 plate x 1 stud, indexed
    (x, y, z) with y vertical and y=0 on the ground, which is what
    brickification/engine.py builds from.
    """

    ## Size of the model: studs along the longest horizontal side
    ## (S/M/L = 16/32/48). The mesh's own units are ignored.
    target_studs: int= 32

    ## Up axis of the input mesh. glTF is "y"; PR #3's gen_model is "z".
    up_axis: str= "y"

    stud_size_m: float= STUD_M
    plate_size_m: float= PLATE_M

    ## Drop a flat ground/lawn plane under the model so it doesn't set the size
    drop_ground_planes: bool= True

    ## Fill the inside of closed meshes; otherwise only the surface is kept
    fill_interior: bool= True

    ## Keep only cells within this many studs of open air (3D distance, so
    ## sloped roofs keep overlapping steps). None keeps the model solid.
    hollow_wall_studs: int | None= 2
    ## Keep a floor when hollow; False leaves the bottom open for a base plate
    floor: bool= True

    ## Round heights to whole bricks (3 plates) before hollowing, so walls
    ## and roof steps are built from bricks instead of stacks of plates
    snap_to_courses: bool= False

    ## Surface samples per unit of grid-space area. Too low leaves holes
    ## in the shell and the interior fill leaks out.
    samples_per_cell: float= 20.0
    seed: int= 0

    ## Used when the mesh carries no color
    default_color: tuple[int, int, int]= (160, 165, 169)

    def __post_init__(self):
        if self.target_studs < 1:
            raise ValueError("target_studs must be >= 1")
        if self.up_axis not in ("y", "z"):
            raise ValueError("up_axis must be 'y' or 'z'")
        if self.stud_size_m <= 0 or self.plate_size_m <= 0:
            raise ValueError("stud and plate size must be positive")
        if self.hollow_wall_studs is not None and self.hollow_wall_studs < 1:
            raise ValueError("hollow_wall_studs must be >= 1 or None")
        if self.samples_per_cell <= 0:
            raise ValueError("samples_per_cell must be positive")

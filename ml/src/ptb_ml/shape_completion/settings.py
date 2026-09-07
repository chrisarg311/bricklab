from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ShapeCompletionSettings:
    # cam intrinsics est
    fov_deg: float = 60.0

    #conf mask
    min_depth_val: int= 100
    max_depth_val: int= 65000

    #RANSAC plane fitting
    plane_distance_threshold: float= 0.02
    plane_ransac_n: int= 3
    plane_num_iterations: int= 1000
    min_plane_inliers: int= 50

    #manhattan alignment
    num_dominant_planes: int= 3

    #TSDF fusion
    tsdf_voxel_length: float= 0.02
    tsdf_sdf_trunc: float= 0.06
    tsdf_depth_scale: float= 65535.0
    tsdf_depth_max: float= 5.0

    def __post_init__(self) -> None:
        if self.min_depth_val >= self.max_depth_val:
            raise ValueError("min_depth_val must be less than max_depth_val")
        if self.tsdf_voxel_length <= 0:
            raise ValueError("tsdf_voxel_length must be > 0")
        if self.num_dominant_planes < 1:
            raise ValueError("num_dominant_planes must be >= 1")
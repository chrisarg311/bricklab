from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from .models import VoxelizationReq, VoxelizationResult
from .settings import VoxelizationSettings

log = logging.getLogger(__name__)


def _load_tsdf(tsdf_path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    """Load points, colors, from tsdf.npz returns points colors vox_len"""
    data= np.load(tsdf_path)
    points= data["points"].astype(np.float32)
    colors= data["colors"].astype(np.float32)
    voxel_len= float(data["voxel_length"][0])
    alignment= data["alignment"].reshape(4, 4)


    # Apply alignment
    if points.shape[0] > 0:
        ones = np.ones((points.shape[0], 1), dtype=np.float32)
        pts_h = np.hstack([points, ones])
        points = np.matmul(pts_h, alignment.T)[:,:3]


    return points, colors, voxel_len


def _fit_to_lego_grid(
        points: np.ndarray,
        colors: np.ndarray,
        settings: VoxelizationSettings,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ Maps real world space points onto a lego stud/plate grid
    returns (grid_indicies, grid_colors, ?grid_normals?, origin)
    grid_indicies: (N,3) int array of (ix, iy, iz) vox coords
    """

    if points.shape[0] == 0:
        return(
            np.zeros((0, 3), dtype=np.int32),
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.float32),
            np.zeros(3, dtype=np.float32),
        )
    
    origin= points.min(axis=0)
    pts = points - origin

    ix= np.floor(pts[:, 0] / settings.stud_size_m).astype(np.int32)
    iy= np.floor(pts[:, 1] / settings.plate_size_m).astype(np.int32)
    iz= np.floor(pts[:, 2] / settings.stud_size_m).astype(np.int32)

    ix= np.clip(ix, 0, settings.max_studs_x - 1)
    iy= np.clip(iy, 0, settings.max_plates_y - 1)
    iz= np.clip(iz, 0, settings.max_studs_z - 1)

    return (
        np.stack([ix, iy, iz], axis=1),
        colors,
        origin,
    )


def _build_occupancy_grid(
        grid_indicies: np.ndarray,
        colors: np.ndarray,
        grid_shape: tuple[int, int, int],
        settings: VoxelizationSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Builds dense occupancy and color arrays from sparse
    grid indices RETURNS:
    (occupancy_grid, colors_grid) --> 
        occupancy_grid : (X,Y,Z) bool
        colors_grid : (X,Y,Z,3) uint8    
    """

    X, Y, Z= grid_shape
    occup= np.zeros((X, Y, Z), dtype=bool)
    color_grid= np.zeros((X, Y, Z, 3), dtype=np.uint8)
    color_acc= np.zeros((X, Y, Z, 3), dtype=np.float64)
    count_grid= np.zeros((X, Y, Z), dtype=np.float32)


    for (ix, iy, iz), color in zip(grid_indicies, colors):
        occup[ix, iy, iz]= True
        color_acc[ix, iy, iz]+= color
        count_grid[ix, iy, iz]+= 1
    
    occupied_mask = count_grid > 0
    color_acc[occupied_mask] /= count_grid[occupied_mask, np.newaxis]
    color_grid= (color_acc * 255).clip(0, 255).astype(np.uint8)

    return occup, color_grid


def _estimate_normals_grid(
        occupancy: np.ndarray,
) -> np.ndarray:
    """
    Estimate per-voxel normals sform occupancy gradient
    Returns (X, Y, Z, 3) float32 normal array
    """
    X, Y, Z = occupancy.shape
    normals = np.zeros((X, Y, Z, 3), dtype=np.float32)

    occ_f = occupancy.astype(np.float32)
    gx= np.gradient(occ_f, axis=0)
    gy= np.gradient(occ_f, axis=1)
    gz= np.gradient(occ_f, axis=2)

    grad= np.stack([gx,gy,gz], axis=-1)

    mag= np.linalg.norm(grad, axis=-1, keepdims=True)
    mag= np.where(mag < 1e-6, 1.0, mag)

    normals= (grad/mag).astype(np.float32)
    return normals



def run_voxelization(
        req: VoxelizationReq,
        settings: VoxelizationSettings,
) -> VoxelizationResult:
    req.output_dir.mkdir(parents=True, exist_ok=True)
    voxel_path = req.output_dir / "occupancy.npz"

    if not req.tsdf_path.exists():
        return VoxelizationResult(
            job_id=req.job_id,
            ok=False,
            voxel_path=voxel_path,
            output_dir=req.output_dir,
            num_occupied_voxels=0,
            grid_shape=(0, 0, 0),
            error=f"No tsdf found in {req.tsdf_path}",
        )
    
    #load point cloud from tsdf

    log.info("Loading TSDF point cloud...")
    points, colors, voxel_len= _load_tsdf(req.tsdf_path)
    log.info(f"Loaded {len(points)} points")

    if len(points) == 0:
        return VoxelizationResult(
            job_id=req.job_id,
            ok=False,
            voxel_path=voxel_path,
            output_dir=req.output_dir,
            num_occupied_voxels=0,
            grid_shape=(0, 0, 0),
            error=f"No points found in {req.tsdf_path}",
        )
    
    log.info("Mapping to LEGO grid")
    grid_indicies, colors, origin= _fit_to_lego_grid(
        points, colors, settings)

    grid_shape= (
        settings.max_studs_x,
        settings.max_plates_y,
        settings.max_studs_z, 
    )

    log.info("Building occupancy grid...")
    occupancy, color_grid= _build_occupancy_grid(
        grid_indicies,
        colors,
        grid_shape,
        settings,
    )


    log.info("Estimating voxel normals...")
    normal_grid= _estimate_normals_grid(occupancy)

    num_occupied= int(occupancy.sum())

    log.info(f"Occupied voxels: {num_occupied} / {occupancy.size}")

    np.savez_compressed(
        voxel_path,
        occupancy=occupancy,
        colors=color_grid,
        normals=normal_grid,
        origin=origin,
        stud_size_m= np.array([settings.stud_size_m]),
        plate_size_m= np.array([settings.plate_size_m]),
        grid_shape= np.array(list(grid_shape)),
    )

    log.info(f"saved occupancy grid to {voxel_path}")

    return VoxelizationResult(
        job_id=req.job_id,
        ok=True,
        voxel_path=voxel_path,
        output_dir=req.output_dir,
        num_occupied_voxels=num_occupied,
        grid_shape=grid_shape,
    )

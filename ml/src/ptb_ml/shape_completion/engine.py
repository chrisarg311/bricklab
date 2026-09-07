from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import open3d as o3d
from PIL import Image

from .models import ShapeCompletionReq, ShapeCompletionResult
from .settings import ShapeCompletionSettings
from .pose_reader import read_colmap_poses

log = logging.getLogger(__name__)


# ===================   #
# Helpers#
# ===================   #

def _get_intrinsics(
    width:int,
    height:int,
    fov_degrees:float, 
    ) -> o3d.camera.PinholeCameraIntrinsic:
    focal = width / (2 * np.tan(np.deg2rad(fov_degrees) / 2))
    return o3d.camera.PinholeCameraIntrinsic(
        width=width,
        height=height,
        fx=focal,
        fy=focal,
        cx=width / 2.0,
        cy=height / 2.0
    )


def _load_depth_o3d(
    depth_path:Path,
    seg_path:Path,
    settings: ShapeCompletionSettings,
) -> o3d.geometry.Image:
    """Loiad uint16 depth png zero out unreliable regions"""
    depth_np = np.array(Image.open(depth_path), dtype=np.uint16)
    seg_np = np.array(Image.open(seg_path), dtype=np.uint8)

    #zero dynamic objects
    depth_np[seg_np > 0] = 0

    # zero out unreliable depth vals
    depth_np[depth_np < settings.min_depth_val] = 0
    depth_np[depth_np > settings.max_depth_val] = 0

    return o3d.geometry.Image(depth_np)


def _load_color_o3d(frame_path:Path) -> o3d.geometry.Image:
    rgb = np.array(Image.open(frame_path).convert("RGB"), dtype=np.uint8)
    return o3d.geometry.Image(rgb)


def _build_point_cloud(
    frames: list[Path],
    depth_dir: Path,
    seg_dir: Path,
    intrinsics: o3d.camera.PinholeCameraIntrinsic,
    settings: ShapeCompletionSettings,
) -> o3d.geometry.PointCloud:
    """"Back-project all depth frames into a single point cloud"""
    combined = o3d.geometry.PointCloud()

    for frame_path in frames:
        stem = frame_path.stem
        depth_path = depth_dir / f"{stem}.png"
        seg_path = seg_dir / f"{stem}.png"

        if not depth_path.exists():
            log.warning(f"Missing depth for frame {stem}")
            continue

        depth_img = _load_depth_o3d(depth_path, seg_path, settings)

        # use identitiy pose - we don't have camera poses in orange path update for blue

        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            o3d.geometry.Image(
                np.zeros(
                    (intrinsics.height, intrinsics.width, 3),
                    dtype=np.uint8,
                ),
            ),
            depth_img,
            depth_scale=settings.tsdf_depth_scale,
            depth_trunc=settings.tsdf_depth_max,
            convert_rgb_to_intensity=False,
        )

        pc = o3d.geometry.PointCloud.create_from_rgbd_image(
            rgbd,
            intrinsics,
        )

        combined += pc

    combined = combined.voxel_down_sample(
        voxel_size=settings.tsdf_voxel_length
    )
    combined.estimate_normals()
    return combined

def _fit_dominant_planes(
    pcd: o3d.geometry.PointCloud,
    settings: ShapeCompletionSettings,
) -> list[np.ndarray]:
    """iteratively fit ransac planes, remove inliers, repeat
    return list of plane normal vectors for MA"""

    remaining = pcd
    plane_normals: list[np.ndarray] = []

    for _ in range(settings.num_dominant_planes):
        if len(remaining.points) < settings.min_plane_inliers:
            break

        plane_model, inliers= remaining.segment_plane(
            distance_threshold= settings.plane_distance_threshold,
            ransac_n= settings.plane_ransac_n,
            num_iterations= settings.plane_num_iterations,
        )

        if len(inliers) < settings.min_plane_inliers:
            break

        normal = np.array(plane_model[:3])
        normal = normal / np.linalg.norm(normal)
        plane_normals.append(normal)

        remaining = remaining.select_by_index(inliers)

    return plane_normals


def _compute_manhattan_alignment(
    plane_normals: list[np.ndarray],
) -> np.ndarray:
    """ccompute a 4x4 rotation matrix that aligns the dom plane norms
    to the nearest XYZ axis. returns identity if no planes foudn"""
    if not plane_normals:
        return np.eye(4)
    
    axes= np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    
    dots = [abs(np.dot(n, np.array([0,1,0]))) for n in plane_normals]
    floor_normal = plane_normals[np.argmax(dots)]

    # rotation tot align floor_normal to Y axis
    y_axis = np.array([0.0, 1.0, 0.0])
    v = np.cross(floor_normal, y_axis)
    s = np.linalg.norm(v)
    c = np.dot(floor_normal, y_axis)

    if s < 1e-6:
        return np.eye(4)

    vx = np.array([
        [0,    -v[2],  v[1]],
        [v[2],  0,    -v[0]],
        [-v[1], v[0],  0   ],
    ])

    R = np.eye(3) + vx + vx @ vx * ((1-c) / (s ** 2))

    T = np.eye(4)
    T[:3, :3] = R
    return T


def _integrate_tsdf(
    frames: list[Path],
    frames_dir: Path,
    depth_dir: Path,
    seg_dir: Path,
    intrinsics: o3d.camera.PinholeCameraIntrinsic,
    alignment: np.ndarray,
    poses: dict[str, np.ndarray],
    settings: ShapeCompletionSettings,
) -> tuple[o3d.pipelines.integration.ScalableTSDFVolume, int]:
    """Integrate all frames into a TSDF volume."""
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=settings.tsdf_voxel_length,
        sdf_trunc=settings.tsdf_sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8,
    )

    integrated = 0
    default_extrinsic = np.linalg.inv(alignment)

    for frame_path in frames:
        stem = frame_path.stem
        depth_path = depth_dir / f"{stem}.png"
        seg_path = seg_dir / f"{stem}.png"
        color_path = frames_dir / frame_path.name

        if not depth_path.exists():
            continue

        color_img = _load_color_o3d(color_path)
        depth_img = _load_depth_o3d(depth_path, seg_path, settings)

        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_img,
            depth_img,
            depth_scale=settings.tsdf_depth_scale,
            depth_trunc=settings.tsdf_depth_max,
            convert_rgb_to_intensity=False,
        )

        if poses and frame_path.name in poses:
            extrinsic= poses[frame_path.name] @ alignment
        else:
            extrinsic = default_extrinsic
            fallback_count+=1

        volume.integrate(
            rgbd,
            intrinsics,
            extrinsic,
        )
        integrated += 1


        if fallback_count > 0:
            log.warning(
                f"{fallback_count}/{integrated} frames used identity pose "
                f"(no SfM pose found for those filenames)"
            )

    return volume, integrated


## Main entrty point

def run_shape_completion(
    req: ShapeCompletionReq,
    settings: ShapeCompletionSettings,
) -> ShapeCompletionResult:
    req.output_dir.mkdir(parents=True, exist_ok=True)

    tsdf_path = req.output_dir / "tsdf.npz"
    mesh_path = req.output_dir / "mesh.ply"

    frames = sorted(req.frames_dir.glob("frame_??????.jpg"))
    if not frames:
        return ShapeCompletionResult(
            job_id=req.job_id,
            ok=False,
            tsdf_path=tsdf_path,
            mesh_path=mesh_path,
            alignment_matrix=tuple(np.eye(4).flatten().tolist()),
            num_frames_integrated=0,
            output_dir=req.output_dir,
            error=f"No frames found in {req.frames_dir}",
        )

    # Get image dimensions from first frame
    first_img = Image.open(frames[0])
    W, H = first_img.size
    intrinsics = _get_intrinsics(W, H, settings.fov_deg)
    log.info(f"Intrinsics: {W}x{H}, focal={intrinsics.get_focal_length()}")

    # Build point cloud for plane fitting
    log.info("Building point cloud...")
    pcd = _build_point_cloud(
        frames, req.depth_dir, req.segmentation_dir, intrinsics, settings
    )
    log.info(f"Point cloud: {len(pcd.points)} points")

    # Fit dominant planes
    log.info("Fitting dominant planes...")
    plane_normals = _fit_dominant_planes(pcd, settings)
    log.info(f"Found {len(plane_normals)} dominant planes")

    # Manhattan alignment
    log.info("Computing Manhattan alignment...")
    alignment = _compute_manhattan_alignment(plane_normals)

    poses:dict[str, np.ndarray] = {}
    if req.sparse_model_dir is not None:
        log.info("Reading SfM camera poses...")
        poses = read_colmap_poses(req.sparse_model_dir, req.colmap_bin)
        log.info(f"Loaded {len(poses)} poses — "
                 f"{'pose-guided' if poses else 'identity fallback'} integration")

    # Apply alignment to point cloud
    pcd.transform(alignment)

    # TSDF fusion
    log.info("Integrating TSDF...")
    volume, num_integrated = _integrate_tsdf(
        frames,
        req.frames_dir,
        req.depth_dir,
        req.segmentation_dir,
        intrinsics,
        alignment,
        poses,
        settings,
    )
    log.info(f"Integrated {num_integrated} frames")

    # Extract mesh for inspection
    log.info("Extracting mesh...")
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(str(mesh_path), mesh)
    log.info(f"Mesh saved to {mesh_path}")

    # Save TSDF as npz for voxelization
    # Extract point cloud from volume as proxy for voxel data
    pcd_from_volume = volume.extract_point_cloud()
    points = np.asarray(pcd_from_volume.points)
    colors = np.asarray(pcd_from_volume.colors)

    np.savez_compressed(
        tsdf_path,
        points=points,
        colors=colors,
        voxel_length=np.array([settings.tsdf_voxel_length]),
        alignment=alignment,
    )
    log.info(f"TSDF saved to {tsdf_path} ({len(points)} points)")

    return ShapeCompletionResult(
        job_id=req.job_id,
        ok=True,
        tsdf_path=tsdf_path,
        mesh_path=mesh_path,
        alignment_matrix=tuple(alignment.flatten().tolist()),
        num_frames_integrated=num_integrated,
        output_dir=req.output_dir,
    )
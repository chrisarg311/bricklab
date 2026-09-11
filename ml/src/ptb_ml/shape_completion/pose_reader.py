"""
Reads COLMAP camera poses from a sparse model directory.
Uses colmap model_converter to convert binary -> text, then parses the text.

COLMAP images.txt format per image (2 lines):
    IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME
    POINTS2D[] as (X, Y, POINT3D_ID)

The extrinsic matrix is R|t where:
    R = rotation_matrix(QW, QX, QY, QZ)  -- world-to-camera rotation
    t = [TX, TY, TZ]                      -- world-to-camera translation
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


def _quat_to_rotation_matrix(qw: float, qx: float, qy: float, qz: float) -> np.ndarray:
    """Convert quaternion to 3x3 rotation matrix."""
    R = np.array([
        [1 - 2*qy**2 - 2*qz**2,  2*qx*qy - 2*qz*qw,  2*qx*qz + 2*qy*qw],
        [2*qx*qy + 2*qz*qw,  1 - 2*qx**2 - 2*qz**2,  2*qy*qz - 2*qx*qw],
        [2*qx*qz - 2*qy*qw,  2*qy*qz + 2*qx*qw,  1 - 2*qx**2 - 2*qy**2],
    ], dtype=np.float64)
    return R


def _parse_images_txt(txt_path: Path) -> dict[str, np.ndarray]:
    """
    Parse images.txt and return dict mapping image filename -> 4x4 extrinsic matrix.
    Extrinsic = [R | t] in homogeneous form (world-to-camera).
    """
    poses: dict[str, np.ndarray] = {}

    lines = txt_path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            i += 1
            continue

        parts = line.split()
        if len(parts) < 9:
            i += 1
            continue

        try:
            # IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME
            qw, qx, qy, qz = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            tx, ty, tz = float(parts[5]), float(parts[6]), float(parts[7])
            name = parts[9]  # image filename

            R = _quat_to_rotation_matrix(qw, qx, qy, qz)
            t = np.array([tx, ty, tz], dtype=np.float64)

            # Build 4x4 extrinsic matrix
            extrinsic = np.eye(4, dtype=np.float64)
            extrinsic[:3, :3] = R
            extrinsic[:3, 3] = t

            poses[name] = extrinsic

        except (ValueError, IndexError) as e:
            log.warning(f"Failed to parse pose line: {line!r} — {e}")

        # Skip the points2D line
        i += 2

    return poses


def read_colmap_poses(
    sparse_model_dir: Path,
    colmap_bin: str = "colmap",
) -> dict[str, np.ndarray]:
    """
    Read camera poses from a COLMAP sparse model directory.
    Returns dict mapping image filename -> 4x4 world-to-camera extrinsic matrix.
    Returns empty dict if poses cannot be read.
    """
    sparse_model_dir = Path(sparse_model_dir)

    if not sparse_model_dir.exists():
        log.warning(f"Sparse model dir does not exist: {sparse_model_dir}")
        return {}

    # Use a temp dir for the converted text model
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        cmd = [
            colmap_bin,
            "model_converter",
            "--input_path", str(sparse_model_dir),
            "--output_path", str(tmp_path),
            "--output_type", "TXT",
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if proc.returncode != 0:
            log.warning(
                f"colmap model_converter failed:\n{proc.stderr}"
            )
            return {}

        images_txt = tmp_path / "images.txt"
        if not images_txt.exists():
            log.warning(f"images.txt not found in {tmp_path}")
            return {}

        poses = _parse_images_txt(images_txt)
        log.info(f"Read {len(poses)} camera poses from {sparse_model_dir}")
        return poses
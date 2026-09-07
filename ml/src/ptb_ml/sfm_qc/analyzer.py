from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ColmapModelStats:
    registered_images: int
    points3d: int
    reprojection_error: float


def run_model_analyzer(
    sparse_model_dir: Path,
    colmap_bin: str = "colmap",
) -> ColmapModelStats:
    """
    Calls `colmap model_analyzer` and parses stdout.
    Raises RuntimeError if the command fails or output can't be parsed.
    """
    cmd = [
        colmap_bin,
        "model_analyzer",
        "--path", str(sparse_model_dir),
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"colmap model_analyzer failed:\n{proc.stderr}"
        )

    return _parse_model_analyzer_output(proc.stdout + proc.stderr)


def _parse_model_analyzer_output(output: str) -> ColmapModelStats:
    """
    Parses colmap model_analyzer output. Example output:
        Cameras: 1
        Images: 17
        Registered images: 16
        Points: 1453
        Observations: 8342
        Mean track length: 5.741
        Mean observations per image: 521.375
        Mean reprojection error: 0.812px
    """
    def extract_int(pattern: str) -> int:
        m = re.search(pattern, output, re.IGNORECASE)
        if not m:
            raise ValueError(
                f"Could not parse pattern '{pattern}' from model_analyzer output:\n{output}"
            )
        return int(m.group(1))

    def extract_float(pattern: str) -> float:
        m = re.search(pattern, output, re.IGNORECASE)
        if not m:
            raise ValueError(
                f"Could not parse pattern '{pattern}' from model_analyzer output:\n{output}"
            )
        return float(m.group(1))

    registered_images = extract_int(r"Registered images:\s*(\d+)")
    points3d = extract_int(r"Points:\s*(\d+)")
    reprojection_error = extract_float(r"Mean reprojection error:\s*([\d.]+)px")

    return ColmapModelStats(
        registered_images=registered_images,
        points3d=points3d,
        reprojection_error=reprojection_error,
    )
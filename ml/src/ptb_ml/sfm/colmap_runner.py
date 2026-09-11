from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess

from .models import SfmReq
from .settings import SfmSettings


@dataclass(frozen=True)
class ColmapCommandResult:
    name: str
    cmd: tuple[str, ...]
    stdout_path: Path
    stderr_path: Path


def _bool01(value: bool) -> str:
    return "1" if value else "0"


def _append_arg(cmd: list[str], flag: str, value: object | None) -> None:
    if value is None:
        return
    cmd.extend([flag, str(value)])


def quote_cmd(cmd: list[str] | tuple[str, ...]) -> str:
    return shlex.join(list(cmd))


def build_feature_extractor_cmd(
    req: SfmReq,
    settings: SfmSettings,
    database_path: Path,
) -> list[str]:
    cmd: list[str] = [
        settings.colmap_bin,
        "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(req.image_dir),
        "--ImageReader.camera_model", settings.camera_model,
        "--ImageReader.single_camera", _bool01(settings.single_camera),
        "--FeatureExtraction.use_gpu", _bool01(settings.use_gpu),
        "--FeatureExtraction.gpu_index", settings.gpu_index,
        "--FeatureExtraction.max_image_size", str(settings.max_image_size),
        "--SiftExtraction.max_num_features", str(settings.max_num_features),
    ]

    if req.mask_dir is not None:
        cmd.extend(["--ImageReader.mask_path", str(req.mask_dir)])

    if req.image_list_path is not None:
        cmd.extend(["--image_list_path", str(req.image_list_path)])

    return cmd


def build_matcher_cmd(
    req: SfmReq,
    settings: SfmSettings,
    database_path: Path,
) -> tuple[str, list[str]]:
    if req.input_mode == "sequential":
        name = "sequential_matcher"
        cmd: list[str] = [
            settings.colmap_bin,
            "sequential_matcher",
            "--database_path", str(database_path),
            "--FeatureMatching.use_gpu", _bool01(settings.use_gpu),
            "--FeatureMatching.gpu_index", settings.gpu_index,
            "--FeatureMatching.max_num_matches", str(settings.max_num_matches),
            "--SequentialMatching.overlap", str(settings.sequential_overlap),
            "--SequentialMatching.quadratic_overlap",
            _bool01(settings.sequential_quadratic_overlap),
            "--SequentialMatching.loop_detection",
            _bool01(settings.sequential_loop_detection),
        ]

        if settings.sequential_loop_detection:
            cmd.extend([
                "--SequentialMatching.loop_detection_period",
                str(settings.sequential_loop_detection_period),
                "--SequentialMatching.loop_detection_num_images",
                str(settings.sequential_loop_detection_num_images),
            ])
        return name, cmd

    name = "exhaustive_matcher"
    cmd = [
        settings.colmap_bin,
        "exhaustive_matcher",
        "--database_path", str(database_path),
        "--FeatureMatching.use_gpu", _bool01(settings.use_gpu),
        "--FeatureMatching.gpu_index", settings.gpu_index,
        "--FeatureMatching.max_num_matches", str(settings.max_num_matches),
    ]
    return name, cmd


def build_mapper_cmd(
    req: SfmReq,
    settings: SfmSettings,
    database_path: Path,
    sparse_dir: Path,
) -> list[str]:
    cmd: list[str] = [
        settings.colmap_bin,
        "mapper",
        "--database_path", str(database_path),
        "--image_path", str(req.image_dir),
        "--output_path", str(sparse_dir),
    ]

    if settings.mapper_ba_use_gpu:
        cmd.extend(["--Mapper.ba_use_gpu", "1"])

    _append_arg(
        cmd,
        "--Mapper.ba_global_max_num_iterations",
        settings.mapper_ba_global_max_num_iterations,
    )
    _append_arg(
        cmd,
        "--Mapper.ba_global_function_tolerance",
        settings.mapper_ba_global_function_tolerance,
    )

    return cmd


def run_colmap_command(
    *,
    name: str,
    cmd: list[str],
    logs_dir: Path,
    cwd: Path | None = None,
) -> ColmapCommandResult:
    logs_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = logs_dir / f"{name}.stdout.log"
    stderr_path = logs_dir / f"{name}.stderr.log"

    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        capture_output=True,
        check=False,
    )

    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    if proc.returncode != 0:
        raise RuntimeError(
            f"COLMAP command failed: {quote_cmd(cmd)}\n"
            f"returncode={proc.returncode}\n"
            f"stdout_log={stdout_path}\n"
            f"stderr_log={stderr_path}"
        )

    return ColmapCommandResult(
        name=name,
        cmd=tuple(cmd),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
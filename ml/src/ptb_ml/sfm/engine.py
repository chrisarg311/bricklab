from __future__ import annotations

from pathlib import Path
import shutil

from .colmap_runner import (
    build_feature_extractor_cmd,
    build_mapper_cmd,
    build_matcher_cmd,
    quote_cmd,
    run_colmap_command,
)
from .models import SfmReq, SfmResult
from .settings import SfmSettings


"""def _prepare_workspace(output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    database_path = output_dir / "database.db"
    sparse_dir = output_dir / "sparse"
    logs_dir = output_dir / "logs"

    # MVP behavior: fresh run each time.
    if database_path.exists():
        database_path.unlink()

    if sparse_dir.exists():
        shutil.rmtree(sparse_dir)
    sparse_dir.mkdir(parents=True, exist_ok=True)

    logs_dir.mkdir(parents=True, exist_ok=True) 

    return database_path, sparse_dir, logs_dir"""

def _resolve_workspace(req: SfmReq) -> tuple[Path, Path, Path]:
    database_path = req.database_path or (req.output_dir / "database.db")
    sparse_dir = req.sparse_dir or (req.output_dir / "sparse")
    logs_dir = req.logs_dir or (req.output_dir / "logs")

    if database_path.exists():
        database_path.unlink()
    if sparse_dir.exists():
        shutil.rmtree(sparse_dir)
    sparse_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    return database_path, sparse_dir, logs_dir


def _find_sparse_models(sparse_dir: Path) -> list[Path]:
    if not sparse_dir.exists():
        return []

    models = [p for p in sparse_dir.iterdir() if p.is_dir() and p.name.isdigit()]
    return sorted(models, key=lambda p: int(p.name))


def run_sfm(req: SfmReq, settings: SfmSettings) -> SfmResult:
    if not settings.enabled:
        return SfmResult(
            ok=False,
            job_id=req.job_id,
            input_mode=req.input_mode,
            image_dir=req.image_dir,
            output_dir=req.output_dir,
            database_path=req.output_dir / "database.db",
            sparse_dir=req.output_dir / "sparse",
            best_model_dir=None,
            error="SFM is disabled in SfmSettings.",
        )

    if not req.image_dir.exists():
        return SfmResult(
            ok=False,
            job_id=req.job_id,
            input_mode=req.input_mode,
            image_dir=req.image_dir,
            output_dir=req.output_dir,
            database_path=req.output_dir / "database.db",
            sparse_dir=req.output_dir / "sparse",
            best_model_dir=None,
            error=f"Input image_dir does not exist: {req.image_dir}",
        )

    if req.mask_dir is not None and not req.mask_dir.exists():
        return SfmResult(
            ok=False,
            job_id=req.job_id,
            input_mode=req.input_mode,
            image_dir=req.image_dir,
            output_dir=req.output_dir,
            database_path=req.output_dir / "database.db",
            sparse_dir=req.output_dir / "sparse",
            best_model_dir=None,
            error=f"Input mask_dir does not exist: {req.mask_dir}",
        )

    database_path, sparse_dir, logs_dir = _resolve_workspace(req)

    commands: list[str] = []
    log_paths: list[Path] = []

    try:
        feature_cmd = build_feature_extractor_cmd(req, settings, database_path)
        commands.append(quote_cmd(feature_cmd))
        res = run_colmap_command(
            name="feature_extractor",
            cmd=feature_cmd,
            logs_dir=logs_dir,
        )
        log_paths.extend([res.stdout_path, res.stderr_path])

        matcher_name, matcher_cmd = build_matcher_cmd(req, settings, database_path)
        commands.append(quote_cmd(matcher_cmd))
        res = run_colmap_command(
            name=matcher_name,
            cmd=matcher_cmd,
            logs_dir=logs_dir,
        )
        log_paths.extend([res.stdout_path, res.stderr_path])

        mapper_cmd = build_mapper_cmd(req, settings, database_path, sparse_dir)
        commands.append(quote_cmd(mapper_cmd))
        res = run_colmap_command(
            name="mapper",
            cmd=mapper_cmd,
            logs_dir=logs_dir,
        )
        log_paths.extend([res.stdout_path, res.stderr_path])

        models = _find_sparse_models(sparse_dir)
        best_model_dir = models[0] if models else None

        return SfmResult(
            ok=True,
            job_id=req.job_id,
            input_mode=req.input_mode,
            image_dir=req.image_dir,
            output_dir=req.output_dir,
            database_path=database_path,
            sparse_dir=sparse_dir,
            best_model_dir=best_model_dir,
            commands=tuple(commands),
            log_paths=tuple(log_paths),
            num_sparse_models=len(models),
            error=None,
        )

    except Exception as exc:
        return SfmResult(
            ok=False,
            job_id=req.job_id,
            input_mode=req.input_mode,
            image_dir=req.image_dir,
            output_dir=req.output_dir,
            database_path=database_path,
            sparse_dir=sparse_dir,
            best_model_dir=None,
            commands=tuple(commands),
            log_paths=tuple(log_paths),
            num_sparse_models=0,
            error=str(exc),
        )
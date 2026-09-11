from __future__ import annotations

from .analyzer import run_model_analyzer
from .models import SfmQcMetrics, SfmQcReq, SfmQcResult
from .settings import SfmQcSettings


def _score_metric(
    value: float,
    minimum: float,
    target: float,
    lower_is_better: bool = False,
) -> float:
    """
    Returns a 0.0-1.0 score for a single metric.
    Below minimum → 0.0. At or beyond target → 1.0. Linear in between.
    """
    if lower_is_better:
        # Flip so minimum/target logic still applies
        value = -value
        minimum = -minimum
        target = -target

    if value <= minimum:
        return 0.0
    if value >= target:
        return 1.0
    return (value - minimum) / (target - minimum)


def _compute_score(
    metrics: SfmQcMetrics,
    settings: SfmQcSettings,
) -> float:
    # Hard floor checks — any single failure forces score to 0.0
    if metrics.registered_images < settings.min_registered_images:
        return 0.0
    if metrics.points3d < settings.min_points3d:
        return 0.0
    if metrics.reprojection_error > settings.max_reprojection_error:
        return 0.0

    s_images = _score_metric(
        metrics.registered_images,
        minimum=settings.min_registered_images,
        target=settings.target_registered_images,
    )
    s_points = _score_metric(
        metrics.points3d,
        minimum=settings.min_points3d,
        target=settings.target_points3d,
    )
    s_reproj = _score_metric(
        metrics.reprojection_error,
        minimum=settings.max_reprojection_error,
        target=settings.target_reprojection_error,
        lower_is_better=True,
    )

    return (
        s_images * settings.weight_registered_images
        + s_points * settings.weight_points3d
        + s_reproj * settings.weight_reprojection_error
    )


def run_sfm_qc(req: SfmQcReq, settings: SfmQcSettings) -> SfmQcResult:
    if not req.sparse_model_dir.exists():
        return SfmQcResult(
            job_id=req.job_id,
            ok=False,
            route="orange",
            score=0.0,
            error=f"sparse_model_dir does not exist: {req.sparse_model_dir}",
        )

    try:
        stats = run_model_analyzer(
            req.sparse_model_dir,
            colmap_bin=settings.colmap_bin,
        )
    except Exception as exc:
        return SfmQcResult(
            job_id=req.job_id,
            ok=False,
            route="orange",
            score=0.0,
            error=str(exc),
        )

    pct_registered = min(1.0, stats.registered_images / req.num_input_images
            if req.num_input_images > 0 else 0.0)

    metrics = SfmQcMetrics(
        registered_images=stats.registered_images,
        points3d=stats.points3d,
        reprojection_error=stats.reprojection_error,
        pct_registered=pct_registered,
    )

    score = _compute_score(metrics, settings)
    route = "blue" if score >= settings.blue_threshold else "orange"

    return SfmQcResult(
        job_id=req.job_id,
        ok=True,
        route=route,
        score=score,
        metrics=metrics,
    )
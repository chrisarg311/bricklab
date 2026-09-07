"""
Celery worker tasks for PictoBrick.

Phase 1 implements a single task: run_mosaic_job
  - Downloads the uploaded image from storage
  - Runs depth-aware colour quantisation (mosaic_engine)
  - Generates a thumbnail
  - Uploads the thumbnail to storage
  - Writes the result JSON to the jobs table

Celery is configured with Redis as both broker and result backend.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import tempfile
from pathlib import Path

from celery import Celery
from PIL import Image

log = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "pictobrick",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry failed tasks at most twice with a short back-off
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


# ---------------------------------------------------------------------------
# Task: run_mosaic_job
# ---------------------------------------------------------------------------

@celery_app.task(
    name="tasks.run_mosaic_job",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def run_mosaic_job(self, job_id: str, s3_key: str, detail: str) -> None:
    """
    Async 2-D mosaic pipeline.

    Args:
        job_id:  UUID string matching jobs.id in PostgreSQL.
        s3_key:  Storage key of the uploaded source image.
        detail:  "Low" | "Medium" | "High"
    """
    # Import here so the module can be imported by app.py without loading
    # heavy ML deps at FastAPI startup (they're already loaded there anyway,
    # but this keeps the dependency graph explicit).
    from db import update_job
    from storage import download_to_path, upload_bytes, presign_url
    from mosaic_engine import (
        _get_depth_pipe,
        build_parts_list,
        depth_aware_quantize,
        grid_dims_for,
        render_thumb,
    )

    try:
        # ── Stage: loading ────────────────────────────────────────────────
        update_job(job_id, status="running", stage="loading", progress=5)
        log.info("[%s] Downloading image from storage key: %s", job_id, s3_key)

        with tempfile.TemporaryDirectory() as tmp_dir:
            img_path = Path(tmp_dir) / "input.jpg"
            download_to_path(s3_key, img_path)
            pil_img = Image.open(img_path).convert("RGB")

        grid_w, grid_h = grid_dims_for(detail, pil_img.width, pil_img.height)
        log.info("[%s] Grid: %dx%d (detail=%s)", job_id, grid_w, grid_h, detail)

        # ── Stage: depth inference ────────────────────────────────────────
        update_job(job_id, stage="depth", progress=15)
        log.info("[%s] Running depth estimation…", job_id)
        depth_pipe = _get_depth_pipe()

        # ── Stage: quantising ─────────────────────────────────────────────
        update_job(job_id, stage="quantizing", progress=30)
        log.info("[%s] Quantising colours…", job_id)
        indices = depth_aware_quantize(pil_img, grid_w, grid_h, depth_pipe)

        # ── Stage: building parts list ────────────────────────────────────
        update_job(job_id, stage="parts", progress=80)
        parts = build_parts_list(indices)

        # ── Stage: thumbnail ──────────────────────────────────────────────
        update_job(job_id, stage="thumbnail", progress=88)
        log.info("[%s] Rendering thumbnail…", job_id)
        thumb_bytes = render_thumb(indices, grid_w, grid_h)

        thumb_key = f"thumbnails/{job_id}.jpg"
        upload_bytes(thumb_bytes, thumb_key, content_type="image/jpeg")
        log.info("[%s] Thumbnail uploaded to %s", job_id, thumb_key)

        # Embed thumbnail as base64 data URL so the frontend can display it
        # immediately without a separate storage fetch (important for local
        # dev where presign_url returns a placeholder).
        thumb_b64 = base64.b64encode(thumb_bytes).decode()
        thumb_data_url = f"data:image/jpeg;base64,{thumb_b64}"

        # ── Complete ──────────────────────────────────────────────────────
        result = {
            "grid_w": grid_w,
            "grid_h": grid_h,
            "palette_indices": indices,
            "parts": parts,
            "thumb_key": thumb_key,
            "thumb_data_url": thumb_data_url,   # always available, no presign needed
        }
        update_job(
            job_id,
            status="completed",
            stage=None,
            progress=100,
            result_json=json.dumps(result),
        )
        log.info("[%s] Job completed (%d bricks, %d colours)", job_id, len(indices), len(parts))

    except Exception as exc:
        log.exception("[%s] Job failed: %s", job_id, exc)
        update_job(job_id, status="failed", error=str(exc))
        raise self.retry(exc=exc)

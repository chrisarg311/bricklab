"""
FastAPI server for PictoBrick ML endpoints.

Phase 0 additions:
  POST /api/mosaic          — synchronous depth-aware colour quantisation

Phase 1 additions:
  POST /api/jobs            — create an async mosaic job (Celery)
  GET  /api/jobs/{job_id}   — poll job status
  GET  /api/jobs/{job_id}/result — fetch completed result

Existing:
  POST /api/depth-grid      — kept for the 3-D bas-relief viewer
  GET  /health
"""
from __future__ import annotations

import base64
import io
import json
import logging
import uuid
from datetime import datetime

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

import auth as _auth  # Clerk JWT helpers

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="PictoBrick ML API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    from db import init_db
    init_db()


# ---------------------------------------------------------------------------
# Helpers — imported lazily to keep the module importable even if some deps
# are missing (e.g. running unit tests without torch installed).
# ---------------------------------------------------------------------------

def _depth_pipe():
    from mosaic_engine import _get_depth_pipe
    return _get_depth_pipe()


# ---------------------------------------------------------------------------
# Existing: /api/depth-grid  (unchanged, used by the 3-D viewer)
# ---------------------------------------------------------------------------

class DepthGridReq(BaseModel):
    image_b64: str
    grid_w: int
    grid_h: int
    max_height: int = 8


class DepthGridResp(BaseModel):
    depths: list[int]


@app.post("/api/depth-grid", response_model=DepthGridResp)
def depth_grid(req: DepthGridReq) -> DepthGridResp:
    if req.grid_w < 1 or req.grid_h < 1 or req.grid_w * req.grid_h > 25_000:
        raise HTTPException(400, "Invalid grid dimensions")
    if req.max_height < 1 or req.max_height > 32:
        raise HTTPException(400, "max_height must be 1–32")

    b64 = req.image_b64
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    try:
        pil_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    except Exception as exc:
        raise HTTPException(400, f"Could not decode image: {exc}") from exc

    pipe = _depth_pipe()
    result = pipe(pil_img)
    depth_pil = result["depth"]
    depth_np = np.array(depth_pil, dtype=np.float32)

    depth_small = np.array(
        Image.fromarray(depth_np).resize((req.grid_w, req.grid_h), Image.LANCZOS),
        dtype=np.float32,
    )
    d_min, d_max = depth_small.min(), depth_small.max()
    norm = (depth_small - d_min) / (d_max - d_min) if d_max > d_min else np.full_like(depth_small, 0.5)
    heights = np.clip(np.round(norm * (req.max_height - 1) + 1).astype(int), 1, req.max_height)

    return DepthGridResp(depths=heights.flatten().tolist())


# ---------------------------------------------------------------------------
# Phase 0: POST /api/mosaic  (synchronous, ~2-4 s)
# ---------------------------------------------------------------------------

@app.post("/api/mosaic")
async def mosaic(
    image: UploadFile = File(...),
    detail: str = Form(default="Medium"),
) -> dict:
    """
    Accepts a single image file and returns the depth-aware colour-quantised
    mosaic as palette indices + parts list.  Runs synchronously — suited for
    the studio preview where the user is waiting in-browser.
    """
    from mosaic_engine import build_parts_list, depth_aware_quantize, grid_dims_for

    data = await image.read()
    try:
        pil_img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(400, f"Could not decode image: {exc}") from exc

    grid_w, grid_h = grid_dims_for(detail, pil_img.width, pil_img.height)
    indices = depth_aware_quantize(pil_img, grid_w, grid_h, _depth_pipe())
    parts = build_parts_list(indices)

    return {
        "grid_w": grid_w,
        "grid_h": grid_h,
        "palette_indices": indices,
        "parts": parts,
    }


# ---------------------------------------------------------------------------
# Phase 1: POST /api/jobs  — create async job
# ---------------------------------------------------------------------------

@app.post("/api/jobs", status_code=202)
async def create_job(
    image: UploadFile = File(...),
    detail: str = Form(default="Medium"),
    title: str = Form(default=""),
    user_id: str = Depends(_auth.get_optional_user_id),
) -> dict:
    """
    Accepts an image upload, stores it, and enqueues a Celery task.
    Returns immediately with a job_id the client can poll.

    user_id is resolved from the Clerk JWT in the Authorization header.
    Falls back to "anonymous" if no token is provided (local dev / PoC).
    """
    from db import create_job as db_create_job
    from storage import upload_bytes
    from tasks import run_mosaic_job

    job_id = str(uuid.uuid4())
    data = await image.read()

    s3_key = f"uploads/{user_id}/{job_id}/input.jpg"
    upload_bytes(data, s3_key, content_type=image.content_type or "image/jpeg")
    log.info("[%s] Image uploaded to storage key: %s", job_id, s3_key)

    resolved_title = title.strip() or f"Build {datetime.now().strftime('%b %d')}"
    db_create_job(
        job_id,
        user_id=user_id,
        title=resolved_title,
        detail=detail,
        input_s3_key=s3_key,
    )

    run_mosaic_job.delay(job_id, s3_key, detail)
    log.info("[%s] Enqueued run_mosaic_job (detail=%s, user=%s)", job_id, detail, user_id)

    return {"job_id": job_id, "status": "queued"}


# ---------------------------------------------------------------------------
# Phase 1: GET /api/jobs/{job_id}  — poll status
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    from db import get_job

    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")

    return {
        "job_id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "progress": job["progress"],
        "error": job["error"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


# ---------------------------------------------------------------------------
# Phase 1: GET /api/jobs/{job_id}/result  — fetch completed result
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/result")
def get_job_result(job_id: str) -> dict:
    from db import get_job

    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job["status"] != "completed":
        raise HTTPException(400, f"Job status is '{job['status']}', not completed")
    if not job.get("result_json"):
        raise HTTPException(500, "Job marked completed but result is missing")

    result = json.loads(job["result_json"])
    return result


# ---------------------------------------------------------------------------
# Phase 2: builds endpoints (auth required)
# ---------------------------------------------------------------------------

@app.get("/api/builds")
def list_builds(user_id: str = Depends(_auth.get_current_user_id)) -> dict:
    """
    Return all completed jobs for the authenticated user, formatted as build
    summaries suitable for the my-builds gallery.
    """
    from db import list_jobs_for_user
    builds = list_jobs_for_user(user_id)
    return {"builds": builds}


@app.patch("/api/builds/{build_id}")
def rename_build(
    build_id: str,
    body: dict,
    user_id: str = Depends(_auth.get_current_user_id),
) -> dict:
    """Rename a build.  Expects JSON body: {"title": "New name"}"""
    from db import rename_job
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title must not be empty")
    if not rename_job(build_id, user_id, title):
        raise HTTPException(404, "Build not found or not owned by this user")
    return {"ok": True}


@app.delete("/api/builds/{build_id}", status_code=204)
def delete_build(
    build_id: str,
    user_id: str = Depends(_auth.get_current_user_id),
) -> None:
    """Permanently delete a build."""
    from db import delete_job
    if not delete_job(build_id, user_id):
        raise HTTPException(404, "Build not found or not owned by this user")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"ok": True}

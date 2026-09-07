"""
Database helpers for PictoBrick job tracking.
Uses synchronous SQLAlchemy (compatible with Celery workers).
Schema is created at startup via CREATE TABLE IF NOT EXISTS — no migration
tooling needed for Phase 1.  Alembic can be layered on top later.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from sqlalchemy import create_engine, text

log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/pictobrick",
)

_engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they don't exist.  Safe to call multiple times."""
    with _engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS jobs (
                id           TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL DEFAULT 'anonymous',
                title        TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'queued',
                stage        TEXT,
                progress     INTEGER NOT NULL DEFAULT 0,
                mode         TEXT NOT NULL DEFAULT '2d_mosaic',
                detail       TEXT NOT NULL DEFAULT 'Medium',
                input_s3_key TEXT,
                result_json  TEXT,
                error        TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
    log.info("DB schema ready.")


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def create_job(
    job_id: str,
    *,
    user_id: str = "anonymous",
    title: str = "",
    mode: str = "2d_mosaic",
    detail: str = "Medium",
    input_s3_key: str | None = None,
) -> None:
    with _engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO jobs (id, user_id, title, mode, detail, input_s3_key)
                VALUES (:id, :user_id, :title, :mode, :detail, :input_s3_key)
            """),
            {
                "id": job_id,
                "user_id": user_id,
                "title": title,
                "mode": mode,
                "detail": detail,
                "input_s3_key": input_s3_key,
            },
        )


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: int | None = None,
    result_json: str | None = None,
    error: str | None = None,
) -> None:
    """Update any subset of mutable job fields plus updated_at."""
    sets: list[str] = ["updated_at = NOW()"]
    params: dict[str, Any] = {"id": job_id}

    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if stage is not None:
        sets.append("stage = :stage")
        params["stage"] = stage
    if progress is not None:
        sets.append("progress = :progress")
        params["progress"] = progress
    if result_json is not None:
        sets.append("result_json = :result_json")
        params["result_json"] = result_json
    if error is not None:
        sets.append("error = :error")
        params["error"] = error

    with _engine.begin() as conn:
        conn.execute(
            text(f"UPDATE jobs SET {', '.join(sets)} WHERE id = :id"),  # noqa: S608
            params,
        )


def list_jobs_for_user(user_id: str) -> list[dict[str, Any]]:
    """
    Return summary rows for all completed jobs owned by *user_id*, newest first.

    Only the fields needed by the my-builds list are returned — the full
    palette_indices array is omitted to keep the response small.
    """
    with _engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, title, detail, result_json, created_at
                FROM   jobs
                WHERE  user_id = :uid AND status = 'completed'
                ORDER  BY created_at DESC
            """),
            {"uid": user_id},
        ).mappings().all()

    summaries = []
    for row in rows:
        d: dict[str, Any] = dict(row)
        if d.get("created_at") is not None:
            d["created_at"] = d["created_at"].isoformat()

        result: dict = {}
        if d.get("result_json"):
            try:
                result = json.loads(d["result_json"])
            except Exception:
                pass

        summaries.append({
            "id":             d["id"],
            "title":          d["title"],
            "detail":         d["detail"],
            "grid_w":         result.get("grid_w"),
            "grid_h":         result.get("grid_h"),
            "thumb_data_url": result.get("thumb_data_url"),
            "parts_count":    len(result.get("parts", [])),
            "created_at":     d["created_at"],
        })
    return summaries


def delete_job(job_id: str, user_id: str) -> bool:
    """Delete a job row.  Returns True if a row was deleted, False if not found / not owned."""
    with _engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM jobs WHERE id = :id AND user_id = :uid"),
            {"id": job_id, "uid": user_id},
        )
    return result.rowcount > 0


def rename_job(job_id: str, user_id: str, title: str) -> bool:
    """Rename a job.  Returns True on success."""
    with _engine.begin() as conn:
        result = conn.execute(
            text("UPDATE jobs SET title = :title, updated_at = NOW() WHERE id = :id AND user_id = :uid"),
            {"title": title.strip(), "id": job_id, "uid": user_id},
        )
    return result.rowcount > 0


def get_job(job_id: str) -> dict[str, Any] | None:
    with _engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM jobs WHERE id = :id"),
            {"id": job_id},
        ).mappings().first()
    if row is None:
        return None
    d = dict(row)
    # Deserialise result_json if present
    if d.get("result_json"):
        try:
            d["result_parsed"] = json.loads(d["result_json"])
        except Exception:
            d["result_parsed"] = None
    # Convert timestamps to ISO strings for JSON serialisation
    for key in ("created_at", "updated_at"):
        if d.get(key) is not None:
            d[key] = d[key].isoformat()
    return d

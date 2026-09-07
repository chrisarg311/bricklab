/**
 * Typed API client for PictoBrick ML endpoints.
 * All functions call Next.js proxy routes (never FastAPI directly from the browser).
 */

import type { DetailLevel, PartsRow } from "./mosaic";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type MosaicResult = {
  grid_w: number;
  grid_h: number;
  palette_indices: number[];
  parts: PartsRow[];
};

export type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string | null;
  progress: number;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type JobResult = {
  grid_w: number;
  grid_h: number;
  palette_indices: number[];
  parts: PartsRow[];
  thumb_key: string;
  /** Base64 data URL — always present, no pre-sign needed. */
  thumb_data_url: string;
};

// ---------------------------------------------------------------------------
// Phase 0: synchronous mosaic (used by studio preview → final generate)
// ---------------------------------------------------------------------------

/**
 * POST /api/ml/mosaic
 * Sends one image file + detail level. Returns depth-aware quantised result.
 * Typical latency: 2–4 s (depth model inference).
 */
export async function createMosaicSync(
  image: File,
  detail: DetailLevel
): Promise<MosaicResult> {
  const form = new FormData();
  form.append("image", image);
  form.append("detail", detail);

  const res = await fetch("/api/ml/mosaic", { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Mosaic request failed (${res.status}): ${text}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase 1: async job lifecycle
// ---------------------------------------------------------------------------

/**
 * POST /api/jobs
 * Uploads one image and enqueues an async mosaic job.
 * Returns immediately with a job_id to poll.
 */
export async function submitJob(
  image: File,
  detail: DetailLevel,
  title: string
): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("image", image);
  form.append("detail", detail);
  form.append("title", title);

  const res = await fetch("/api/jobs", { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Job submission failed (${res.status}): ${text}`);
  }
  return res.json();
}

/**
 * GET /api/jobs/{jobId}
 * Returns the current job status and progress percentage.
 */
export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Status check failed (${res.status}): ${text}`);
  }
  return res.json();
}

/**
 * GET /api/jobs/{jobId}/result
 * Fetches the completed result payload. Only call when status === "completed".
 */
export async function getJobResult(jobId: string): Promise<JobResult> {
  const res = await fetch(`/api/jobs/${jobId}/result`);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Result fetch failed (${res.status}): ${text}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase 2: builds (server-persisted, auth-gated)
// ---------------------------------------------------------------------------

/**
 * Summary shape returned by GET /api/builds.
 * Intentionally lightweight — does NOT include palette_indices.
 */
export type BuildSummary = {
  id: string;
  title: string;
  detail: string;
  grid_w: number;
  grid_h: number;
  thumb_data_url: string | null;
  parts_count: number;
  created_at: string;
};

/**
 * GET /api/builds
 * Returns all completed builds for the signed-in user.
 * Throws if the user is not authenticated or the service is unreachable.
 */
export async function listBuilds(): Promise<BuildSummary[]> {
  const res = await fetch("/api/builds");
  if (res.status === 401) return [];        // not signed in yet — empty list
  if (!res.ok) {
    throw new Error(`Failed to load builds (${res.status})`);
  }
  const data = await res.json();
  return data.builds ?? [];
}

/**
 * PATCH /api/builds/{id}
 * Rename a build server-side.
 */
export async function renameBuildRemote(id: string, title: string): Promise<void> {
  const res = await fetch(`/api/builds/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Rename failed (${res.status}): ${text}`);
  }
}

/**
 * DELETE /api/builds/{id}
 * Permanently delete a build server-side.
 */
export async function deleteBuildRemote(id: string): Promise<void> {
  const res = await fetch(`/api/builds/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Delete failed (${res.status}): ${text}`);
  }
}

// ---------------------------------------------------------------------------
// Helper: convert a base64 data URL to a File object
// ---------------------------------------------------------------------------

export function dataUrlToFile(dataUrl: string, filename: string): File {
  const [header, b64] = dataUrl.split(",", 2);
  const mime = header.match(/:(.*?);/)?.[1] ?? "image/jpeg";
  const bytes = atob(b64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  return new File([arr], filename, { type: mime });
}

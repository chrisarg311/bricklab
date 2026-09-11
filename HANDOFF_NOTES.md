# PictoBrick – Developer Handoff Notes

## What It Does

PictoBrick lets users upload photos or videos and converts them into LEGO mosaic/3D build instructions. There are two distinct features:

1. **2D Mosaic Studio** – upload a photo, get a color-quantized brick layout and parts list. Runs entirely in the browser (no server needed for this part).
2. **3D Model Builder** – upload a video or image set, the ML pipeline reconstructs a 3D LEGO sculpture and outputs a GLB model file with step-by-step build instructions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| ML Backend | Python / FastAPI |
| Database | PostgreSQL 15 |
| Cache / Queue | Redis 7 |
| Auth | Clerk |
| 3D Viewing | Three.js (GLB viewer) |
| Containerization | Docker Compose |

---

## Project Structure

```
pictobrickWebApp/
├── compose.yaml          # Docker Compose – runs everything
├── frontend/             # Next.js app
│   ├── app/              # Pages and API routes
│   └── ...
└── ml/                   # Python ML package + FastAPI server
    ├── app.py            # FastAPI server entry point
    ├── main.py           # CLI entry point for running the pipeline locally
    └── src/ptb_ml/       # Core ML pipeline code
```

---

## How to Run

### Full stack (recommended)
```bash
docker compose up
```
- Frontend: http://localhost:3000
- FastAPI ML server: http://localhost:8000
- Postgres: localhost:5432
- Redis: localhost:6379

### Frontend only (dev mode)
```bash
cd frontend
npm install
npm run dev
```

### ML pipeline locally (no Docker)
```bash
cd ml
python main.py --job-id my-test-job path/to/video.mp4
```

---

## Environment Variables

There is a `.env.local` file in the project root that is **gitignored** — you need to share this manually (via password manager). It contains:

- `CLERK_SECRET_KEY` – secret key for Clerk auth

Everything else is either already in `compose.yaml` (Postgres/Redis credentials are just `postgres/postgres` for dev) or is a public key safe to commit.

For the ML service, see `ml/.env.example`.

---

## Frontend Pages

| Route | What it does |
|---|---|
| `/` | Landing / marketing page |
| `/create` | 2D Mosaic Studio (main feature) |
| `/create-3d` | 3D Model Builder (upload video/images) |
| `/build/[id]` | View a saved mosaic build |
| `/my-builds` | List of user's saved builds |
| `/model/[jobId]` | View completed 3D GLB model |
| `/gallery` | Gallery page |
| `/pricing` | Pricing page |
| `/faq` | FAQ page |

---

## Frontend → ML API (How They Talk)

The Next.js app has proxy API routes under `frontend/app/api/ml/` that forward requests to the FastAPI server so the browser never hits FastAPI directly.

| Next.js Route | Forwards to FastAPI |
|---|---|
| `POST /api/ml/jobs` | Start a 3D pipeline job |
| `GET /api/ml/jobs/[jobId]` | Poll job status |
| `GET /api/ml/jobs/[jobId]/glb` | Download the finished GLB file |
| `POST /api/ml/depth-grid` | Single-image depth estimation |

The frontend polls job status every 3 seconds until the job is `done` or `failed`, then redirects to `/model/[jobId]`.

---

## ML Pipeline (3D Model Builder)

When a video or image set is uploaded, it runs through these stages in order:

1. **Preprocess** – extracts frames from video, applies quality filters (sharpness, brightness), deduplicates similar frames
2. **SfM (Structure from Motion)** – runs COLMAP to reconstruct a 3D point cloud from the frames
3. **SfM QC** – quality-checks the SfM output, scores and routes to "orange" (full) or "blue" (fallback) pipeline
4. **Learned Priors** – runs depth estimation, surface normals, and segmentation on each frame
5. **Shape Completion** – integrates depth/normals into a TSDF mesh
6. **Voxelization** – converts the mesh into a voxel grid
7. **Brickification** – maps voxels to LEGO bricks, produces a bill of materials (BOM)
8. **Instructions** – generates a `.glb` 3D file and a step-by-step JSON build guide

Each stage is a separate module under `ml/src/ptb_ml/`. If any stage fails, the pipeline stops and returns an error.

**Note:** Currently the pipeline always routes to "orange" (full pipeline). The "blue" (simpler) route is marked as TODO.

---

## 2D Mosaic (How It Works Client-Side)

All the mosaic logic lives in `frontend/lib/mosaic.ts`. When a user uploads a photo:
1. The image is quantized using dithering into LEGO color indices
2. A canvas renders the brick grid with an animated scan-line reveal
3. On "Generate Layout", the build is saved to localStorage and the user is redirected to `/build/[id]`

No server call is made for 2D mosaics — it's entirely in the browser.

---

## Auth

Auth is handled by **Clerk** (`@clerk/nextjs`). The middleware at `frontend/middleware.ts` protects routes. You'll need a Clerk account and the keys from `.env.local` to run the app with auth working.

---

## Key Things Still In Progress / TODOs

- The "blue" (lower-quality fallback) pipeline route is not yet implemented
- Debug mode for storing pipeline diagnostics is marked TODO in `main.py`
- The `--relax-quality-filter` flag was added as a test option for challenging datasets

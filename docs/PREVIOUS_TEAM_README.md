<!-- Verbatim copy of the previous team's root README from
     Aleonawork/AIPurpixBrickLab @ 5d9cbf5, kept for reference.
     Some of it is out of date for our repo — see docs/PREVIOUS_TEAM.md. -->

# AIPurpixBrickLab

Monorepo for the PictoBrick / Purpix project — a web app that turns user photos into buildable LEGO-style brick mosaics and 3D LEGO sculptures.

## Repo Layout

```
AIPurpixBrickLab/
├── pictobrickWebApp/
│   ├── frontend/             # Next.js 16 (App Router, React 19, Tailwind v4, shadcn, Three.js)
│   ├── ml/                   # FastAPI ML service (depth estimation + full 3-D pipeline)
│   └── compose.yaml          # Docker Compose: frontend + fastapi + postgres + redis
└── README.md
```

## Prerequisites

- Docker Desktop (for `docker compose`)
- Node.js ≥ 20.9 (only for running frontend outside Docker)
- Access to the Clerk workspace — ask the project owner for `CLERK_SECRET_KEY`

## First-Time Setup

1. **Clone** the repo.
2. **Create the secrets file** at `pictobrickWebApp/.env.local`:
   ```
   CLERK_SECRET_KEY=sk_test_...
   ```
   Gitignored. The Clerk publishable key is already baked into `compose.yaml`.
3. **Start the stack:**
   ```bash
   cd pictobrickWebApp
   docker compose up --build
   ```
4. Open <http://localhost:3000>.

> **First build is slow** — the FastAPI container downloads the Depth Anything V2 model (~100 MB) and bakes it into the image. Subsequent builds use the cached layer.

## Services

| Service    | Port | Description |
| ---------- | ---- | ----------- |
| `frontend` | 3000 | Next.js app |
| `fastapi`  | 8000 | ML API (depth estimation, 3-D job queue) |
| `postgres` | 5432 | Database (reserved for future persistence) |
| `redis`    | 6379 | Cache (reserved for future use) |

## Common Commands

| Action | From `pictobrickWebApp/` |
| --- | --- |
| Start everything | `docker compose up --build` |
| Stop everything | `docker compose down` |
| Rebuild after code change | `docker compose up --build` |
| Tail frontend logs | `docker compose logs -f frontend` |
| Tail ML service logs | `docker compose logs -f fastapi` |

## Features

### Mosaic Generation (`/create`)
- Upload up to 5 photos
- **Live preview** — mosaic animates onto the canvas with a glowing orange scan-line as soon as a photo is uploaded; re-animates when detail level changes
- Detail levels: Low (48 studs), Medium (72), High (104) on the long edge
- **Floyd-Steinberg dithering** for smooth color transitions
- Custom build name input
- Generates and saves to browser `localStorage`; routes to result page

### Build Result Page (`/build/[id]`)
- **2D mosaic** with color-highlight on hover (hover a parts-list row → other bricks dim)
- **Before/After toggle** — flip between original photo and mosaic
- **Build Guide mode** — step through one color at a time like real LEGO instructions; progress bar; click any row to jump to that step
- **3D View** — full WebGL scene (Three.js, `InstancedMesh`): beveled bricks + studs, orbit controls, auto-rotate, color highlight synced with parts list
- **AI Depth (bas-relief)** — when the FastAPI service is running, clicking 3D View fetches a depth grid from Depth Anything V2 and stacks each brick column to the correct height, giving a sculpted bas-relief effect
- Download PNG / Download GLB
- Delete build

### My Builds (`/my-builds`)
- Real thumbnails from `localStorage`
- Click card → result page; trash icon → confirm + delete
- Inline rename (pencil icon on card title)

### 3D Model Builder (`/create-3d`)
- Upload a video or image set (walk around your subject)
- Polls job status every 3 seconds with elapsed timer
- On completion, opens a full GLB viewer at `/model/[jobId]`
- Requires the full pipeline container — see **Full 3-D Pipeline** below

## Authentication

All generative routes require sign-in via Clerk (modal). Protected routes:
`/create`, `/build/*`, `/my-builds`, `/create-3d`, `/model/*`

## ML Service

### Depth endpoint (always available)
```
POST /api/depth-grid
```
Accepts a base64 image + grid dimensions, returns per-cell brick heights using Depth Anything V2 Small. Called automatically by the frontend when 3D View is opened.

### 3-D pipeline endpoint (requires `Dockerfile.pipeline`)
```
POST /api/jobs/3d      — upload video/images, get job_id
GET  /api/jobs/3d/{id} — poll status
GET  /api/jobs/3d/{id}/glb — download finished GLB
```
The default `Dockerfile.fastapi` is lightweight (depth only). The full pipeline (COLMAP + Open3D + TSDF + brickification) uses `Dockerfile.pipeline`:

```bash
cd pictobrickWebApp/ml
docker build -f Dockerfile.pipeline -t ptb-pipeline .
docker run -p 8000:8000 -v $(pwd)/jobs:/tmp/ptb_jobs ptb-pipeline
```

### Standalone demo script
Generate a GLB from a single image without the web app:

```bash
cd pictobrickWebApp/ml

# Install deps (once)
pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
pip install transformers accelerate pillow numpy pygltflib

# Generate
python3 scripts/generate_demo.py dog.jpg demo.glb --size 96 --max-height 12
```

Open `demo.glb` at <https://gltf.report> or in Blender.

## Deployment (AWS Amplify + separate ML host)

Amplify deploys the Next.js frontend only. The FastAPI service needs its own host:

1. Deploy `Dockerfile.fastapi` to Railway, Render, Fly.io, or AWS App Runner
2. In **Amplify console → Environment variables** set:
   ```
   FASTAPI_INTERNAL_URL=https://your-ml-service.railway.app
   ```
3. Redeploy on Amplify

## Troubleshooting

- **"Missing publishableKey"** → `.env.local` is missing or compose wasn't rebuilt. Run `docker compose up --build`.
- **3D View shows "ML service offline"** → FastAPI container isn't running or crashed. Check `docker compose logs fastapi`.
- **Build page 404** → was caused by `.dockerignore` excluding the `build/` directory. Fixed — `build/` is no longer ignored.
- **Push denied to GitHub** → `gh auth status` to check, then `gh auth setup-git`.

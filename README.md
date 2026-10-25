# Purpix BrickLab

Turn a photo of a building into a buildable LEGO®-style model — with step-by-step instructions and a
shopping list of bricks.

> Auburn University · COMP 4710 Senior Design · Team #16
> An Dinh · Christos Argyropoulos · Carlos Oceguera · Sponsor: Leal "Al" Smith, Purpix Media LLC

---

## What it does

You upload a photo. We cut the subject out of its background, work out how tall/wide/deep it is, turn a photo of a building into a buildable brick model, with a parts list you can order and (coming next) step-by-step build instructions.

## How it works

```mermaid
flowchart LR
    IMG["📷 your photo"] --> CUT["1 · Cut out the house<br/>background removal"]
    CUT --> GEN["2 · Make a 3D model<br/>one photo → house .glb"]
    GEN --> VOX["3 · Brick grid<br/>model → studs × plates"]
    VOX --> OPT["4 · Fewest bricks<br/>optimizer, 20-shape catalog"]
    OPT --> OUT["🧱 3D brick model · parts list · order total"]
```

**In plain terms, one step at a time:**

1. **Cut out the house.** Background removal erases everything except the building.
2. **Make a 3D model.** From that one photo we generate a 3D model of the house (.glb).
3. **Turn it into a brick grid.** The model is scaled to the size you pick (16, 20 or 24 studs wide) and cut
   into a grid where each cell is one stud wide and one plate tall. Walls are kept hollow, the way a real
   brick house is built.
4. **Pick the fewest bricks.** An optimizer (OR-Tools CP-SAT) fills each layer with the fewest bricks from a
   fixed 20-shape catalog, staggering joints so the walls hold together. Bricks come in white, black and red,
   on one green base plate.
5. **Parts list and price.** Every part is matched to its store ID, so the list can be ordered part by part
   and priced.

## Project status

| Cycle | Goal | Status |
|:--|:--|:--|
| **0** | Repo foundation — import previous team's work, document it, set up docs & licensing | ✅ **Done** |
| **1** | Subject isolation + background removal | ✅ **Done and in review** |
| **2** | 2D → dimensions → bas-relief 3D model | ✅ **Done** |
| **3** | Color refinement, brick stability, instructions + parts list | ⬜ Started the parts list |

**Non-functional targets:** end-to-end generation in **≤ 300 seconds**; models buildable from a
**limited brick palette** with a configurable piece-count budget (minimum ~20 pieces).

## Repository layout

```
bricklab/
├── frontend/                    Next.js 16 · React 19 · Tailwind · Three.js
│   ├── app/
│   │   ├── page.tsx               landing
│   │   ├── create/                2D Mosaic Studio  ← the "Pixel/Mosaic" style
│   │   ├── create-3d/             upload → poll → 3D  ← Cycle 1 & 2 UI lands here
│   │   ├── build/[id]/            mosaic result: parts list, build guide
│   │   ├── model/[jobId]/         GLB viewer  ← Cycle 3 adds tabs
│   │   ├── my-builds/ gallery/ pricing/ faq/
│   │   └── api/                   proxy routes — the browser never calls FastAPI directly
│   ├── components/                GlbViewer · MosaicViewer3D · Navbar · ui/
│   ├── lib/                       mosaic.ts (palette) · depth.ts · api.ts · builds.ts
│   ├── middleware.ts              Clerk auth gate ⚠️ blocks /create-3d without keys
│   └── public/                    landing images, demo GLTF
│
├── ml/                          Python · FastAPI · Celery
│   ├── scripts/glb_to_bricks.py   compare catalogs on a .glb
│   ├── app.py                     HTTP endpoints
│   ├── tasks.py                   Celery background jobs
│   ├── mosaic_engine.py           LEGO palette · dithering · depth-aware quantize
│   ├── main.py                    CLI entrypoint
│   ├── db.py · storage.py · auth.py
│   └── src/ptb_ml/
│       ├── one_photo/             🆕 photo → 3D house model (.glb)          PR #3
│       ├── mesh_voxel/            🆕 3D model → stud/plate brick grid       PR #4
│       ├── brick_optimizer/       🆕 brick grid → fewest bricks + parts list PR #4
│       ├── brickification/        ◐  old greedy brick placer (kept for comparison)
│       ├── instructions/          ✅ GLB + build steps              REUSED
│       ├── voxelization/          ◐  LEGO grid fitting (settings reused, loader bypassed)
│       ├── preprocess/            💤 frame extraction, masking
│       ├── sfm/ · sfm_qc/         💤 COLMAP structure-from-motion
│       ├── priors/                💤 needs DSINE — cannot run, see docs/THIRD_PARTY.md
│       ├── shape_completion/      💤 Open3D TSDF fusion
│       └── pipeline/              💤 orchestrates the dormant chain
│
├── docs/                        PREVIOUS_TEAM · DECISIONS · THIRD_PARTY · BRICK_CATALOG
├── compose.yaml                 frontend + fastapi + worker + postgres + redis
└── LICENSE                      placeholder — see docs/THIRD_PARTY.md
```

✅ actively reused · ◐ partly reused · 💤 dormant (the previous team's photogrammetry
path — kept in-tree as the future "walk around your house" feature, not used by our cycles)

## How the folders connect

One upload, traced through every file it touches. The browser never calls FastAPI
directly — it always goes through a Next.js proxy route.

```mermaid
flowchart TB
    subgraph B["🌐 browser"]
        P1["app/create-3d/page.tsx"]
        P2["app/model/[jobId]/page.tsx"]
    end
    subgraph N["▲ Next.js server — frontend/"]
        L["lib/api.ts<br/>typed client"]
        R1["app/api/ml/subject/route.ts<br/>Cycle 1 — new"]
        R2["app/api/ml/jobs/route.ts"]
        R3["app/api/ml/jobs/[jobId]/glb/route.ts"]
        MW["middleware.ts<br/>Clerk gate"]
    end
    subgraph F["🐍 FastAPI — ml/"]
        A["app.py"]
        T["tasks.py<br/>Celery"]
    end
    subgraph M["📦 pipeline — ml/src/ptb_ml/"]
        S["one_photo/<br/>PR #3"]
        V["mesh_voxel/<br/>PR #4"]
        BO["brick_optimizer/<br/>PR #4"]
        IN["instructions/<br/>reused, Cycle 3"]
    ...
    T -.planned.-> S --> V --> BO --> IN
    end

    MW -.guards.-> P1
    P1 --> L
    L --> R1 & R2
    R1 --> A
    R2 --> A
    A --> T
    T --> S --> D --> BR --> IN
    D -.reuses.-> ME
    BR -.reuses.-> ME
    IN --> G[("model.glb<br/>steps.json<br/>bom.json")]
    P2 --> R3 --> A
    A --> G
```

**Reading it:** `create-3d` calls a typed function in `lib/api.ts`, which hits a Next
proxy route, which forwards to `ml/app.py`. Long work is handed to a Celery task that
walks the pipeline modules left to right. The two new Cycle 1–2 modules feed the two
modules we inherited unchanged. After PR #3 and PR #4 are merged, the task will run them in order.

## Running it

BrickLab is not deployed. It runs on your machine at <http://localhost:3000>.

### Setup — required once

Sign-in is handled by Clerk. The sponsor has provided credentials; **nobody has
signed in and generated the keys yet**, so the app will not start until someone does.

Create `frontend/.env.local` (gitignored — never commit it):

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

Until that file exists, `docker compose up` exits immediately (`compose.yaml`
requires it) and `npm run dev` fails on the missing publishable key.

### Method 1 — everything (frontend + ML)

**Needs:** Docker Desktop. Use whenever you change `ml/`.

```bash
docker compose up --build
```

```
frontend   :3000   web app
fastapi    :8000   Python ML API
worker             background jobs (Celery)
postgres   :5432   job records
redis      :6379   job queue
```

First build takes roughly 10–20 minutes — it bakes the depth model (~100 MB) into
the image. Later builds reuse that layer.

```bash
docker compose logs -f fastapi   # watch the ML service
docker compose down              # stop everything
```

### Method 2 — web app only

**Needs:** Node.js 20.9+. Use for pages, styling, and components.

```bash
cd frontend && npm install && npm run dev
```

Starts in seconds with hot reload. **Anything calling the ML service will not work** —
background removal, 3D generation, the depth viewer. Those need Method 1, or at
minimum the FastAPI container on port 8000.

### Method 3: brick step only (no Docker)

**Needs:** Python 3.11+ with the `ml` dependencies. Turns any house `.glb` into bricks and a parts list:

    PYTHONPATH=ml/src python ml/scripts/glb_to_bricks.py house.glb --studs 16 --hollow 2 --catalog optimized-20

Writes `bricks.npz`, `bom.json` (parts, store IDs, order total) and `report.json`.

### Previous team's deployment

<https://main.d2hnowa3ob8fvm.amplifyapp.com/> — a visual reference for the inherited
UI, not a dev environment. It is their AWS account and frontend-only: Amplify hosts no
Python backend, so ML routes return `503`. The 2D mosaic works there because it runs
entirely in the browser.

## Documentation

| Doc | What's in it |
|---|---|
| [`docs/PREVIOUS_TEAM.md`](docs/PREVIOUS_TEAM.md) | What we inherited, what works, what's broken, and a file-by-file keep/drop inventory |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Running log of technical decisions and why we made them |
| [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md) | Open-source licenses — **read before adding a dependency or swapping a model** |
| [`HANDOFF_NOTES.md`](HANDOFF_NOTES.md) | The previous team's own handoff notes (kept verbatim) |
| [`docs/BRICK_CATALOG.md`](docs/BRICK_CATALOG.md) | The 20 brick shapes, colors, store IDs and how often each is used |

## Credits

Built on work by the previous senior design team
([`Aleonawork/AIPurpixBrickLab`](https://github.com/Aleonawork/AIPurpixBrickLab)), shared by our sponsor.

LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this project.

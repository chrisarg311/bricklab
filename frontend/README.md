# PictoBrick Frontend

Next.js 16 app (App Router) using React 19, Tailwind v4, shadcn/ui, Three.js, and Clerk for authentication.

> For monorepo-wide setup see the [top-level README](../../README.md). This file covers frontend-specific details.

## Directory Structure

```
frontend/
├── app/
│   ├── page.tsx               # Homepage — hero + feature cards
│   ├── layout.tsx             # Root layout — ClerkProvider, Navbar, footer
│   ├── create/                # Mosaic studio (upload → live preview → generate)
│   ├── build/[id]/            # Result page — 2D mosaic, 3D viewer, build guide
│   ├── my-builds/             # Auth-gated build history (localStorage)
│   ├── create-3d/             # 3D Model Builder — upload video/images for full pipeline
│   ├── model/[jobId]/         # GLB viewer for completed 3-D pipeline jobs
│   ├── gallery/               # Community showcase (placeholder)
│   ├── pricing/               # Static
│   ├── faq/                   # Static
│   └── api/
│       └── ml/
│           ├── depth-grid/    # Proxies POST → fastapi /api/depth-grid
│           └── jobs/          # Proxies POST/GET → fastapi /api/jobs/3d
│               └── [jobId]/
│                   └── glb/   # Proxies GET → fastapi /api/jobs/3d/{id}/glb
├── components/
│   ├── Navbar.tsx             # Global nav; shows "3D Model" link when signed in
│   ├── MosaicViewer3D.tsx     # Three.js InstancedMesh viewer (bricks + studs + depths)
│   ├── GlbViewer.tsx          # Three.js GLTFLoader viewer for full pipeline GLB output
│   └── ui/                    # shadcn primitives (Button, Card, …)
├── lib/
│   ├── mosaic.ts              # LEGO palette, dithering, Canvas render, highlight, build-step render
│   ├── builds.ts              # localStorage CRUD for StoredBuild
│   └── depth.ts              # fetchDepthGrid() — calls /api/ml/depth-grid
├── public/                    # Static assets (/logobackgroundremoved.png, /viewer.js, …)
├── middleware.ts              # Clerk auth — protects /create, /build, /my-builds, /create-3d, /model
├── Dockerfile.frontend        # Multi-stage build (standalone Next output)
└── package.json
```

## Running (Docker — preferred)

```bash
cd pictobrickWebApp
docker compose up --build
```

Frontend at <http://localhost:3000>, ML API at <http://localhost:8000>.

## Running (Local, no Docker)

```bash
cd pictobrickWebApp/frontend
npm install
npm run dev
```

Needs a `.env.local` here (not in `pictobrickWebApp/`):
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
FASTAPI_INTERNAL_URL=http://localhost:8000   # if running ML service locally
```

## Route Reference

| Route | Auth | Description |
| --- | --- | --- |
| `/` | Public | Landing page |
| `/create` | Required | Upload photos, live mosaic preview, generate |
| `/build/[id]` | Required | Mosaic result — 2D/3D view, build guide, parts list |
| `/my-builds` | Required | Build history from localStorage |
| `/create-3d` | Required | Upload video/images for full 3-D reconstruction |
| `/model/[jobId]` | Required | GLB viewer for completed 3-D jobs |
| `/gallery` | Public | Placeholder |
| `/pricing` | Public | Static |
| `/faq` | Public | Static |

## Key Libraries

| Package | Purpose |
| --- | --- |
| `three` | 3D rendering — mosaic viewer + GLB viewer |
| `framer-motion` | Page/element animations |
| `@clerk/nextjs` | Authentication |
| `lucide-react` | Icons |
| `shadcn` (Button, Card) | UI primitives |

## lib/mosaic.ts — API

| Export | Description |
| --- | --- |
| `PALETTE` | 22-color LEGO palette array |
| `quantizeImageDithered()` | Floyd-Steinberg dithering to palette |
| `renderMosaic()` | Draw full mosaic to canvas |
| `renderMosaicWithHighlight()` | Draw mosaic with one color lit, rest dimmed |
| `renderBuildStep()` | Draw build-guide step (current color bright, placed dimmed, future ghost) |
| `makeThumbDataUrl()` | Small mosaic JPEG for cards |
| `makeSourceThumbDataUrl()` | Small original-photo JPEG for before/after |

## lib/builds.ts — StoredBuild schema

```typescript
type StoredBuild = {
  id: string;
  title: string;
  createdAt: string;        // ISO
  detail: "Low"|"Medium"|"High";
  gridW: number;
  gridH: number;
  indices: number[];        // flat palette indices, length = gridW*gridH
  thumbDataUrl: string;     // mosaic JPEG thumbnail
  sourceThumbDataUrl?: string; // original photo JPEG (for before/after)
  parts: { hex, name, count }[];
}
```

Stored at `localStorage["pictobrick.builds.v1"]`. The `deleteBuild`, `renameBuild`, `listBuilds`, `getBuild`, `saveBuild` functions handle all CRUD.

## Authentication

- Provider: Clerk `@clerk/nextjs` v7
- Modal sign-in/up — no dedicated auth pages
- `middleware.ts` uses `createRouteMatcher` + `auth.protect()`
- `useUser()` hook for client-side auth state

## Env Vars

| Variable | Where used | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client bundle (build time) | Baked into `compose.yaml` for Docker |
| `CLERK_SECRET_KEY` | Server (middleware) | Never commit. Load from `.env.local` |
| `FASTAPI_INTERNAL_URL` | Server API routes | Docker: `http://fastapi:8000`. Amplify: set in console |
| `DATABASE_URL` | Server | Postgres — reserved for future use |
| `REDIS_URL` | Server | Redis — reserved for future use |

## Common Gotchas

- **Changed a `NEXT_PUBLIC_*` var and nothing changed?** These are baked in at build time — rebuild with `docker compose up --build`.
- **`/build/[id]` gives 404?** The `build/` directory was previously excluded by `.dockerignore`. Fixed — no longer excluded.
- **3D View shows flat mosaic with "ML service offline"?** The FastAPI container isn't running. Check `docker compose logs fastapi`.
- **Canvas is empty after toggling between 2D/3D views?** The canvas element stays mounted (hidden with CSS) so the WebGL context is never lost — toggling should restore correctly.
- **Depth grid takes 10+ seconds on first 3D View?** Normal — Depth Anything V2 runs on CPU. Subsequent requests on the same container are faster (model stays in memory).

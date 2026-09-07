# Purpix BrickLab

Turn a photo of a building into a buildable LEGO®-style model — with step-by-step instructions and a
shopping list of bricks.

> Auburn University · COMP 4710 Senior Design · Team #16
> An Dinh · Christos Argyropoulos · Carlos Oceguera · Sponsor: Leal "Al" Smith, Purpix Media LLC

---

## What it does

You upload a photo. We cut the subject out of its background, work out how tall/wide/deep it is, turn it
into a 3D shape made of LEGO bricks in real LEGO colors, and hand you back a 3D model you can spin around,
a step-by-step build manual, and a parts list you can actually buy.

## How it works

```mermaid
flowchart LR
    IMG["📷 your photo"] --> SUB["1 · Cut out the subject<br/><i>backgroundremover / U²-Net</i>"]
    SUB --> DIM["2a · Measure it<br/><i>width × height × depth in studs</i>"]
    DIM --> REL["2b · Give it depth<br/><i>depth model sets how far each<br/>column sticks out</i>"]
    REL --> BRK["3a · Turn voxels into real bricks<br/><i>greedy merge into 2×4s, 1×2s…</i>"]
    BRK --> INS["3b · Colors + instructions<br/><i>snap to LEGO palette, build steps</i>"]
    INS --> OUT["🧱 3D model · manual · parts list"]
```

**In plain terms, one step at a time:**

1. **Cut out the subject.** A background-removal model finds the building and erases everything else, so
   the sky and the neighbor's car don't end up as bricks.
2. **Measure it.** From the cut-out shape we work out proportions — how wide and tall it is — and convert
   that into a stud count that fits the model size you picked (Small / Medium / Large).
3. **Give it depth.** A depth-estimation model looks at the photo and estimates how far away each part of
   the building is. A porch that sticks out becomes bricks that stick out. This is what makes the result a
   *3D shape* rather than a flat pixel picture.
4. **Turn it into real bricks.** The shape starts as a grid of 1×1 cubes. A placement algorithm merges
   them into real LEGO pieces — 2×4s, 1×2s — the way you'd actually build it, staggering the seams so it
   holds together.
5. **Color and instruct.** Each brick gets the closest real LEGO color, and the model is sliced into
   bottom-up build steps with a parts list.

## Project status

| Cycle | Goal | Status |
|:--|:--|:--|
| **0** | Repo foundation — import previous team's work, document it, set up docs & licensing | ✅ **Done** |
| **1** | Subject isolation + background removal | ⬜ Not started |
| **2** | 2D → dimensions → bas-relief 3D model | ⬜ Not started |
| **3** | Color refinement, brick stability, instructions + parts list | ⬜ Not started |

**Non-functional targets:** end-to-end generation in **≤ 300 seconds**; models buildable from a
**limited brick palette** with a configurable piece-count budget (minimum ~20 pieces).

## Repository layout

```
bricklab/
├── frontend/          Next.js 16 web app (upload, 3D viewers, build guide)
├── ml/                Python FastAPI service + the ML pipeline
│   ├── app.py           HTTP endpoints
│   ├── tasks.py         Celery background jobs
│   ├── mosaic_engine.py LEGO palette + color quantization
│   └── src/ptb_ml/      pipeline modules (brickification, instructions, …)
├── docs/              architecture notes, decisions, licensing
└── compose.yaml       docker compose: frontend + fastapi + worker + postgres + redis
```

## Running it

```bash
docker compose up --build
```

Then open <http://localhost:3000>. First build is slow — the FastAPI image downloads and bakes in the
depth model (~100 MB).

Frontend only, for UI work:

```bash
cd frontend && npm install && npm run dev
```

> Needs a `.env.local` with `CLERK_SECRET_KEY` — ask a teammate.

## Documentation

| Doc | What's in it |
|---|---|
| [`docs/PREVIOUS_TEAM.md`](docs/PREVIOUS_TEAM.md) | What we inherited, what works, what's broken, and a file-by-file keep/drop inventory |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Running log of technical decisions and why we made them |
| [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md) | Open-source licenses — **read before adding a dependency or swapping a model** |
| [`HANDOFF_NOTES.md`](HANDOFF_NOTES.md) | The previous team's own handoff notes (kept verbatim) |

## Credits

Built on work by the previous senior design team
([`Aleonawork/AIPurpixBrickLab`](https://github.com/Aleonawork/AIPurpixBrickLab)), shared by our sponsor.

LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this project.

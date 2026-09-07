# Decision Log

Running record of technical decisions, newest last. Report §4 notes that our design choices depend on which
open-source tools interoperate — this is where we capture that reasoning as it happens.

**Format:** what we decided · why · what would make us revisit it.

---

## D1 — CPU-only, no GPU assumed
**Date:** 2026-09-01 · **Status:** Active

Everything must run on team laptops without CUDA.

**Why:** that's the hardware we have. A GPU dependency would block three of us from running the pipeline.

**Consequence:** rules out heavier image-to-3D models on the critical path; makes the 300-second budget a
real design constraint rather than a formality.

**Revisit if:** the sponsor funds a GPU host, or Auburn provides cluster access.

---

## D2 — Build on the previous team's source rather than starting fresh
**Date:** 2026-09-01 · **Status:** Active

Imported `pictobrickWebApp/` (frontend + ml) as our baseline in commit `4ce3d19`.

**Why:** their web app, job infrastructure, LEGO palette, brick-placement engine, and GLB builder are all
working. Rebuilding that scaffold would consume the whole semester and produce nothing new.

**Authorization:** sponsor shared the source expressly for us to build on (report §8, meeting 8.27.2026).

**Revisit if:** their code proves more expensive to understand than to replace — track this against report
§6's "prone to bugs because we don't have the same understanding" risk.

---

## D3 — Cycle 2 is image → dimensions → bas-relief, not full mesh reconstruction
**Date:** 2026-09-07 · **Status:** Active

**Why:** it fits the 300-second CPU budget, and it directly serves user story 1 ("parse basic geometric
dimensions — length, width, height"). Full single-image mesh reconstruction is a much larger bet.

**Important:** *bas-relief* here does **not** mean the previous team's flat mosaic plaque. Two differences:
(a) we orient it vertically — image column → X, image row → **Y (height)**, depth → **Z (thickness)** — so
the building stands up; (b) we feed the voxel grid through `run_brickification()` instead of emitting one
1×1×1 brick per voxel like `scripts/generate_demo.py` does.

**Revisit if:** relief output looks too flat to satisfy the sponsor, or Cycle 2 finishes early.

---

## D4 — TripoSR parked as a future option, not used now
**Date:** 2026-09-07 · **Status:** Deferred

**Why deferred:** compute and scope, per D1 and D3 — not licensing.

**Correction to an earlier assumption:** TripoSR's code *and* the `stabilityai/TripoSR` weights are both
**MIT licensed, commercial use permitted**. We initially believed it was non-commercial; it is not. Nobody
should re-reject it on licensing grounds.

**Revisit for:** the "Full 3D / Architectural" style option, once a GPU or a longer time budget exists.

---

## D5 — brickalize is an algorithm reference only, never imported
**Date:** 2026-09-01 · **Status:** Active

**Why:** [`CreativeMindstorms/brickalize`](https://github.com/CreativeMindstorms/brickalize) is **GPLv3**.
Importing it would oblige us to release this entire product under GPLv3 with source. Incompatible with a
commercial product.

**Useful ideas to reimplement ourselves:** hollow-shell voxelization (big piece-count savings), sparse
pillar supports for overhangs, per-layer instruction images.

**How to borrow safely:** clean-room. One person reads it and writes a plain-English spec; a *different*
person implements from the spec only.

---

## D6 — Cycle 2 MVP takes one photo; the API accepts a list
**Date:** 2026-09-07 · **Status:** Active

**Why:** user story 1 and meeting 9.3 call for 3+ front/side photos, but a single photo gets us to a working
demo far faster. Typing the function as `estimate_dimensions(images: list[Path], ...)` from day one means
adding real multi-view depth later is an implementation change, not an interface change.

---

## D7 — Background removal via `backgroundremover`
**Date:** 2026-09-07 · **Status:** Active — pending bake-off

Chose [`nadermx/backgroundremover`](https://github.com/nadermx/backgroundremover) over `rembg`.

**Why:** code MIT / models Apache-2.0 (both commercial-safe), and it is **PyTorch-based**, reusing the
`torch` already pinned in `ml/pyproject.toml` instead of pulling in `onnxruntime` as an extra heavy
dependency. Its `u2net_human_seg` model also covers the sponsor's portrait style.

**Open task (tester role, report §5):** benchmark `backgroundremover` (`u2netp`, `u2net`) against `rembg`
on ~10 sample building photos for edge quality and seconds-per-image on CPU. Record the result here. The
Cycle 1 wrapper puts the model name in settings, so switching is a one-line change.

---

## D8 — Depth model is pinned to Depth-Anything-V2-**Small**
**Date:** 2026-09-07 · **Status:** Active — ⚠️ do not change casually

Pinned to `depth-anything/Depth-Anything-V2-Small-hf`.

**Why this is a licensing decision, not a quality one:** the Small checkpoint is **Apache-2.0** (commercial
OK). The **Base and Large** checkpoints are **CC-BY-NC-4.0 — non-commercial**. Upgrading the model to
"improve quality" would silently make the product commercially unusable, with no error message.

**Action:** add a CI check asserting the model ID stays `...V2-Small-hf`.

---

## D9 — DSINE excluded from the repo
**Date:** 2026-09-07 · **Status:** Active

Excluded `ml/vendor/DSINE/` (184 MB) from the import.

**Why:** its Imperial College London license states *"You may not use the Software for commercial
purposes."* It is used only by `ptb_ml/priors/`, part of the dormant photogrammetry path.

**Consequence:** `ptb_ml/priors/` cannot run. Acceptable — that path is dormant and could not ship
commercially anyway. `ml/vendor/` is kept as an empty directory so `pyproject.toml`'s
`packages.find(where=["src","vendor"])` still resolves.

---

## Open decisions — need a team call

- **O1 — Infrastructure weight.** Keep Clerk + Postgres + Redis + Celery + S3, or swap to a filesystem job
  store for local dev? They work, but they're heavy for a CPU-only prototype. **Decide before Cycle 2**
  wires the job endpoints. See `docs/PREVIOUS_TEAM.md` §8.
- **O2 — Repository license.** `LICENSE` is currently a conservative all-rights-reserved placeholder.
  The sponsor should confirm the real terms. See `docs/THIRD_PARTY.md`.
- **O3 — Frontend pruning.** `/gallery`, `/pricing`, `/faq`, and the 11 MB `LegoTest` demo model are marked
  **Discuss** in the inventory.
- **O4 — Paper trail.** Optional but cheap: a one-line email from Mr. Smith confirming we may reuse the
  previous team's code, filed here. Their repo has no LICENSE file, so nothing else records the permission.

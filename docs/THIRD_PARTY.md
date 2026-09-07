# Third-Party Licenses

**Read this before adding a dependency or swapping a model.**

*Not legal advice. Before any commercial launch the sponsor should have counsel review this, together with
whatever Auburn IP / senior-design agreement governs our work.*

---

## The three tiers

| Tier | Examples | Commercial use | Is crediting them enough? |
|---|---|---|---|
| **Permissive** | MIT, Apache-2.0, BSD | ✅ Yes | Almost — you must ship the **license text and copyright notice**, not just a thank-you. |
| **Copyleft** | GPLv3, AGPLv3 | ⚠️ Only if you open-source your entire product | ❌ No. Attribution buys you nothing here. |
| **Non-commercial** | CC-BY-NC, bespoke academic licenses | ❌ Never, in a paid product | ❌ No. |

**Two traps that are easy to miss:**

1. **A repo's code license and its model-weights license are separate things.** A repo can be MIT while its
   published weights are non-commercial. Check both, every time. See Depth Anything V2 below — same project,
   same page, different license depending on model size.
2. **Trademarks are separate from software licenses.** No open-source license grants trademark rights.

---

## Audit of our stack

Verified 2026-09-07.

| Component | Used for | Code license | Weights license | Commercial? |
|---|---|---|---|---|
| [`backgroundremover`](https://github.com/nadermx/backgroundremover) | Cycle 1 subject cut-out | MIT | Apache-2.0 | ✅ |
| [`Depth-Anything-V2-Small-hf`](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf) | Depth estimation | Apache-2.0 | **Apache-2.0** | ✅ |
| `Depth-Anything-V2-Base` / `-Large` | *(not used)* | — | **CC-BY-NC-4.0** | ❌ 🚫 |
| [`TripoSR`](https://github.com/VAST-AI-Research/TripoSR) | *(deferred — see D4)* | MIT | MIT | ✅ |
| **DSINE** | *(excluded — see D9)* | Imperial College London bespoke | — | ❌ 🚫 |
| [`brickalize`](https://github.com/CreativeMindstorms/brickalize) | *(reference reading only)* | **GPLv3** | — | ⚠️ 🚫 |
| Next.js, React, Three.js, Tailwind | Frontend | MIT | — | ✅ |
| FastAPI, Uvicorn, Celery, Pydantic | Backend | MIT / BSD | — | ✅ |
| PyTorch, torchvision | ML runtime | BSD-3-Clause | — | ✅ |
| transformers, Open3D | ML | Apache-2.0 / MIT | — | ✅ |
| PostgreSQL, Redis | Infrastructure | PostgreSQL / RSALv2+SSPL | — | ✅ (as an unmodified service) |

### 🚫 Hard rules

1. **Never upgrade the depth model to Base or Large.** They are CC-BY-NC-4.0. The Small checkpoint we pin is
   Apache-2.0. Swapping them for "better quality" silently destroys commercial viability, with no error.
   See `docs/DECISIONS.md` D8.
2. **Never re-add `ml/vendor/DSINE/`.** Its license forbids commercial use outright. It is in `.gitignore`.
   See D9.
3. **Never `pip install brickalize` or copy its code.** GPLv3. Read it for ideas only, clean-room. See D5.

---

## Our own license

`LICENSE` at the repo root is currently a **conservative all-rights-reserved placeholder**. This is
deliberate: you can always relax a proprietary license later, but you cannot un-open-source a product.

**Open item (O2):** the sponsor should confirm the actual terms and who owns the copyright — Purpix Media
LLC, the student authors, Auburn University, or some combination set by the senior-design agreement.

**Note on what we inherited:** the previous team's repository had **no LICENSE file at all**, which by
default means all rights reserved. Our authorization to build on it is the sponsor sharing it with us for
that purpose (report §8). We are adding a LICENSE here so the *next* team doesn't inherit the same gap.

---

## Trademark

**LEGO®** is a trademark of the LEGO Group. No software license grants any right to it. Practically:

- The product cannot be named or branded "LEGO."
- Use it as an adjective with attribution — "LEGO® bricks," "LEGO-compatible" — never as the name of our
  product or as a noun for the output.
- Include a disclaimer that the LEGO Group does not sponsor, authorize, or endorse this project.

The sponsor memo already hedges appropriately ("LEGO-compatible or official resale where allowed").

---

## Adding a dependency — checklist

1. Find the **code** license. Permissive? Fine. Copyleft or non-commercial? Stop and raise it.
2. If it ships **model weights**, find their license separately. It is often different.
3. Add a row to the audit table above.
4. Add the full license text to the distribution (a `NOTICES` file, once we have a release process).
5. If it's a judgment call, log it in `docs/DECISIONS.md`.

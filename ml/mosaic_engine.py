"""
Shared depth-aware mosaic logic used by both the FastAPI endpoints (sync)
and the Celery worker (async).  No ptb_ml imports — standalone.
"""
from __future__ import annotations

import io
import logging
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LEGO colour palette — mirrors frontend/lib/mosaic.ts PALETTE exactly
# ---------------------------------------------------------------------------

# (name, R, G, B)
_PALETTE_DEF: list[tuple[str, int, int, int]] = [
    ("White",            245, 245, 240),
    ("Light Gray",       175, 181, 199),
    ("Dark Gray",         99,  95,  97),
    ("Black",             27,  27,  29),
    ("Bright Red",       196,  40,  28),
    ("Dark Red",         123,  46,  47),
    ("Orange",           218, 133,  65),
    ("Bright Yellow",    245, 205,  47),
    ("Tan",              215, 197, 153),
    ("Reddish Brown",    105,  64,  39),
    ("Brown",             88,  57,  39),
    ("Lime",             187, 233,  11),
    ("Bright Green",      75, 151,  74),
    ("Dark Green",        40,  92,  51),
    ("Sand Green",       160, 188, 172),
    ("Bright Blue",       13, 105, 172),
    ("Dark Azure",         7, 139, 201),
    ("Sand Blue",        116, 134, 156),
    ("Dark Blue",         32,  58,  86),
    ("Bright Purple",    205,  98, 152),
    ("Medium Lavender",  160, 132, 187),
    ("Pink",             253, 195, 217),
]

PALETTE_NAMES: list[str]         = [d[0] for d in _PALETTE_DEF]
PALETTE_RGB:   list[tuple[int, int, int]] = [(d[1], d[2], d[3]) for d in _PALETTE_DEF]
PALETTE_HEX:   list[str]         = [
    f"#{r:02x}{g:02x}{b:02x}" for (_, r, g, b) in _PALETTE_DEF
]

# Per-colour saturation, pre-computed for the depth penalty
_PALETTE_SAT: list[float] = []
for _, r, g, b in _PALETTE_DEF:
    mx, mn = max(r, g, b), min(r, g, b)
    _PALETTE_SAT.append((mx - mn) / mx if mx > 0 else 0.0)

# Numpy array (22, 3) for vectorised distance computation
_PALETTE_NP = np.array(PALETTE_RGB, dtype=np.float32)  # shape (22, 3)

# ---------------------------------------------------------------------------
# Grid sizing — mirrors gridDimsFor() in mosaic.ts
# ---------------------------------------------------------------------------

_DETAIL_TO_LONG: dict[str, int] = {"Low": 48, "Medium": 72, "High": 104}


def grid_dims_for(detail: str, img_w: int, img_h: int) -> tuple[int, int]:
    long = _DETAIL_TO_LONG.get(detail, 72)
    if img_w >= img_h:
        grid_w = long
        grid_h = max(8, round((img_h / img_w) * long))
    else:
        grid_h = long
        grid_w = max(8, round((img_w / img_h) * long))
    return grid_w, grid_h


# ---------------------------------------------------------------------------
# Depth model — cached, loaded on first call
# ---------------------------------------------------------------------------

DEPTH_MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"


@lru_cache(maxsize=1)
def _get_depth_pipe():
    from transformers import pipeline as hf_pipeline
    log.info("Loading depth model %s…", DEPTH_MODEL_ID)
    return hf_pipeline(task="depth-estimation", model=DEPTH_MODEL_ID, device=-1)


# ---------------------------------------------------------------------------
# Colour quantisation with Floyd-Steinberg dithering + depth bias
# ---------------------------------------------------------------------------

def _nearest_palette_depth(r: float, g: float, b: float, depth_norm: float) -> int:
    """
    Return the palette index closest to (r, g, b) weighted by depth.

    depth_norm: 0 = far background, 1 = close foreground.

    Far pixels pay an extra penalty for highly-saturated palette entries,
    simulating atmospheric perspective (backgrounds become muted).
    The penalty weight (8000) is calibrated so that at maximum distance a
    fully-saturated colour is penalised by ~sqrt(8000) ≈ 89 in RGB distance
    units — enough to nudge the choice toward muted colours without being
    a hard override.
    """
    best_idx = 0
    best_score = float("inf")
    depth_penalty_weight = 8000.0 * (1.0 - depth_norm)
    for i, (cr, cg, cb) in enumerate(PALETTE_RGB):
        dist = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2
        penalty = depth_penalty_weight * _PALETTE_SAT[i]
        score = dist + penalty
        if score < best_score:
            best_score = score
            best_idx = i
    return best_idx


def depth_aware_quantize(
    pil_img: Image.Image,
    grid_w: int,
    grid_h: int,
    depth_pipe,
) -> list[int]:
    """
    Resize pil_img to (grid_w, grid_h), run depth inference, then apply
    Floyd-Steinberg dithering with a depth-biased palette selection.

    Returns a flat list of palette indices, row-major, length = grid_w * grid_h.
    """
    # --- Resize source to grid ------------------------------------------------
    small = pil_img.resize((grid_w, grid_h), Image.LANCZOS)
    rgb = np.array(small, dtype=np.float32)   # (H, W, 3)

    # --- Depth map ------------------------------------------------------------
    depth_result = depth_pipe(pil_img)
    depth_pil = depth_result["depth"]          # PIL Image, relative depth
    depth_np = np.array(depth_pil, dtype=np.float32)
    depth_small = np.array(
        Image.fromarray(depth_np).resize((grid_w, grid_h), Image.LANCZOS),
        dtype=np.float32,
    )
    d_min, d_max = depth_small.min(), depth_small.max()
    if d_max > d_min:
        depth_norm = (depth_small - d_min) / (d_max - d_min)   # 0=far, 1=close
    else:
        depth_norm = np.full((grid_h, grid_w), 0.5, dtype=np.float32)

    # --- Floyd-Steinberg dithering with depth-aware selection -----------------
    r_buf = rgb[:, :, 0].copy()
    g_buf = rgb[:, :, 1].copy()
    b_buf = rgb[:, :, 2].copy()

    indices = np.zeros(grid_w * grid_h, dtype=np.int32)

    for y in range(grid_h):
        for x in range(grid_w):
            p = y * grid_w + x
            rv = float(np.clip(r_buf[y, x], 0, 255))
            gv = float(np.clip(g_buf[y, x], 0, 255))
            bv = float(np.clip(b_buf[y, x], 0, 255))
            dn = float(depth_norm[y, x])

            idx = _nearest_palette_depth(rv, gv, bv, dn)
            indices[p] = idx

            cr, cg, cb = PALETTE_RGB[idx]
            er, eg, eb = rv - cr, gv - cg, bv - cb

            # Distribute quantisation error (Floyd-Steinberg coefficients)
            if x + 1 < grid_w:
                r_buf[y, x + 1] += er * 7 / 16
                g_buf[y, x + 1] += eg * 7 / 16
                b_buf[y, x + 1] += eb * 7 / 16
            if y + 1 < grid_h:
                if x > 0:
                    r_buf[y + 1, x - 1] += er * 3 / 16
                    g_buf[y + 1, x - 1] += eg * 3 / 16
                    b_buf[y + 1, x - 1] += eb * 3 / 16
                r_buf[y + 1, x] += er * 5 / 16
                g_buf[y + 1, x] += eg * 5 / 16
                b_buf[y + 1, x] += eb * 5 / 16
                if x + 1 < grid_w:
                    r_buf[y + 1, x + 1] += er / 16
                    g_buf[y + 1, x + 1] += eg / 16
                    b_buf[y + 1, x + 1] += eb / 16

    return indices.tolist()


# ---------------------------------------------------------------------------
# Parts list
# ---------------------------------------------------------------------------

def build_parts_list(indices: list[int]) -> list[dict]:
    """Return sorted list of {hex, name, count} dicts, descending by count."""
    counts: dict[int, int] = {}
    for i in indices:
        counts[i] = counts.get(i, 0) + 1
    rows = [
        {"hex": PALETTE_HEX[i], "name": PALETTE_NAMES[i], "count": c}
        for i, c in counts.items()
    ]
    return sorted(rows, key=lambda r: r["count"], reverse=True)


# ---------------------------------------------------------------------------
# Thumbnail renderer — server-side, no canvas
# ---------------------------------------------------------------------------

def render_thumb(
    indices: list[int],
    grid_w: int,
    grid_h: int,
    max_long: int = 320,
) -> bytes:
    """
    Render a flat pixel mosaic (no studs) and return JPEG bytes.
    Each grid cell maps to brick_px × brick_px pixels using nearest-neighbour
    scaling so the result looks crisp rather than blurry.
    """
    # Build (H, W, 3) colour array at grid resolution
    arr = np.array(
        [PALETTE_RGB[i] for i in indices], dtype=np.uint8
    ).reshape(grid_h, grid_w, 3)

    brick_px = max(2, max_long // max(grid_w, grid_h))
    pil = Image.fromarray(arr, "RGB").resize(
        (grid_w * brick_px, grid_h * brick_px),
        Image.NEAREST,
    )
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

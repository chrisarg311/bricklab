"""
Generate a demo bas-relief LEGO GLB from a single image.
No COLMAP required — uses Depth Anything V2 for monocular depth.

Requirements (install once):
    pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
    pip install transformers accelerate pillow numpy pygltflib

Usage:
    python scripts/generate_demo.py dog.jpg demo.glb
    python scripts/generate_demo.py dog.jpg demo.glb --size 72 --max-height 12
    python scripts/generate_demo.py dog.jpg demo.glb --size 96 --max-height 16 --flat

Open the resulting .glb in Windows 3D Viewer, Blender, or https://gltf.report
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


# ── LEGO palette (same as the web app) ────────────────────────────────────────

PALETTE: list[tuple[int, int, int]] = [
    (245, 245, 240),  # White
    (175, 181, 199),  # Light Gray
    ( 99,  95,  97),  # Dark Gray
    ( 27,  27,  29),  # Black
    (196,  40,  28),  # Bright Red
    (123,  46,  47),  # Dark Red
    (218, 133,  65),  # Orange
    (245, 205,  47),  # Bright Yellow
    (215, 197, 153),  # Tan
    (105,  64,  39),  # Reddish Brown
    ( 88,  57,  39),  # Brown
    (187, 233,  11),  # Lime
    ( 75, 151,  74),  # Bright Green
    ( 40,  92,  51),  # Dark Green
    (160, 188, 172),  # Sand Green
    ( 13, 105, 172),  # Bright Blue
    (  7, 139, 201),  # Dark Azure
    (116, 134, 156),  # Sand Blue
    ( 32,  58,  86),  # Dark Blue
    (205,  98, 152),  # Bright Purple
    (160, 132, 187),  # Medium Lavender
    (253, 195, 217),  # Pink
]
_PAL = np.array(PALETTE, dtype=np.float32)


def nearest_color(r: float, g: float, b: float) -> tuple[int, int, int]:
    q = np.array([r, g, b], dtype=np.float32)
    idx = int(np.argmin(np.sum((_PAL - q) ** 2, axis=1)))
    return PALETTE[idx]


def quantize_dithered(img: np.ndarray, grid_w: int, grid_h: int) -> np.ndarray:
    """Floyd-Steinberg dithering to LEGO palette. Returns (gridH, gridW, 3) uint8."""
    small = np.array(
        Image.fromarray(img).resize((grid_w, grid_h), Image.LANCZOS),
        dtype=np.float32,
    )
    r = small[:, :, 0].copy()
    g = small[:, :, 1].copy()
    b = small[:, :, 2].copy()
    out = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)

    for y in range(grid_h):
        for x in range(grid_w):
            rv = float(np.clip(r[y, x], 0, 255))
            gv = float(np.clip(g[y, x], 0, 255))
            bv = float(np.clip(b[y, x], 0, 255))
            nr, ng, nb = nearest_color(rv, gv, bv)
            out[y, x] = (nr, ng, nb)
            er, eg, eb = rv - nr, gv - ng, bv - nb
            if x + 1 < grid_w:
                r[y, x+1] += er * 7/16; g[y, x+1] += eg * 7/16; b[y, x+1] += eb * 7/16
            if y + 1 < grid_h:
                if x > 0:
                    r[y+1,x-1] += er * 3/16; g[y+1,x-1] += eg * 3/16; b[y+1,x-1] += eb * 3/16
                r[y+1, x] += er * 5/16; g[y+1, x] += eg * 5/16; b[y+1, x] += eb * 5/16
                if x + 1 < grid_w:
                    r[y+1,x+1] += er / 16; g[y+1,x+1] += eg / 16; b[y+1,x+1] += eb / 16
    return out


def get_depth_grid(pil_img: Image.Image, grid_w: int, grid_h: int) -> np.ndarray:
    """Run Depth Anything V2 and return (gridH, gridW) float32 in [0,1], larger=closer."""
    print("  Loading Depth Anything V2 (first run downloads ~100 MB)…")
    from transformers import pipeline
    pipe = pipeline(
        task="depth-estimation",
        model="depth-anything/Depth-Anything-V2-Small-hf",
        device=-1,
    )
    depth_raw = np.array(pipe(pil_img)["depth"], dtype=np.float32)
    small = np.array(
        Image.fromarray(depth_raw).resize((grid_w, grid_h), Image.LANCZOS),
        dtype=np.float32,
    )
    d_min, d_max = small.min(), small.max()
    if d_max > d_min:
        return (small - d_min) / (d_max - d_min)
    return np.full_like(small, 0.5)


def build_brick_array(
    colors: np.ndarray,   # (H, W, 3) uint8
    heights: np.ndarray,  # (H, W) int, 1..max_height
) -> np.ndarray:
    """Build (N, 9) int32 brick array [x, y, z, w, d, h, r, g, b]."""
    grid_h, grid_w = heights.shape
    rows: list[list[int]] = []
    for z in range(grid_h):
        for x in range(grid_w):
            col_h = int(heights[z, x])
            r, g, b = int(colors[z, x, 0]), int(colors[z, x, 1]), int(colors[z, x, 2])
            for y in range(col_h):
                rows.append([x, y, z, 1, 1, 1, r, g, b])
    return np.array(rows, dtype=np.int32)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo LEGO GLB from a single image.")
    parser.add_argument("image", help="Input image path (jpg, png, etc.)")
    parser.add_argument("output", help="Output GLB path (e.g. demo.glb)")
    parser.add_argument("--size", type=int, default=72,
                        help="Mosaic long-edge in studs (default 72 ≈ Medium)")
    parser.add_argument("--max-height", type=int, default=10,
                        help="Max brick column height (default 10)")
    parser.add_argument("--flat", action="store_true",
                        help="Skip depth estimation — generate a flat mosaic plaque")
    args = parser.parse_args()

    img_path = Path(args.image)
    out_path = Path(args.output)
    if not img_path.exists():
        sys.exit(f"Image not found: {img_path}")

    print(f"[1/4] Loading {img_path.name}…")
    pil_img = Image.open(img_path).convert("RGB")
    W, H = pil_img.size
    if W >= H:
        grid_w = args.size
        grid_h = max(8, round(H / W * args.size))
    else:
        grid_h = args.size
        grid_w = max(8, round(W / H * args.size))
    print(f"      Grid: {grid_w} × {grid_h} studs")

    print("[2/4] Quantizing to LEGO palette (dithered)…")
    img_np = np.array(pil_img)
    colors = quantize_dithered(img_np, grid_w, grid_h)

    if args.flat:
        print("[3/4] Flat mode — skipping depth estimation.")
        heights = np.ones((grid_h, grid_w), dtype=np.int32)
    else:
        print("[3/4] Running depth estimation…")
        depth_norm = get_depth_grid(pil_img, grid_w, grid_h)
        heights = np.clip(
            np.round(depth_norm * (args.max_height - 1) + 1).astype(np.int32),
            1, args.max_height,
        )

    total_bricks = int(heights.sum())
    print(f"[4/4] Building GLB ({total_bricks:,} bricks)…")

    bricks = build_brick_array(colors, heights)

    # Use the existing GLB builder from ptb_ml
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    sys.path.insert(0, str(Path(__file__).parent.parent / "vendor"))
    from ptb_ml.instructions.glb_builder import build_glb
    from ptb_ml.instructions.settings import InstructionsSettings

    build_glb(bricks, InstructionsSettings(), out_path)
    print(f"\n✓  Saved: {out_path.resolve()}")
    print("   Open in Blender, Windows 3D Viewer, or https://gltf.report")

    # Parts list summary
    from collections import Counter
    color_counts: Counter = Counter()
    for row in bricks:
        color_counts[(int(row[6]), int(row[7]), int(row[8]))] += 1
    print(f"\nParts list ({len(color_counts)} colors, {total_bricks:,} total):")
    for (r, g, b), count in sorted(color_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  #{r:02x}{g:02x}{b:02x}  {count:>6,} bricks")
    if len(color_counts) > 10:
        print(f"  … and {len(color_counts) - 10} more colors")


if __name__ == "__main__":
    main()

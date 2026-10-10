from __future__ import annotations

import json
import logging
from collections import Counter

import numpy as np
from ortools.sat.python import cp_model
from scipy import ndimage
from scipy.cluster.vq import kmeans2
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from ..brickification.colors import BRICK_COLORS
from .models import BrickOptReq, BrickOptResult
from .settings import BrickOptSettings


log = logging.getLogger(__name__)


def _kit_palette(settings: BrickOptSettings) -> np.ndarray:
    by_name = {name: (r, g, b) for name, r, g, b in BRICK_COLORS}
    missing = [c for c in settings.colors if c not in by_name]
    if missing:
        raise ValueError(f"unknown brick colors: {missing}")
    return np.array([by_name[c] for c in settings.colors], dtype=np.int32)


def _snap_colors(colors: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """(X,Y,Z,3) RGB -> (X,Y,Z) index of the nearest kit color."""
    d = ((colors[..., None, :].astype(np.int32) - palette) ** 2).sum(-1)
    return d.argmin(-1)


def _luma(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float64)
    return rgb @ np.array([0.2126, 0.7152, 0.0722])


def _saturation(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float64)
    hi, lo = rgb.max(-1), rgb.min(-1)
    return np.where(hi > 0, (hi - lo) / np.maximum(hi, 1e-9), 0.0)


def _rank_colors(
    colors: np.ndarray,
    occupancy: np.ndarray,
    palette: np.ndarray,
    settings: BrickOptSettings,
) -> np.ndarray:
    """Map the model's colors onto the kit by rank, not by distance: cluster
    the cell colors (one cluster per kit color), give the most saturated
    cluster the kit's most saturated color, and the rest by lightness
    (lightest -> white, darkest -> black). This keeps walls, roof and trim
    apart even on a dark model. Returns (X,Y,Z) kit color indices.
    """
    out = np.zeros(occupancy.shape, dtype=np.int64)
    pts = colors[occupancy].astype(np.float64)
    if len(pts) == 0:
        return out

    k = min(len(palette), len(np.unique(pts, axis=0)))
    centers, labels = kmeans2(pts, k, minit="++", seed=0)
    # Merge clusters whose centers are nearly the same color
    used = np.unique(labels)
    centers = centers[used]
    labels = np.searchsorted(used, labels)
    merged = list(range(len(centers)))
    for i in range(len(centers)):
        for j in range(i):
            if np.linalg.norm(centers[i] - centers[j]) < settings.merge_color_distance:
                merged[i] = merged[j]
                break
    roots = sorted(set(merged))
    labels = np.array([roots.index(merged[l]) for l in labels])
    centers = np.array([pts[labels == r].mean(0) for r in range(len(roots))])

    kit_accent = int(np.argmax(_saturation(palette)))
    kit_rest = [i for i in np.argsort(-_luma(palette)) if i != kit_accent]   # light -> dark

    sat = _saturation(centers)
    clusters = list(range(len(centers)))
    mapping: dict[int, int] = {}
    if len(clusters) > 1 and (
        sat.max() >= settings.accent_min_saturation or len(clusters) > len(kit_rest)
    ):
        accent = int(np.argmax(sat))
        mapping[accent] = kit_accent
        clusters.remove(accent)

    by_light = sorted(clusters, key=lambda c: -_luma(centers[c]))
    if len(by_light) == len(kit_rest):
        mapping.update(zip(by_light, kit_rest))
    else:
        # Fewer clusters than kit colors: each goes to the kit color
        # closest in lightness
        for c in by_light:
            mapping[c] = min(kit_rest, key=lambda i: abs(_luma(palette[i]) - _luma(centers[c])))

    out[occupancy] = np.array([mapping[l] for l in labels])
    return out


def _smooth_colors(
    color_idx: np.ndarray, occupancy: np.ndarray, n_colors: int, rounds: int
) -> np.ndarray:
    """Majority filter over each cell and its occupied neighbours (3x3x3,
    counted in brick courses), so speckles from textures and material seams
    don't split walls into many small parts."""

    X, Y, Z = occupancy.shape
    if rounds <= 0 or Y % 3:
        return color_idx
    occ = occupancy[:, ::3, :]
    lab = color_idx[:, ::3, :].copy()
    for _ in range(rounds):
        votes = np.stack([
            ndimage.uniform_filter(((lab == c) & occ).astype(np.float64), size=3, mode="constant")
            for c in range(n_colors)
        ])
        lab = np.where(occ, votes.argmax(0), lab)
    return np.repeat(lab, 3, axis=1)


def _footprints(settings: BrickOptSettings, h: int) -> list[tuple[int, int]]:
    """(w along x, d along z) for every catalog part of height h, both
    orientations, largest first."""
    out = set()
    for w, d, hh in settings.catalog:
        if hh == h:
            out |= {(w, d), (d, w)}
    return sorted(out, key=lambda s: (-s[0] * s[1], s))


def _window_full(mask: np.ndarray, w: int, d: int) -> np.ndarray:
    """True at (x, z) where mask[x:x+w, z:z+d] is entirely True."""
    X, Z = mask.shape
    if w > X or d > Z:
        return np.zeros((0, 0), dtype=bool)
    s = np.zeros((X + 1, Z + 1), dtype=np.int32)
    s[1:, 1:] = mask.cumsum(0).cumsum(1)
    total = s[w:, d:] - s[:-w, d:] - s[w:, :-d] + s[:-w, :-d]
    return total == w * d


def _solve_layer(
    cells: np.ndarray,
    color_idx: np.ndarray,
    footprints: list[tuple[int, int]],
    below: np.ndarray | None,
    pieces: list,
    settings: BrickOptSettings,
) -> tuple[list[tuple[int, int, int, int, int]], bool]:
    """Exact cover of `cells` (X,Z) with footprints of one color each.

    below: owner ids of the layer underneath (-1 = empty), or None at the
    ground; pieces: the pieces placed so far, indexed by those ids.
    Returns ([(x, z, w, d, links_below)], proven_optimal).
    """
    X, Z = cells.shape
    cands: list[tuple[int, int, int, int, int]] = []
    costs: list[int] = []
    for c in np.unique(color_idx[cells]):
        m = cells & (color_idx == c)
        for w, d in footprints:
            for x, z in np.argwhere(_window_full(m, w, d)):
                if below is None:
                    links, cost = 1, 0
                else:
                    ids = np.unique(below[x:x + w, z:z + d])
                    links = int((ids >= 0).sum())
                    cost = 0
                    if links == 0:
                        cost += settings.unsupported_cost
                    cost -= settings.link_bonus * min(max(links - 1, 0), settings.link_cap)
                    if links == 1:
                        px, _, pz, pw, pd, *_ = pieces[ids[ids >= 0][0]]
                        if (px, pz, pw, pd) == (x, z, w, d):
                            cost += settings.stacked_cost
                if w * d == 1:
                    cost += settings.one_by_one_cost
                cands.append((int(x), int(z), w, d, links))
                costs.append(settings.piece_cost + cost)

    model = cp_model.CpModel()
    use = [model.NewBoolVar("") for _ in cands]
    covering: dict[tuple[int, int], list] = {}
    for v, (x, z, w, d, _) in zip(use, cands):
        for i in range(x, x + w):
            for k in range(z, z + d):
                covering.setdefault((i, k), []).append(v)
    for cell in map(tuple, np.argwhere(cells)):
        model.AddExactlyOne(covering[cell])
    model.Minimize(sum(c * v for c, v in zip(costs, use)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = settings.time_limit_s
    solver.parameters.num_workers = settings.workers
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"no tiling found ({solver.StatusName(status)})")
    chosen = [c for c, v in zip(cands, use) if solver.Value(v)]
    return chosen, status == cp_model.OPTIMAL


def _part_name(w: int, d: int, h: int) -> str:
    a, b = sorted((w, d))
    if h == 1 and a >= 16:
        return f"{a}x{b} base plate"
    return f"{a}x{b} {'brick' if h == 3 else 'plate'}"


def _tile(
    occupancy: np.ndarray,
    color_idx: np.ndarray,
    settings: BrickOptSettings,
) -> tuple[list[tuple[int, int, int, int, int, int, int]], np.ndarray, int]:
    """Tile the whole grid bottom-up. Returns (pieces as x y z w d h color,
    owner grid of piece ids, layers not proven optimal)."""

    X, Y, Z = occupancy.shape
    brick_fp = _footprints(settings, 3)
    plate_fp = _footprints(settings, 1)
    owner = np.full((X, Y, Z), -1, dtype=np.int32)
    pieces: list[tuple[int, int, int, int, int, int, int]] = []
    not_optimal = 0

    def place(layer, y: int, h: int, colors_2d: np.ndarray) -> None:
        for x, z, w, d, _ in layer:
            owner[x:x + w, y:y + h, z:z + d] = len(pieces)
            pieces.append((x, y, z, w, d, h, int(colors_2d[x, z])))

    # Bands of 3 plates: full-height bricks where a column is occupied and
    # one color through the band, plates for whatever is left
    for y0 in range(0, Y, 3):
        if brick_fp and y0 + 3 <= Y:
            c = color_idx[:, y0:y0 + 3, :]
            full = occupancy[:, y0:y0 + 3, :].all(1) & (c[:, 0] == c[:, 1]) & (c[:, 1] == c[:, 2])
            if full.any():
                below = owner[:, y0 - 1, :] if y0 > 0 else None
                layer, opt = _solve_layer(full, c[:, 0], brick_fp, below, pieces, settings)
                not_optimal += not opt
                place(layer, y0, 3, c[:, 0])
        for y in range(y0, min(y0 + 3, Y)):
            rest = occupancy[:, y, :] & (owner[:, y, :] < 0)
            if rest.any():
                below = owner[:, y - 1, :] if y > 0 else None
                layer, opt = _solve_layer(rest, color_idx[:, y, :], plate_fp, below, pieces, settings)
                not_optimal += not opt
                place(layer, y, 1, color_idx[:, y, :])
    return pieces, owner, not_optimal


def _loose(pieces, owner: np.ndarray) -> np.ndarray:
    """Bool per piece: not connected to a ground piece through studs
    (pieces touching directly above or below)."""

    n = len(pieces)
    if n == 0:
        return np.zeros(0, dtype=bool)
    Y = owner.shape[1]
    rows, cols = [], []
    for i, (x, y, z, w, d, h, _) in enumerate(pieces):
        if y + h < Y:
            above = np.unique(owner[x:x + w, y + h, z:z + d])
            above = above[above >= 0]
            rows += [i] * len(above)
            cols += above.tolist()
    graph = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    _, label = connected_components(graph, directed=False)
    grounded = np.unique(label[[i for i, p in enumerate(pieces) if p[1] == 0]])
    return ~np.isin(label, grounded)


def _add_support(
    pieces, owner, loose, occupancy, solid, color_idx, max_plates: int
) -> int:
    """Under each loose piece with nothing below it, fill each column of its
    footprint straight down inside the filled model, but only where it
    meets material within max_plates. Returns cells added."""

    added = 0
    for i in np.flatnonzero(loose):
        x, y, z, w, d, _, color = pieces[i]
        if y == 0 or (owner[x:x + w, y - 1, z:z + d] >= 0).any():
            continue
        for cx in range(x, x + w):
            for cz in range(z, z + d):
                lo = max(y - max_plates, 0)
                col = occupancy[cx, lo:y, cz]
                hits = np.flatnonzero(col)
                if not len(hits):
                    continue
                top = lo + hits[-1] + 1
                gap = slice(top, y)
                if solid[cx, gap, cz].all():
                    occupancy[cx, gap, cz] = True
                    color_idx[cx, gap, cz] = color
                    added += y - top
    return added


def run_brick_optimization(
    req: BrickOptReq,
    settings: BrickOptSettings,
) -> BrickOptResult:
    req.output_dir.mkdir(parents=True, exist_ok=True)
    bricks_path = req.output_dir / "bricks.npz"
    bom_path = req.output_dir / "bom.json"

    def fail(error: str) -> BrickOptResult:
        return BrickOptResult(
            job_id=req.job_id, ok=False, bricks_path=bricks_path, bom_path=bom_path,
            output_dir=req.output_dir, num_bricks=0, num_bom_entries=0, error=error,
        )

    if not req.voxel_path.exists():
        return fail(f"voxel_path does not exist: {req.voxel_path}")

    data = np.load(req.voxel_path)
    occupancy = data["occupancy"].astype(bool)
    solid = data["solid"].astype(bool) if "solid" in data else None
    palette = _kit_palette(settings)
    if settings.color_mapping == "rank":
        color_idx = _rank_colors(data["colors"], occupancy, palette, settings)
    else:
        color_idx = _snap_colors(data["colors"], palette)
    color_idx = _smooth_colors(color_idx, occupancy, len(palette), settings.color_smoothing)

    support_cells = 0
    try:
        for round_ in range(settings.repair_rounds + 1):
            pieces, owner, not_optimal = _tile(occupancy, color_idx, settings)
            loose = _loose(pieces, owner)
            if not loose.any() or solid is None or round_ == settings.repair_rounds:
                break
            added = _add_support(
                pieces, owner, loose, occupancy, solid, color_idx, settings.max_support_plates
            )
            if added == 0:
                break
            support_cells += added
            log.info(f"Round {round_}: {loose.sum()} loose pieces, added {added} support cells")
    except RuntimeError as e:
        return fail(str(e))

    # Pieces that still float can't be built: leave them out, report the count
    dropped = 0
    if settings.drop_loose and loose.any():
        dropped = int(loose.sum())
        pieces = [p for p, l in zip(pieces, loose) if not l]
        loose = np.zeros(len(pieces), dtype=bool)

    log.info(f"Placed {len(pieces)} parts ({dropped} loose dropped, "
             f"{int(loose.sum())} loose kept, {not_optimal} layers not proven optimal)")

    # One square base plate under everything, counted as one part. The
    # model is centered on it and lifted one plate
    base_size = 0
    if settings.base_plate and pieces:
        X, _, Z = occupancy.shape
        need = max(X, Z)
        base_size = next((n for n in settings.base_plate_sizes if n >= need), need)
        ox, oz = (base_size - X) // 2, (base_size - Z) // 2
        pieces = [(x + ox, y + 1, z + oz, w, d, h, c) for x, y, z, w, d, h, c in pieces]
        # The base plate's color is outside the kit colors (bricks only)
        pieces.insert(0, (0, 0, 0, base_size, base_size, 1, len(palette)))

    by_name = {name: (r, g, b) for name, r, g, b in BRICK_COLORS}
    out_palette = np.vstack([palette, [by_name[settings.base_plate_color]]])
    out_names = tuple(settings.colors) + (settings.base_plate_color,)
    rgb = out_palette[[p[6] for p in pieces]] if pieces else np.zeros((0, 3), np.int32)
    brick_array = np.array([p[:6] for p in pieces], dtype=np.int32).reshape(-1, 6)
    brick_array = np.hstack([brick_array, rgb.astype(np.int32)])
    np.savez_compressed(bricks_path, bricks=brick_array)

    bom = Counter((_part_name(*p[3:6]), out_names[p[6]]) for p in pieces)
    bom_path.write_text(json.dumps({
        "job_id": req.job_id,
        "total_bricks": len(pieces),
        "unique_parts": len({part for part, _ in bom}),
        "unique_entries": len(bom),
        "loose_pieces": int(loose.sum()),
        "dropped_loose_pieces": dropped,
        "base_plate": f"{base_size}x{base_size}" if base_size else None,
        "entries": [
            {"part": part, "color": color, "quantity": n}
            for (part, color), n in bom.most_common()
        ],
    }, indent=2), encoding="utf-8")

    return BrickOptResult(
        job_id=req.job_id,
        ok=True,
        bricks_path=bricks_path,
        bom_path=bom_path,
        output_dir=req.output_dir,
        num_bricks=len(pieces),
        num_bom_entries=len(bom),
        num_loose=int(loose.sum()),
        num_dropped=dropped,
        base_plate_size=base_size,
        num_support_cells=support_cells,
        num_layers_not_optimal=not_optimal,
    )

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage

from .models import MeshVoxelReq, MeshVoxelResult
from .settings import MeshVoxelSettings


log = logging.getLogger(__name__)

# Rotates a Z-up mesh to Y-up: (x, y, z) -> (x, z, -y)
_Z_UP_TO_Y_UP = np.array([
    [1, 0, 0, 0],
    [0, 0, 1, 0],
    [0, -1, 0, 0],
    [0, 0, 0, 1],
], dtype=np.float64)


def _load_meshes(
    mesh_path: Path,
    settings: MeshVoxelSettings,
) -> list[trimesh.Trimesh]:
    """Load every mesh in the file with node transforms baked in, Y-up.

    Meshes are kept separate rather than concatenated so each keeps its own
    texture for color sampling.
    """
    scene = trimesh.load(mesh_path, force="scene")
    meshes = [g for g in scene.dump() if isinstance(g, trimesh.Trimesh) and len(g.faces)]
    if settings.up_axis == "z":
        for m in meshes:
            m.apply_transform(_Z_UP_TO_Y_UP)
    if settings.drop_ground_planes:
        meshes = _drop_ground_planes(meshes)
    return meshes


def _drop_ground_planes(meshes: list[trimesh.Trimesh]) -> list[trimesh.Trimesh]:
    """Remove flat meshes at the bottom that are much wider than the rest
    (a ground plane). Left in, it would set the model's size."""

    if len(meshes) < 2:
        return meshes
    lo = np.min([m.bounds[0] for m in meshes], axis=0)
    hi = np.max([m.bounds[1] for m in meshes], axis=0)
    height = hi[1] - lo[1]

    def xz_area(ms) -> float:
        a = np.min([m.bounds[0] for m in ms], axis=0)
        b = np.max([m.bounds[1] for m in ms], axis=0)
        return float((b[0] - a[0]) * (b[2] - a[2]))

    keep = []
    for i, m in enumerate(meshes):
        rest = meshes[:i] + meshes[i + 1:]
        flat = m.extents[1] < 0.02 * height
        at_bottom = m.bounds[0][1] - lo[1] < 0.25 * height
        if flat and at_bottom and xz_area([m]) > 1.5 * xz_area(rest):
            log.info(f"Dropping ground plane ({len(m.faces)} faces)")
            continue
        keep.append(m)
    return keep or meshes


def _to_grid_units(
    meshes: list[trimesh.Trimesh],
    settings: MeshVoxelSettings,
) -> tuple[tuple[int, int, int], float]:
    """Scale meshes in place so 1 unit = 1 stud in x/z and 1 plate in y,
    with the min corner at the origin. Returns (grid_shape, scale), where
    scale is grid studs per mesh unit."""

    lo = np.min([m.bounds[0] for m in meshes], axis=0)
    hi = np.max([m.bounds[1] for m in meshes], axis=0)
    extent = hi - lo

    s = settings.target_studs / max(extent[0], extent[2])
    plates_per_stud = settings.stud_size_m / settings.plate_size_m

    T = np.diag([s, s * plates_per_stud, s, 1.0])
    T[:3, 3] = -lo * np.array([s, s * plates_per_stud, s])
    for m in meshes:
        m.apply_transform(T)

    # Small tolerance so 2.9999999 / 3.0000001 both give 3 cells
    grid_extent = extent * np.array([s, s * plates_per_stud, s])
    shape = tuple(max(1, int(np.ceil(e - 1e-6))) for e in grid_extent)
    return shape, float(s)


def _linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    """glTF color factors are linear light; convert to display sRGB 0-255."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return (c * 255).round().clip(0, 255)


def _mesh_colors(
    mesh: trimesh.Trimesh,
    face_index: np.ndarray,
    bary: np.ndarray,
    settings: MeshVoxelSettings,
) -> np.ndarray:
    """RGB per sample: texture at the sample's UV, else face/vertex colors,
    else the material's flat color, else settings.default_color."""

    visual = mesh.visual
    if isinstance(visual, trimesh.visual.TextureVisuals):
        material = visual.material
        pbr = isinstance(material, trimesh.visual.material.PBRMaterial)
        # glTF (PBR) keeps its texture in baseColorTexture; OBJ in image
        image = material.baseColorTexture if pbr else getattr(material, "image", None)
        factor = getattr(material, "baseColorFactor", None) if pbr else None
        if visual.uv is not None and image is not None:
            uv_tri = visual.uv[mesh.faces[face_index]]           # (n, 3, 2)
            uv = (uv_tri * bary[:, :, None]).sum(axis=1)
            rgb = trimesh.visual.color.uv_to_interpolated_color(uv, image)[:, :3]
            if factor is not None:
                rgb = rgb * (np.asarray(factor[:3]) / 255.0)
            return rgb
        main = factor if factor is not None else getattr(material, "main_color", None)
        if main is not None:
            rgb = np.asarray(main)[:3]
            if pbr:
                rgb = _linear_to_srgb(rgb)
            return np.tile(rgb, (len(face_index), 1))
    elif isinstance(visual, trimesh.visual.ColorVisuals) and visual.defined:
        return visual.face_colors[face_index][:, :3]

    return np.tile(settings.default_color, (len(face_index), 1))


def _sample_surface(
    meshes: list[trimesh.Trimesh],
    settings: MeshVoxelSettings,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Random points on every mesh surface. Returns (points, RGB colors,
    mesh index per point, color-vote weight per point)."""

    rng = np.random.default_rng(settings.seed)
    points, colors, mesh_ids, weights = [], [], [], []
    for i, m in enumerate(meshes):
        n = max(1, int(m.area * settings.samples_per_cell))
        pts, face_index, bary = trimesh.sample.sample_surface(
            m, n, return_barycentric=True, seed=rng
        )
        # Vertices too, so tiny faces and sharp corners are never missed.
        # Each vertex is sampled through one face that uses it. They mark
        # occupancy but barely vote on color: a dense mesh has many
        # vertices whatever its visible area
        v_face = m.vertex_faces[:, 0]
        used = v_face >= 0
        v_face = v_face[used]
        v_bary = (m.faces[v_face] == np.flatnonzero(used)[:, None]).astype(np.float64)

        points += [pts, m.vertices[used]]
        colors += [
            _mesh_colors(m, face_index, bary, settings),
            _mesh_colors(m, v_face, v_bary, settings),
        ]
        mesh_ids += [np.full(len(pts), i), np.full(int(used.sum()), i)]
        weights += [np.ones(len(pts)), np.full(int(used.sum()), 1e-3)]
    return (
        np.vstack(points),
        np.vstack(colors).astype(np.float64),
        np.concatenate(mesh_ids),
        np.concatenate(weights),
    )


def _surface_grid(
    points: np.ndarray,
    colors: np.ndarray,
    mesh_ids: np.ndarray,
    weights: np.ndarray,
    shape: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Bin points into cells. Each cell takes the color of the mesh with the
    most surface in it, averaged over that mesh's points only, so cells on
    a border between materials don't come out as a blend of both."""

    idx = np.floor(points).astype(np.int64)
    idx = np.clip(idx, 0, np.array(shape) - 1)
    flat = np.ravel_multi_index(idx.T, shape)

    size = int(np.prod(shape))
    n_mesh = int(mesh_ids.max()) + 1
    key = flat * n_mesh + mesh_ids
    vote = np.bincount(key, weights=weights, minlength=size * n_mesh).reshape(size, n_mesh)
    count = np.bincount(key, minlength=size * n_mesh).reshape(size, n_mesh)
    color_sum = np.zeros((size * n_mesh, 3), dtype=np.float64)
    np.add.at(color_sum, key, colors)
    color_sum = color_sum.reshape(size, n_mesh, 3)

    surface = count.sum(1) > 0
    best = vote.argmax(1)
    rows = np.arange(size)
    cell_colors = color_sum[rows, best] / np.maximum(count[rows, best], 1)[:, None]
    cell_colors[~surface] = 0
    return (
        surface.reshape(shape),
        cell_colors.reshape(shape + (3,)).round().clip(0, 255).astype(np.uint8),
    )


def _fill(surface: np.ndarray) -> np.ndarray:
    """Fill the closed interior. Meshes with an open bottom (a house with no
    floor) leak in 3D, so fall back to filling each horizontal slice."""

    solid = ndimage.binary_fill_holes(surface)
    if solid.sum() == surface.sum():
        log.warning("3D fill added nothing (mesh open?); filling per y-slice")
        for y in range(surface.shape[1]):
            solid[:, y, :] = ndimage.binary_fill_holes(surface[:, y, :])
    return solid


def _hollow(
    solid: np.ndarray, wall: int, plate_ratio: float, floor: bool
) -> np.ndarray:
    """Keep cells within `wall` studs of open air, measured as 3D distance
    (a plate is plate_ratio studs tall), so sloped roofs stay thick enough
    for each step to overlap the one below. The extra half stud keeps the
    diagonal neighbour on a 45-degree step. With floor=False the ground
    counts as material, leaving the bottom open for a base plate.
    """
    X, Y, Z = solid.shape
    padded = np.zeros((X + 2, Y + 2, Z + 2), dtype=bool)
    padded[1:-1, 1:-1, 1:-1] = solid
    if not floor:
        padded[1:-1, 0, 1:-1] = solid[:, 0, :]
    dist = ndimage.distance_transform_edt(padded, sampling=(1.0, plate_ratio, 1.0))
    return solid & (dist[1:-1, 1:-1, 1:-1] <= wall + 0.5)


def _to_courses(grid: np.ndarray) -> np.ndarray:
    """(X, Y plates, Z) -> (X, K courses, Z): a 3-plate course of a column
    is filled when at least 2 of its plates are. Y is padded up to 3K."""

    X, Y, Z = grid.shape
    K = -(-Y // 3)
    padded = np.zeros((X, K * 3, Z), dtype=bool)
    padded[:, :Y] = grid
    return padded.reshape(X, K, 3, Z).sum(2) >= 2


def run_mesh_voxelization(
    req: MeshVoxelReq,
    settings: MeshVoxelSettings,
) -> MeshVoxelResult:
    req.output_dir.mkdir(parents=True, exist_ok=True)
    voxel_path = req.output_dir / "occupancy.npz"

    def fail(error: str) -> MeshVoxelResult:
        return MeshVoxelResult(
            job_id=req.job_id,
            ok=False,
            voxel_path=voxel_path,
            grid_shape=(0, 0, 0),
            num_occupied=0,
            num_surface=0,
            error=error,
        )

    if not req.mesh_path.exists():
        return fail(f"mesh_path does not exist: {req.mesh_path}")

    try:
        meshes = _load_meshes(req.mesh_path, settings)
    except Exception as e:
        return fail(f"could not load mesh: {e}")
    if not meshes:
        return fail(f"no triangle meshes in {req.mesh_path}")

    shape, scale = _to_grid_units(meshes, settings)
    log.info(f"Grid: {shape[0]}x{shape[1]}x{shape[2]} (studs x plates x studs)")

    points, colors, mesh_ids, weights = _sample_surface(meshes, settings)
    surface, surface_colors = _surface_grid(points, colors, mesh_ids, weights, shape)

    solid = _fill(surface) if settings.fill_interior else surface.copy()
    plate_ratio = settings.plate_size_m / settings.stud_size_m
    if settings.snap_to_courses:
        # Work in whole bricks: round, hollow per course, then expand back
        # to plates so every course is either fully filled or empty
        courses = _to_courses(solid)
        shell = courses
        if settings.hollow_wall_studs is not None:
            shell = _hollow(courses, settings.hollow_wall_studs, 3 * plate_ratio, settings.floor)
        solid = np.repeat(courses, 3, axis=1)
        occupancy = np.repeat(shell, 3, axis=1)
        surface = np.pad(surface, ((0, 0), (0, solid.shape[1] - surface.shape[1]), (0, 0)))
        shape = solid.shape
    else:
        occupancy = solid
        if settings.hollow_wall_studs is not None:
            occupancy = _hollow(solid, settings.hollow_wall_studs, plate_ratio, settings.floor)

    # Every occupied cell takes the color of the nearest surface cell
    surface_colors = np.pad(
        surface_colors, ((0, 0), (0, surface.shape[1] - surface_colors.shape[1]), (0, 0), (0, 0))
    )
    _, nearest = ndimage.distance_transform_edt(~surface, return_indices=True)
    colors_grid = surface_colors[nearest[0], nearest[1], nearest[2]]
    if settings.snap_to_courses:
        # One color per course: its middle plate's
        X, Y, Z = shape
        middle = colors_grid.reshape(X, Y // 3, 3, Z, 3)[:, :, 1:2]
        colors_grid = np.repeat(middle, 3, axis=2).reshape(X, Y, Z, 3)
    colors_grid[~occupancy] = 0

    log.info(f"Occupied: {occupancy.sum()} (surface {surface.sum()})")

    np.savez_compressed(
        voxel_path,
        occupancy=occupancy,
        colors=colors_grid,
        # Filled model before hollowing: where support can be added later
        solid=solid,
        scale=scale,
        up_axis=settings.up_axis,
        source=str(req.mesh_path),
    )

    return MeshVoxelResult(
        job_id=req.job_id,
        ok=True,
        voxel_path=voxel_path,
        grid_shape=tuple(int(v) for v in shape),
        num_occupied=int(occupancy.sum()),
        num_surface=int(surface.sum()),
    )

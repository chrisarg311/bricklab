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
    return meshes


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
        image = getattr(material, "image", None)
        if visual.uv is not None and image is not None:
            uv_tri = visual.uv[mesh.faces[face_index]]           # (n, 3, 2)
            uv = (uv_tri * bary[:, :, None]).sum(axis=1)
            return trimesh.visual.color.uv_to_interpolated_color(uv, image)[:, :3]
        main = getattr(material, "main_color", None)
        if main is not None:
            return np.tile(np.asarray(main)[:3], (len(face_index), 1))
    elif isinstance(visual, trimesh.visual.ColorVisuals) and visual.defined:
        return visual.face_colors[face_index][:, :3]

    return np.tile(settings.default_color, (len(face_index), 1))


def _sample_surface(
    meshes: list[trimesh.Trimesh],
    settings: MeshVoxelSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Random points on every mesh surface plus their RGB colors."""

    rng = np.random.default_rng(settings.seed)
    points, colors = [], []
    for m in meshes:
        n = max(1, int(m.area * settings.samples_per_cell))
        pts, face_index, bary = trimesh.sample.sample_surface(
            m, n, return_barycentric=True, seed=rng
        )
        # Vertices too, so tiny faces and sharp corners are never missed.
        # Each vertex is sampled through one face that uses it.
        v_face = m.vertex_faces[:, 0]
        used = v_face >= 0
        v_face = v_face[used]
        v_bary = (m.faces[v_face] == np.flatnonzero(used)[:, None]).astype(np.float64)

        points += [pts, m.vertices[used]]
        colors += [
            _mesh_colors(m, face_index, bary, settings),
            _mesh_colors(m, v_face, v_bary, settings),
        ]
    return np.vstack(points), np.vstack(colors).astype(np.float64)


def _surface_grid(
    points: np.ndarray,
    colors: np.ndarray,
    shape: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Bin points into cells; average their colors per cell."""

    idx = np.floor(points).astype(np.int64)
    idx = np.clip(idx, 0, np.array(shape) - 1)
    flat = np.ravel_multi_index(idx.T, shape)

    size = int(np.prod(shape))
    count = np.bincount(flat, minlength=size)
    color_sum = np.zeros((size, 3), dtype=np.float64)
    np.add.at(color_sum, flat, colors)

    surface = count > 0
    color_sum[surface] /= count[surface, None]
    return (
        surface.reshape(shape),
        color_sum.reshape(shape + (3,)).round().clip(0, 255).astype(np.uint8),
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


def _hollow(solid: np.ndarray, wall: int, cap: int) -> np.ndarray:
    """Keep cells within `wall` studs of the outside in x/z, or within `cap`
    plates of open air above/below, so the model becomes walls plus a floor
    and a covered top instead of a solid block."""

    # Erode in x/z only: a structure that is flat along y
    xz = np.zeros((3, 3, 3), dtype=bool)
    xz[:, 1, :] = ndimage.generate_binary_structure(2, 1)
    # Erode in y only
    y = np.zeros((3, 3, 3), dtype=bool)
    y[1, :, 1] = True

    inner = ndimage.binary_erosion(solid, structure=xz, iterations=wall)
    inner &= ndimage.binary_erosion(solid, structure=y, iterations=cap)
    return solid & ~inner


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

    points, colors = _sample_surface(meshes, settings)
    surface, surface_colors = _surface_grid(points, colors, shape)

    occupancy = _fill(surface) if settings.fill_interior else surface.copy()
    if settings.hollow_wall_studs is not None:
        occupancy = _hollow(
            occupancy, settings.hollow_wall_studs, settings.cap_plates
        )

    # Every occupied cell takes the color of the nearest surface cell
    _, nearest = ndimage.distance_transform_edt(~surface, return_indices=True)
    colors_grid = surface_colors[nearest[0], nearest[1], nearest[2]]
    colors_grid[~occupancy] = 0

    log.info(f"Occupied: {occupancy.sum()} (surface {surface.sum()})")

    np.savez_compressed(
        voxel_path,
        occupancy=occupancy,
        colors=colors_grid,
        scale=scale,
        up_axis=settings.up_axis,
        source=str(req.mesh_path),
    )

    return MeshVoxelResult(
        job_id=req.job_id,
        ok=True,
        voxel_path=voxel_path,
        grid_shape=shape,
        num_occupied=int(occupancy.sum()),
        num_surface=int(surface.sum()),
    )

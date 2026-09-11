"""
GLB builder — converts brick layout to a GLB file for web viewing.
- Per-brick colors via separate materials
- Y axis flipped so model sits right-side up
- Beveled boxes with stud cylinders
"""
from __future__ import annotations

import math
import struct
from pathlib import Path
from collections import defaultdict

import numpy as np

from .settings import InstructionsSettings


def _box_mesh(
    x: float, y: float, z: float,
    w: float, h: float, d: float,
    bevel: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Beveled box mesh. Returns (vertices, indices)."""
    b = min(bevel, w * 0.1, h * 0.1, d * 0.1)
    verts = np.array([
        [x+b,   y,   z+b],
        [x+w-b, y,   z+b],
        [x+w-b, y,   z+d-b],
        [x+b,   y,   z+d-b],
        [x+b,   y+h, z+b],
        [x+w-b, y+h, z+b],
        [x+w-b, y+h, z+d-b],
        [x+b,   y+h, z+d-b],
    ], dtype=np.float32)

    indices = np.array([
        0, 2, 1,  0, 3, 2,   # bottom
        4, 5, 6,  4, 6, 7,   # top
        0, 1, 5,  0, 5, 4,   # front
        2, 3, 7,  2, 7, 6,   # back
        0, 4, 7,  0, 7, 3,   # left
        1, 2, 6,  1, 6, 5,   # right
    ], dtype=np.uint32)

    return verts, indices


def _stud_mesh(
    cx: float, cy: float, cz: float,
    radius: float, height: float,
    segments: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    """Cylinder stud mesh. Returns (vertices, indices)."""
    verts = [[cx, cy, cz], [cx, cy + height, cz]]  # bottom/top centers

    for i in range(segments):
        a = 2 * math.pi * i / segments
        verts.append([cx + radius * math.cos(a), cy,          cz + radius * math.sin(a)])
    for i in range(segments):
        a = 2 * math.pi * i / segments
        verts.append([cx + radius * math.cos(a), cy + height, cz + radius * math.sin(a)])

    verts = np.array(verts, dtype=np.float32)
    indices = []

    rb = 2
    rt = 2 + segments

    for i in range(segments):
        ni = (i + 1) % segments
        # bottom cap
        indices.extend([0, rb + ni, rb + i])
        # top cap
        indices.extend([1, rt + i, rt + ni])
        # sides
        indices.extend([rb+i, rb+ni, rt+ni, rb+i, rt+ni, rt+i])

    return verts, np.array(indices, dtype=np.uint32)


def _build_brick_mesh(
    bx: int, by: int, bz: int,
    bw: int, bd: int, bh: int,
    settings: InstructionsSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Build combined box + studs mesh for one brick."""
    # Convert to metres, flip Y so model is right-side up
    x = float(bx) * settings.stud_size_m
    y = -float(by) * settings.plate_size_m   # Y flip
    z = float(bz) * settings.stud_size_m
    w = float(bw) * settings.stud_size_m
    h = -float(bh) * settings.plate_size_m  # Y flip
    d = float(bd) * settings.stud_size_m

    # Ensure h is negative (pointing down after flip) — swap y/h so box is correct
    if h < 0:
        y, h = y + h, -h

    bevel = min(w, h, d) * settings.bevel_size_ratio

    all_verts = []
    all_inds = []

    def add_mesh(v, i):
        base = sum(len(x) for x in all_verts)
        all_verts.append(v)
        all_inds.append(i + base)

    # Box
    bv, bi = _box_mesh(x, y, z, w, h, d, bevel)
    add_mesh(bv, bi)

    # Studs on top face (y + h after flip)
    stud_r = settings.stud_size_m * settings.stud_radius_ratio
    stud_h = settings.stud_height_m
    top_y = y + h

    for sx in range(int(bw)):
        for sz in range(int(bd)):
            cx = x + (sx + 0.5) * settings.stud_size_m
            cz = z + (sz + 0.5) * settings.stud_size_m
            sv, si = _stud_mesh(cx, top_y, cz, stud_r, stud_h)
            add_mesh(sv, si)

    return np.vstack(all_verts), np.concatenate(all_inds)


def build_glb(
    bricks: np.ndarray,
    settings: InstructionsSettings,
    output_path: Path,
) -> None:
    """
    Build GLB with per-color materials and correct Y orientation.
    bricks: (N, 9) int32 array [x, y, z, w, d, h, r, g, b]
    """
    import pygltflib

    if len(bricks) == 0:
        return

    # Group bricks by color
    color_to_bricks: dict[tuple, list[int]] = defaultdict(list)
    for i, brick in enumerate(bricks):
        color = (int(brick[6]), int(brick[7]), int(brick[8]))
        color_to_bricks[color].append(i)

    gltf = pygltflib.GLTF2()
    gltf.asset = pygltflib.Asset(version="2.0", generator="PictoBrick")
    gltf.scene = 0
    gltf.scenes = [pygltflib.Scene(nodes=[])]
    gltf.materials = []
    gltf.meshes = []
    gltf.nodes = []
    gltf.accessors = []
    gltf.bufferViews = []

    all_buffer_data = bytearray()
    accessor_idx = 0
    buffer_view_idx = 0

    for color, indices in color_to_bricks.items():
        r, g, b = color
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0

        # Build combined mesh for all bricks of this color
        group_verts = []
        group_inds = []

        for brick_idx in indices:
            br = bricks[brick_idx]
            v, i = _build_brick_mesh(
                int(br[0]), int(br[1]), int(br[2]),
                int(br[3]), int(br[4]), int(br[5]),
                settings,
            )
            base = sum(len(x) for x in group_verts)
            group_verts.append(v)
            group_inds.append(i + base)

        vertices = np.vstack(group_verts).astype(np.float32)
        indices_arr = np.concatenate(group_inds).astype(np.uint32)

        verts_bytes = vertices.tobytes()
        inds_bytes = indices_arr.tobytes()

        # Align to 4 bytes
        def pad4(data):
            pad = (4 - len(data) % 4) % 4
            return data + b'\x00' * pad

        verts_bytes_padded = pad4(verts_bytes)
        inds_bytes_padded = pad4(inds_bytes)

        vert_offset = len(all_buffer_data)
        all_buffer_data.extend(verts_bytes_padded)
        ind_offset = len(all_buffer_data)
        all_buffer_data.extend(inds_bytes_padded)

        # Buffer views
        gltf.bufferViews.append(pygltflib.BufferView(
            buffer=0,
            byteOffset=vert_offset,
            byteLength=len(verts_bytes),
            target=pygltflib.ARRAY_BUFFER,
        ))
        gltf.bufferViews.append(pygltflib.BufferView(
            buffer=0,
            byteOffset=ind_offset,
            byteLength=len(inds_bytes),
            target=pygltflib.ELEMENT_ARRAY_BUFFER,
        ))

        # Accessors
        vmin = vertices.min(axis=0).tolist()
        vmax = vertices.max(axis=0).tolist()

        gltf.accessors.append(pygltflib.Accessor(
            bufferView=buffer_view_idx,
            componentType=pygltflib.FLOAT,
            count=len(vertices),
            type=pygltflib.VEC3,
            min=vmin,
            max=vmax,
        ))
        gltf.accessors.append(pygltflib.Accessor(
            bufferView=buffer_view_idx + 1,
            componentType=pygltflib.UNSIGNED_INT,
            count=len(indices_arr),
            type=pygltflib.SCALAR,
        ))

        # Material
        mat_idx = len(gltf.materials)
        gltf.materials.append(pygltflib.Material(
            pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                baseColorFactor=[rf, gf, bf, 1.0],
                metallicFactor=0.05,
                roughnessFactor=0.4,
            ),
            name=f"lego_{r}_{g}_{b}",
        ))

        # Mesh
        mesh_idx = len(gltf.meshes)
        gltf.meshes.append(pygltflib.Mesh(
            primitives=[pygltflib.Primitive(
                attributes=pygltflib.Attributes(POSITION=accessor_idx),
                indices=accessor_idx + 1,
                material=mat_idx,
            )]
        ))

        # Node
        node_idx = len(gltf.nodes)
        gltf.nodes.append(pygltflib.Node(mesh=mesh_idx))
        gltf.scenes[0].nodes.append(node_idx)

        accessor_idx += 2
        buffer_view_idx += 2

    # Single buffer
    gltf.buffers = [pygltflib.Buffer(byteLength=len(all_buffer_data))]
    gltf.set_binary_blob(bytes(all_buffer_data))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    gltf.save_binary(str(output_path))
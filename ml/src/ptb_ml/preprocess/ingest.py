from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple, List
from .io import JobWorkSpace
from PIL import Image, ImageOps

# HEIC/HEIF support (iPhone photos)
try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
except Exception:
    # If pillow-heif isn't installed, HEIC files will fail to open later with a clear error.
    pillow_heif = None

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}

def split_inputs(paths:Iterable[str | Path]) -> tuple[list[Path], list[Path]]:
    """Split input paths into images and videos based on file extension"""
    imgs:list[Path] = []
    vids:list[Path] = []
    for p in paths:
        pp = Path(p)
        ext = pp.suffix.lower()
        if ext in IMAGE_EXTS:
            imgs.append(pp)
        elif ext in VIDEO_EXTS:
            vids.append(pp)
        else:
            raise ValueError(f"Unsupported file type {ext} for input {pp}")
    return imgs, vids


def normalize_images_to_frames(
        ws: JobWorkSpace,
        image_paths: Iterable[Path],
        *,
        start_idx:int = 0,
        jpg_quality:int = 95,
) -> tuple[list[Path], int]:
    """
    Reads image inputs, fixes EXIF orientation, converts to RGB, and saves as JPEG frames in the workspace.
    Returns a list of frame paths and the next available index after the last frame.
    """
    written:list[Path] = []
    idx = start_idx

    for src in image_paths:
        dst = ws.frame_path(idx, ext=".jpg")

        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)  # Fix orientation based on EXIF
            if im.mode != "RGB":
                im = im.convert("RGB")  # Ensure RGB format for JPEG
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst, format="JPEG", quality=jpg_quality)
        
        written.append(dst)
        idx += 1

    return written, idx


def stage_raw_inputs(ws: JobWorkSpace, input_paths: Iterable[str | Path]) -> list[Path]:
    """Copy raw uploads into ws.inputs_dir for traceability."""
    return ws.stage_inputs(input_paths, copy=True)


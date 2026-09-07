from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from .models import PriorsFrameResult, PriorsReq, PriorsResult
from .settings import PriorsSettings

log = logging.getLogger(__name__)


def _resolve_device(device: str) -> str:
    if device.strip().lower() == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device.strip().lower()


def _load_depth_pipeline(model_id: str, device: str):
    from transformers import pipeline
    return pipeline(
        task="depth-estimation",
        model=model_id,
        device=device,
    )


def _load_deeplab(device: str, classes_to_mask: tuple[str, ...]):
    """Reuse DeepLabv3 context from preprocess masking."""
    from ptb_ml.preprocess.masking import _init_deeplab_ctx
    return _init_deeplab_ctx(device=device, classes_to_mask=classes_to_mask)


def _save_depth_png(depth_np: np.ndarray, path: Path, max_val: int) -> None:
    """Save depth as 16-bit PNG for lossless precision."""
    path.parent.mkdir(parents=True, exist_ok=True)
    d = depth_np.astype(np.float32)
    # Normalize to [0, max_val]
    d_min, d_max = d.min(), d.max()
    if d_max > d_min:
        d = (d - d_min) / (d_max - d_min) * max_val
    else:
        d = np.zeros_like(d)
    Image.fromarray(d.astype(np.uint16)).save(str(path))


def _save_normals_png(normals: np.ndarray, path: Path) -> None:
    """Save normals as 8-bit RGB PNG. Maps [-1,1] -> [0,255]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = ((normals + 1.0) / 2.0 * 255).clip(0, 255).astype(np.uint8)
    Image.fromarray(n, mode="RGB").save(str(path))


def _save_segmentation_png(seg_mask: np.ndarray, path: Path) -> None:
    """Save segmentation mask as 8-bit PNG. 255=dynamic object, 0=static."""
    path.parent.mkdir(parents=True, exist_ok=True)
    m = (seg_mask.astype(np.uint8) * 255)
    Image.fromarray(m, mode="L").save(str(path))


def run_priors(req: PriorsReq, settings: PriorsSettings) -> PriorsResult:
    device = _resolve_device(settings.device)

    depth_dir = req.output_dir / "depth"
    normals_dir = req.output_dir / "normals"
    segmentation_dir = req.output_dir / "segmentation"
    manifest_path = req.output_dir / "priors_manifest.json"

    for d in (depth_dir, normals_dir, segmentation_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Collect frames
    frames = sorted(req.frames_dir.glob("frame_??????.jpg"))
    if not frames:
        return PriorsResult(
            job_id=req.job_id,
            ok=False,
            frames=(),
            depth_dir=depth_dir,
            normals_dir=normals_dir,
            segmentation_dir=segmentation_dir,
            manifest_path=manifest_path,
            error=f"No frames found in {req.frames_dir}",
        )

    # Load models once
    log.info("Loading Depth Anything V2...")
    depth_pipe = _load_depth_pipeline(settings.depth_model_id, device)

    log.info("Loading DSINE...")
    from ptb_ml.priors.dsine_loader import DSINEPredictor
    dsine = DSINEPredictor(
        device=device,
        local_file_path=settings.dsine_local_weights,
    )

    log.info("Loading DeepLabv3...")
    deeplab_ctx = _load_deeplab(
        device=device,
        classes_to_mask=settings.semantic_classes_to_mask,
    )

    frame_results: list[PriorsFrameResult] = []

    for frame_path in frames:
        log.info(f"Processing {frame_path.name}...")

        # Load image once
        pil_img = Image.open(frame_path).convert("RGB")
        img_np = np.array(pil_img, dtype=np.uint8)

        # --- Stage 1: Segmentation (dynamic object mask) ---
        from ptb_ml.preprocess.masking import _deeplab_mask
        seg_mask = _deeplab_mask(img_np, deeplab_ctx)  # bool HxW, True=dynamic

        # --- Stage 2: Depth (mask dynamic objects before estimation) ---
        # Zero out dynamic regions so they don't influence depth
        masked_img = img_np.copy()
        masked_img[seg_mask] = 0
        masked_pil = Image.fromarray(masked_img)

        depth_result = depth_pipe(masked_pil)
        depth_np = np.array(depth_result["depth"], dtype=np.float32)

        # --- Stage 3: Normals (mask dynamic objects) ---
        normals_np = dsine.infer(masked_img)  # HxWx3 in [-1,1]

        # --- Save outputs ---
        stem = frame_path.stem  # e.g. frame_000001

        depth_path = depth_dir / f"{stem}.png"
        normals_path = normals_dir / f"{stem}.png"
        seg_path = segmentation_dir / f"{stem}.png"

        _save_depth_png(depth_np, depth_path, settings.depth_png_max_val)
        _save_normals_png(normals_np, normals_path)
        _save_segmentation_png(seg_mask, seg_path)

        frame_results.append(PriorsFrameResult(
            frame=frame_path.name,
            depth_path=str(depth_path),
            normals_path=str(normals_path),
            segmentation_path=str(seg_path),
        ))

    # Write manifest
    payload = {
        "version": 1,
        "job_id": req.job_id,
        "device": device,
        "depth_model": settings.depth_model_id,
        "normals_model": "DSINE_v02",
        "segmentation_model": "deeplabv3_resnet50",
        "total_frames": len(frame_results),
        "frames": [
            {
                "frame": r.frame,
                "depth": r.depth_path,
                "normals": r.normals_path,
                "segmentation": r.segmentation_path,
            }
            for r in frame_results
        ],
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    return PriorsResult(
        job_id=req.job_id,
        ok=True,
        frames=tuple(frame_results),
        depth_dir=depth_dir,
        normals_dir=normals_dir,
        segmentation_dir=segmentation_dir,
        manifest_path=manifest_path,
    )
"""masking.py — per-frame foreground mask generation.

Strategies
----------
none        All-white mask (all pixels foreground). Zero cost, safe default.
threshold   Fast luminance threshold. Best for white/studio backgrounds.
grabcut     OpenCV GrabCut with a central-rectangle heuristic. Good general-
            purpose option with no extra dependencies.
rembg       ML-based removal via the `rembg` package (optional dep).
            Best quality for complex or outdoor backgrounds.

All strategies write a single-channel uint8 PNG to ws.masks_dir where
255 = allowed and 0 = forbidden, matching the NeRF/3DGS convention.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from .io import mask_path

import numpy as np
from PIL import Image, ImageFilter

from .settings import MaskingSettings

log =logging.getLogger(__name__)

@dataclass(frozen=True)
class MaskingFrameStatus:
    image:str
    mask:str
    width:int
    height:int
    unmasked_ratio:float
    masked_ratio:float
    bad_for_sfm:bool
    notes:tuple[str, ...] = ()


@dataclass(frozen=True)
class MaskingRunResults:
    masks_dir:Path
    manifest_path:Path
    frames:tuple[MaskingFrameStatus, ...]
    masked_frames:int
    bad_for_sfm_frames:int


def run_masking(
        image_paths:Sequence[Path],
        image_root:Path,
        output_dir:Path,
        *,
        settings: MaskingSettings,
) -> Optional[MaskingRunResults]:
    """ Validate the config and run the masking. Returns None if masking is disabled. """
    """ Creates per pixel mask -PNGs where 255=foreground, 0=background. Returns summary results. """
    if not isinstance(settings, MaskingSettings):
        raise TypeError("settings must be a MaskingSettings instance")

    if not settings.enabled or settings.backend.strip().lower() in ("none", ""):
        return None
    
    image_root = Path(image_root)
    output_dir = Path(output_dir)
    
    backend_1 = settings.backend.strip().lower()
    use_sky = "sky_hsv" in backend_1
    use_deeplab = "deeplab" in backend_1

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "mask_manifest.json"

    deeplab_ctx = None
    if use_deeplab:
        deeplab_ctx = _init_deeplab_ctx(
            device=settings.device, 
            classes_to_mask=settings.semantic_classes_to_mask
    )

    stats:list[MaskingFrameStatus] = []
    bad_count = 0
    for img_p in image_paths:
        img_p = Path(img_p)
        if not img_p.exists():
            log.warning(f"Masking: image path {img_p} does not exist, skipping.")
            continue

        rgb= _read_rgb(img_p)
        h,w = rgb.shape[:2]

        keep = np.ones((h,w), dtype=bool)
        notes: list[str] = []

        if use_sky:
            sky = _sky_mask(
                rgb,
                top_fraction= settings.sky_top_fraction,
                blue_strength= settings.sky_blue_strength,
                low_sat= settings.sky_low_sat,
                high_val= settings.sky_high_val
            )
            keep[sky] = False
            notes.append("sky_hsv")

        if use_deeplab and deeplab_ctx is not None:
            sem = _deeplab_mask(rgb, deeplab_ctx)
            keep[sem] = False
            notes.append("deeplab")

        if settings.dilation_px and settings.dilation_px > 0:
            keep = _dilate_masked_out(keep, dilation_px= settings.dilation_px)

        
        unmasked_ratio = float(np.mean(keep))
        masked_ratio = 1.0 - unmasked_ratio
        bad_for_sfm = unmasked_ratio < settings.min_unmasked_ratio
        if bad_for_sfm:
            bad_count += 1
            notes.append(f"low_unmasked_ratio<{settings.min_unmasked_ratio:g}")
        
        mask_u8 = np.where(keep, 255, 0).astype(np.uint8)
        mask_p = mask_path(
            image_path=img_p,
            image_root=image_root,
            mask_root=output_dir,
        )
        _write_mask(mask_u8, mask_p)

        stats.append(
            MaskingFrameStatus(
                image=str(img_p),
                mask=str(mask_p),
                width=w,
                height=h,   
                unmasked_ratio=unmasked_ratio,
                masked_ratio=masked_ratio,
                bad_for_sfm=bad_for_sfm,
                notes=tuple(notes)
            )   
            
        )
    
    payload: dict[str, Any] = {
        "version": 1,
        "backend": settings.backend,
        "masked_frames": len(stats),
        "bad_for_sfm_frames": bad_count,
        "frames": [asdict(s) for s in stats]
    }

    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return MaskingRunResults(
        masks_dir=output_dir,
        manifest_path=manifest_path,
        frames=tuple(stats),
        masked_frames=len(stats),
        bad_for_sfm_frames=bad_count
    )




def _read_rgb(path:Path) -> np.ndarray:
    with Image.open(path) as im:
        im = im.convert("RGB")
        return np.asarray(im, dtype=np.uint8)
    

@dataclass(frozen=True)
class _DeepLabCtx:
    model: Any
    device: str
    class_ids_to_mask: set[int]
    preprocess: Any
    
def _init_deeplab_ctx(*, device:str, classes_to_mask:tuple[str, ...]) -> _DeepLabCtx:
    try:
        import torch
        from torchvision.models.segmentation import deeplabv3_resnet50, DeepLabV3_ResNet50_Weights
    except Exception as e:
        raise RuntimeError(
            "deeplabv3 masking requires torch+torchvision. "
            "Switch backend to 'sky_hsv' if you don't want that dependency."
        ) from e
    

    weights = DeepLabV3_ResNet50_Weights.DEFAULT
    cats = list(weights.meta.get("categories", []))
    name_to_id = {name: i for i, name in enumerate(cats)}

    dev = device.strip().lower()
    if dev == "auto":
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    elif dev not in ("cpu", "cuda"):
        raise ValueError(f"Invalid device '{device}' for deeplabv3 masking, must be one of auto|cpu|cuda")
    
    model = deeplabv3_resnet50(weights=weights).eval().to(dev)
    preprocess = weights.transforms()

    ids = {name_to_id[name] for name in classes_to_mask if name in name_to_id}
    if not ids:
        log.warning(f"deeplabv3 masking: no valid classes to mask found in model categories, got {classes_to_mask}, model categories are {cats}")
    
    return _DeepLabCtx(
        model=model, 
        device=dev, 
        class_ids_to_mask=ids,
        preprocess=preprocess,
    )

def _deeplab_mask(rgb:np.ndarray, ctx: _DeepLabCtx) -> np.ndarray:
    import torch
    import torch.nn.functional as F
    
    if not ctx.class_ids_to_mask:
        return np.zeros(rgb.shape[:2], dtype=bool)
    
    h,w = rgb.shape[:2]

    pil = Image.fromarray(rgb, mode="RGB")
    input_tensor = ctx.preprocess(pil).unsqueeze(0).to(ctx.device)  

    with torch.no_grad():
        out = ctx.model(input_tensor)["out"]
        out = F.interpolate(
            out,
            size=(h, w),
            mode="bilinear",
            align_corners=False
        )
        pred = out.argmax(1).squeeze(0).cpu().numpy().astype(np.int32)

    return np.isin(pred, list(ctx.class_ids_to_mask))


def _sky_mask(
        rgb:np.ndarray,
        *,
        top_fraction:float,
        blue_strength:float,
        low_sat:float,
        high_val:float
) -> np.ndarray:
    """
    Returns boolean mask of where true means mask out
    only considers top portion of the image as the sky to avoid confusing for blue objects
    """

    h,w = rgb.shape[:2]
    top_h= int(max(1, min(h, round(h * top_fraction))))
    region = rgb[:top_h].astype(np.float32) / 255.0

    r= region[...,0]
    g = region[...,1]
    b = region[...,2]

    blue_dom = (b - np.maximum(r, g)) > blue_strength

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    val = maxc
    sat = np.where(maxc > 1e-6, (maxc - minc) / maxc, 0.0)

    cloudy = (sat < low_sat) & (val > high_val)
    sky_top = blue_dom | cloudy

    out = np.zeros((h,w), dtype=bool)
    out[:top_h] = sky_top
    return out
    

def _dilate_masked_out(mask:np.ndarray, dilation_px:int) -> np.ndarray:
    """Dilates the False (masked-out) regions of the mask by the specified pixel radius."""
    if dilation_px <=0:
        return mask
    
    masked_out = (~mask).astype(np.uint8)*255

    k = max(3, 2 * int(dilation_px) + 1)

    im= Image.fromarray(masked_out, mode="L")
    dilated = im.filter(ImageFilter.MaxFilter(size=k))
    dilated_masked_out = np.asarray(dilated, dtype=np.uint8) > 0

    return ~dilated_masked_out


def _write_mask(mask_u8:np.ndarray, path:Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mask_u8.dtype != np.uint8:
        mask_u8 = mask_u8.astype(np.uint8)

    with Image.fromarray(mask_u8, mode="L") as im:
        im.save(path, format="PNG")


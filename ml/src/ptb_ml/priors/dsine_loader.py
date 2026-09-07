"""
CPU-compatible DSINE loader — patches hubconf.py's hardcoded CUDA device.
Weights are downloaded from HuggingFace on first use and cached by torch.hub.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms

# Ensure DSINE vendor repo is on the path
_DSINE_ROOT = Path(__file__).resolve().parents[3] / "vendor" / "DSINE"
if str(_DSINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_DSINE_ROOT))


def _load_state_dict(local_file_path: Optional[str] = None) -> dict:
    if local_file_path is not None and Path(local_file_path).exists():
        state_dict = torch.load(local_file_path, map_location="cpu")
    else:
        url = "https://huggingface.co/camenduru/DSINE/resolve/main/dsine.pt"
        state_dict = torch.hub.load_state_dict_from_url(
            url, file_name="dsine.pt", map_location="cpu"
        )
    return state_dict["model"]


class DSINEPredictor:
    """
    Device-agnostic wrapper around DSINE_v02.
    Predicts surface normals from RGB images.
    Output normals are in [-1, 1] range per channel (X, Y, Z).
    """

    def __init__(self, device: str = "cpu", local_file_path: Optional[str] = None) -> None:
        from vendor.DSINE.models.dsine.v02 import DSINE_v02
        import vendor.DSINE.utils.utils as utils
        self._utils = utils

        self.device = torch.device(device)
        self.transform = transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        )

        state_dict = _load_state_dict(local_file_path)

        # DSINE_v02 requires an args object — build a minimal one
        args = _build_dsine_args()
        self.model = DSINE_v02(args)
        self.model.load_state_dict(state_dict, strict=False)
        self.model.eval()
        self.model = self.model.to(self.device)
        self.model.pixel_coords = self.model.pixel_coords.to(self.device)

    def infer(self, img_rgb: np.ndarray, intrins: Optional[torch.Tensor] = None) -> np.ndarray:
        """
        Args:
            img_rgb: HxWx3 uint8 numpy array in RGB order
            intrins: optional (1,3,3) camera intrinsics tensor

        Returns:
            normals: HxWx3 float32 numpy array in [-1, 1]
        """
        img = img_rgb.astype(np.float32) / 255.0
        img_t = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).to(self.device)
        _, _, orig_H, orig_W = img_t.shape

        # Pad to nearest multiple of 32
        pad_H = (32 - orig_H % 32) % 32
        pad_W = (32 - orig_W % 32) % 32
        l, r, t, b = 0, pad_W, 0, pad_H
        img_t = F.pad(img_t, (l, r, t, b), mode="constant", value=0.0)
        img_t = self.transform(img_t)

        if intrins is None:
            intrins = _get_intrins_from_fov(
                fov=60.0, H=orig_H, W=orig_W, device=self.device
            ).unsqueeze(0)

        intrins[:, 0, 2] += l
        intrins[:, 1, 2] += t

        with torch.no_grad():
            pred = self.model(img_t, intrins=intrins)[-1]
            pred = pred[:, :, t:t + orig_H, l:l + orig_W]

        # (1, 3, H, W) -> (H, W, 3)
        return pred.squeeze(0).permute(1, 2, 0).cpu().numpy()


def _get_intrins_from_fov(
    fov: float, H: int, W: int, device: torch.device
) -> torch.Tensor:
    """Estimate a simple pinhole intrinsics matrix from FOV."""
    focal = W / (2 * np.tan(np.deg2rad(fov) / 2))
    intrins = torch.tensor([
        [focal, 0, W / 2],
        [0, focal, H / 2],
        [0,     0,     1],
    ], dtype=torch.float32, device=device)
    return intrins


def _build_dsine_args():
    """
    Builds a minimal args namespace matching DSINE_v02's expected config.
    Values match the defaults from the original DSINE training config.
    """
    from types import SimpleNamespace
    return SimpleNamespace(
        NNET_encoder_B=5,
        NNET_decoder_NF=2048,
        NNET_decoder_BN=False,
        NNET_decoder_down=8,
        NNET_learned_upsampling=True,
        NNET_output_dim=3,
        NNET_feature_dim=64,
        NNET_hidden_dim=64,
        NRN_prop_ps=5,
        NRN_num_iter_train=5,
        NRN_num_iter_test=5,
        NRN_ray_relu=True,
    )
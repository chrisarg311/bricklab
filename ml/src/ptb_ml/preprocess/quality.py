from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np

from .settings import PreprocessSettings


@dataclass
class QualityMetrics:
    sharpness:float
    brightness:float
    clip_high:float
    clip_low:float


def compute_metrics(image_path:Path) -> QualityMetrics:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Sharpness via Variance of Laplacian
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Brightness via mean pixel value normalized to [0,1]
    brightness = float(gray.mean() / 255.0)

    # Clipping fractions
    clip_high = float(np.mean(gray >= 250).mean())
    clip_low = float(np.mean(gray <= 5).mean())

    return QualityMetrics(sharpness=sharpness, brightness=brightness, clip_high=clip_high, clip_low=clip_low)


def passes_quality(m:QualityMetrics, s:PreprocessSettings) -> tuple[bool, Optional[str]]:
    if m.sharpness < s.min_sharpness:
        return False, "blur"
    if not (s.min_brightness <= m.brightness <= s.max_brightness):
        return False, "bad exposure"
    if m.clip_high > s.max_clip_high:
        return False, "clipped_highlights"
    if m.clip_low > s.max_clip_low:
        return False, "crushed_shadows"
    return True, None

def score_and_filter(
        frames_paths:list[Path],
        settings:PreprocessSettings
    ) -> tuple[list[tuple[Path, QualityMetrics]], list[Tuple[Path, str, QualityMetrics]]]:
    """

    """
    kept:list[tuple[Path, QualityMetrics]] = []
    dropped:list[Tuple[Path, str, QualityMetrics]] = []

    for p in frames_paths:
        m = compute_metrics(p)
        passed, reason = passes_quality(m, settings)
        if passed:
            kept.append((p, m))
        else:
            dropped.append((p, reason or "unknown", m))
    return kept, dropped



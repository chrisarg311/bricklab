from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PIL import Image
import imagehash

from .quality import QualityMetrics
from .settings import PreprocessSettings


def phash(path:Path, hash_size:int) -> imagehash.ImageHash:
    with Image.open(path) as img:
        return imagehash.phash(img, hash_size=hash_size)
    

def dedupe_keep_best(
        keep:list[tuple[Path, QualityMetrics]],
        settings:PreprocessSettings
) -> tuple[list[tuple[Path, QualityMetrics]], list[Path]]:
    """
    Greedy dedupe: keep one representative for each near duplicate cluster
    "BEST" = highest sharpness, then brightness closer to mid
    returns (deduped_kept, removed_paths)
    """

    hashes:list[tuple[Path, QualityMetrics, imagehash.ImageHash]] = []
    for p,m in keep:
        h = phash(p, hash_size=settings.dedupe_phash_size)
        hashes.append((p, m, h))

    selected:list[tuple[Path, QualityMetrics, imagehash.ImageHash]] = []
    removed:list[Path] = []

    def score(m:QualityMetrics) -> tuple[float, float]:
        # maxamize sharpness, then minimize dist of brightness from 0.5
        return(m.sharpness, -abs(m.brightness - 0.5))
    
    for p, m, h in hashes:
        found_cluster= False
        for i, (sp, sm, sh) in enumerate(selected):
            if (h - sh) <= settings.dedupe_hamming_threshold:
                found_cluster = True
                # same cluster, keep the better one
                if score(m) > score(sm):
                    # replace with current one
                    removed.append(sp)
                    selected[i] = (p, m, h)
                else:
                    # keep existing, remove current
                    removed.append(p)
                break

        if not found_cluster:
            selected.append((p, m, h))
    deduped = [(p,m) for p, m, _ in selected]
    return deduped, removed
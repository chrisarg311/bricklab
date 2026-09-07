from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from .glb_builder import build_glb
from .models import BuildStep, InstructionsReq, InstructionsResult
from .settings import InstructionsSettings

log = logging.getLogger(__name__)


def _load_bricks(bricks_path: Path) -> np.ndarray:
    data = np.load(bricks_path)
    return data["bricks"]   # (N, 9) int32


def _compute_sections(
    bricks: np.ndarray,
    settings: InstructionsSettings,
) -> list[BuildStep]:
    """
    Group bricks into spatial sections, ordered bottom-up.
    Each section covers (section_size_studs x section_size_studs) in XZ
    and one layer range in Y.
    """
    if len(bricks) == 0:
        return []

    ss = settings.section_size_studs

    steps: list[BuildStep] = []
    step_num = 0

    # Get layer range
    y_min = int(bricks[:, 1].min())
    y_max = int(bricks[:, 1].max())

    # Get XZ range
    x_min = int(bricks[:, 0].min())
    x_max = int(bricks[:, 0].max())
    z_min = int(bricks[:, 2].min())
    z_max = int(bricks[:, 2].max())

    # Process bottom-up
    y = y_min
    while y <= y_max:
        y_end = min(y + 3, y_max + 1)  # group 3 plates (1 brick) per layer

        # Process sections in XZ
        x = x_min
        while x <= x_max:
            z = z_min
            while z <= z_max:
                # Find bricks in this section
                mask = (
                    (bricks[:, 0] >= x) & (bricks[:, 0] < x + ss) &
                    (bricks[:, 1] >= y) & (bricks[:, 1] < y_end) &
                    (bricks[:, 2] >= z) & (bricks[:, 2] < z + ss)
                )
                indices = np.where(mask)[0]

                if len(indices) > 0:
                    # Split into sub-steps if too many bricks
                    for chunk_start in range(
                        0, len(indices), settings.max_bricks_per_step
                    ):
                        chunk = indices[
                            chunk_start:chunk_start + settings.max_bricks_per_step
                        ]
                        steps.append(BuildStep(
                            step_number=step_num,
                            brick_indices=tuple(int(i) for i in chunk),
                            section_x=x // ss,
                            section_z=z // ss,
                            layer_min=y,
                            layer_max=y_end - 1,
                        ))
                        step_num += 1

                z += ss
            x += ss
        y = y_end

    return steps


def _steps_to_json(
    steps: list[BuildStep],
    bricks: np.ndarray,
    job_id: str,
) -> dict:
    return {
        "job_id": job_id,
        "total_steps": len(steps),
        "total_bricks": len(bricks),
        "steps": [
            {
                "step": s.step_number,
                "section_x": s.section_x,
                "section_z": s.section_z,
                "layer_min": s.layer_min,
                "layer_max": s.layer_max,
                "brick_count": len(s.brick_indices),
                "bricks": [
                    {
                        "x": int(bricks[i, 0]),
                        "y": int(bricks[i, 1]),
                        "z": int(bricks[i, 2]),
                        "w": int(bricks[i, 3]),
                        "d": int(bricks[i, 4]),
                        "h": int(bricks[i, 5]),
                        "color": [
                            int(bricks[i, 6]),
                            int(bricks[i, 7]),
                            int(bricks[i, 8]),
                        ],
                    }
                    for i in s.brick_indices
                ],
            }
            for s in steps
        ],
    }


def run_instructions(
    req: InstructionsReq,
    settings: InstructionsSettings,
) -> InstructionsResult:
    req.output_dir.mkdir(parents=True, exist_ok=True)
    glb_path = req.output_dir / "model.glb"
    steps_path = req.output_dir / "steps.json"

    if not req.bricks_path.exists():
        return InstructionsResult(
            job_id=req.job_id,
            ok=False,
            glb_path=glb_path,
            steps_path=steps_path,
            output_dir=req.output_dir,
            num_steps=0,
            num_bricks=0,
            error=f"bricks_path does not exist: {req.bricks_path}",
        )

    log.info("Loading bricks...")
    bricks = _load_bricks(req.bricks_path)
    log.info(f"Loaded {len(bricks)} bricks")

    # Build GLB
    log.info("Building GLB...")
    build_glb(bricks, settings, glb_path)
    log.info(f"GLB saved to {glb_path} ({glb_path.stat().st_size / 1024:.1f} KB)")

    # Compute build steps
    log.info("Computing build steps...")
    steps = _compute_sections(bricks, settings)
    log.info(f"Generated {len(steps)} build steps")

    # Save steps JSON
    steps_json = _steps_to_json(steps, bricks, req.job_id)
    steps_path.write_text(
        json.dumps(steps_json, indent=2), encoding="utf-8"
    )

    return InstructionsResult(
        job_id=req.job_id,
        ok=True,
        glb_path=glb_path,
        steps_path=steps_path,
        output_dir=req.output_dir,
        num_steps=len(steps),
        num_bricks=len(bricks),
    )
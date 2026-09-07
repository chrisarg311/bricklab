from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from ..preprocess.engine import PreprocessReq, PreprocessResult, run_preprocess
from ..preprocess.io import JobWorkSpace
from ..preprocess.settings import PreprocessSettings
from ..sfm.engine import run_sfm
from ..sfm.models import SfmReq, SfmResult
from ..sfm.settings import SfmSettings
from ..sfm_qc.engine import run_sfm_qc
from ..sfm_qc.models import SfmQcReq, SfmQcResult
from ..sfm_qc.settings import SfmQcSettings
from ..priors.engine import run_priors
from ..priors.models import PriorsReq, PriorsResult
from ..priors.settings import PriorsSettings
from ..shape_completion.engine import run_shape_completion
from ..shape_completion.models import ShapeCompletionReq, ShapeCompletionResult
from ..shape_completion.settings import ShapeCompletionSettings
from ..voxelization.engine import run_voxelization
from ..voxelization.models import VoxelizationReq, VoxelizationResult
from ..voxelization.settings import VoxelizationSettings
from ..brickification.engine import run_brickification
from ..brickification.models import BrickificationReq, BrickificationResult
from ..brickification.settings import BrickificationSettings
from ..instructions.engine import run_instructions
from ..instructions.models import InstructionsReq, InstructionsResult
from ..instructions.settings import InstructionsSettings


# Maps preprocess source_type -> SfM input_mode
_SOURCE_TO_MODE: dict[str, Literal["sequential", "unordered"]] = {
    "video": "sequential",
    "image_set": "unordered",
}


@dataclass(frozen=True)
class PipelineReq:
    base_dir: str | Path
    job_id: str
    input_paths: list[str | Path]
    clean: bool = False
    preprocess_settings: PreprocessSettings = None  # defaults applied below
    sfm_settings: SfmSettings = None               # defaults applied below
    # Optional callback invoked after each stage: (stage_name, progress_pct)
    progress_cb: Callable[[str, int], None] | None = None

    def __post_init__(self) -> None:
        if self.preprocess_settings is None:
            object.__setattr__(self, "preprocess_settings", PreprocessSettings())
        if self.sfm_settings is None:
            object.__setattr__(self, "sfm_settings", SfmSettings())


@dataclass(frozen=True)
class PipelineResult:
    job_id: str
    preprocess: PreprocessResult
    sfm: SfmResult
    sfm_qc: SfmQcResult
    ok: bool
    error: str | None = None
    priors: PriorsResult | None = None
    shape_completion: ShapeCompletionResult | None = None
    voxelization: VoxelizationResult | None = None
    brickification: BrickificationResult | None = None
    instructions: InstructionsResult | None = None


def _read_source_type(manifest_path: Path) -> str:
    """Read source_type out of manifest.json written by preprocessor."""
    with manifest_path.open(encoding="utf-8") as f:
        data = json.load(f)
    source_type = data.get("source_type")
    if source_type not in _SOURCE_TO_MODE:
        raise ValueError(
            f"Unknown source_type '{source_type}' in manifest {manifest_path}. "
            f"Expected one of {list(_SOURCE_TO_MODE)}"
        )
    return source_type


def _mask_dir_if_present(ws: JobWorkSpace) -> Path | None:
    """Return ws.masks_dir only if the masking manifest was actually written."""
    mask_manifest = ws.masks_dir / "mask_manifest.json"
    return ws.masks_dir if mask_manifest.exists() else None


def preprocess_to_sfm_req(
    preprocess_result: PreprocessResult,
    ws: JobWorkSpace,
    sfm_settings: SfmSettings,
) -> SfmReq:
    """Build an SfmReq from a completed PreprocessResult + its workspace."""
    source_type = _read_source_type(preprocess_result.manifest_path)
    input_mode = _SOURCE_TO_MODE[source_type]

    return SfmReq(
        job_id=ws.job_id,
        image_dir=ws.frames_dir,
        output_dir=ws.sfm_dir,
        input_mode=input_mode,
        database_path=ws.sfm_database_path,
        sparse_dir=ws.sfm_sparse_dir,
        logs_dir=ws.sfm_logs_dir,
        mask_dir=_mask_dir_if_present(ws),
        manifest_path=preprocess_result.manifest_path,
    )


def run_pipeline(req: PipelineReq) -> PipelineResult:
    def _report(stage: str, pct: int) -> None:
        if req.progress_cb is not None:
            try:
                req.progress_cb(stage, pct)
            except Exception:
                pass  # never let a callback crash the pipeline

    # --- Stage 1: Preprocess ---
    preprocess_req = PreprocessReq(
        base_dir=req.base_dir,
        job_id=req.job_id,
        input_paths=req.input_paths,
        clean=req.clean,
        settings=req.preprocess_settings,
    )
    preprocess_result = run_preprocess(preprocess_req)
    _report("preprocess", 12)

    if preprocess_result.kept_frames == 0:
        # No point running SfM with zero frames
        sfm_result = SfmResult(
            ok=False,
            job_id=req.job_id,
            input_mode="unordered",
            image_dir=Path(req.base_dir) / req.job_id / "frames",
            output_dir=Path(req.base_dir) / req.job_id / "sfm",
            database_path=Path(req.base_dir) / req.job_id / "sfm" / "database.db",
            sparse_dir=Path(req.base_dir) / req.job_id / "sfm" / "sparse",
            best_model_dir=None,
            error="Preprocess produced zero kept frames; SfM skipped.",
        )
        return PipelineResult(
            job_id=req.job_id,
            preprocess=preprocess_result,
            sfm=sfm_result,
            ok=False,
            error=sfm_result.error,
        )

    # --- Stage 2: Build workspace handle and SfmReq ---
    ws = JobWorkSpace(
        job_id=req.job_id,
        root=Path(req.base_dir) / req.job_id,
    )

    sfm_req = preprocess_to_sfm_req(preprocess_result, ws, req.sfm_settings)

    # --- Stage 3: SfM ---
    sfm_result = run_sfm(sfm_req, req.sfm_settings)
    _report("sfm", 30)

    sfm_qc_result: SfmQcResult | None = None
    if sfm_result.ok and sfm_result.best_model_dir is not None:
        sfm_qc_result = run_sfm_qc(
            SfmQcReq(
                job_id=req.job_id,
                sparse_model_dir=sfm_result.best_model_dir,
                num_input_images=preprocess_result.kept_frames,
            ),
            SfmQcSettings(colmap_bin=req.sfm_settings.colmap_bin),
        )
    else:
        sfm_qc_result = SfmQcResult(
            job_id=req.job_id,
            ok=False,
            route="orange",
            score=0.0,
            error="SfM produced no sparse models — routing Orange",
        )

    _report("sfm_qc", 42)

    #Priors
    priors_result:PriorsResult | None=None
    if True: #sfm_qc_result.route == "orange": # temporary force routing to orange \
        #for testing until blue implemented TODO
        priors_result = run_priors(
            PriorsReq(
                job_id=req.job_id,
                frames_dir=ws.frames_dir,
                output_dir=ws.root / "priors",
            ),
            PriorsSettings(device="cpu"),
    )
    if priors_result is not None and priors_result.ok:
        _report("priors", 58)
    """sfm_qc_result.route == "orange" and""" # dont check for orange pipeline
    # until all blue is added TODO
    shape_result: ShapeCompletionResult | None = None
    if  priors_result is not None and priors_result.ok:
        shape_result = run_shape_completion(
            ShapeCompletionReq(
                job_id=req.job_id,
                frames_dir=ws.frames_dir,
                depth_dir=priors_result.depth_dir,
                normals_dir=priors_result.normals_dir,
                segmentation_dir=priors_result.segmentation_dir,
                output_dir=ws.root / "shape_completion",
                sparse_model_dir=sfm_result.best_model_dir,
                colmap_bin=req.sfm_settings.colmap_bin,
            ),
            ShapeCompletionSettings(),
        )

    if shape_result is not None and shape_result.ok:
        _report("shape_completion", 70)
    #Voxelization
    voxel_result: VoxelizationResult | None = None
    if shape_result is not None and shape_result.ok:
        voxel_result = run_voxelization(
            VoxelizationReq(
                job_id=req.job_id,
                tsdf_path=shape_result.tsdf_path,
                output_dir=ws.root / "voxelization",
            ),
            VoxelizationSettings(),
        )

    if voxel_result is not None and voxel_result.ok:
        _report("voxelization", 80)
    # Brickification
    brickification_result: BrickificationResult | None = None
    if voxel_result is not None and voxel_result.ok:
        brickification_result = run_brickification(
            BrickificationReq(
                job_id=req.job_id,
                voxel_path=voxel_result.voxel_path,
                output_dir=ws.root / "brickification",
            ),
            BrickificationSettings(),
        )

        _report("brickification", 90)
        # Instruction Generation and final outputs
        instructions_result: InstructionsResult | None = None
    if brickification_result is not None and brickification_result.ok:
        instructions_result = run_instructions(
            InstructionsReq(
                job_id=req.job_id,
                bricks_path=brickification_result.bricks_path,
                bom_path=brickification_result.bom_path,
                output_dir=ws.root / "instructions",
        ),
        InstructionsSettings(),
    )

    _report("instructions", 100)
    return PipelineResult(
        job_id=req.job_id,
        preprocess=preprocess_result,
        sfm=sfm_result,
        sfm_qc= sfm_qc_result,
        priors=priors_result,
        shape_completion=shape_result,
        voxelization=voxel_result,
        brickification=brickification_result,
        instructions=instructions_result,
        ok=sfm_result.ok,
        error=sfm_result.error,
    )
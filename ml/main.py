from __future__ import annotations

import argparse
from pathlib import Path

from src.ptb_ml.pipeline import PipelineReq, run_pipeline
from src.ptb_ml.preprocess.settings import PreprocessSettings, MaskingSettings
from src.ptb_ml.sfm.settings import SfmSettings


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PTB pipeline: preprocess -> SfM"
    )

    # Job
    p.add_argument("--job-id", required=True)
    p.add_argument("--out", dest="base_dir", default="tmp/ptb_jobs",
                   help="Base output directory")
    p.add_argument("--clean", action="store_true",
                   help="Delete existing job folder before running")

    # Preprocess
    p.add_argument("--fps", type=float, default=2.0,
                   help="Video sampling FPS")
    p.add_argument("--max-frames", type=int, default=400,
                   help="Soft cap for extracted frames")
    p.add_argument("--masking-backend", default="sky_hsv",
                   choices=["none", "sky_hsv", "sky_hsv+deeplabv3"],
                   help="Masking backend")
    p.add_argument("--masking-device", default="auto",
                   choices=["auto", "cpu", "cuda"],
                   help="Device for deeplabv3 masking")

    # SfM
    p.add_argument("--no-sfm", action="store_true",
                   help="Skip SfM stage (preprocess only)")
    p.add_argument("--no-gpu", action="store_true",
                   help="Disable GPU for COLMAP feature extraction and matching")
    p.add_argument("--colmap-bin", default="colmap",
                   help="Path to COLMAP executable")
    p.add_argument("--camera-model", default="SIMPLE_RADIAL",
                   help="COLMAP camera model")
    
    # Relax Quality Filters (TEST)
    p.add_argument("--relax-quality-filter", action="store_true",
               help="Disable quality filtering for challenging or pre-curated datasets")
    # TODO: Debug Mode for storing information

    # Inputs
    p.add_argument("inputs", nargs="+", help="Input files: images and/or videos")

    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.relax_quality_filter:
        preprocess_settings = PreprocessSettings(
            fps=args.fps,
            max_video_frames=args.max_frames,
            min_sharpness=0.0,
            min_brightness=0.0,
            max_brightness=1.0,
            max_clip_high=1.0,
            max_clip_low=1.0,
            masking=MaskingSettings(
                enabled=args.masking_backend != "none",
                backend=args.masking_backend,
                device=args.masking_device,
            ),
        )
    
    else:
        preprocess_settings = PreprocessSettings(
            fps=args.fps,
            max_video_frames=args.max_frames,
            masking=MaskingSettings(
                enabled=args.masking_backend != "none",
                backend=args.masking_backend,
                device=args.masking_device,
            ),
        )

    sfm_settings = SfmSettings(
        enabled=not args.no_sfm,
        colmap_bin=args.colmap_bin,
        camera_model=args.camera_model,
        use_gpu=not args.no_gpu,
    )

    req = PipelineReq(
        base_dir=Path(args.base_dir),
        job_id=args.job_id,
        input_paths=[Path(x) for x in args.inputs],
        clean=args.clean,
        preprocess_settings=preprocess_settings,
        sfm_settings=sfm_settings,
    )

    result = run_pipeline(req)

    # --- Preprocess summary ---
    print("\n=== Preprocess ===")
    print(f"  job_root:       {result.preprocess.job_root}")
    print(f"  manifest:       {result.preprocess.manifest_path}")
    print(f"  total frames:   {result.preprocess.total_frames}")
    print(f"  kept:           {result.preprocess.kept_frames}")
    print(f"  dropped:        {result.preprocess.dropped_frames}")
    print(f"  deduped:        {result.preprocess.deduped_frames}")

    # --- SfM summary ---
    print("\n=== SfM ===")
    if not result.sfm.ok:
        print(f"  FAILED: {result.sfm.error}")
    else:
        print(f"  sparse models:  {result.sfm.num_sparse_models}")
        print(f"  best model:     {result.sfm.best_model_dir}")
        print(f"  database:       {result.sfm.database_path}")

    # SFM QC:
    print("\n=== SfM QC ===")
    if not result.sfm_qc.ok:
        print(f"  FAILED: {result.sfm_qc.error}")
    else:
        print(f"  score:      {result.sfm_qc.score:.2f}")
        print(f"  route:      {result.sfm_qc.route.upper()}")
        print(f"  registered: {result.sfm_qc.metrics.registered_images}")
        print(f"  points3d:   {result.sfm_qc.metrics.points3d}")
        print(f"  reproj err: {result.sfm_qc.metrics.reprojection_error:.3f}px")
        print(f"  pct reg:    {result.sfm_qc.metrics.pct_registered:.1%}")

    # Leanerd Priors (ORANGE):
    if result.priors is not None:
        print("\n=== Learned Priors ===")
        if not result.priors.ok:
            print(f"  FAILED: {result.priors.error}")
        else:
            print(f"  frames processed: {len(result.priors.frames)}")
            print(f"  depth dir:        {result.priors.depth_dir}")
            print(f"  normals dir:      {result.priors.normals_dir}")
            print(f"  segmentation dir: {result.priors.segmentation_dir}")
    else:
        print("\n=== Learned Priors ===")
        print("  skipped (Blue route)")   


    # Shape Completion
    if result.shape_completion is not None:
        print("\n=== Shape Completion ===")
        if not result.shape_completion.ok:
            print(f"  FAILED: {result.shape_completion.error}")
        else:
            print(f"  frames integrated: {result.shape_completion.num_frames_integrated}")
            print(f"  mesh:              {result.shape_completion.mesh_path}")
            print(f"  tsdf:              {result.shape_completion.tsdf_path}")
    else:
        print("\n=== Shape Completion ===")
        print("  skipped (Blue route)") 
    
    # Voxelization
    if result.voxelization is not None:
        print("\n=== Voxelization ===")
        if not result.voxelization.ok:
            print(f"  FAILED: {result.voxelization.error}")
        else:
            print(f"  occupied voxels: {result.voxelization.num_occupied_voxels}")
            print(f"  grid shape:      {result.voxelization.grid_shape}")
            print(f"  voxel grid:      {result.voxelization.voxel_path}")
    else:
        print("\n=== Voxelization ===")
        print("  skipped (Blue route)") 

    # Brickification
    if result.brickification is not None:
        print("\n=== Brickification ===")
        if not result.brickification.ok:
            print(f"  FAILED: {result.brickification.error}")
        else:
            print(f"  total bricks:    {result.brickification.num_bricks}")
            print(f"  unique BOM:      {result.brickification.num_bom_entries}")
            print(f"  bricks layout:   {result.brickification.bricks_path}")
            print(f"  BOM:             {result.brickification.bom_path}")
    else:
        print("\n=== Brickification ===")
        print("  skipped (Blue route)")


    # Instructions
    if result.instructions is not None:
        print("\n=== Instructions ===")
        if not result.instructions.ok:
            print(f"  FAILED: {result.instructions.error}")
        else:
            print(f"  build steps: {result.instructions.num_steps}")
            print(f"  total bricks: {result.instructions.num_bricks}")
            print(f"  GLB:          {result.instructions.glb_path}")
            print(f"  steps JSON:   {result.instructions.steps_path}")
    else:
        print("\n=== Instructions ===")
        print("  skipped")

    # --- Overall ---
    print(f"\n{'OK' if result.ok else 'FAILED'}")
    if result.error:
        print(f"  {result.error}")


if __name__ == "__main__":
    main()
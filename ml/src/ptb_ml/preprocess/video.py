from __future__ import annotations

import subprocess
from pathlib import Path

from .io import JobWorkSpace
from .settings import PreprocessSettings


def extract_frames_ffmpeg(
        ws: JobWorkSpace,
        video_path: Path,
        *,
        settings: PreprocessSettings,
        start_idx:int = 0,
) -> int:
    """
    Extract frames from video into ws.frame_dir as frame_######.jpg using ffmpeg
    """

    out_pattern = str(ws.frames_dir / "frame_%06d.jpg")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error", "-i",
        str(video_path),
        "-vf", f"fps={settings.fps}",
        "-q:v", "2", "-start_number",
        str(start_idx),
        out_pattern
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed. \n"
                           f"cmd: {' '.join(cmd)}\n"
                           f"stdderr: \n{proc.stderr}")
    
    
    # Count how many frames were written to calculate next index
    frames= sorted(ws.frames_dir.glob("frame_??????.jpg"))
    if not frames:
        return start_idx
    #next idx is last frame index + 1
    last = frames[-1].stem
    num = int(last.split("_")[1])
    return num + 1

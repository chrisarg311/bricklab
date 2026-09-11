import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from ptb_ml.preprocess.engine import PreprocessReq, run_preprocess
from ptb_ml.preprocess.settings import PreprocessSettings


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _make_test_image(path: Path, size=(320, 240), color=(30, 120, 200)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")


def _make_test_video_ffmpeg(path: Path, seconds: float = 1.0, fps: int = 10, size="320x240") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size={size}:rate={fps}",
        "-t",
        str(seconds),
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg video generation failed:\n{proc.stderr}")


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not available on PATH")
def test_preprocess_smoke(tmp_path: Path):
    # Arrange synthetic inputs
    img = tmp_path / "in" / "house.png"
    vid = tmp_path / "in" / "walk.mp4"
    _make_test_image(img)
    _make_test_video_ffmpeg(vid)

    # Run preprocess
    req = PreprocessReq(
        base_dir=tmp_path / "jobs",
        job_id="smoke1",
        input_paths=[img, vid],
        clean=True,
        settings=PreprocessSettings(fps=2.0),
    )
    res = run_preprocess(req)

    # Assert outputs exist
    assert res.manifest_path.exists()
    frames_dir = res.job_root / "frames"
    assert frames_dir.exists()

    frames = sorted(frames_dir.glob("frame_*.jpg"))
    assert len(frames) >= 2  # 1 from image + >=1 from video (at fps=2 for ~1s)

    # Assert manifest looks sane
    manifest = json.loads(res.manifest_path.read_text())
    assert manifest["job_id"] == "smoke1"
    assert isinstance(manifest["frames"], list)
    assert len(manifest["frames"]) >= 0

    # paths should be relative (no leading slash)
    for fr in manifest["frames"]:
        assert not fr["path"].startswith("/")
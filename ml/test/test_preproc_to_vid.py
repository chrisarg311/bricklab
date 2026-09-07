import subprocess
from pathlib import Path

import pytest
from PIL import Image

from ptb_ml.preprocess.io import JobWorkSpace
from ptb_ml.preprocess import ingest
from ptb_ml.preprocess.video import extract_frames_ffmpeg
from ptb_ml.preprocess.settings import PreprocessSettings


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _make_test_image(path: Path, size=(320, 240), color=(255, 0, 0)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color)
    img.save(path, format="PNG")


def _make_test_video_ffmpeg(path: Path, seconds: float = 1.0, fps: int = 10, size="320x240") -> None:
    """
    Generates a synthetic MP4 using ffmpeg's test pattern.
    No external assets needed.
    """
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


def test_workspace_creates_tree(tmp_path: Path):
    ws = JobWorkSpace.create(tmp_path / "jobs", "test123")

    assert ws.root.exists()
    assert ws.inputs_dir.exists()
    assert ws.frames_dir.exists()
    assert ws.metadata_dirname.exists()
    assert ws.logs_dir.exists()
    assert ws.tmp_dir.exists()
    assert ws.masks_dir.exists()


def test_stage_split_and_normalize_images(tmp_path: Path):
    # Arrange: make two input images
    inputs_dir = tmp_path / "inputs"
    img1 = inputs_dir / "a.png"
    img2 = inputs_dir / "b.png"
    _make_test_image(img1, color=(255, 0, 0))
    _make_test_image(img2, color=(0, 255, 0))

    ws = JobWorkSpace.create(tmp_path / "jobs", "job_images")

    # Act: stage, split, normalize to frames
    staged = ingest.stage_raw_inputs(ws, [img1, img2])
    imgs, vids = ingest.split_inputs(staged)
    assert len(imgs) == 2
    assert len(vids) == 0

    written, next_idx = ingest.normalize_images_to_frames(ws, imgs, start_idx=0)

    # Assert: frames exist and are JPGs named frame_000001.jpg, frame_000002.jpg
    assert next_idx == 2
    assert len(written) == 2
    for i, p in enumerate(written, start=0):
        assert p.exists()
        assert p.name == f"frame_{i:06d}.jpg"

        # ensure readable
        with Image.open(p) as im:
            assert im.mode == "RGB"
            assert im.size[0] > 0 and im.size[1] > 0


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not available on PATH")
def test_extract_frames_from_video_continues_numbering(tmp_path: Path):
    # Arrange: create one image and one synthetic video
    inputs_dir = tmp_path / "inputs"
    img1 = inputs_dir / "img.png"
    vid1 = inputs_dir / "vid.mp4"
    _make_test_image(img1, color=(10, 20, 30))
    _make_test_video_ffmpeg(vid1, seconds=1.0, fps=10, size="320x240")

    ws = JobWorkSpace.create(tmp_path / "jobs", "job_video")

    staged = ingest.stage_raw_inputs(ws, [img1, vid1])
    imgs, vids = ingest.split_inputs(staged)
    assert len(imgs) == 1
    assert len(vids) == 1

    # Normalize image -> frame_000000.jpg
    _, next_idx = ingest.normalize_images_to_frames(ws, imgs, start_idx=0)
    assert next_idx == 1

    # Act: extract video frames at fps=2, starting at 2
    settings = PreprocessSettings(fps=2.0)
    next_after_video = extract_frames_ffmpeg(ws, vids[0], start_idx=next_idx, settings=settings)

    # Assert: we now have >= 2 frames total (1 from image + some from video)
    frames = ws.list_frames()
    assert len(frames) >= 2

    # The first frame should still be the image one
    assert (ws.frames_dir / "frame_000000.jpg").exists()

    # Video frames should start at 000002
    assert (ws.frames_dir / "frame_000001.jpg").exists()

    # next index should be last frame number + 1
    last_num = int(frames[-1].stem.split("_")[1])
    assert next_after_video == last_num + 1
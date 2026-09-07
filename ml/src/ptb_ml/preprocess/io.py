# io.py defines the workspace layout and file paths that every later step will rely on
from __future__ import annotations

import re
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


_JOB_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")

def sanatize_job_id(job_id: str) -> str:
    if not job_id:
        raise ValueError("job_id cannot be empty")
    safe = _JOB_ID_RE.sub("_", job_id)
    #Prevent '.' and or '..' cases
    if safe in (".", ".."):
        raise ValueError(f"job_id cannot be {safe}")
    return safe


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def mask_path(*, image_path: Path, image_root: Path, mask_root: Path) -> Path:
        """mask for a given frame file name"""
        image_path = Path(image_path)
        image_root = Path(image_root)
        mask_root = Path(mask_root)

        rel = image_path.relative_to(image_root)
        return mask_root / rel.parent / f"{rel.name}.png"

def _atomic_write_bytes(dst:Path, data:bytes) -> None:
    """Atomic Write to dst by writing to a tmp file in the same direcroty then replace"""
    ensure_dir(dst.parent)
    fd, tmp_path = tempfile.mkstemp(prefix=dst.name + ".", suffix=".tmp", dir=str(dst.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        Path(tmp_path).replace(dst)
    except:
        # Clean up the tmp file on any failure
        try:
            os.close(fd)
        except OSError:
            pass # already closed
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise



def atomic_write_text(dst:Path, text:str, encoding:str="utf-8") -> None:
    _atomic_write_bytes(dst, text.encode(encoding))

def atomic_write_json(dst:Path, obj:Any, *, indent:int=2) -> None:
    payload = json.dumps(obj, indent=indent, ensure_ascii=False, sort_keys=False) +"\n"
    atomic_write_text(dst, payload)


@dataclass(frozen=True)
class WorkSpace:
    """Standardized DIR layout for preproc outputs """
    frames_dirname:str = "frames"
    masks_dirname:str = "masks"
    metadata_filename:str = "metadata"
    logs_dirname:str = "logs"
    tmp_dirname:str = "tmp"
    inputs_dirname:str = "inputs"

    manifest_filename:str = "manifest.json"
    quality_report_filename:str = "quality_report.json"

    sfm_dirname="sfm"


@dataclass
class JobWorkSpace:
    """Represents a preprocessing job worksapce on a disk
    job_root/
        inputs/
        frames/
        masks/
        metadata/
            manifest.json
            queality_report.json
        logs/
        tmp/
    """

    job_id:str
    root:Path
    layout:WorkSpace = WorkSpace()
    
    def __post_init__(self) -> None:
        self.job_id = sanatize_job_id(self.job_id)
        self.root = self.root.resolve()

    @classmethod
    def create(cls, base_dir:Path | str, job_id:str, *, layout:WorkSpace=WorkSpace(), clean:bool=False) -> "JobWorkSpace":
        base = Path(base_dir).resolve()
        ws = cls(job_id=job_id, root=base / sanatize_job_id(job_id), layout=layout)
        if clean and ws.root.exists():
            shutil.rmtree(ws.root)
        ws.ensure()
        return ws
    
    def ensure(self) -> None:
        """Ensure the workspace directories exist on disk"""
        ensure_dir(self.frames_dir)
        ensure_dir(self.masks_dir)
        ensure_dir(self.metadata_dir)
        ensure_dir(self.logs_dir)
        ensure_dir(self.tmp_dir)
        ensure_dir(self.inputs_dir)
        ensure_dir(self.sfm_dir)
        ensure_dir(self.root)
    
    # ----- Properties  ----- #
    @property
    def sfm_dir(self) -> Path:
        return self.root / self.layout.sfm_dirname

    @property
    def sfm_database_path(self) -> Path:
        return self.sfm_dir / "database.db"

    @property
    def sfm_sparse_dir(self) -> Path:
        return self.sfm_dir / "sparse"

    @property
    def sfm_logs_dir(self) -> Path:
        return self.sfm_dir / "logs"

    @property
    def inputs_dir(self) -> Path:
        return self.root / self.layout.inputs_dirname
    
    @property
    def frames_dir(self) -> Path:
        return self.root / self.layout.frames_dirname
    
    @property
    def masks_dir(self) -> Path:
        return self.root / self.layout.masks_dirname
    
    @property
    def metadata_dir(self) -> Path:
        return self.root / self.layout.metadata_filename
    
    @property
    def logs_dir(self) -> Path:
        return self.root / self.layout.logs_dirname
    
    @property
    def tmp_dir(self) -> Path:
        return self.root / self.layout.tmp_dirname
    
    @property
    def manifest_path(self) -> Path:
        return self.metadata_dir / self.layout.manifest_filename
    
    @property
    def quality_report_path(self) -> Path:
        return self.metadata_dir / self.layout.quality_report_filename  
    
    # ----- Utility Methods ----- #
    def frame_path(self, index:int, ext:str=".jpg") -> Path:
       if index < 0:
              raise ValueError("index must be 0 or greater")
       if not ext.startswith("."):
              ext = "." + ext
       return self.frames_dir / f"frame_{index:06d}{ext}"
    

    def write_manifest(self, manifest:dict) -> None:
        atomic_write_json(self.manifest_path, manifest)

    def write_quality_report(self, report:dict) -> None:
        atomic_write_json(self.quality_report_path, report)

    def write_log(self, name:str, text:str) -> Path:
        safe = _JOB_ID_RE.sub("_", name.strip()) or "log"
        log_path = self.logs_dir / f"{safe}.log"
        atomic_write_text(log_path, text)
        return log_path
    
    def stage_inputs(self, input_paths: Iterable[Path | str], *, copy:bool=True) -> list[Path]:
        """Stage raw uploads inot  inputs/ . IF copy=False, moves instead"""
        staged: list[Path] = []
        for p in input_paths:
            src = Path(p).resolve()
            if not src.exists():
                raise FileNotFoundError(f"Input file {src} does not exist")
            dst = self.inputs_dir / src.name
            if dst.exists():
                raise FileExistsError(f"Staged file {dst} already exists")
            if copy:
                shutil.copy2(src, dst)
            else:
                shutil.move(str(src), str(dst))
            staged.append(dst)
        return staged
    

    def list_frames(self) -> list[Path]:
        """List all frame files in frames/ sorted by name"""
        if not self.frames_dir.exists():
            return []
        return sorted(self.frames_dir.glob("frame_??????.*"))
    
    def wipe_tmp(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        ensure_dir(self.tmp_dir)
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

SourceType = Literal["video", "image_set"]

class CamIntrinsics(BaseModel):
    fx:float
    fy:float
    cx:float
    cy:float

class FrameRecord(BaseModel):
    id:str
    path:str
    width:int
    height:int
    timestamp_ms:Optional[int]=None

    sharpness:Optional[float]=None
    exposure:Optional[float]=None

    intrinsics:Optional[CamIntrinsics]=None
    intrinsics_conf:Optional[float]=None

    mask_path:Optional[str]=None


class DroppedRec(BaseModel):
    path:str
    reason:str

class Manifest(BaseModel):
    job_id:str
    source_type:SourceType
    frames:list[FrameRecord]= Field(default_factory=list)
    dropped_frames:list[DroppedRec] = Field(default_factory=list)
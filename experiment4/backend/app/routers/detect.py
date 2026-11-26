from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from ..deps import require_key
from ..errors import ok
from ..schemas import ApiResponse
from ..service import detect_bytes

router = APIRouter(tags=["图像检测"])


@router.post("/detect", response_model=ApiResponse, summary="多目标垃圾检测",
             description="multipart/form-data 上传一张 JPG/PNG（≤10 MB）。返回每个目标的类别、置信度、"
                         "640 标准化坐标框 box、原图坐标框 box_original 与投放建议。")
def detect(file: UploadFile = File(..., description="JPG/PNG 图片"),
           conf: float = Form(0.25, description="置信度阈值 0.01-0.95"),
           backend: str | None = Form(None, description="tensorrt_fp16 / onnx_fp32 / pytorch_fp32"),
           region: str = Form("general", description="general / shanghai"),
           _=Depends(require_key)):
    data = file.file.read()
    result = detect_bytes(data, file.filename, file.content_type, conf, backend, region)
    return ok(result, result["backend_note"] or "ok")

"""图片解码与标准化：与实验一 process() 中的 640×640 等比缩放 + 灰边填充一致。

实验一对训练、验证、测试图片统一做了：方向校正、剥离 EXIF、转 RGB、LANCZOS 等比缩放、
居中贴到 (114,114,114) 灰底的 640×640 画布。推理输入按同样方式处理，保证分布一致；
检测框先在 640 坐标系输出，再映射回原图坐标并用实验一的 clean_box 裁剪到图像边界。
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import ALLOWED_SUFFIXES, IMG_SIZE
from .errors import InputError, PayloadTooLarge
from .reuse import clean_box

Image.MAX_IMAGE_PIXELS = 60_000_000  # 防止超大图片耗尽内存
# Ultralytics 会给 Image.open 打补丁（解析失败时尝试安装 HEIF 插件），这里保留原始实现
_pil_open = getattr(Image, "_ecosort_original_open", Image.open)
Image._ecosort_original_open = _pil_open


@dataclass
class Letterbox:
    width: int
    height: int
    scale: float
    pad_x: int
    pad_y: int
    size: int = IMG_SIZE

    def to_original(self, x1, y1, x2, y2):
        """640 坐标 → 原图坐标，并复用实验一 clean_box 裁剪越界部分。"""
        ox, oy = (x1 - self.pad_x) / self.scale, (y1 - self.pad_y) / self.scale
        ow, oh = (x2 - x1) / self.scale, (y2 - y1) / self.scale
        box = clean_box([ox, oy, ow, oh], self.width, self.height)
        if box is None:
            return None
        x, y, w, h = box
        return {"x1": round(x, 1), "y1": round(y, 1), "x2": round(x + w, 1), "y2": round(y + h, 1)}

    def as_dict(self):
        return {"width": self.width, "height": self.height, "standardized": self.size,
                "scale": round(self.scale, 6), "pad": [self.pad_x, self.pad_y]}


def check_upload(filename: str | None, content_type: str | None, data: bytes, max_mb: float) -> None:
    suffix = Path(filename or "").suffix.lower()
    if not data:
        raise InputError("上传的文件为空，请重新选择图片")
    if suffix not in ALLOWED_SUFFIXES and content_type not in ("image/jpeg", "image/png"):
        raise InputError("图像格式错误，请上传 PNG/JPG")
    if len(data) > max_mb * 1024 * 1024:
        raise PayloadTooLarge(f"图片大小 {len(data)/1048576:.1f} MB，超过 {max_mb:g} MB 上限；"
                              f"高分辨率图片请到“批量任务”提交")


def decode_image(data: bytes) -> Image.Image:
    try:
        with _pil_open(io.BytesIO(data)) as im:
            if im.format not in ("JPEG", "PNG", "MPO"):
                raise InputError("图像格式错误，请上传 PNG/JPG")
            im = ImageOps.exif_transpose(im)  # 方向校正（实验一已对数据集做过同样处理）
            return im.convert("RGB")           # 转 RGB 时 EXIF/GPS 不再保留
    except InputError:
        raise
    except Image.DecompressionBombError:
        raise InputError("图片像素过多（超过 6000 万像素），请缩小后再上传")
    except (UnidentifiedImageError, OSError, ValueError, ImportError, SyntaxError):
        raise InputError("无法解析图片内容，文件可能已损坏，请上传 PNG/JPG")


def standardize(image: Image.Image, size: int = IMG_SIZE) -> tuple[np.ndarray, Letterbox]:
    """等比缩放 + 居中灰边，返回 BGR uint8 数组（Ultralytics 约定）和映射参数。"""
    old_w, old_h = image.size
    scale = min(size / old_w, size / old_h)
    new_w, new_h = round(old_w * scale), round(old_h * scale)
    px, py = (size - new_w) // 2, (size - new_h) // 2
    canvas = image if image.size == (new_w, new_h) else image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    if canvas.size != (size, size):
        board = Image.new("RGB", (size, size), (114, 114, 114))
        board.paste(canvas, (px, py))
        canvas = board
    rgb = np.asarray(canvas, dtype=np.uint8)
    return np.ascontiguousarray(rgb[:, :, ::-1]), Letterbox(old_w, old_h, scale, px, py, size)


def load_path(path: Path) -> tuple[np.ndarray, Letterbox]:
    return standardize(decode_image(Path(path).read_bytes()))

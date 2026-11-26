"""EcoSort 单张或文件夹图片预测。相对路径均以本脚本所在目录为基准。

python predict.py --source ../data/split/images/test --limit 12
python predict.py --source "D:/my_images/example.jpg"
"""
from __future__ import annotations

import argparse
import platform
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
import torch
import ultralytics
from ultralytics import YOLO
from ultralytics.cfg import DEFAULT_CFG_DICT

from src.experiment_registry import read_json, register_record, sha256, write_csv, write_json
from src.metrics import ECOSORT_NAMES, detections_from_result, normalize_names


SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
DETECTION_FIELDS = [
    'image_index', 'source_image', 'class_id', 'class_name', 'class_name_zh',
    'confidence', 'x1', 'y1', 'x2', 'y2', 'original_width', 'original_height',
]


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return (SCRIPT_DIR / path).resolve() if not path.is_absolute() else path.resolve()


def collect_images(source: Path, recursive: bool = False, limit: int = 0) -> list[Path]:
    if limit < 0:
        raise ValueError('--limit 必须大于或等于 0，0 表示全部图片')
    if source.is_file():
        if source.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f'不支持的图片格式：{source.suffix}')
        images = [source]
    elif source.is_dir():
        candidates = source.rglob('*') if recursive else source.iterdir()
        images = sorted(
            (path for path in candidates if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES),
            key=lambda path: (path.as_posix().casefold(), path.as_posix()),
        )
    else:
        raise FileNotFoundError(f'图片或目录不存在：{source}')
    if not images:
        raise ValueError(f'没有找到支持的图片：{source}')
    return images[:limit] if limit else images


def read_image(path: Path):
    """Decode locally, including Unicode paths; reject bad files without plugin installs."""
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None
    if image is None:
        raise ValueError(f'无法解码图片，请确认文件完整且格式受 OpenCV 支持：{path}')
    return image


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description='EcoSort 图片检测与结果导出（不训练、不计算 AP）')
    parser.add_argument('--run', default='outputs/baseline/yolo11n_baseline_amp', help='训练结果目录')
    parser.add_argument('--weights', choices=('best', 'last'), default='best')
    parser.add_argument('--source', required=True, help='单张图片或图片文件夹，支持含空格/中文的路径')
    parser.add_argument('--recursive', action='store_true', help='递归读取子文件夹')
    parser.add_argument('--limit', type=int, default=0, help='按路径排序后取前 N 张；0 表示全部')
    parser.add_argument('--output', default='outputs/predictions', help='输出根目录，每次创建独立子目录')
    parser.add_argument('--device', default='0', help='单张 CUDA GPU 编号或 cpu')
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--conf', type=float, default=0.25, help='展示置信度阈值，默认 0.25')
    parser.add_argument('--iou', type=float, default=0.7, help='NMS IoU 阈值')
    parser.add_argument('--max-det', type=int, default=300)
    args = parser.parse_args(argv)

    if not 0 < args.conf <= 1 or not 0 < args.iou <= 1:
        parser.error('--conf 和 --iou 必须在 (0, 1] 范围内')
    if args.imgsz <= 0 or args.max_det <= 0 or args.limit < 0:
        parser.error('--imgsz/--max-det 必须大于 0，--limit 必须大于或等于 0')
    run_dir = resolve_path(args.run)
    checkpoint = run_dir / 'weights' / f'{args.weights}.pt'
    if not checkpoint.is_file():
        raise FileNotFoundError(f'找不到模型权重：{checkpoint}')
    source = resolve_path(args.source)
    images = collect_images(source, args.recursive, args.limit)
    if args.device != 'cpu':
        if not args.device.isdigit():
            parser.error('--device 仅支持单张 GPU 编号，例如 0，或 cpu')
        if not torch.cuda.is_available() or int(args.device) >= torch.cuda.device_count():
            raise RuntimeError(f'CUDA GPU {args.device} 不可用；请检查环境，或显式使用 --device cpu')

    model = YOLO(str(checkpoint))
    if model.task != 'detect':
        raise ValueError('当前脚本仅支持目标检测模型')
    names = normalize_names(model.names)
    if names != ECOSORT_NAMES:
        raise ValueError('模型类别必须与 EcoSort 的固定十类名称和顺序一致')
    checkpoint_hash = sha256(checkpoint)
    training_summary_path = run_dir / 'train_summary.json'
    training_summary = read_json(training_summary_path) if training_summary_path.is_file() else {}

    now = datetime.now(timezone(timedelta(hours=8)))
    prediction_id = f'predict_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}'
    output_dir = resolve_path(args.output) / f'{run_dir.name}_{prediction_id}'
    output_dir.mkdir(parents=True, exist_ok=False)
    annotated_dir = output_dir / 'annotated'
    annotated_dir.mkdir()
    json_dir = output_dir / 'json'
    json_dir.mkdir()
    predict_args = {
        'imgsz': args.imgsz, 'conf': args.conf, 'iou': args.iou, 'max_det': args.max_det,
        'device': args.device, 'batch': 1, 'rect': True, 'augment': False,
        'classes': None, 'agnostic_nms': False, 'single_cls': False,
        'save': False, 'save_txt': False, 'save_crop': False, 'show': False, 'verbose': False,
        'project': str(output_dir.parent), 'name': output_dir.name, 'exist_ok': True,
    }
    if 'quantize' in DEFAULT_CFG_DICT:
        predict_args['quantize'] = 32
    else:
        predict_args['half'] = False
    summary = {
        'prediction_id': prediction_id, 'record_type': 'prediction', 'created_at': now.isoformat(),
        'status': 'running', 'run_dir': str(run_dir), 'checkpoint': str(checkpoint),
        'checkpoint_sha256': checkpoint_hash, 'source': str(source), 'output_dir': str(output_dir),
        'prediction_precision': 'FP32', 'prediction_config': predict_args,
        'recursive': args.recursive, 'limit': args.limit, 'input_image_count': len(images),
        'training_method': training_summary.get('method'),
        'environment': {
            'python': sys.version, 'platform': platform.platform(), 'torch': str(torch.__version__),
            'cuda': torch.version.cuda, 'ultralytics': ultralytics.__version__, 'device': args.device,
        },
        'notes': [
            '坐标为原图像素 xyxy；类别 ID 从 0 开始。',
            '未读取真值标注，不计算 Precision/Recall/AP，也不自动判断误检或漏检。',
            'conf=0.25 是本次展示阈值，不是经过验证集优化的部署阈值；评估脚本使用 conf=0.001。',
            '总耗时含预测初始化、读图、输入哈希、绘图和导出，不能作为纯模型推理速度。',
        ],
    }
    summary_path = output_dir / 'prediction_summary.json'
    write_json(summary_path, summary)
    print(f'模型：{checkpoint}\n图片数：{len(images)}\n输出目录：{output_dir}')

    image_rows, detection_rows = [], []
    started = time.perf_counter()
    for index, image_path in enumerate(images, 1):
        # Numbered filenames avoid collisions across folders or image extensions.
        stem = f'{index:06d}'
        image_json = json_dir / f'{stem}.json'
        image_record = {
            'image_index': index, 'source_image': str(image_path), 'status': 'failed',
            'source_sha256': None, 'original_width': None, 'original_height': None,
            'detection_count': 0, 'annotated_image': None, 'error': None,
        }
        detections = []
        try:
            image_record['source_sha256'] = sha256(image_path)
            # OpenCV returns BGR, the array format expected by Ultralytics.
            # One image per call avoids loading an entire folder into RAM at once.
            image = read_image(image_path)
            result = model.predict(source=image, **predict_args)[0]
            detections = detections_from_result(result, names)
            height, width = (int(value) for value in result.orig_shape)
            annotated_path = annotated_dir / f'{stem}.jpg'
            result.save(filename=str(annotated_path), conf=True, labels=True, line_width=2)
            if not annotated_path.is_file() or not annotated_path.stat().st_size:
                raise OSError(f'预测图保存失败：{annotated_path}')
            image_record.update(
                status='completed', original_width=width, original_height=height,
                detection_count=len(detections), annotated_image=str(annotated_path),
            )
            for detection in detections:
                x1, y1, x2, y2 = detection['xyxy']
                detection_rows.append({
                    'image_index': index, 'source_image': str(image_path),
                    **{key: detection[key] for key in ('class_id', 'class_name', 'class_name_zh', 'confidence')},
                    'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                    'original_width': width, 'original_height': height,
                })
            print(f'[{index}/{len(images)}] {image_path.name}：{len(detections)} 个检测目标')
        except Exception as error:
            image_record['error'] = f'{type(error).__name__}: {error}'
            detections = []
            print(f'[{index}/{len(images)}] 失败 {image_path.name}：{image_record["error"]}')
        write_json(image_json, {**image_record, 'detections': detections})
        image_rows.append({**image_record, 'prediction_json': str(image_json)})

    successes = sum(row['status'] == 'completed' for row in image_rows)
    failed = len(images) - successes
    summary.update({
        'status': 'completed' if failed == 0 else ('completed_with_errors' if successes else 'failed'),
        'duration_seconds': time.perf_counter() - started,
        'successful_image_count': successes, 'failed_image_count': failed,
        'images_without_detections': sum(row['status'] == 'completed' and row['detection_count'] == 0 for row in image_rows),
        'detection_count': len(detection_rows), 'images': image_rows,
    })
    write_json(summary_path, summary)
    write_csv(output_dir / 'images.csv', image_rows)
    write_csv(output_dir / 'detections.csv', detection_rows, fieldnames=DETECTION_FIELDS)
    flat = {key: summary[key] for key in (
        'prediction_id', 'record_type', 'created_at', 'status', 'run_dir', 'checkpoint',
        'checkpoint_sha256', 'source', 'input_image_count', 'successful_image_count',
        'failed_image_count', 'images_without_detections', 'detection_count', 'duration_seconds',
    )}
    flat.update(conf=args.conf, iou=args.iou, imgsz=args.imgsz, device=args.device,
                prediction_precision='FP32', prediction_summary=str(summary_path))
    register_record(SCRIPT_DIR / 'outputs' / 'registry', f'{run_dir.name}_{prediction_id}', summary, flat)
    print(f'\n预测完成：成功 {successes} 张，失败 {failed} 张\n摘要：{summary_path}\n检测图：{annotated_dir}')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

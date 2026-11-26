"""Experiment 3.1.4: isolated YOLO11n TensorRT FP16 acceleration experiment."""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Ultralytics settings, font download and all caches stay in experiment3.
for _directory in ('.ultralytics', '.matplotlib', '.torch'):
    (ROOT / _directory).mkdir(exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(ROOT / '.ultralytics')
os.environ['MPLCONFIGDIR'] = str(ROOT / '.matplotlib')
os.environ['TORCH_HOME'] = str(ROOT / '.torch')
os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['PYTHONIOENCODING'] = 'utf-8'

import cv2
import numpy as np
import torch
import yaml
from ultralytics import YOLO, settings
from ultralytics.cfg import DEFAULT_CFG_DICT
from ultralytics.nn.autobackend import AutoBackend

from prepare_inputs import sha256, write_json
from src.metrics import ECOSORT_NAMES, collect_per_class, normalize_names

settings.update({'datasets_dir': str(ROOT / 'data'), 'weights_dir': str(ROOT / 'models'),
                 'runs_dir': str(ROOT / 'outputs'), 'sync': False})
MODELS = {'pytorch_fp32': ROOT / 'models/baseline.pt',
          'tensorrt_fp16': ROOT / 'models/baseline.engine'}
SEED = 20261026


def precision_args(half):
    return {'quantize': 16 if half else 32} if 'quantize' in DEFAULT_CFG_DICT else {'half': half}


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def environment():
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA PyTorch is required; CPU fallback would not meet this experiment protocol.')
    torch.cuda.set_device(0)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    packages = {}
    for name in ('torch', 'torchvision', 'ultralytics', 'onnx', 'onnxslim', 'tensorrt-cu12',
                 'tensorrt-cu12-bindings', 'tensorrt-cu12-libs', 'numpy', 'opencv-python'):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
            'gpu': torch.cuda.get_device_name(0), 'gpu_memory_bytes': torch.cuda.get_device_properties(0).total_memory,
            'cuda': torch.version.cuda, 'cudnn': torch.backends.cudnn.version(), 'packages': packages,
            'pytorch_tf32': False, 'seed': SEED,
            'nvidia_smi': subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,driver_version',
                                                  '--format=csv,noheader'], text=True).strip()}


def initialize():
    for name in ('outputs', 'records', 'reports', 'configs'):
        (ROOT / name).mkdir(exist_ok=True)
    env = environment()
    write_json(ROOT / 'records/environment.json', env)
    config = yaml.safe_load((ROOT / 'records/source_data.yaml').read_text(encoding='utf-8'))
    config.update({'path': (ROOT / 'data').as_posix(), 'train': 'images/val',
                   'val': 'images/val', 'test': 'images/test'})
    # No training/calibration is performed. train is an unused schema placeholder.
    (ROOT / 'configs/data.yaml').write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
    protocol = {
        'task': '3.1.4 inference acceleration, no optional stage 3.2',
        'source_model': 'experiment2 A best checkpoint; unchanged architecture and weights',
        'source_checkpoint_sha256': sha256(MODELS['pytorch_fp32']),
        'optimization': 'TensorRT FP16 layer/tactic optimization; no INT8, pruning or retraining',
        'imgsz': 640, 'batch_sizes': [1, 32], 'device': 0,
        'timing_warmup_iterations': 30, 'timing_rounds': 3,
        'timing_iterations': {'model_b1': 100, 'model_b32': 40, 'pipeline_b1': 50, 'pipeline_b32': 20},
        'timing_order': 'alternate baseline/optimized between rounds',
        'model_timing_scope': 'wall clock with CUDA synchronize, preallocated GPU tensor -> raw network output; excludes H2D and NMS',
        'pipeline_timing_scope': 'decoded CPU BGR images -> preprocessing/H2D -> network -> NMS -> Results; CUDA synchronize; excludes file IO/drawing/saving',
        'accuracy': {'imgsz': 640, 'batch': 32, 'rect': False, 'conf': 0.001, 'iou': 0.7,
                     'max_det': 300, 'augment': False, 'workers': 0, 'split_order': ['val', 'test']},
        'selection': 'FP16 backend fixed before test evaluation; no test-driven tuning',
        'accuracy_target_interpretation': 'absolute mAP50-95 loss <= 1 percentage point; also report relative loss',
        'targets': {'latency_reduction_percent': 40, 'throughput_increase_percent': 50, 'map_loss_percentage_points': 1},
        'notes': ['Detection mAP replaces classification Top-1; no claims of pruning FLOPs/parameter reduction.',
                  'CPU and GPU cross-platform deployment is outside this experiment.',
                  'Historical experiment2 speed from another GPU is not used as timing baseline.'],
    }
    path = ROOT / 'configs/protocol.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != protocol:
            raise RuntimeError('Existing frozen protocol differs; use a new experiment directory.')
    else:
        write_json(path, protocol)
    print(json.dumps(env, ensure_ascii=True), flush=True)
    from ultralytics.utils.torch_utils import get_flops
    model = YOLO(str(MODELS['pytorch_fp32']))
    write_json(ROOT / 'records/model_structure.json', {
        'parameters': sum(p.numel() for p in model.model.parameters()),
        'gflops_at_640': get_flops(model.model, imgsz=640),
        'checkpoint_bytes': MODELS['pytorch_fp32'].stat().st_size,
        'optimization_changes_architecture': False,
        'note': 'FP16/TensorRT changes execution precision and graph scheduling, not logical network parameter count or algorithmic FLOPs.'})


def export():
    import tensorrt as trt
    import onnx
    checkpoint = MODELS['pytorch_fp32']
    if MODELS['tensorrt_fp16'].exists():
        raise FileExistsError('Engine already exists; preserve existing results.')
    model = YOLO(str(checkpoint))
    if normalize_names(model.names) != ECOSORT_NAMES:
        raise ValueError('Checkpoint class mapping mismatch')
    start = time.perf_counter()
    result = model.export(format='engine', imgsz=640, batch=32, dynamic=True,
                          device=0, workspace=4, simplify=False, nms=False,
                          **precision_args(True))
    torch.cuda.synchronize()
    onnx_path = ROOT / 'models/baseline.onnx'
    graph = onnx.load(str(onnx_path))
    onnx.checker.check_model(graph)
    write_json(ROOT / 'records/export.json', {
        'status': 'completed', 'duration_seconds': time.perf_counter() - start,
        'checkpoint_sha256': sha256(checkpoint), 'engine': str(result),
        'engine_sha256': sha256(MODELS['tensorrt_fp16']), 'engine_bytes': MODELS['tensorrt_fp16'].stat().st_size,
        'onnx_sha256': sha256(onnx_path), 'tensorrt_version': trt.__version__,
        'requested_precision': 'FP16 enabled, TensorRT may retain selected layers in FP32/TF32 with default tactics',
        'tensorrt_tf32_builder_flag': 'default enabled; no strict per-layer precision constraints',
        'batch_profile_max': 32, 'workspace_gib': 4, 'nms_embedded': False,
        'onnx_inputs': [v.name for v in graph.graph.input],
        'onnx_outputs': [v.name for v in graph.graph.output],
    })


def load_backend(name):
    backend = AutoBackend(model=str(MODELS[name]), device=torch.device('cuda:0'),
                          fp16=name == 'tensorrt_fp16', fuse=True, verbose=True)
    backend.eval()
    if normalize_names(backend.names) != ECOSORT_NAMES:
        raise ValueError('Backend class mapping mismatch')
    return backend


def tensor_output(value):
    if isinstance(value, (list, tuple)):
        return tensor_output(value[0])
    return value


@torch.inference_mode()
def smoke():
    images = sorted((ROOT / 'data/images/val').glob('*.png'))[:4]
    arrays = [cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR) for p in images]
    x = torch.from_numpy(np.stack(arrays)[..., ::-1].transpose(0, 3, 1, 2).copy()).cuda().float() / 255
    outputs = {}
    for name in MODELS:
        backend = load_backend(name)
        outputs[name] = tensor_output(backend(x.half() if backend.fp16 else x)).float().cpu()
        del backend
        torch.cuda.empty_cache()
    a, b = outputs.values()
    if a.shape != b.shape or not torch.isfinite(b).all():
        raise RuntimeError('Invalid engine output')
    write_json(ROOT / 'records/smoke.json', {'passed': True, 'images': [p.name for p in images],
               'output_shape': list(a.shape), 'max_abs_difference': (a-b).abs().max().item(),
               'mean_abs_difference': (a-b).abs().mean().item(),
               'note': 'Raw tensors contain pixel boxes and class scores in different units; full mAP evaluation establishes accuracy.'})
    # Real end-to-end image prediction outputs, inside experiment3 only.
    for name, path in MODELS.items():
        model = YOLO(str(path), task='detect')
        results = model.predict(source=arrays, imgsz=640, device=0, rect=False, conf=0.25,
                                iou=0.7, max_det=300, verbose=False, **precision_args(name != 'pytorch_fp32'))
        directory = ROOT / 'outputs/smoke_predictions' / name
        directory.mkdir(parents=True, exist_ok=True)
        records = []
        for p, result in zip(images, results):
            result.save(filename=str(directory / f'{p.stem}.jpg'))
            records.append({'source': p.name, 'detections': json.loads(result.to_json())})
        write_json(directory / 'predictions.json', records)
        del model
        torch.cuda.empty_cache()
    print('Smoke test completed', flush=True)


def evaluate(split):
    for name, path in MODELS.items():
        out = ROOT / 'outputs/evaluation' / split / name
        if (out / 'summary.json').exists():
            raise FileExistsError(out / 'summary.json')
        model = YOLO(str(path), task='detect')
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        metrics = model.val(data=str(ROOT / 'configs/data.yaml'), split=split, imgsz=640,
                            batch=32, rect=False, device=0, workers=0, conf=0.001, iou=0.7,
                            max_det=300, augment=False, plots=True, save_json=False,
                            project=str(out.parent), name=out.name, exist_ok=True,
                            verbose=False, **precision_args(name != 'pytorch_fp32'))
        torch.cuda.synchronize()
        p, r, ap50, ap = map(float, metrics.box.mean_results())
        classes = collect_per_class(metrics, ECOSORT_NAMES)
        np.save(out / 'confusion_matrix.npy', metrics.confusion_matrix.matrix)
        write_json(out / 'summary.json', {'status': 'completed', 'split': split, 'backend': name,
                   'model_sha256': sha256(path), 'annotation_sha256': sha256(ROOT / f'data/{split}.json'),
                   'precision': p, 'recall': r, 'map50': ap50, 'map50_95': ap,
                   'duration_seconds': time.perf_counter() - start,
                   'framework_speed_ms_per_image': metrics.speed,
                   'pytorch_peak_allocated_mib': torch.cuda.max_memory_allocated() / 1024**2,
                   'memory_note': 'PyTorch allocator excludes TensorRT external allocations; not a fair total GPU memory comparison.',
                   'per_class': classes})
        write_csv(out / 'per_class.csv', classes)
        del model, metrics
        torch.cuda.empty_cache()
        print(f'{split} {name}: mAP50-95={ap:.6f}', flush=True)


def timed(call, count, warmup=30):
    for _ in range(warmup):
        call()
    torch.cuda.synchronize()
    samples = []
    for _ in range(count):
        torch.cuda.synchronize()
        start = time.perf_counter_ns()
        call()
        torch.cuda.synchronize()
        samples.append((time.perf_counter_ns() - start) / 1e6)
    return samples


@torch.inference_mode()
def benchmark():
    out = ROOT / 'outputs/benchmark'
    if (out / 'summary.json').exists():
        raise FileExistsError(out / 'summary.json')
    paths = sorted((ROOT / 'data/images/val').glob('*.png'))
    # Fixed evenly spread validation samples; never select timings from the test set.
    chosen = [paths[i] for i in np.linspace(0, len(paths)-1, 32, dtype=int)]
    images = [cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR) for p in chosen]
    write_json(out / 'inputs.json', [{'name': p.name, 'sha256': sha256(p)} for p in chosen])
    raw = []
    for scope in ('model', 'pipeline'):
        for batch in (1, 32):
            for round_index in range(3):
                names = list(MODELS) if round_index % 2 == 0 else list(reversed(MODELS))
                for name in names:
                    if scope == 'model':
                        backend = load_backend(name)
                        x = torch.from_numpy(np.stack(images[:batch])[..., ::-1].transpose(0,3,1,2).copy()).cuda()
                        x = x.to(dtype=torch.float16 if backend.fp16 else torch.float32) / 255
                        call = lambda: backend(x)
                    else:
                        backend = YOLO(str(MODELS[name]), task='detect')
                        kwargs = dict(imgsz=640, batch=batch, device=0, rect=False, conf=0.25,
                                      iou=0.7, max_det=300, verbose=False, save=False,
                                      **precision_args(name != 'pytorch_fp32'))
                        call = lambda: backend.predict(source=images[:batch], **kwargs)
                    count = (100 if batch == 1 else 40) if scope == 'model' else (50 if batch == 1 else 20)
                    samples = timed(call, count)
                    raw.extend({'scope': scope, 'batch': batch, 'round': round_index+1,
                                'backend': name, 'iteration': i+1, 'latency_ms': value}
                               for i, value in enumerate(samples))
                    write_csv(out / 'iterations.csv', raw)
                    print(f'{scope} B{batch} round {round_index+1} {name}: {statistics.mean(samples):.3f} ms', flush=True)
                    del call, backend
                    if scope == 'model':
                        del x
                    torch.cuda.empty_cache()
    rows = []
    for scope in ('model', 'pipeline'):
        for batch in (1, 32):
            for name in MODELS:
                values = [r['latency_ms'] for r in raw if (r['scope'],r['batch'],r['backend']) == (scope,batch,name)]
                mean = statistics.mean(values)
                rows.append({'scope': scope, 'batch': batch, 'backend': name, 'iterations': len(values),
                             'mean_ms_per_batch': mean, 'median_ms_per_batch': float(np.median(values)),
                             'p95_ms_per_batch': float(np.percentile(values,95)), 'std_ms': statistics.stdev(values),
                             'mean_ms_per_image': mean/batch, 'throughput_images_per_second': batch*1000/mean})
    comparisons = []
    for scope in ('model', 'pipeline'):
        for batch in (1,32):
            a,b = [r for r in rows if r['scope']==scope and r['batch']==batch]
            ratio = a['mean_ms_per_batch'] / b['mean_ms_per_batch']
            reduction = (1-1/ratio)*100
            gain = (ratio-1)*100
            comparisons.append({'scope':scope,'batch':batch,'speedup':ratio,
                                'latency_reduction_percent':reduction,'throughput_increase_percent':gain,
                                'latency_target_pass':reduction>=40,'throughput_target_pass':gain>=50})
    write_csv(out/'summary.csv', rows)
    write_json(out/'summary.json', {'status':'completed','measurements':rows,'comparisons':comparisons,
                                  'protocol_sha256':sha256(ROOT/'configs/protocol.json')})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['initialize','export','smoke','val','test','benchmark'])
    args=parser.parse_args()
    environment()
    {'initialize':initialize,'export':export,'smoke':smoke,'val':lambda:evaluate('val'),
     'test':lambda:evaluate('test'),'benchmark':benchmark}[args.command]()


if __name__ == '__main__':
    main()

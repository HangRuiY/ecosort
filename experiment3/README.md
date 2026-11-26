# 实验三 YOLO11n 推理加速


## 输入与隔离

- `models/baseline.pt` 是实验二 A 组 `best.pt` 的独立副本。
- `data/images/{val,test}` 和 `data/labels/{val,test}` 是公共数据的独立副本，不使用硬链接。扫描缓存只会写入本目录。
- `src/metrics.py` 从实验二复制后使用；其他实验三逻辑在本目录内编写。
- `records/input_manifest.json` 保存全部输入的 SHA256。
- `records/original_files_before.json`、`original_files_verification.json` 用于验证实验一、二全部文件内容未改变。
- `configs/protocol.json` 在正式评估前冻结比较方法与目标。

## 运行

在项目根目录 PowerShell 中使用本目录独立解释器：

```powershell
& ./experiment3/.venv/Scripts/python.exe -u experiment3/run_experiment.py initialize
& ./experiment3/.venv/Scripts/python.exe -u experiment3/run_experiment.py export
& ./experiment3/.venv/Scripts/python.exe -u experiment3/run_experiment.py smoke
& ./experiment3/.venv/Scripts/python.exe -u experiment3/run_experiment.py val
& ./experiment3/.venv/Scripts/python.exe -u experiment3/run_experiment.py test
& ./experiment3/.venv/Scripts/python.exe -u experiment3/run_experiment.py benchmark
& ./experiment3/.venv/Scripts/python.exe experiment3/prepare_inputs.py --verify-originals
```

检测新图片或文件夹：

```powershell
& ./experiment3/.venv/Scripts/python.exe experiment3/predict.py --source "C:/your_images/example.jpg"
& ./experiment3/.venv/Scripts/python.exe experiment3/predict.py --source data/images/val --limit 4 --batch 32
```

新电脑使用 Python 3.12 运行 `setup_environment.ps1`，或在 PyCharm 中将解释器指向本目录 `.venv/Scripts/python.exe`。重建图表先运行 `build_figures.py` 和 `expand_report_assets.py`，再运行 `build_report.py` 生成 Word 和 Markdown；相应依赖已收录在锁定文件中。

这些命令用于复现，不必对已完成的结果再次运行。导出、正式评估和测速在已有结果存在时拒绝覆盖，复现实验请复制本目录脚本到一个新的实验目录，并重新准备输入。`.venv` 不可跨电脑直接搬运；根据 `requirements-lock.txt` 重建。TensorRT 引擎与构建 GPU/CUDA/TensorRT 版本有关，新电脑应从 `.pt` 或 ONNX 重新构建。

首次准备输入才运行 `prepare_inputs.py`，会复制约两千张验证/测试图像，不能在已准备的目录重复运行。仅做 FP16 加速，无需复制训练集；数据 YAML 的 train 是框架格式所需的未使用字段，本实验不训练也不校准。

## 测量口径

- 同机、同一 checkpoint、固定 640×640，batch 为 1 和 32。
- 模型测速：输入已在 GPU；包含同步的 Python 调用到网络原始输出，不含上传、预处理和 NMS。
- 流程测速：输入为已解码的 CPU 图片，包含预处理、上传、推理、NMS 及结果封装，不含磁盘读写、绘图和保存。
- 每轮预热 30 次，重复 3 轮，轮间交替模型顺序；原始每次耗时保存在 `outputs/benchmark/iterations.csv`。
- 两种测速口径均报告，不能用模型推理耗时代替流程耗时，也不能使用实验二另一张 GPU 的速度作为基线。
- 完整验证与测试使用相同阈值（conf=0.001、NMS IoU=0.7、max_det=300），以 mAP50-95 作为主要检测精度指标。精度差异目标按绝对百分点解释，并同时提供相对变化。
- FP16/TensorRT 不改变逻辑网络参数量和算法 FLOPs；TensorRT 引擎文件大小不能直接解释为权重压缩率。

## 输出

- `records/`：环境、输入校验、导出、冒烟测试和原文件保护记录。
- `models/`：模型副本、ONNX 和 TensorRT 引擎。
- `outputs/evaluation/`：验证集、测试集的指标、逐类 CSV、混淆矩阵及框架图表。
- `outputs/benchmark/`：测速输入、逐次耗时、汇总与达标判断。
- `outputs/smoke_predictions/`：两种后端真实图片预测。
- `reports/`：实验三报告、配图与数据表。
- `logs/`：每一步实际运行日志。


## 本次实际结果

| 指标 | PyTorch FP32 | TensorRT FP16 | 变化 |
| --- | ---: | ---: | ---: |
| 单图模型推理延迟 | 18.587 ms | 2.485 ms | 降低86.63% |
| Batch 32模型推理延迟 | 41.292 ms/批 | 12.614 ms/批 | 降低69.45% |
| 单图流程延迟 | 24.074 ms | 8.406 ms | 降低65.08% |
| Batch 32流程延迟 | 176.871 ms/批 | 175.202 ms/批 | 降低0.94%，未达40%目标 |
| 测试集mAP50-95 | 17.5281% | 17.5155% | 损失0.0126个百分点 |



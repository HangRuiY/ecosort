# 实验二 模型设计与训练

本目录基于实验一的数据集开展循智 EcoSort 多目标垃圾检测实验，完成 YOLO11n 全量微调、卷积 LoRA 与检测头微调，以及统一验证集、测试集评估。

交接记录更新于 **2026-10-20**。A/B 微调策略对照、C/D 实验一增强对照的正式训练、FP32 验证集及最终测试集评估均已完成。已依据验证集确定 A 为主模型，无需重复训练或评估。结果表、逐类分析、资源口径和数据—模型关联表见 [报告素材汇总](reports/experiment2_results.md)。


## 2026-10-20 空间清理与恢复

**后来人员请先看：C/D 的生成图片和 YOLO 标签已经清理，目前不能直接运行 C/D 训练命令。先重新生成数据，再训练；原始数据和已有正式实验结果均保留。**

正式四组模型的全部权重、训练摘要、逐类评估、registry、预测结果和报告均保留。公共 `data/raw` 与 `data/split`、源代码、配置和原始 `yolo11n.pt` 也保留。清理了 C/D 可再生成的图片与 YOLO 标签、冒烟测试/失败运行产物、Python 与 YOLO 数据扫描缓存，以及当前配置未使用的 `weights/yolo26n.pt`。小型调试记录与本次清理清单位于 `reports/cleanup_records/20261020/`。

C/D 的 `preparation_summary.json`、`manifest.csv`、预览、数据 YAML、COCO 标注及逐组摘要已归档至 `datasets/augmentation_control_records/`，代表历史数据生成记录，不能直接作为完整训练数据使用。A/B 的训练、评估与预测仍读取公共数据，不需要恢复 C/D 数据。

### 第一步：恢复 C/D 数据

在已安装项目依赖的环境中，打开 PyCharm 终端，执行：

```powershell
cd D:\Pycharm\ecosort\experiment2
python prepare_augmentation.py --output datasets/augmentation_control --seed 20261003
```

其他电脑请将第一行改为本机项目的 `experiment2` 路径。该准备命令会一次恢复 C/D 两组数据，并写回两个配置原先指向的位置，**不需要修改配置，也不会重新随机划分训练、验证和测试集**。保持种子 `20261003`，沿用现有公共数据和生成规则。

恢复会重新占用清理时释放的大部分空间。脚本要求输出目录不存在或为空；如果数据已经完整恢复，就不要重复执行，也不要先手动创建非空的 `datasets/augmentation_control` 目录。若准备中途失败，先检查保留的部分生成目录，不要直接重复运行。

### 第二步：生成完成后再训练

确认上一步正常完成后，在同一个 `experiment2` 目录按需执行：

```powershell
# C 组：原图重复对照，关闭在线增强
python train_baseline.py --config configs/no_augmentation.yaml

# D 组：原图加实验一离线增强，关闭在线增强
python train_baseline.py --config configs/experiment1_augmentation.yaml
```

重新评估 C/D 也应先恢复数据。缓存由框架按需重建。**如果只是查看已有指标、阅读报告，或者使用已训练模型预测新图片，不需要恢复 C/D 数据，也不需要重新训练。** 现有四组指标及报告无需重新计算。

## 1 当前进度

| 工作 | 状态 | 说明 |
| --- | --- | --- |
| YOLO11n 全量微调 + AMP | 已完成 | 训练 60 轮，完成 FP32 验证与测试集评估 |
| neck 卷积 LoRA + 检测头微调 + AMP | 已完成 | 计划 60 轮，实际 55 轮早停，完成权重合并及 FP32 验证、测试集评估 |
| 训练和评估配置记录 | 已完成基础版本 | 运行参数、环境、指标、部分资源统计已保存 |
| 实验一未增强与增强数据对照 | 已完成 | C/D 均完整训练 30 轮，完成 FP32 验证与测试集评估 |
| 训练资源与实验关联记录完善 | 已完成现有测量汇总 | C/D 记录逐轮资源；评估读取 LoRA 记录，旧 A 缺失测量保留 null |
| 测试集最终评估 | 已完成 | 四组在 2026-10-18 完成；不再据此反复调参 |
| 报告结果素材 | 数值及案例已汇总 | 见 reports/experiment2_results.md、reports/prediction_cases.md；学校模板正文已生成完整初稿 |
| 报告配图导出 | 已完成，10 张逐图验收通过 | 修正混淆矩阵横轴截断；原始评估数据不变 |
| 参考文献与技术依据 | 已完成核对 | 9 项核心引用及代码、记录对应关系见 reports/references.md |
| 实验二 Word 报告 | 完整初稿已编写并检查 20 页排版 | 沿用实验一六位成员，补充分工，日期留空；见 reports/实验二报告_循智EcoSort.docx |
| 独立图片预测脚本 | 已完成真实 GPU 运行 | 主模型预测 12 张，成功 12 张、输出 14 框；已核对真值案例 |

## 2 任务与数据

本项目是目标检测任务：一张图片中可能同时包含多个垃圾目标，模型对每个目标输出边界框、类别和置信度。不能将每张图片直接当作单一类别样本训练。

公共数据位于项目根目录的 `data/split/`，实验二直接读取，不复制或重新随机划分。

| 子集 | 图片数 | 目标数 | 用途 |
| --- | ---: | ---: | --- |
| train | 8,422 | 73,235 | 训练 |
| val | 1,053 | 14,725 | 调参、模型选择和现阶段对照 |
| test | 1,053 | 12,536 | 方案确定后的最终评估 |
| 合计 | 10,528 | 100,496 | 不包含增强副本 |

图片为清洗后的 640×640 RGB PNG。这里的“未增强数据”指实验一清洗和标准化后的真实图像，不是来源网站的原始分辨率文件。

YOLO 类别从 0 开始，顺序不能修改：

| ID | 标签 | 中文含义 |
| --- | --- | --- |
| 0 | plastic_rigid | 硬质塑料 |
| 1 | plastic_flexible | 软质塑料 |
| 2 | plastic_unspecified | 形态不明塑料 |
| 3 | paper_cardboard | 纸及纸板 |
| 4 | composite_packaging | 复合包装 |
| 5 | metal | 金属 |
| 6 | glass | 玻璃 |
| 7 | food_waste | 食物残余 |
| 8 | cigarette | 烟蒂 |
| 9 | special_unknown | 特殊及不明垃圾 |

这些是视觉材质及特殊类别，不是当地四类垃圾投放结论。数据来源、许可限制、分组划分和细分类信息见项目根目录的 `data/README.md`。

## 3 目录及文件状态

```text
experiment2/
├─ README.md
├─ requirements-experiment2.txt
├─ yolo11n.pt                         原始预训练权重
├─ train_baseline.py                  已实现：全量微调
├─ train_lora.py                      已实现：LoRA + 检测头微调
├─ evaluate.py                        已实现：统一评估及记录导出
├─ predict.py                         已实现：独立图片检测、标框及结果导出
├─ export_report_figures.py           已实现：从既有记录导出报告配图（CPU）
├─ prepare_augmentation.py            已实现：生成等样本预算的两组增强对照数据
├─ reports/
│  ├─ experiment2_results.md         已汇总：四组结果、资源及数据—模型关联表
│  ├─ prediction_cases.md            已核对：12 张预测图的成功、漏检、类别错误
│  ├─ prediction_case_review.json    案例框、匹配索引及标签哈希
│  ├─ references.md                 已核对：参考文献、技术依据与结论范围
│  ├─ 实验二报告_循智EcoSort.docx    已编写：学校模板完整报告，成员沿用实验一，日期留空
│  └─ figures/                      运行配图脚本后生成，每次独立目录
├─ configs/
│  ├─ baseline.yaml                  已实现
│  ├─ lora_amp.yaml                  已实现
│  ├─ no_augmentation.yaml           已实现：原图重复组，30轮，关闭在线增强
│  └─ experiment1_augmentation.yaml  已实现：实验一离线增强组，30轮，关闭在线增强
├─ src/
│  ├─ __init__.py                    空文件，用于标记 Python 包
│  ├─ lora_layers.py                 已实现：低秩卷积、注入和合并
│  ├─ model_factory.py               已实现：自定义训练器及导出
│  ├─ train_utils.py                 已实现：全量训练参数、显存、耗时及 AMP 更新记录
│  ├─ metrics.py                     已实现：类别映射、逐类指标、预测框序列化
│  └─ experiment_registry.py         已实现：JSON/CSV、元数据、关联记录
├─ datasets/
│  └─ augmentation_control_records/  C/D 数据生成记录与标注；生成图片、标签已清理
├─ weights/                          预留目录，当前原始权重在本目录根部
└─ outputs/
   ├─ baseline/                      全量微调结果
   ├─ lora_amp/                      LoRA 结果
   ├─ augmentation_control/          已完成：C/D 训练及验证、测试结果
   ├─ predictions/                   独立图片预测输出，每次使用唯一目录
   └─ registry/                      evaluate.py 生成的 JSON/CSV 记录
```

全量训练资源统计位于 `src/train_utils.py`，LoRA 沿用其现有训练监控逻辑。`evaluate.py` 与 `predict.py` 复用 `src/metrics.py` 和 `src/experiment_registry.py`；原有评估的指标计算及关联 CSV 字段保持一致。`src/__init__.py` 保持空文件是正常的 Python 包结构，无需补写业务代码。

## 4 环境与路径约定

已成功运行的环境：Windows 11、Python 3.13.9、PyTorch 2.11.0+cu128、CUDA 12.8、Ultralytics 8.4.175，GPU 为 NVIDIA GeForce RTX 5060 Laptop GPU，约 8 GB 显存。

LoRA 训练器使用了 Ultralytics 的内部训练接口。接手时优先沿用 **Ultralytics 8.4.175**；当前 requirements 中的 `ultralytics>=8.3.0` 只是宽范围依赖声明，并不是精确的复现环境锁定文件。不要为运行本项目随意升级框架或覆盖已经可用的 CUDA 版 PyTorch。

以下命令统一在 `experiment2` 目录执行。当前电脑示例：

```powershell
conda activate mypy
cd D:\Pycharm\ecosort\experiment2
```

其他电脑替换环境名和项目根路径即可。

- 训练配置中的 `data`、`run.project` 按配置文件所在目录解析。
- `train_baseline.py` 的命令行 `--config` 相对终端工作目录解析。
- `train_lora.py` 的命令行 `--config`，以及 `evaluate.py` 的 `--run`、`--data`，相对脚本所在目录解析。
- 新全量训练摘要另存相对 `experiment2` 的数据 YAML 路径，`evaluate.py` 默认沿用它；旧 A/B 记录默认使用公共 `data/split/data.yaml`，也可显式传入 `--data`。
- 训练输出里的绝对路径是运行记录。项目迁移后重新运行评估时，应传入当前机器的实际目录，不要照抄历史记录中的旧路径。

公共 `data/split/data.yaml` 当前不写 `path`，保留以下相对路径及原类别映射：

```yaml
train: images/train
val: images/val
test: images/test
```

训练脚本将数据 YAML 的绝对文件路径交给框架；评估脚本在评估结果目录生成带本机根路径的 `dataset_resolved.yaml`，不修改源数据配置。实验一旧版 `--config` 或重建逻辑可能重新写入绝对 `path`，使用后需要检查。

## 5 已有正式结果

接手时以这四个正式目录为准：

```text
outputs/baseline/yolo11n_baseline_amp/
outputs/lora_amp/yolo11n_lora_amp-2/
outputs/augmentation_control/yolo11n_no_augmentation_amp-2/
outputs/augmentation_control/yolo11n_experiment1_augmentation_amp/
```

早先失败的 `outputs/lora_amp/yolo11n_lora_amp/` 及 `_smoke` 调试目录已清理。小型调试记录归档于 `reports/cleanup_records/20261020/`；正式四组训练结果均保留。

配置 `exist_ok: false` 时，输出目录重名会自动增加后缀，例如 `-2`。每次以终端打印的实际目录为准，并确认存在 `weights/best.pt` 与 `train_summary.json`。

两组已完成统一 FP32 验证集评估：

| 指标 | 全量微调 + AMP | LoRA + 检测头微调 + AMP |
| --- | ---: | ---: |
| Precision | 30.64% | 41.40% |
| Recall | 28.33% | 23.65% |
| mAP50 | 22.04% | 20.70% |
| mAP50-95 | 16.07% | 14.95% |
| 实际训练轮数 | 60 | 55 |
| 最佳轮次，按训练 CSV 的 mAP50-95 | 43 | 35 |
| 训练调用总耗时 | 52.66 分钟 | 39.44 分钟 |

精度取自下列独立评估记录，不混用训练结束时的混合精度验证值：

```text
outputs/baseline/yolo11n_baseline_amp/evaluation/
  val_best_20261013_155237_1ca1c6/evaluation_summary.json

outputs/lora_amp/yolo11n_lora_amp-2/evaluation/
  val_best_20261018_112948_1f3b39/evaluation_summary.json
```

当前结论与解释边界：

- LoRA 在本次单次对照中降低了可训练参数量和总耗时，但 mAP50-95 比基线低约 1.12 个百分点。
- LoRA 的 55 轮结束与 `patience=20`、最佳轮次 35 相符。总耗时减少约 25.10%，包含了少训练 5 轮的影响，不能直接当作每步训练加速比例。
- LoRA 可训练参数为 478,862，占含适配器模型总参数 2,638,046 的 18.15%。其中低秩适配器 30,976 个参数，检测头 447,886 个参数。这不是全部层只训练 LoRA 的方案，也不是模型压缩实验。
- LoRA 训练批次阶段峰值已分配显存为 1308.62 MiB；基线没有同口径的训练显存记录，不能计算显存节省百分比。
- Precision 是类别平均值。烟蒂类别出现 `P=1、R=0`，会抬高平均值，不能理解为该类识别成功；总体比较应结合 mAP、Recall 和逐类指标。
- 食物残余在验证集中只有 1 个目标，无法据此得到可靠的类别泛化结论。
- 两组都启用了 AMP，也都使用 YOLO 在线增强。它们比较的是整套微调策略，不能单独证明 AMP 的收益或数据增强的收益。

### 5.1 四组最终测试结果

| 组别 | Precision | Recall | mAP50 | mAP50-95 |
| --- | ---: | ---: | ---: | ---: |
| A | 33.17% | 31.18% | 24.28% | 17.46% |
| B | 37.01% | 26.40% | 22.43% | 16.26% |
| C | 31.82% | 25.74% | 17.86% | 12.44% |
| D | 31.77% | 26.90% | 20.40% | 14.16% |

A：全量微调 + 在线增强；B：LoRA + 检测头微调 + 在线增强；C：无图像变换的重复原图；D：原图 + 实验一离线增强。A 已在测试前依据验证集确定为主模型。

C/D 均为 30 轮、8,635 次成功更新；D 的验证集 mAP50-95 比 C 高 0.61 个百分点，测试集高 1.71 个百分点。不同类别收益不一致。完整记录定位及逐类表见 [报告素材](reports/experiment2_results.md)。

## 6 训练与评估流程

已有正式结果可直接评估，无需再次训练。下列训练命令用于在新环境复现，重新运行会生成新的结果目录。

### 6.1 全量微调

首次在新环境运行时，可先做冒烟测试：

```powershell
python train_baseline.py --config configs/baseline.yaml --smoke-test
```

该测试使用约 2% 训练图片、1 轮训练，只检查运行链路。正式训练：

```powershell
python train_baseline.py --config configs/baseline.yaml
```

正式配置为 YOLO11n 预训练权重、640 输入、batch 16、最多 60 轮、AdamW、初始学习率 0.001、余弦学习率、3 轮预热、种子 20261003、AMP、patience 20。

### 6.2 LoRA 与检测头微调

首次运行可先测试：

```powershell
python train_lora.py --config configs/lora_amp.yaml --smoke-test
```

当前 LoRA 冒烟测试使用约 2% 训练图片、3 轮、`nbs=16`；这些只是调试设置。正式训练不带 `--smoke-test`：

```powershell
python train_lora.py --config configs/lora_amp.yaml
```

正式训练使用与基线相同的主要超参数，默认 `nbs=64`，batch 为 16 时通常累积 4 个 batch，预热期间累积量由框架调整。

实现策略：

1. 从原始 `yolo11n.pt` 开始，不从已经训练好的基线 `best.pt` 开始。
2. 冻结 backbone，在 neck 的 11 个符合条件的普通 1×1 卷积中加入 LoRA；`rank=8`、`alpha=16`。
3. 训练适配器和检测头，DFL 固定权重除外；冻结 backbone 和 neck 的 BatchNorm 参数及运行统计。
4. 在创建优化器时重新应用冻结策略，并核对优化器参数，避免框架初始化流程重新启用原始参数。
5. 低秩矩阵乘法使用 FP32，卷积仍受外部 AMP 控制。日志记录 AMP 跳过更新次数及 B 矩阵是否改变。
6. 完成后校验合并前后输出，并导出普通 YOLO 权重。

正式训练记录显示 7,619 次优化器更新尝试，7,611 次未被 AMP 跳过，8 次跳过；适配器已更新，11 个适配层的合并检查通过。

当前自定义 LoRA 入口只支持单张 CUDA GPU、AdamW、`compile=False`，不支持断点续训。

### 6.3 统一验证集评估

使用已有正式模型：

```powershell
python evaluate.py --run outputs/baseline/yolo11n_baseline_amp
python evaluate.py --run outputs/lora_amp/yolo11n_lora_amp-2
```

默认读取 `weights/best.pt`，使用验证集、FP32、imgsz 640、batch 16、conf 0.001、NMS IoU 0.7、max_det 300，不启用测试时增强。每次评估生成独立的时间编号目录。

`conf=0.001` 用于保留预测并计算 PR/AP，不等同于展示图片时的推荐置信度；总体 P/R 使用框架选择的工作点。NMS IoU 0.7 不等于 mAP 的匹配阈值。

当前评估脚本要求数据 YAML 所在目录包含 `images/<split>`、`labels/<split>`，且 YAML 中相应字段为 `images/val` 或 `images/test`。新数据准备脚本也生成这种标准目录结构，评估默认读取新训练摘要的数据相对路径，也可以通过 `--data` 显式指定对应 YAML；不支持任意清单或跨目录验证路径。

### 6.4 测试集评估

四组最终测试已于 2026-10-18 完成。以下仅为复现命令，无需再次执行：

```powershell
python evaluate.py --run outputs/baseline/yolo11n_baseline_amp --split test
python evaluate.py --run outputs/lora_amp/yolo11n_lora_amp-2 --split test
python evaluate.py --run outputs/augmentation_control/yolo11n_no_augmentation_amp-2 --split test
python evaluate.py --run outputs/augmentation_control/yolo11n_experiment1_augmentation_amp --split test
```

不要使用测试集反复调参。主划分仍共享工业视频来源，不能把结果直接解释为跨视频或真实校园新场景的独立泛化效果。

### 6.5 独立图片预测（真实 GPU 运行已完成）

训练和最终评估已经完成。用户于 2026-10-20 成功运行主模型图片预测，确认真实权重到可视化图片的链路正常。默认使用依据验证集确定的主模型 A 的 `best.pt`、CUDA GPU 0、FP32。该脚本不训练、不计算 AP，也不自动判断误检/漏检。

以下命令已生成 12 张展示图，保留作复现示例，当前无需重跑：

```powershell
python predict.py --source ../data/split/images/test --limit 12
```

自己的单张图片、文件夹和其他模型也支持：

```powershell
python predict.py --source "D:/my_images/example.jpg"
python predict.py --source "D:/my_images" --recursive --limit 30
python predict.py --run outputs/lora_amp/yolo11n_lora_amp-2 --source ../data/split/images/test --limit 12
```

路径均相对于 `predict.py` 所在目录；含空格的路径加引号。`--limit 0` 表示全部图片，未启用 `--recursive` 时只读取文件夹第一层。图片按路径排序后取前 N 张，不是随机抽样，不能据此推断整个数据集的效果。

支持 JPG/JPEG、PNG、BMP、TIF/TIFF、WebP（实际须能被 OpenCV 解码）。脚本逐张在本地解码并传入模型，损坏图片单独记入失败记录；不覆盖输入图片。同名图片按输入顺序编号输出，避免相互覆盖。CUDA 不可用时会报错；只有显式传入 `--device cpu` 才改用 CPU。

默认 `--conf 0.25 --iou 0.7 --imgsz 640 --max-det 300`。0.25 是展示阈值，尚未优化为部署阈值；与评估时用于 PR/AP 的 conf=0.001 用途不同。更改展示阈值不会改写已有评估结果。

每次输出到 `outputs/predictions/<模型目录名>_predict_<时间编号>/`：

| 文件或目录 | 内容 |
| --- | --- |
| `annotated/*.jpg` | 原图大小的检测图，英文类别及置信度；文件名按序编号 |
| `json/*.json` | 每张图的原路径、原尺寸、输入 SHA256、检测框和失败原因 |
| `images.csv` | 每张输入图的状态、检测数及输出位置，零检测图片也保留 |
| `detections.csv` | 每个预测框的类别、中英文名称、置信度及原图像素 xyxy；零框时保留表头 |
| `prediction_summary.json` | 模型哈希、配置、图片数、检测数、失败数及图片索引 |

`outputs/registry/` 同时保存独立的预测 JSON/CSV 登记。存在损坏或不支持图片时，脚本处理其他图片后以退出码 1 结束，摘要状态为 `completed_with_errors` 或 `failed`；全部正常时为 `completed`，即使所有图片都没有检测框也算正常完成。

实际结果目录为 `outputs/predictions/yolo11n_baseline_amp_predict_20261020_092009_55381e/`：输入 12 张、全部成功、14 个预测框、1 张零框、失败 0 张。模型为 A 的 best.pt，FP32，conf=0.25。

已与对应测试集 YOLO 标注核对：在同类一对一匹配 IoU≥0.5 的案例规则下，29 个标注目标对应 TP=6、FP=8、FN=23。这里只统计这 12 张按路径排序的预览图，不替代完整测试集评估，也不是新的 AP 指标。正确检测、漏检、类别混淆及跨类别重复框的具体位置见 [案例分析](reports/prediction_cases.md)。配图已导出并验收，参考文献与技术依据已核对，见第 6.6、6.7 节；报告正文按后续安排编写，不需要重复训练或评估。

### 6.6 报告配图导出（已完成并验收）

四组训练、验证、最终测试及独立预测案例已经完成。报告配图已生成，以下为复现命令，当前无需重复执行：

```powershell
python export_report_figures.py
```

该步骤只用 CPU 读取既有结果、绘图和复制框架原图，不加载模型、不启动训练、不重新推理或计算 AP。已于 2026-10-20 查看全部 10 张图：中文、图例与案例标签可读；混淆矩阵原横轴截断已修复。实际目录为 reports/figures/report_20261020_093501_878347/。

输出到 `reports/figures/report_<时间编号>/`，每次创建独立目录：

| 文件 | 用途 |
| --- | --- |
| `01_validation_test_comparison.png` | 四组验证/测试 mAP50 和 mAP50-95 对比 |
| `02_training_curves.png` | 逐轮验证 mAP 和训练/验证边界框损失 |
| `03_augmentation_per_class.png` | C/D 测试集逐类 AP50-95 对比，附样本数 |
| `04_case_correct_plastic.png` | 硬质塑料瓶正确检测，真实标注与预测并排 |
| `05_case_correct_metal.png` | 植被背景中金属目标正确检测 |
| `06_case_missed_objects.png` | 冰箱多目标漏检案例 |
| `07_case_wrong_class.png` | 金属被预测为软质塑料的案例 |
| `08_case_duplicate_classes.png` | 同一目标跨类别重复框案例 |
| `09_A_test_confusion_matrix_normalized.png` | A 组测试集混淆矩阵，保留色块与数值，修正横轴标签排版 |
| `10_A_test_PR_curve.png` | A 组测试集 PR 曲线，复制框架原图 |
| `figure_manifest.json` | 导出状态、图注、来源哈希与输出哈希 |
| `README.md` | 每张图的建议图注和使用说明 |

新绘制 PNG 为 300 dpi；混淆矩阵重排横轴类别标签以避免截断，保留原图色块和数值；PR 图保留原分辨率。默认使用本机微软雅黑等中文字体；如果脚本报告缺少中文字体，可以运行：

```powershell
python export_report_figures.py --font C:/Windows/Fonts/msyh.ttc
```

只检查输入、不生成图片时使用 `--check-inputs`。`--project` 可指定 experiment2 根目录，`--output` 默认为相对该目录的 reports/figures。

案例图依据已经保存的真实框和预测框重画，绿色表示正确匹配，红色表示未匹配真值，橙色表示未匹配预测。标签 G/P 编号与图下注释对应；采用同类一对一匹配 IoU≥0.5 的预览核对规则，不等于完整测试 AP。脚本核对选定图片及标签的哈希，文件若发生变化会停止，避免图与先前分析不一致。

本次配图已完成上述排版检查，无需再次导出。若后续新增实验，应对新导出的图重新检查字体、图例与标签；无需为导出配图重复运行训练或评估。

### 6.7 参考文献与技术依据（已核对）

已于 2026-10-20 对照原始论文、官方文档及固定版本源码，整理 [参考文献与技术依据](reports/references.md)：包含 TACO、SortWaste、YOLO11、LoRA、混合精度、PyTorch AMP、AdamW、训练器和检测指标共 9 项核心引用，并说明对应代码与实验记录。

YOLO11 引用官方软件和文档；卷积 LoRA 加检测头是本项目的具体适配方案。四组均启用 AMP，未独立验证其加速比例；A/B 总耗时比较包含实际训练轮数不同的影响。论文用于解释原理，本次性能数字以正式 JSON/CSV 为准。此步骤不要求新增训练或评估，正文暂按用户安排后续编写。

## 7 输出文件说明

| 文件 | 用途 |
| --- | --- |
| `args.yaml` | 框架实际使用的训练参数，包括未在自定义配置中写出的默认值 |
| `resolved_config.yaml` | 入口脚本解析后的配置和路径 |
| `results.csv` | 逐轮训练与验证损失、P/R、mAP、学习率及累计时间 |
| `environment.json` | 环境记录 |
| `train_summary.json` | 总耗时、权重路径、配置；LoRA 和更新后的全量入口还包含实际轮数、更新计数、训练显存和参数报告 |
| `parameter_report.json` | 训练时可训练参数和冻结参数；LoRA 另含注入位置 |
| `training_resources.json` | 新全量训练的资源记录及固定预算是否完整执行 |
| `epoch_resources.csv` | 新全量训练逐轮耗时（不含验证）、批次数、显存峰值及累计优化器更新计数 |
| `weights/best.pt` | 最佳模型；LoRA 目录内为合并后的标准 YOLO 模型，可直接评估 |
| `weights/best_lora.pt` | 保留自定义 LoRA 结构的最佳模型；使用时需保留 `src` 模块 |
| `weights/adapter_and_head.pt` | 适配器及检测头状态，不是可独立交给 YOLO 加载的模型 |
| `weights/last.pt` | 最后一轮权重；LoRA 中仍为自定义结构；训练结束后不应假定它可恢复优化器续训 |
| `evaluation/<编号>/evaluation_summary.json` | 精度、逐类指标、评估设置、环境、权重哈希和数据元数据哈希 |
| `evaluation/<编号>/per_class_metrics.csv` | 每类样本数、P/R/F1、AP50、AP50-95 |
| `evaluation/<编号>/dataset_resolved.yaml` | 本次评估生成的数据根路径配置 |
| `outputs/registry/<编号>.json/.csv` | 每次评估的关联记录，独立编号保存 |

框架还会生成训练曲线、PR 曲线、混淆矩阵和部分标注/预测图，以实际目录为准。JSON/CSV 的指标通常为 0 到 1，报告中展示为百分数时乘以 100。

## 8 已知缺口及下一步

### 8.1 实验一增强对照已完成

报告模板要求基于实验一未增强数据与增强数据开展检测效果对照。现有两组输入虽未保存离线增强副本，但实际训练开启了 YOLO 在线增强，例如 Mosaic、颜色扰动、平移、缩放和水平翻转，不能作为“无增强组”。

已约定的补充方案：

| 对照组 | 数据 | 训练设置 |
| --- | --- | --- |
| C 未增强组 | 实验一清洗后的真实训练图，按约定重复采样 | 全量微调 + AMP，关闭在线增强 |
| D 实验一增强组 | 原训练图加按实验一策略生成的增强图 | 与 C 相同，关闭在线增强 |

复用实验一的水平翻转及 0.9–1.1 倍亮度、对比度调整，框和多边形同步变换。只增强训练集，保留父图、分组和来源对应关系。

两组需要控制样本曝光与优化更新预算，不能让增强组只因图片翻倍、更新次数翻倍而获得额外训练量。关闭在线增强须明确设置各增强参数，不能仅依赖 `augment: false`。如果对照采用固定预算，不能让两组早停导致未记录的预算差异。

2026-10-18 曾生成 `datasets/augmentation_control/`，未替换公共 `data/split`。2026-10-20 空间清理已删除生成的图片与 YOLO 标签，其余生成记录、COCO 标注和预览归档于 `datasets/augmentation_control_records/`。仅查看现有结果不必恢复；若要重新训练或重新评估 C/D，先在 experiment2 目录运行下列命令，恢复原数据路径：

```powershell
python prepare_augmentation.py
```

脚本仅使用 CPU 准备数据，不启动训练。完成后输出结构为：

```text
datasets/augmentation_control_records/   # 已归档记录，图片/标签需重新生成
├─ preparation_summary.json
├─ manifest.csv
├─ augmentation_preview.jpg
├─ no_augmentation/
│  ├─ data.yaml
│  ├─ summary.json
│  └─ train.json / val.json / test.json    # images、labels 已清理
└─ experiment1_augmentation/
   └─ 与上一组相同的目录结构
```

准备摘要确认：每组有 16,844 个训练条目、146,470 个训练目标；它们仍只对应 8,422 张不同的原始训练图片，不能把重复或增强条目计作新采集的真实图片。两组验证集均为 1,053 张、测试集均为 1,053 张，图像和标签沿用公共数据。复制测试文件只是准备目录，不是执行测试集评估。

未变化图像优先使用硬链接以节省空间，增强图单独保存。不要原地编辑这些硬链接图片。脚本拒绝覆盖非空输出目录；中途失败会保留 `.build_<编号>` 供检查，不会清理原数据。

已收到 `preparation_summary.json` 及 `augmentation_preview.jpg`：源元数据哈希未变化，验证/测试标注一致，预览中可见的框随图像水平翻转。两个配置都使用 30 轮、`patience=0` 禁用早停、batch 16、nbs 64、同一预训练模型和种子，并明确关闭在线图像增强。每个父图每轮对应两个条目。正式运行记录确认两组均尝试更新 8,643 次、成功 8,635 次、AMP 跳过 8 次，固定预算完成标记均为 True。

正式训练沿用 `train_baseline.py`，已执行的配置命令为（仅供复现）：

```powershell
python train_baseline.py --config configs/no_augmentation.yaml
python train_baseline.py --config configs/experiment1_augmentation.yaml
```

两组现已完整训练 30 轮，无需重新执行。C 实际目录为 `yolo11n_no_augmentation_amp-2`，D 为 `yolo11n_experiment1_augmentation_amp`；最佳验证轮次分别为 7、6，最终评估加载各自 best.pt。

已保留两组实际输出目录中的 `results.csv`、`train_summary.json`、`epoch_resources.csv` 与 `parameter_report.json`。新摘要记录训练数据相对路径及元数据哈希；评估默认沿用对应视图，命令如下（若目录增加后缀，以实际目录为准）：

```powershell
python evaluate.py --run outputs/augmentation_control/yolo11n_no_augmentation_amp-2
python evaluate.py --run outputs/augmentation_control/yolo11n_experiment1_augmentation_amp
```

两组 val/test 图片及标签一致；验证和最终测试均已单独运行。评估器默认仍只评估 val，test 需显式指定 --split test。

### 8.2 资源与关联记录的统计口径

- 新全量训练入口记录训练轮次内的 PyTorch 峰值已分配/保留显存，单位 MiB，不含验证及启动检查；每轮重置峰值，整次训练取各轮最大值。保留显存还可能含框架缓存，不等于活跃张量大小。
- 逐轮时间从训练轮次开始到训练轮次结束，不含随后验证；`duration_seconds` 仍是 `model.train` 调用总时间，含准备与最终验证，二者不能混用。
- 从优化器创建后的实际模型读取可训练参数；沿用框架原始训练步骤，只统计 GradScaler 降低 scale 时的 AMP 跳步，不改变原有更新逻辑。
- C/D 开始及每轮核对 batch、条目数、在线增强和禁用早停设置。完成标记结合实际 CSV 轮数、逐轮批次数及计划轮数判断；本次 C/D 成功更新数一致，均为 8,635；后续复现实验仍需检查计数。
- `evaluate.py` 将训练显存、实际轮数、可训练参数、LoRA 配置、更新计数和数据视图写入关联记录。`training_epochs` 保留原计划轮数字段，另存 `training_completed_epochs`；LoRA 正式结果为 55 轮。
- 旧基线未记录的训练显存无法事后恢复，仍为 null；更新代码不会补造历史测量，也不会改写已有评估文件。旧评估若需要新字段，可以另跑评估生成新记录。
- 评估显存不能替代训练显存；合并后的模型参数量不能替代训练时可训练参数量。数据哈希覆盖 YAML、COCO 标注和摘要，不是全部图片像素的完整指纹。

### 8.3 报告整理

数据—模型关联表应说明数据特点如何决定方案，而不只是罗列路径。例如：多目标框对应目标检测、640×640 标准化对应输入尺寸、10 类映射对应检测头、类别不平衡对应逐类评估、固定分组对应沿用划分、实验一增强策略对应新增 C/D 对照。

训练、验证、模型选择与最终测试已完成；现有数值和结论已整理到 reports/experiment2_results.md。训练曲线、混淆矩阵、预测案例及学校模板报告正文均已整理完成。predict.py 和两个共享模块已实现；用户已完成实际 GPU 预测，并已核对 12 张预览图的真实标注。案例分析见 reports/prediction_cases.md；配图已导出并完成逐图检查。参考文献与技术依据已核对，见 [references.md](reports/references.md)。完整报告已按学校模板编写至 [实验二报告](reports/实验二报告_循智EcoSort.docx)，共 20 页，包含 9 张正文表格、10 张配图和 9 项参考文献；已逐页检查。第 8 组六位成员姓名学号沿用实验一，分工按本次模块补充，封面日期留空。提交前可结合组员实际工作调整分工并填写日期。

增强或 LoRA 是否改善效果以实测为准，不能预设提升结论。目前已有的结果可用于描述本数据划分、本配置、单次运行下的取舍，尚不能证明普遍或统计显著的收益。

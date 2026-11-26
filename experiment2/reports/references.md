# 实验二参考文献与技术依据核对

核对日期：2026-10-20。范围：数据来源、模型选型、LoRA、混合精度、优化器、梯度与过程控制、检测指标；对照现有代码及正式运行记录。本文是报告准备材料，尚未编写报告正文，也未重新训练或评估。

## 1 核对结论

现有方案具有可追溯的技术依据，无需因补充参考文献而改变模型或重新训练。报告需要区分三类证据：论文解释方法原理；官方文档和固定版本源码说明框架行为；项目 JSON/CSV 记录证明本次实际效果。外部论文的加速、显存或精度数字不能替代本项目测量。

数据来源为垃圾检测数据集 TACO 和 SortWaste。任务是十类多目标检测。LoRA 方案为 neck 部分 1×1 卷积的低秩适配加检测头微调；四组训练均启用 AMP。采用 Ultralytics 8.4.175、PyTorch 2.11.0+cu128 的实际记录，不能把在线文档当前默认行为直接视为当时的训练行为。

## 2 已核实的参考文献

以下按资料类型整理为可供报告使用的条目；最终编号应随正文首次引用顺序调整。网络资料访问日期统一为 2026-10-20。会议论文与其 arXiv 预印本是同一工作的不同载体，不必重复计为两篇。

**[1]** PROENÇA P F, SIMÕES P. TACO: Trash Annotations in Context for Litter Detection[EB/OL]. 2020[2026-10-20]. [arXiv:2003.06975](https://arxiv.org/abs/2003.06975).

核实依据：[作者官方仓库及其引用条目](https://github.com/pedropro/TACO)。用于说明野外垃圾图像来源与标注背景。仓库明确区分正式标注与尚未经作者审查的社区标注；项目将后者限制在训练集。不要误引同名的代码生成数据集 TACO。

**[2]** INÁCIO S, PROENÇA H, NEVES J C. SortWaste: A Densely Annotated Dataset for Object Detection in Industrial Waste Sorting[EB/OL]. 2026[2026-10-20]. [arXiv:2601.02299](https://arxiv.org/abs/2601.02299).

核实依据：[数据集官网](https://sortwaste.di.ubi.pt/)、[作者官方仓库](https://github.com/sarainacio/SortWaste)。用于说明工业传送带场景、密集目标和遮挡背景。它与 ZeroWaste 是不同数据集；本项目没有实现论文提出的 ClutterScore，不能把它列为已完成的方法。

**[3]** JOCHER G, QIU J. Ultralytics YOLO11[EB/OL]. 2024[2026-10-20]. [官方模型文档及软件引用](https://docs.ultralytics.com/models/yolo11/).

官方文档说明尚无 Ultralytics 正式发表的 YOLO11 研究论文，并给出上述软件作者和年份。报告引用官方软件与文档即可，不编造 YOLO11 论文、期刊或 DOI。官方示例的 `yolo11n.pt` 为 COCO 预训练检测权重；本项目再按十类数据训练。文档引用中的模型版本 `11.0.0` 与本次安装的软件包版本 `8.4.175` 是不同概念。

**[4]** HU E J, SHEN Y, WALLIS P, et al. LoRA: Low-Rank Adaptation of Large Language Models[C/OL]//International Conference on Learning Representations. 2022[2026-10-20]. [论文全文（arXiv:2106.09685）](https://arxiv.org/abs/2106.09685).

会议年份由[作者官方仓库的引用条目](https://github.com/microsoft/LoRA#citation)核实；预印本首次发布于 2021 年。用于支持冻结原始权重、低秩更新与权重合并的原理。原论文主要研究语言模型；本项目将这一原理用于卷积检测网络，不是复现论文中的 NLP 实验。

**[5]** MICIKEVICIUS P, NARANG S, ALBEN J, et al. Mixed Precision Training[C/OL]//International Conference on Learning Representations. 2018[2026-10-20]. [论文及会议信息（arXiv:1710.03740）](https://arxiv.org/abs/1710.03740).

预印本首次发布于 2017 年，会议版本为 2018 年。用于解释混合精度和损失缩放的背景；本项目实际自动混合精度流程以 PyTorch 和训练器为准，不能声称逐项复现该论文的底层实现。

**[6]** PYTORCH CONTRIBUTORS. Automatic Mixed Precision examples: PyTorch 2.11 documentation[EB/OL]. [2026-10-20]. [PyTorch 2.11 AMP 官方示例](https://docs.pytorch.org/docs/2.11/notes/amp_examples.html).

用于支持 `autocast`、`GradScaler`、先反缩放再裁剪梯度，以及非有限梯度导致跳过优化器更新的实现依据。使用 2.11 版本链接，避免 `stable` 链接随新版本变化。梯度范数裁剪的接口另见 [PyTorch 2.11 clip_grad_norm_](https://docs.pytorch.org/docs/2.11/generated/torch.nn.utils.clip_grad_norm_.html)。

**[7]** LOSHCHILOV I, HUTTER F. Decoupled Weight Decay Regularization[C/OL]//International Conference on Learning Representations. 2019[2026-10-20]. [论文及会议信息（arXiv:1711.05101）](https://arxiv.org/abs/1711.05101).

预印本首次发布于 2017 年，会议版本为 2019 年。用于支持 AdamW 的解耦权重衰减原理。四组均使用 AdamW，没有开展 Adam 与 AdamW 对照，不能声称本实验单独验证了其收益。

**[8]** ULTRALYTICS. Ultralytics v8.4.175: BaseTrainer source code[EB/OL]. [2026-10-20]. [固定版本训练器源码](https://github.com/ultralytics/ultralytics/blob/v8.4.175/ultralytics/engine/trainer.py).

用于核对 AMP、梯度累积、梯度裁剪、学习率调度和训练循环行为。模型结构可追溯至同一版本的 [YOLO11 模型 YAML](https://github.com/ultralytics/ultralytics/blob/v8.4.175/ultralytics/cfg/models/11/yolo11.yaml)。参数说明另见[官方训练文档](https://docs.ultralytics.com/modes/train/)，实际值以每次输出的 `args.yaml` 为准。

**[9]** ULTRALYTICS. Ultralytics v8.4.175: Detection metrics source code[EB/OL]. [2026-10-20]. [固定版本指标源码](https://github.com/ultralytics/ultralytics/blob/v8.4.175/ultralytics/utils/metrics.py).

用于核对 `ap_per_class`、`Metric`、P/R 与 AP 的聚合方式。本报告使用框架检测指标，不把分类准确率、预测框置信度或 12 张案例的匹配率称为 mAP。

## 3 技术依据与项目实现对应

| 技术内容 | 外部依据 | 本项目实际实现及证据 | 报告表述范围 |
| --- | --- | --- | --- |
| 数据与任务 | [1][2] | [数据说明](../../data/README.md)、公共 `data/split` 标注；清洗后 10,528 张真实图片、100,496 个目标，统一为十类 | 本项目融合整理的数据集，不是任一来源的原始官方基准划分 |
| 模型选型与迁移学习 | [3][8] | [baseline.yaml](../configs/baseline.yaml)、[train_baseline.py](../train_baseline.py)；以 `yolo11n.pt` 初始化，输入 640、batch 16 | 在单张约 8 GB CUDA GPU 上选择轻量检测模型；没有多个模型家族的选型竞赛，不声称 YOLO11n 全局最优 |
| 卷积低秩适配 | [4] | [lora_layers.py](../src/lora_layers.py) 的 `LoRAConv2d`；[lora_amp.yaml](../configs/lora_amp.yaml)；rank=8、alpha=16 | 对普通 groups=1 的 1×1 卷积使用低秩权重增量，不是对全部网络层添加 LoRA |
| 冻结与检测头训练 | [4] 的适配思想，具体策略为项目实现 | [model_factory.py](../src/model_factory.py) 的 `apply_training_policy`、`build_optimizer`、`_model_train`；[参数报告](../outputs/lora_amp/yolo11n_lora_amp-2/parameter_report.json) | 冻结 backbone/neck 原权重及相应 BN 统计；训练适配器与检测头，DFL 固定权重除外。共 11 层适配器、30,976 个 LoRA 参数、447,886 个检测头参数 |
| 混合精度与数值处理 | [5][6][8] | 四份训练配置均 `amp: true`；低秩矩阵乘积显式使用 FP32，外部卷积仍遵循 AMP；优化器更新和跳步记录见两种训练器 | 采用 AMP；首次尝试可能因溢出被跳过，不能仅凭第一轮 B 仍为零判定适配器永久失效。是否学到更新以诊断和后续权重为准 |
| AdamW 与学习率控制 | [7][8] | 配置 `optimizer: AdamW`、`lr0: 0.001`、`lrf: 0.01`、`warmup_epochs: 3.0`、`cos_lr: true` | 采用 AdamW、预热与余弦衰减；未采用带周期重启的 SGDR，不为方法名相似而添加错误引用 |
| 梯度与过程控制 | [6][8] | 本机框架 `BaseTrainer.optimizer_step` 先反缩放，再 `clip_grad_norm_(max_norm=10.0)`；`nbs=64`、batch 16；A/B patience 20，C/D patience 0 | 梯度累积通常为 4 个 batch，预热期间动态调整。沿用框架裁剪，不声称独立设计了新裁剪算法；C/D 固定 30 轮，B 实际 55 轮早停 |
| 权重合并 | [4] | `to_plain_conv`、`merge_lora_layers`、`export_best_model`；正式 B 的 `weights/best.pt` 为合并后的普通模型 | 合并低秩增量后可按普通 YOLO 加载；可训练参数占比不代表推理模型缩小比例，也不证明推理更快 |
| 实验一增强对照 | 项目自身实验设计与记录 | [prepare_augmentation.py](../prepare_augmentation.py)、[准备摘要](../datasets/augmentation_control_records/preparation_summary.json)、C/D 配置和更新计数 | D 为原图加水平翻转与亮度/对比度扰动，C 为等量重复原图；均关闭在线图像增强。只增强训练集，不增加真实父图数量 |
| 指标与统一评估 | [9] | [evaluate.py](../evaluate.py)、[metrics.py](../src/metrics.py)、四组独立 val/test 摘要与逐类 CSV | 正式评估为 FP32、conf=0.001、NMS IoU=0.7、max_det=300；指标与预览图使用的 conf=0.25 分开解释 |

## 4 容易混淆的原理与统计口径

### 4.1 LoRA 公式、初始化和参数量

本项目将 1×1 卷积权重按输出/输入通道视为矩阵，并实现：

```text
W_effective = W0 + (alpha / r) * (B @ A)
A.shape = [r, C_in]
B.shape = [C_out, r]
适配器参数数 = r * (C_in + C_out)
```

低秩更新和缩放原理对应文献 [4]；本项目代码的 A 使用 Kaiming 均匀初始化，B 为零。原论文正文的 A 为高斯初始化，不能写成所有初始化细节均与论文完全一致。B 初始为零使初始增量为零，训练后是否更新由实际诊断确认。

B 组可训练参数为 478,862，占含适配器总参数 2,638,046 的 18.15%；其中检测头参数占主要部分。该比例的分母不是 A 组的可训练参数，也不是合并后推理模型的参数量。代码先计算完整的 `B @ A` 再执行卷积，未测量该计算方式的独立 FLOPs 或每步加速收益。

### 4.2 指标不等于置信度或分类准确率

按文献 [9] 对应版本：mAP50 是 IoU=0.5 下的类别平均 AP；mAP50-95 对 IoU=0.50、0.55、…、0.95 的 AP 再取平均。P/R 从平均 F1 曲线峰值对应的阈值位置提取，再按类别平均；不是固定 conf=0.25 下直接合并全部图片得到的微平均 P/R。

因此，某少数类出现 P=1、R=0 不能解释为识别完美；应结合 AP、Recall 与样本数。评估配置中的 NMS IoU=0.7 用于抑制重叠预测，和 AP 的真值匹配 IoU 是不同参数。12 张案例使用同类一对一 IoU≥0.5 匹配，仅供错误分析，不替代完整测试指标。

### 4.3 来源统计与本项目统计

[SortWaste 官网](https://sortwaste.di.ubi.pt/)列出的原始版本有 5,261 张图、8 类；[本项目数据说明](../../data/README.md)记录清洗后的 SortWaste 子集为 5,255 张，并与 TACO 一起映射到十类。两种数字的对象不同，不能用官网数字替换本地清洗结果，也不能称我们的十类映射为 SortWaste 官方十类。

本项目另有 1,498 张 TACO 正式来源图和 3,775 张 TACO 社区来源图，社区来源只参与训练。图像许可沿用数据说明中的逐来源证据；代码仓库许可证不等于全部图像许可证，本次文献核对不产生新的图像授权结论。

## 5 本次实验结论所需的本地证据

详细结果及文件定位见 [experiment2_results.md](experiment2_results.md)。下表中的数值均来自项目记录，不来自参考文献。

| 可写的结论 | 已有依据 | 必须保留的限制 |
| --- | --- | --- |
| A 被选为主模型，最终测试 mAP50-95=17.46%；B 为 16.26% | 先前验证集选型记录、两组最终测试摘要 | 选择依据是验证集，不能改写成测试集调参选型 |
| B 使用较少可训练参数，训练调用总耗时较 A 少约 25.10% | 参数报告、训练摘要；A 60 轮、B 55 轮 | 总耗时含不同轮数影响，不是同预算的每步速度提升；不能仅归因于低秩矩阵 |
| 本次不能计算 LoRA 相对 A 的训练显存节省比例 | A 无同口径训练显存记录；B 有自身记录 | 不以 C/D 显存代替 A，不以评估显存代替训练显存 |
| 已采用 AMP 训练 | 配置、环境、训练器与跳步记录 | 四组均启用 AMP，没有 amp=False 消融；论文数字不能充当本实验加速或显存节省百分比 |
| 匹配预算下，D 测试集 mAP50-95 较 C 高约 1.71 个百分点 | C/D 均 30 轮、8,635 次成功更新，验证/测试数据一致 | 单一种子与单次划分的观测；不能扩展成所有增强策略、所有场景均有效 |
| 已分析成功、漏检、类别混淆与跨类别重复框 | [案例分析](prediction_cases.md)、案例 JSON、已验收配图 | 12 张图按路径排序选取，不是随机抽样，也不能作为整体性能估计 |

## 6 后续正文引用位置

| 正文内容 | 建议引用 |
| --- | --- |
| 数据—模型关联表中的来源与场景背景 | [1][2]，并标明样本量和十类映射来自实验一处理结果 |
| 模型选型、预训练权重和框架版本 | [3][8] |
| LoRA 原理、卷积适配、冻结范围与合并 | [4]；实现细节引用项目代码及参数报告 |
| 混合精度、梯度缩放、累积和裁剪 | [5][6][8] |
| AdamW、预热、余弦学习率和早停 | AdamW 原理用 [7]；具体控制行为用 [8] 和运行参数 |
| P/R、mAP 和逐类评估解释 | [9] |
| 四组性能、资源对比、增强作用和预测案例 | 项目 JSON/CSV 与图表，不把外部文献作为本次实验数值来源 |

目前参考资料足以支撑已完成的实验流程；没有因为文献核对新增必须执行的训练任务。报告正文、封面和人员信息继续按后续安排填写。

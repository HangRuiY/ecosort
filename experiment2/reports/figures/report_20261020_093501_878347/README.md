# 实验二报告配图

本目录仅读取已有结果生成，不包含重新训练、预测或 AP 计算。

| 文件 | 建议图注 |
| --- | --- |
| [01_validation_test_comparison.png](01_validation_test_comparison.png) | 四组统一验证与测试 AP；A 在测试前依据验证集确定为主模型。 |
| [02_training_curves.png](02_training_curves.png) | 逐轮训练曲线；曲线来自训练期验证，与独立 FP32 评估存在精度设置差异，不混用数值。 |
| [03_augmentation_per_class.png](03_augmentation_per_class.png) | C/D 测试集逐类 AP50–95，图中 n 为真值目标数。 |
| [04_case_correct_plastic.png](04_case_correct_plastic.png) | 000036.png：正确检测：硬质塑料瓶。不用于继续根据测试集调参。 |
| [05_case_correct_metal.png](05_case_correct_metal.png) | 000018.png：正确检测：植被背景中的金属目标。不用于继续根据测试集调参。 |
| [06_case_missed_objects.png](06_case_missed_objects.png) | 000012.png：漏检：多目标场景没有输出框。不用于继续根据测试集调参。 |
| [07_case_wrong_class.png](07_case_wrong_class.png) | 000031.png：类别错误：金属被预测为软质塑料。不用于继续根据测试集调参。 |
| [08_case_duplicate_classes.png](08_case_duplicate_classes.png) | 000032.png：跨类别重复框：金属和硬质塑料同时输出。不用于继续根据测试集调参。 |
| [09_A_test_confusion_matrix_normalized.png](09_A_test_confusion_matrix_normalized.png) | A 组最终测试归一化混淆矩阵，保留原色块和数值，已修正横轴标签截断；未重新计算。 |
| [10_A_test_PR_curve.png](10_A_test_PR_curve.png) | A 组最终测试 PR 曲线，来自原始评估目录，未重新计算。 |

新绘制图为 300 dpi。混淆矩阵只重排横轴标签，保留原图色块及数值；PR 图保留原分辨率。

报告可优先使用 01、02、03，再选 2–3 张成功/失败案例；矩阵和 PR 曲线按模板篇幅安排。

颜色含义：案例图绿色为正确匹配，红色为未匹配真值，橙色为未匹配预测。匹配要求同类且 IoU≥0.5；这是预览案例核对规则，不等于完整测试集 AP。

截图可读性、图例遮挡和中文字体需在本机打开图片后检查。原始记录、现有模型与输入图片均未改写。

2026-10-20 已逐一查看全部 10 张图片。01–08 和 10 可用；09 原横轴英文类别名截断，已完成标签排版修复并重新检查。原始框架图仍保留在评估目录，模型与指标记录未修改。

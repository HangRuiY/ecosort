# 循智 EcoSort：多目标垃圾检测

项目保留实验一数据处理和实验二的数据准备。输入一张含多个垃圾的图片，后续模型逐目标输出位置和类别。当前保留数据，不包含已经训练的垃圾检测模型。

## 文件介绍

```text
ecosort/
├─ experiment1.py          唯一处理脚本：清洗、格式转换、划分、导出、检查和加载
├─ requirements.txt        实验一所需的三个基础依赖
├─ README.md               本文件：项目结构与运行方法
└─ data/
   ├─ README.md            数据来源、类别、划分和限制说明
   ├─ raw/
   │  ├─ images/           10,528张未增强输入图片
│  └─ annotations.json  输入标注、文本、固定分组划分及来源与历史记录
   └─ split/
      ├─ images/train/、val/、test/   划分后的图片
      ├─ labels/train/、val/、test/   YOLO逐目标标签
      ├─ train.json、val.json、test.json   COCO多目标标注
      ├─ data.yaml         实验二YOLO数据配置
      ├─ images.csv        图片统计与训练集拟合的数值归一化特征
      └─ summary.json      处理与检查结果、文本清洗与TF-IDF特征
```

`raw`表示本项目未增强的输入。这批输入已完成此前的清洗和640×640标准化，并非来源原始尺寸图片。脚本保留已有分组划分，避免因整理目录改变验证集和测试集。

## 实验一怎么运行

在项目根目录、已安装依赖的Python环境中运行：

```powershell
python -m pip install -r requirements.txt
python experiment1.py --check
```

现有划分已生成，可直接检查后使用。需要重新处理时运行`python experiment1.py`；加`--augment`才生成额外的训练增强图，验证集和测试集保持不变。默认不保留离线增强副本。

处理脚本检查目标框和类别，裁剪越界框、去除同图重复目标、剥离图像元数据、等比例标准化，并同步转换多边形；保留原始细类及来源记录。默认复用现有分组与8:1:1划分，社区未审核标注只用于训练。

原先分开的文本处理与数值标准化也合并进这个脚本；文本和历史Data-Juicer执行证据放入已有JSON中，不再增加文件夹。

同尺寸、无元数据的图片优先通过硬链接放入划分目录，逻辑上有输入和划分两个位置，物理存储通常只占一份；不支持硬链接时使用复制。修改数据请更新输入标注后通过脚本重新生成，避免手工覆盖共享图片。

## 实验二怎么接着做

配置好检测训练环境后，安装模型依赖并使用已生成的配置：

```powershell
python -m pip install torch torchvision ultralytics
yolo detect train model=yolo11n.pt data=data/split/data.yaml epochs=60 imgsz=640 batch=4 device=0
```

设备按实际机器选择；CPU可用`device=cpu`。此训练命令未在实验一执行。迁移项目后先运行`python experiment1.py --config`更新数据路径。

自定义PyTorch模型可从`experiment1.py`调用`create_torch_dataset('train')`与`detection_collate`，图像返回`[3,640,640]`张量，目标返回变长框和类别。多任务研究所需的来源细类、TACO物品类型和分组信息保留在COCO标注中，无需额外导出目录。

研二阶段可继续比较小目标策略、加入社区标签的影响、按来源的域泛化，以及层次多任务监督。实验三至五在实际训练后依次做模型压缩、接口页面与有来源的回收指导。数据详情见`data/README.md`。

# 循智 EcoSort 离线完整版使用说明

本文件夹包含实验一至实验五的全部代码、数据集、模型权重与实验报告，
组内成员解压后无需 Git、无需 conda、无需 Node.js，两个 bat 即可运行完整系统。

## 一、目录结构

```
ecosort_离线完整版/
├─ 一键安装.bat            首次运行：自动建 Python 环境（需联网约10分钟）
├─ 一键启动.bat            日常运行：启动后端+Agent 并打开页面
├─ 一键停止.bat            停止全部服务
├─ requirements.txt        统一依赖清单（清华/腾讯镜像）
├─ experiment1/            实验一：数据整理（10,528张图/21条文本/清洗脚本）
├─ experiment2/            实验二：YOLO 训练（A/B/C/D四组方案 + weights/ 权重）
├─ experiment3/            实验三：推理优化（TensorRT/ONNX 脚本与报告，已剔除 venv）
├─ experiment4/            实验四：Web 前后端（backend/ + frontend/，dist 已预编译）
├─ experiment5/            实验五：大模型 Agent（服务/工具/测试/微调产物 adapter）
├─ dataset/                舍友训练用五类数据集（train/val/test/challenge，1.8G）
└─ docs/                   实验五报告、项目总结报告、换示例图操作步骤
```

## 二、快速开始（三步）

1. **首次**：双击 `一键安装.bat`——自动寻找 Python 3.10+，在本目录建 venv 并装依赖。
   没装 Python 的先装 3.12：https://www.python.org/downloads/ （勾选 Add to PATH）
2. **日常**：双击 `一键启动.bat`——45 秒后浏览器自动打开 `http://localhost:8000`
3. **关闭**：双击 `一键停止.bat`，或直接关掉两个服务窗口

在线版（相同系统）：http://121.204.246.140:8000

## 三、系统功能入口（http://localhost:8000）

- **图像检测**：上传照片或点示例图，画框+置信度+投放建议（默认阈值 0.40，滑块可调）
- **文本问答**：口语/品牌描述均可（"一瓶农夫山泉"会先被 AI 理解为"塑料矿泉水瓶"），判定+AI解读
- **智能助手**：自然语言聊天，自动选择检测/问答工具，支持图片上传、多轮上下文、历史记录（浏览器本地保存）
- **图文匹配 / 批量任务 / 接口与模型**：同实验四

## 四、模型与依赖说明

- 检测模型：五类 YOLO11s（v4 权重，`experiment2/weights/best_5class_v4.pt/.onnx`），
  由 `ECOSORT_PT/ECOSORT_ONNX` 环境变量指定，启动脚本已配置好
- Agent 大脑：DeepSeek 云 API（key 已在 `experiment5/.env`，仅供课程使用，请勿外传）
- LoRA 微调产物：`experiment5/outputs/lora_intent_run/qwen_ecosort_lora/`（4.2M adapter）
  及训练/评估记录（大体积 int8 检查点已剔除，如需可向姚瑞航索取）
- **有 NVIDIA 显卡的机器（可选加速）**：
  1. 重装 CUDA 版 torch：`venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126`（RTX 50 系用 cu128）
  2. `pip install tensorrt-cu12`
  3. 在 `experiment4/backend` 下运行 `python scripts\build_engine.py`（约5-12分钟，在本机显卡上构建 FP16 引擎）
  4. 重启后，"接口与模型"页 TensorRT FP16 显示已加载
  - 注意：TensorRT 引擎与显卡绑定，不可跨机器拷贝

## 五、常见问题

| 问题 | 处理 |
|---|---|
| 安装很慢/失败 | 换网络或把 requirements.txt 镜像地址换成阿里云 https://mirrors.aliyun.com/pypi/simple |
| 启动后页面打不开 | 等满 45 秒（模型加载）；看两个服务窗口有无报错 |
| 首次聊天特别慢 | 正常（LangChain 冷启动约1分钟），之后再问即 2 秒级 |
| 检测无目标 | 把置信度滑块拖到 0.25 试试 |
| 8000 被占用 | 关闭占用程序，或改一键启动.bat 里的端口（同时改浏览器地址） |
| 改了前端代码 | 需装 Node.js 后在 experiment4/frontend 执行 `npm install && npm run build`（dist 会被后端自动托管） |

## 六、在线部署（服务器）

云服务器（Ubuntu 24.04）部署方式见组内记录：/opt/ecosort，systemd 服务
ecosort-backend / ecosort-agent 已配置开机自启。公网地址：http://121.204.246.140:8000

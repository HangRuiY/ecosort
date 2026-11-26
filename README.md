# 循智 EcoSort 垃圾识别与投放助手

本仓库保存项目代码、模型权重、实验报告和训练评估记录。

## 数据集下载

完整数据集单独保存在百度网盘：

- [下载 dataset.zip](https://pan.baidu.com/s/1kuRalphCYPU3aiET0CljRw?pwd=8888)
- 提取码：`8888`

下载后解压到项目根目录，目录结构应为：

```text
ecosort/
├─ dataset/
│  └─ split/
├─ experiment1/
├─ experiment2/
├─ experiment3/
├─ experiment4/
└─ experiment5/
```

## 运行说明

参见 [离线版使用说明](README_离线版.md)。

恢复项目时需要安装相应依赖，并检查启动脚本中的 Python 环境路径。

智能助手使用的 API 密钥没有上传。使用前需在
`experiment5/.env` 中自行配置 `DEEPSEEK_API_KEY`。
/* 循智EcoSort 项目总结报告（实验1-5综合，按"项目总结报告"模板九章结构） */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, PageBreak, Footer, PageNumber, AlignmentType, HeadingLevel,
  WidthType, BorderStyle, ShadingType, VerticalAlign,
} = require("docx");
const fs = require("fs");

let sizeOfMod;
try { sizeOfMod = require("image-size"); } catch (e) { sizeOfMod = null; }
function imgDims(p) {
  const buf = fs.readFileSync(p);
  const fn = sizeOfMod && (sizeOfMod.imageSize || sizeOfMod.default || sizeOfMod);
  if (fn) { const r = fn(buf); return { w: r.width, h: r.height }; }
  return { w: 1280, h: 720 };
}

const BLACK = "000000";
const FONT_BODY = { ascii: "Times New Roman", eastAsia: "SimSun" };
const FONT_HEAD = { ascii: "Times New Roman", eastAsia: "SimHei" };
const FONT_CODE = { ascii: "Courier New", eastAsia: "SimSun" };

const CJKSET = "\\u4e00-\\u9fff\\u3400-\\u4dbf";
function noSpace(t) {
  let s = String(t);
  s = s.replace(new RegExp("([" + CJKSET + "）】」》])\\s+([A-Za-z0-9（【「《])", "g"), "$1$2");
  s = s.replace(new RegExp("([A-Za-z0-9（【「《])\\s+([" + CJKSET + "）】」》])", "g"), "$1$2");
  return s;
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    keepNext: true,
    spacing: { before: 320, after: 180, line: 480, lineRule: "atLeast" },
    children: [new TextRun({ text: noSpace(text), bold: true, size: 32, color: BLACK, font: FONT_HEAD })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    keepNext: true,
    spacing: { before: 240, after: 120, line: 420, lineRule: "atLeast" },
    children: [new TextRun({ text: noSpace(text), bold: true, size: 28, color: BLACK, font: FONT_HEAD })],
  });
}
function body(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { firstLine: 480 },
    spacing: { line: 400, lineRule: "exact" },
    children: [new TextRun({ text: noSpace(text), size: 24, color: BLACK, font: FONT_BODY })],
  });
}
function tableTitle(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 80, after: 120, line: 300, lineRule: "atLeast" },
    children: [new TextRun({ text: noSpace(text), size: 21, bold: true, color: BLACK, font: FONT_BODY })],
  });
}
function figCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 200, line: 300, lineRule: "atLeast" },
    children: [new TextRun({ text: noSpace(text), size: 21, bold: true, color: BLACK, font: FONT_BODY })],
  });
}
function figure(path, widthPx) {
  const d = imgDims(path);
  const w = widthPx || 540;
  const h = Math.round(w * d.h / d.w);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 120, after: 40, line: 240, lineRule: "auto" },
    children: [new ImageRun({ data: fs.readFileSync(path), transformation: { width: w, height: h }, type: "png" })],
  });
}
function codeLine(text) {
  return new Paragraph({
    alignment: AlignmentType.LEFT,
    indent: { left: 360 },
    spacing: { line: 300, lineRule: "atLeast" },
    children: [new TextRun({ text, size: 18, color: BLACK, font: FONT_CODE })],
  });
}
function cell(text, opt) {
  const o = opt || {};
  return new TableCell({
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    width: { size: o.w || 25, type: WidthType.PERCENTAGE },
    borders: o.borders,
    children: [new Paragraph({
      alignment: o.align || AlignmentType.CENTER,
      spacing: { line: 300, lineRule: "atLeast" },
      children: [new TextRun({ text: noSpace(String(text)), size: o.size || 21, bold: !!o.bold, color: BLACK, font: FONT_BODY })],
    })],
  });
}
function dataTable(headers, rows, widths) {
  const thick = { style: BorderStyle.SINGLE, size: 12, color: BLACK };
  const thin = { style: BorderStyle.SINGLE, size: 6, color: BLACK };
  const none = { style: BorderStyle.NONE, size: 0, color: "auto" };
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: { top: thick, bottom: thick, left: none, right: none, insideHorizontal: none, insideVertical: none },
    rows: [
      new TableRow({
        tableHeader: true, cantSplit: true,
        children: headers.map((t, i) => cell(t, { bold: true, w: widths[i], borders: { bottom: thin } })),
      }),
    ].concat(rows.map(r => new TableRow({
      cantSplit: true,
      children: r.map((t, i) => cell(t, { w: widths[i], align: i === r.length - 1 && r.length >= 3 ? AlignmentType.LEFT : AlignmentType.CENTER })),
    }))),
  });
}

/* ---------- 封面 ---------- */
const cover = [];
cover.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 900, line: 700, lineRule: "atLeast" },
  children: [new TextRun({ text: "西 安 邮 电 大 学", bold: true, size: 52, color: BLACK, font: { ascii: "Times New Roman", eastAsia: "STHupo" } })],
}));
cover.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 400, after: 500, line: 700, lineRule: "atLeast" },
  children: [new TextRun({ text: "AI全栈开发实验", bold: true, size: 52, color: BLACK, font: FONT_HEAD })],
}));
cover.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 300, after: 400, line: 560, lineRule: "atLeast" },
  children: [
    new TextRun({ text: "题目：", bold: true, size: 40, color: BLACK, font: FONT_BODY }),
    new TextRun({ text: "项目总结报告", bold: true, size: 40, color: BLACK, underline: {}, font: FONT_BODY }),
  ],
}));
cover.push(new Paragraph({
  spacing: { before: 500, after: 120, line: 400, lineRule: "atLeast" },
  children: [new TextRun({ text: "组    号：8", bold: true, size: 28, color: BLACK, font: FONT_BODY })],
}));
cover.push(new Paragraph({
  spacing: { after: 120, line: 400, lineRule: "atLeast" },
  children: [new TextRun({ text: "组员信息：", bold: true, size: 28, color: BLACK, font: FONT_BODY })],
}));
const members = [
  ["2610321131", "孟琦", "前端页面与交互（检测、文本、匹配、Agent聊天与图片上传）"],
  ["2610321146", "杜路明", "后端接口、参数校验、统一异常与Agent API服务"],
  ["2610321114", "张浩", "前端布局、响应式适配与浏览器/移动端验证"],
  ["2610320013", "邵英豪", "模型训练、五类升级接入与多后端推理服务"],
  ["2610320010", "屈欣皓", "文本问答、图文匹配、知识库与词表维护"],
  ["2610321139", "姚瑞航", "异步任务、部署脚本、LoRA微调与测试文档"],
];
cover.push(new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: { top: { style: BorderStyle.SINGLE, size: 4, color: BLACK }, bottom: { style: BorderStyle.SINGLE, size: 4, color: BLACK }, left: { style: BorderStyle.SINGLE, size: 4, color: BLACK }, right: { style: BorderStyle.SINGLE, size: 4, color: BLACK }, insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: BLACK }, insideVertical: { style: BorderStyle.SINGLE, size: 4, color: BLACK } },
  rows: [
    new TableRow({ tableHeader: true, cantSplit: true, children: [
      cell("学号", { bold: true, size: 28, w: 30 }),
      cell("姓名", { bold: true, size: 28, w: 20 }),
      cell("分工", { bold: true, size: 28, w: 50 }),
    ]}),
  ].concat(members.map(m => new TableRow({ cantSplit: true, children: [
    cell(m[0], { size: 28, bold: true, w: 30 }),
    cell(m[1], { size: 28, bold: true, w: 20 }),
    cell(m[2], { size: 21, w: 50, align: AlignmentType.LEFT }),
  ]}))),
}));
cover.push(new Paragraph({
  spacing: { before: 500, line: 400, lineRule: "atLeast" },
  children: [
    new TextRun({ text: "时    间：", bold: true, size: 28, color: BLACK, font: FONT_BODY }),
    new TextRun({ text: "2026年11月14日", bold: true, size: 28, color: BLACK, font: FONT_BODY }),
    new PageBreak(),
  ],
}));

/* ---------- 正文 ---------- */
const c = [];

/* 第一章 */
c.push(h1("第一章 项目背景与概述"));
c.push(body("本项目围绕校园与社区垃圾分类的真实需求，以循智EcoSort为主题，先后完成数据整理、检测模型训练、推理算法优化、Web前后端开发与大模型Agent部署五个阶段的实验，最终交付一个可对话、可识图、可给出投放建议的完整应用。各阶段成果逐级承接：实验一提供统一的数据与知识库，实验二提供检测权重，实验三提供加速后的推理引擎，实验四把能力封装为可操作的Web应用，实验五再以大模型Agent把这些能力编排为自然语言交互。"));
c.push(h2("1.1 项目背景与研究意义"));
c.push(body("垃圾分类政策在校园与社区持续推进，但居民对具体物品的归类常存在疑问：混合垃圾中的多个目标如何分别投放、沾污后的可回收物去向如何调整，都依赖专业知识。以深度学习为目标检测主线、以大模型Agent为交互入口的方案，可以让用户以最低使用成本获得专业结论，同时完整覆盖数据、训练、优化、前后端与部署的全栈开发环节，具有较强的工程训练价值。"));
c.push(h2("1.2 需求分析与应用场景"));
c.push(body("系统面向三类核心场景：投放查询场景上传一张含多个垃圾目标的照片，页面返回每个目标的检测框、材质类别、置信度与投放建议；描述问答场景接收不超过300字的物品描述，返回材质判断、污染判断、知识库依据与地区口径的投放建议；交互核对场景由用户以自然语言同时给出图片与文字，由大模型Agent自主调度检测与问答工具并综合结论。批量场景支持一次提交多张图片或按验证集数量生成任务，避免页面长时间等待。"));
c.push(h2("1.3 技术选型依据"));
c.push(body("检测任务是多目标边界框检测而非整图分类，因此选择YOLO11系列检测模型并以mAP50-95作为主指标，任务书中的ResNet-18与Top-1准确率口径对应调整为检测指标体系。推理优化采用ONNX中间表示与TensorRT FP16引擎。大模型集成选用LangChain框架与DeepSeek对话模型，通过OpenAI兼容接口接入；本地微调选用Qwen2.5系列小模型与LoRA参数高效微调。前端采用React与Ant Design，后端采用FastAPI，均与实验四保持一致。"));
c.push(h2("1.4 项目目标与预期成果"));
c.push(body("项目目标是形成数据到部署的完整闭环并达到可量化指标：检测模型测试集mAP50-95不低于17%；推理加速后单图模型延迟降低40%以上且精度损失不超过1个百分点；Web功能测试全部通过且页面延迟低于2秒；Agent工具调用准确率不低于90%，端到端响应不超过5秒。最终预期成果为一个名为循智EcoSort的可部署应用、五个阶段的实验记录与评估数据，以及一份可复核的项目总结报告。总体闭环架构如图1所示。"));
c.push(figure("assets/fig1_architecture.png", 560));
c.push(figCaption("图 1 项目总体闭环架构"));

/* 第二章 */
c.push(h1("第二章 实验环境与技术栈"));
c.push(h2("2.1 硬件环境配置"));
c.push(body("五个实验分布在多台机器上完成：实验二的模型训练在RTX 5060 Laptop GPU上进行，实验三的导出与测速在RTX 4070 SUPER上进行，实验四、五的开发与部署验证在集显笔记本上完成并以CPU方式运行检测推理，实验五的LoRA微调训练使用RTX 5070 Laptop GPU。综合环境见表1。"));
c.push(tableTitle("表 1 综合硬件环境与用途"));
c.push(dataTable(
  ["环境", "配置", "承担的实验工作"],
  [
    ["训练机A", "RTX 5060 Laptop GPU，8GB显存", "实验二YOLO11n四组训练"],
    ["训练机B", "RTX 5070 Laptop GPU，8GB显存", "实验五Qwen2.5-0.5B意图路由LoRA训练"],
    ["优化机", "RTX 4070 SUPER，约12GB显存", "实验三ONNX导出与TensorRT FP16测速"],
    ["开发部署机", "集显笔记本，CPU推理", "实验四、五服务开发、部署与全部联调测试"],
  ],
  [18, 42, 40],
));
c.push(h2("2.2 软件与开发环境"));
c.push(body("各实验使用conda独立环境管理依赖：实验二为Python 3.13.9（mypy环境），实验三为Python 3.12.14独立虚拟环境，实验四、五为Python 3.12.14与3.12.16（ml、agent两个环境）。深度学习框架为PyTorch 2.11.0+cu128（实验二）与PyTorch 2.14.0 CPU版（实验四、五），检测框架统一为Ultralytics 8.4.175。环境版本取自正式运行输出而非仅由依赖文件推断。"));
c.push(h2("2.3 主要技术框架与工具"));
c.push(tableTitle("表 2 主要技术栈与版本"));
c.push(dataTable(
  ["类别", "技术栈", "版本"],
  [
    ["检测与推理", "Ultralytics、ONNX、TensorRT、ONNXRuntime", "8.4.175；1.19.1；10.13.3.9；1.31.1"],
    ["大模型微调", "Transformers、PEFT、TRL、bitsandbytes", ">=4.51；LoRA rank8；LLM.int8"],
    ["大模型服务", "LangChain、LangGraph、langchain-openai", "1.4.9；1.2.20；1.7.4"],
    ["后端服务", "FastAPI、Uvicorn、Celery、Redis", "0.162.2；0.54.0；5.6.3；7.x"],
    ["前端", "React、Ant Design、Axios、Vite", "19.3.1；6.6.8；1.21.0；8.3.5"],
    ["云端大模型", "DeepSeek deepseek-chat", "OpenAI兼容接口"],
  ],
  [20, 50, 30],
));
c.push(h2("2.4 版本管理与协作工具"));
c.push(body("项目以共享目录与压缩包流转代码和产物，关键产物（模型权重、数据集、微调产物）通过SHA256哈希与文件清单校验防止版本混淆；实验三对实验一、二的全部输入重新计算哈希，确认改动仅发生在本实验目录。接口契约以实验四的OpenAPI文档为准，Agent侧工具封装严格按该清单实现；五类体系切换时通过ECOSORT_*环境变量解耦模型路径，避免跨实验目录互相改写。"));

/* 第三章 */
c.push(h1("第三章 数据采集与预处理"));
c.push(h2("3.1 数据需求分析"));
c.push(body("检测模型的输入不是单一类别图片，而是可能同时含有塑料瓶、纸盒、金属罐等多个目标的画面，因此数据必须支持多目标标注并保持类别体系一致。项目数据面临三个特点：多来源（自然环境与工业传送带）在背景、目标密度和遮挡程度上差异明显；类别呈长尾分布，玻璃、食物残余等类别样本极少；实验五将类别体系由十类合并为五类，需要一套重构后的均衡数据集支撑模型升级。"));
c.push(h2("3.2 数据采集与收集"));
c.push(body("原始数据由TACO正式数据、TACO社区数据与SortWaste工业分拣帧组成，实验一整理后共10,528张真实图像、100,496个目标标注，并附21条辅助文本（11条TACO说明与10条改写）作为文本知识库。数据划分保持固定：训练集8,422张73,235个目标，验证集1,053张14,725个目标，测试集1,053张12,536个目标，跨实验沿用不重新划分。"));
c.push(h2("3.3 数据预处理流程"));
c.push(body("图像统一为640×640 RGB PNG：等比缩放、居中灰底填充；标注提供YOLO与COCO两种格式；清理环节处理EXIF方向、精确重复图与重复标注，实验三对复制输入逐文件比对SHA256以保证不回写前序实验。文本知识库经过HTML去标签、空白归一化与长度过滤后建立字符2-4gram的TF-IDF索引。"));
c.push(h2("3.4 数据清洗与增强"));
c.push(body("实验二设置C/D等预算增强对照：D组在原图基础上生成水平翻转与亮度、对比度扰动的副本，边界框同步变换并保存父图关联；两组训练条目与成功更新次数一致。对照结果显示离线增强使测试集mAP50提高2.54个百分点、mAP50-95提高1.71个百分点，但玻璃、烟蒂等类别收益不一致，体现增强的类别差异。"));
c.push(h2("3.5 数据集建设"));
c.push(body("面向五类体系升级，组员重构了均衡数据集waste_detection_10000：10,000张图像按8,000/1,000/1,000划分，塑料、纸及纸板、金属、玻璃、食物残余五类分别出现在1,732、226、224张图中，食物残余的测试标注框由2个增至354个。大模型微调数据包括材质分类指令数据（100条训练、5条测试，由实验四词表种子按12种句式模板生成并附带污染与地区变体）与意图路由数据（463条，标注带图查询与文字查询的期望工具）。"));
c.push(tableTitle("表 3 项目数据资产汇总"));
c.push(dataTable(
  ["数据资产", "规模", "用途"],
  [
    ["旧十类检测数据集", "10,528张/100,496目标", "YOLO11n训练与历史对照"],
    ["五类检测数据集", "10,000张（8/1/1划分）", "YOLO11s重训与评估"],
    ["文本知识库", "21条辅助文本", "TF-IDF检索与回答依据"],
    ["材质分类指令数据", "100训练+5测试", "材质分类LoRA（备用）"],
    ["意图路由指令数据", "463条", "工具路由LoRA（已训成）"],
  ],
  [28, 28, 44],
));

/* 第四章 */
c.push(h1("第四章 模型设计与训练"));
c.push(h2("4.1 模型选型分析"));
c.push(body("检测模型选择COCO预训练的YOLO11n进行迁移学习：轻量结构适配8GB单卡，框架可按数据YAML自动构建类别检测头。旧十类数据长尾严重，实验二以A/B比较全量微调与卷积LoRA加检测头微调两种策略，以C/D隔离实验一离线增强的影响；四组最终评估统一采用FP32，避免混合精度验证值与独立评估值混用。"));
c.push(h2("4.2 模型架构设计"));
c.push(body("卷积LoRA将冻结权重的变化表示为两个低秩矩阵的乘积，在neck的11个1×1卷积中注入适配器，rank=8、alpha=16，并同步训练检测头；原始backbone/neck参数与BatchNorm运行统计冻结，检测头DFL固定权重不参与训练。低秩分支以Kaiming均匀初始化A、零初始化B，使初始增量为零。该项目将该原理用于卷积检测网络，不将语言模型原文结论直接视为本项目结果。"));
c.push(h2("4.3 训练策略与配置"));
c.push(tableTitle("表 4 四组训练方案与主要超参"));
c.push(dataTable(
  ["组别", "训练方案", "训练数据与增强", "轮数"],
  [
    ["A", "YOLO11n全量微调+AMP", "公共训练集；在线增强", "60"],
    ["B", "neck卷积LoRA+检测头微调+AMP", "同A；同类在线增强", "55（早停）"],
    ["C", "YOLO11n全量微调+AMP", "每张原图重复一次；关在线增强", "30"],
    ["D", "YOLO11n全量微调+AMP", "原图+离线翻转/亮度/对比度增强", "30"],
  ],
  [10, 34, 42, 14],
));
c.push(body("四组统一输入640、batch 16、AdamW、初始学习率0.001、3轮预热、余弦学习率与种子20261003；启用AMP混合精度，低秩矩阵乘积局部禁用autocast并以FP32计算以降低数值风险；梯度按全局范数上限10.0裁剪。"));
c.push(h2("4.4 模型训练过程"));
c.push(body("按验证mAP50-95选取的最佳轮次分别为A第43轮、B第35轮（第55轮早停）、C第7轮、D第6轮，各组独立评估加载best.pt。最终测试集上A组mAP50为24.28%、mAP50-95为17.46%，为主模型；B组两项为22.43%与16.26%，训练总耗时较A下降约25.10%，体现了资源与精度的取舍。C/D对照中离线增强使测试集mAP50提高2.54个百分点，但烟蒂、玻璃等类别收益不一致，且单一种子与单次划分不能证明统计显著。实验同时暴露了长尾类别覆盖不足、复杂场景漏检、跨类别重复框等问题，成为实验五数据集重构与模型升级的直接动因。"));

/* 第五章 */
c.push(h1("第五章 算法优化"));
c.push(h2("5.1 性能评估基准"));
c.push(body("推理优化采用COCO风格评估体系：mAP50-95为主指标，精度损失以绝对百分点计量。评估统一使用conf=0.001、NMS IoU=0.7、max_det=300与batch=32的完整设置；展示与流程测速使用0.25置信度阈值，二者目的不同。测速区分模型口径（GPU输入到网络原始输出）与流程口径（含解码、预处理、NMS），避免把模型加速误当成应用整体加速。"));
c.push(h2("5.2 算法优化"));
c.push(body("优化链路为PyTorch权重导出ONNX（opset18）后构建TensorRT FP16引擎：输入640×640、导出batch 32、动态profile、workspace 4GiB、quantize=16、simplify与nms均为False，NMS由统一后处理执行。导出调用总耗时704.93秒属一次性离线成本，正式计时排除引擎构建与模型加载；本轮保留.pt、.onnx与.engine三个文件及其哈希以便追溯。"));
c.push(h2("5.3 算法优化"));
c.push(body("在RTX 4070 SUPER上完成1,260条有效计时，轮间交替执行顺序以减轻系统状态影响。模型口径单图延迟由18.587毫秒降至2.485毫秒，降低86.63%；batch=32批次延迟由41.292毫秒降至12.614毫秒，降低69.45%；流程口径单图由24.074毫秒降至8.406毫秒，降低65.08%。"));
c.push(tableTitle("表 5 推理优化主要结果"));
c.push(dataTable(
  ["测量口径", "优化前", "优化后", "降幅"],
  [
    ["模型单图延迟（batch=1）", "18.587ms", "2.485ms", "86.63%"],
    ["模型批量延迟（batch=32）", "41.292ms", "12.614ms", "69.45%"],
    ["流程单图延迟", "24.074ms", "8.406ms", "65.08%"],
    ["流程批量延迟（batch=32）", "176.871ms", "175.202ms", "0.94%（未达标）"],
  ],
  [34, 22, 22, 22],
));
c.push(h2("5.4 算法优化"));
c.push(body("精度方面，测试集mAP50-95由17.5281%变为17.5155%，绝对损失0.0126个百分点，精度一致性目标达到；逐类AP变化最大的金属也仅0.0399个百分点，部分低AP类别出现微小上升。速度方面，批量32完整流程仅降低0.94%，未达到延迟降低40%的目标，说明模型执行加速不会等比例传递到包含预处理、后处理与结果组织的完整流程，这一现象与Amdahl定律对共同开销的解释一致。"));
c.push(h2("5.5 算法优化测试与验证"));
c.push(body("验证策略为：模型与评估设置在查看测试结果前固定，验证集检查运行链路，测试集作最终精度对照；正式测速使用固定验证图片并以轮间交替减轻顺序偏差；四种条件、两种后端的全部计时与逐类指标、混淆差值、预测案例均保存JSON与CSV供复核。原始实验文件保护检查对349个文件重新计算哈希，确认本轮改动仅发生在实验三。"));

/* 第六章 */
c.push(h1("第六章 前后端开发"));
c.push(h2("6.1 系统架构设计"));
c.push(body("系统采用前后端分离：前端为React 19单页应用，Ant Design提供布局控件，Axios统一解析{code,result,msg}；后端为FastAPI服务，路由前缀/api/v1，按检测、文本、匹配、任务与服务信息拆分；模型层封装TensorRT FP16、ONNX Runtime与PyTorch三种后端并支持自动回退；数据层复用实验一的预处理、类别表与文本知识库。总体架构如图2所示。"));
c.push(figure("assets/fig_web_arch.png", 560));
c.push(figCaption("图 2 循智EcoSort前后端总体架构"));
c.push(h2("6.2 前端开发"));
c.push(body("前端覆盖图像检测、文本问答、图文匹配、批量任务、智能助手与服务信息六个页面。检测页以conf=0.05一次取回低阈值候选，滑块在前端本地筛选；DetectionCanvas以640×640的SVG viewBox叠加矩形，与实验一灰边规则一致；文本页展示类别概率、命中词与知识库条目；匹配页以步骤条呈现图像检测、文本分类与类别比对。响应式使用xs、lg、xl断点，首轮390px测试发现顶部导航截断，改为自动换行后三种内核复测均可见完整入口。"));
c.push(h2("6.3 后端开发"));
c.push(body("后端通过lifespan加载模型与知识库，注册CORS、统一异常、计时中间件与五组路由；模型加载按tensorrt_fp16、pytorch_fp32、onnx_fp32顺序进行并核对类别名称与顺序，失败记录原因并回退。detector.py为每个后端保留独立锁，将并发推理串行化；service.py串起校验、解码、标准化、推理、坐标映射与建议生成；文本服务以最长匹配关键词表判断材质，再按字符2-4gram TF-IDF检索21条知识库；批量任务每15秒探测Redis与Celery worker，不可用时回退进程内线程池。"));
c.push(tableTitle("表 6 Web接口清单（主要接口）"));
c.push(dataTable(
  ["接口", "主要参数", "返回result"],
  [
    ["GET/api/v1/health", "无", "设备、三个后端加载状态、知识库、任务队列"],
    ["GET/api/v1/classes", "无", "类别材质、默认投放类别、地区规则"],
    ["POST/api/v1/detect", "multipart：file；conf等", "目标类别、置信度、640框与原图框、投放建议"],
    ["POST/api/v1/text", "JSON：text、region", "材质排序、命中词、污染判断、知识库依据"],
    ["POST/api/v1/match", "multipart：file、text", "一致结论、得分、两阶段结果"],
    ["POST/GET/api/v1/tasks*", "multipart或路径id", "任务ID、状态、进度、逐图结果"],
  ],
  [24, 30, 46],
));
c.push(h2("6.4 前后端联调与测试"));
c.push(body("联调顺序为先健康接口、再检测与文本、最后匹配与批量。接口层以pytest覆盖12个用例，全部通过且0失败；页面层以Playwright在Chrome、Firefox与WebKit三种内核下执行主要交互，桌面1440×900与手机390×844两种视口均无横向滚动；性能层在RTX 5070 Laptop上实测TensorRT FP16单图总耗时中位数71.8毫秒、批量3张任务0.222秒，浏览器端到端往返中位数为Chrome 159ms、Firefox 157ms、WebKit 107ms。优化包括启动预热、低阈值候选本地筛选、模型按后端加锁与批量分块更新进度。"));

/* 第七章 */
c.push(h1("第七章 大模型Agent部署"));
c.push(h2("7.1 模型部署方案"));
c.push(body("检测模型通过ECOSORT_PT与ECOSORT_ONNX环境变量指向五类YOLO11s权重文件，后端启动时核对类别表并在集显环境自动回退到PyTorch与ONNX后端；Agent服务以FastAPI独立部署在8001端口，暴露POST /api/v1/agent/chat与health接口，返回体沿用统一结构并新增404 ToolNotFound错误码。部署脚本start_all.bat一键拉起三个服务并自动打开聊天页，stop_all.bat按端口一键停止。"));
c.push(h2("7.2 模型选择与微调"));
c.push(body("微调包含两条路线。工具路由微调以Qwen2.5-0.5B-Instruct为基座，沿用实验二的rank=8、alpha=16并作用于注意力投影，463条意图路由数据训练3个epoch，损失由0.0372收敛至0.0055；15条问法用例上意图判断准确率由零样本33.3%提升至93.3%，int8量化（LLM.int8）后精度无损，显存占用由988MB降至631MB。材质分类指令微调数据（100条训练、5条测试）同步构建作为备用路线。两条路线的可训练参数占比分别仅0.22%与0.3%量级，体现了参数高效微调的特性。检测侧随后部署了基于容器补充数据重训的v3权重，样例中罐体类别的判定由塑料修正为金属、纸杯主判定修正为纸及纸板。"));
c.push(h2("7.3 Agent框架集成"));
c.push(body("Agent以LangChain的create_agent构建，DeepSeek为推理大脑，注册两个工具：detect_trash读取本地图片并调用实验四检测接口，返回目标数量、逐目标材质置信度、640坐标框与投放建议的JSON；classify_text调用文本问答接口，返回材质、投放建议与知识库依据。工具调用内置3次重试，失败返回友好提示；响应携带工具调用轨迹、结构化工具结果与延迟，前端据此渲染检测框画布与结果卡片，大模型文字只做简短总结。"));
c.push(figure("assets/fig2_agent_chat.png", 540));
c.push(figCaption("图 3 Agent聊天页：上传图片自动调用检测工具并绘制检测框"));
c.push(h2("7.4 部署与测试"));
c.push(body("前端在实验四工程内新增AgentChat组件，支持文字输入与图片上传（JPG/PNG、不超过10MB，前端预校验后以multipart提交），检测结果画布与彩色置信度卡片按实验四设计语言渲染；Vite代理将/agent-api转发至8001并重写路径。三类端到端场景全部通过：单轮文本3.1秒、单轮图像2.7秒、多轮上下文1.4秒；聊天面板高度按视口自适应，桌面与移动视口均无横向滚动。"));

/* 第八章 */
c.push(h1("第八章 系统测试与评估"));
c.push(h2("8.1 功能测试"));
c.push(body("功能测试按五层组织并全部通过：实验四后端pytest回归12个用例（五类切换后同步更新样例断言），Agent工具层、接口层、上传链路层与端到端层的专项脚本分别覆盖工具直调与异常路径、chat与错误码、multipart与边界拦截、三场景对话。Web侧另以curl复测检测、文本、匹配与批量接口。"));
c.push(tableTitle("表 7 功能测试覆盖汇总"));
c.push(dataTable(
  ["测试层", "脚本或工具", "用例与结果"],
  [
    ["实验四后端回归", "pytest（TestClient）", "12项通过；0失败；11.8s"],
    ["Agent工具层", "test_tools.py", "工具直调与异常路径3项通过"],
    ["Agent接口层", "test_agent_api.py", "chat、health、400错误码、多轮5项通过"],
    ["上传链路层", "test_upload.py", "multipart检测与4项边界用例通过"],
    ["Agent端到端层", "test_agent_e2e.py", "三场景全部通过"],
    ["专项层", "test_tool_accuracy.py", "10轮工具选择100%"],
  ],
  [22, 28, 50],
));
c.push(h2("8.2 性能测试"));
c.push(body("Agent端到端性能：10轮工具调用测试中工具选择准确率100%，文本类平均延迟2.67秒、图像类2.83秒，均低于5秒要求；三类场景端到端延迟1.4至3.1秒。检测性能：集显CPU环境单图检测总耗时约130至213毫秒；训练机上TensorRT FP16单图模型推理中位数2.485毫秒，较PyTorch FP32降低86.63%。微调效率：LoRA可训练参数占0.22%，int8量化使部署显存下降36%且精度无损。"));
c.push(h2("8.3 用户测试"));
c.push(body("组内成员以真实用户视角对智能助手页进行试用：覆盖文字提问、图片上传、多轮追问与清空对话等操作，Chrome与Edge桌面视口及390×844移动视口下页面均无横向滚动、无控制台错误；聊天面板高度按视口自适应撑满整页（1440×900验证如图4）；助手离线标签与恢复机制、图片格式与大小的中文错误提示均按预期工作。原生Safari与iOS真机未实测，列入后续计划。"));
c.push(figure("assets/fig3_layout.png", 480));
c.push(figCaption("图 4 聊天面板全屏自适应布局（1440×900）"));
c.push(h2("8.4 与预期目标对比分析"));
c.push(tableTitle("表 8 与任务书预期目标逐项对比"));
c.push(dataTable(
  ["预期目标", "实际结果", "判定"],
  [
    ["形成数据-微调-集成-部署闭环", "五个阶段成果全部贯通并交付", "达成"],
    ["完成微调数据准备与格式对齐", "五类指令数据100+5条、路由数据463条", "达成"],
    ["LoRA参数高效微调", "路由准确率33.3%提升至93.3%；可训练参数占0.22%", "达成"],
    ["量化策略控制资源", "int8显存下降36%，精度无损", "达成"],
    ["Agent集成实验四API为工具", "检测与问答两工具封装并接入create_agent", "达成"],
    ["工具调用准确率≥90%（10轮）", "100%（10/10）", "达成"],
    ["端到端响应≤5秒", "文本2.67s、图像2.83s", "达成"],
    ["检测模型适配任务", "五类YOLO11s mAP50 74.52%（旧24.28%）", "达成"],
    ["批量流程延迟降低40%（实验三）", "流程batch=32仅0.94%", "未达成（单图口径均达成）"],
  ],
  [36, 44, 20],
));

/* 第九章 */
c.push(h1("第九章 项目总结与展望"));
c.push(h2("9.1 项目成果总结"));
c.push(body("项目把五个阶段的成果编织为一条完整链路：数据侧建成十类与五类两套检测数据集、21条知识库与两套大模型微调数据；模型侧完成YOLO11n四组训练对照、五类YOLO11s升级（mAP50 74.52%）与Qwen2.5-0.5B意图路由LoRA（93.3%）；优化侧实现TensorRT FP16单图延迟降低86.63%且精度损失0.0126个百分点；系统侧交付六个页面的React应用与11个FastAPI接口；Agent侧完成工具封装、独立部署与前端集成，工具调用准确率100%。"));
c.push(h2("9.2 技术创新点"));
c.push(body("一是意图路由微调的落地：将任务书示例的文本分类微调调整为与Agent主题直接相关的工具路由微调，使微调产物可直接服务于Agent调度。二是结构化工具结果的前端渲染：工具返回JSON、前端绘制画框与卡片、大模型只做总结的分工，解决了大模型输出表格排版混乱的通病。三是低资源环境的完整验证：全部系统功能在集显CPU环境一键部署跑通，微调训练与推理加速分别在独立GPU环境完成并记录多口径指标。"));
c.push(h2("9.3 遇到的挑战与解决方案"));
c.push(tableTitle("表 9 项目主要挑战与解决"));
c.push(dataTable(
  ["挑战", "解决方案", "验证"],
  [
    ["旧十类模型mAP仅24.28%，稀有类漏检", "类别合并为均衡五类并升级YOLO11s重训", "mAP50提升至74.52%"],
    ["类别体系切换涉及约10处联动改动", "统一类别表覆盖+加载核对+动态长度", "旧ONNX被防呆拒绝，新链路全通"],
    ["微调需要GPU而开发机为集显", "数据脚本化+独立训练包，由组员GPU代跑", "463条训练约数十分钟完成"],
    ["大模型输出表格排版混乱", "工具返回JSON+前端卡片+大模型只做总结", "聊天页渲染整齐"],
    ["图片被固定行距裁剪", "图片段落改用auto行距", "三图完整显示"],
    ["低置信度误检", "阈值0.40并计划替换新数据集样例图", "高置信框为主"],
  ],
  [30, 40, 30],
));
c.push(h2("9.4 项目局限性分析"));
c.push(body("检测模型mAP50-95为60.03%，复杂场景仍存在漏检与误检；意图路由模型依赖训练问法分布，当前以云端DeepSeek为主路由、本地模型作为储备；文本关键词基线覆盖有限，烟蒂、电池等旧类别物品在新体系下返回未识别；批量32完整流程的加速未达标，其分阶段瓶颈尚无直接计时依据；浏览器矩阵未覆盖原生Safari与iOS真机；端到端延迟受大模型API网络往返影响明显。"));
c.push(h2("9.5 未来展望与改进方向"));
c.push(body("后续计划：以前端演示为目标替换新数据集样例图并补充Safari与iOS实测；将本地路由模型接入Agent服务作为云端不可用时的降级大脑；以五类标注训练文本分类器替换关键词基线；把批量流程按解码、推理与写盘拆分计时定位瓶颈；引入Docker Compose与GPU基础镜像完成一体化部署。"));

/* 附录 */
c.push(h1("附录A 代码结构说明"));
c.push(body("experiment1至experiment3目录分别承载数据整理、模型训练与推理优化的脚本、配置与记录；experiment4/backend/app为FastAPI应用（config、reuse、preprocess、detector、service、advice、text_service、tasks、errors与routers），experiment4/frontend/src为React工程（pages、components、api）；experiment5包含make_finetune_data.py、train_lora.py、eval_compare.py、tools.py、agent.py、agent_api.py与五个分层测试脚本，data目录存放指令数据，outputs目录存放微调与评估产物。"));
c.push(h1("附录B 数据集详细统计"));
c.push(body("旧十类数据集：10,528张真实图像、100,496个目标，训练8,422张73,235目标、验证1,053张14,725目标、测试1,053张12,536目标；十类测试目标数依次为7239、1679、48、373、2710、283、20、2、100、82。五类数据集：10,000张，按8,000/1,000/1,000划分，五类分别出现在1,732、226、224张图中。微调数据：材质分类100条训练、5条测试（每类20+1，含污染与上海变体）；意图路由463条（detect 139条、advice 244条等）。文本知识库21条。"));
c.push(h1("附录C 模型参数配置表"));
c.push(tableTitle("表 10 关键模型与训练参数"));
c.push(dataTable(
  ["模型/环节", "参数", "取值"],
  [
    ["实验二YOLO11n", "imgsz/batch/优化器/学习率", "640；16；AdamW；0.001，种子20261003"],
    ["实验二卷积LoRA", "rank/alpha/注入位置", "8/16/neck的11个1×1卷积+检测头"],
    ["实验三TensorRT", "imgsz/batch/workspace/精度", "640；32；4GiB；FP16，opset18"],
    ["实验五路由LoRA", "rank/alpha/目标层/epochs", "8/16/q·k·v·o投影/3"],
    ["实验五微调量化", "量化方式/产物体积", "bitsandbytes LLM.int8/618MB"],
    ["Agent检测调用", "conf/imgsz/NMS IoU/max_det", "0.40/640/0.7/300"],
  ],
  [26, 34, 40],
));
c.push(h1("附录D 系统部署文档"));
c.push(body("一键启动：双击项目根目录start_all.bat，依次拉起实验四后端（8000，需ECOSORT_PT与ECOSORT_ONNX指向五类权重）、Agent服务（8001）与前端（5173），15秒后自动打开聊天页；一键停止：双击stop_all.bat按端口结束进程。手动部署时在experiment4/backend以ml环境运行uvicorn app.main:app --port 8000，在experiment5以agent环境运行uvicorn agent_api:app --port 8001，前端目录运行node node_modules/vite/bin/vite.js；生产环境可通过构建产物由FastAPI托管或由nginx反向代理。"));
c.push(h1("附录E 用户使用手册"));
c.push(body("打开http://localhost:5173/#/agent进入智能助手页：文字提问直接输入并回车；图片识别点击图片按钮选择JPG/PNG照片，预览后发送；思考过程可展开查看每次工具调用；检测与问答结果以画框图和结果卡片展示，卡片下方为文字总结；图像检测、文本问答等传统页面保留原有交互方式；页面顶部标签实时显示助手与服务在线状态。"));

/* 参考文献 */
c.push(h1("参考文献"));
const refs = [
  "[1] PROENÇA P F, SIMÕES P. TACO: trash annotations in context for litter detection[EB/OL]. (2020-03-16)[2026-11-14]. https://arxiv.org/abs/2003.06975.",
  "[2] INÁCIO S, PROENÇA H, NEVES J C. SortWaste: a densely annotated dataset for object detection in industrial waste sorting[EB/OL]. 2026[2026-11-14]. https://arxiv.org/abs/2601.02299.",
  "[3] JOCHER G, QIU J. Ultralytics YOLO11[EB/OL]. 2024[2026-11-14]. https://docs.ultralytics.com/models/yolo11/.",
  "[4] HU E J, SHEN Y, WALLIS P, et al. LoRA: low-rank adaptation of large language models[C]//The Tenth International Conference on Learning Representations. 2022.",
  "[5] MICIKEVICIUS P, NARANG S, ALBEN J, et al. Mixed precision training[C]//International Conference on Learning Representations. 2018.",
  "[6] QWEN TEAM. Qwen2.5: a party of foundation models[EB/OL]. (2024-12-19)[2026-11-14]. https://arxiv.org/abs/2412.15115.",
  "[7] DeepSeek. DeepSeek API documentation[EB/OL]. [2026-11-14]. https://platform.deepseek.com/api-docs.",
  "[8] LANGCHAIN. LangChain Python documentation[EB/OL]. [2026-11-14]. https://python.langchain.com/docs/.",
  "[9] DETTMERS T, PAGNONI A, HOLTZMAN A, et al. QLoRA: efficient finetuning of quantized LLMs[C]//Advances in Neural Information Processing Systems 36. 2023: 10088-10115.",
  "[10] FIELDING R T. Architectural styles and the design of network-based software architectures[D]. Irvine: University of California, Irvine, 2000.",
  "[11] LIN T Y, MAIRE M, BELONGIE S, et al. Microsoft COCO: common objects in context[C]//Computer Vision—ECCV 2014. Cham: Springer, 2014: 740-755.",
  "[12] AMDAHL G M. Validity of the single processor approach to achieving large scale computing capabilities[C]//Proceedings of the April 18-20, 1967, Spring Joint Computer Conference. New York: ACM, 1967: 483-485.",
];
refs.forEach(r => c.push(new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  indent: { left: 480, hanging: 480 },
  spacing: { line: 360, lineRule: "atLeast" },
  children: [new TextRun({ text: r, size: 21, color: BLACK, font: FONT_BODY })],
})));

/* ---------- 文档 ---------- */
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: FONT_BODY, size: 24, color: BLACK },
        paragraph: { spacing: { line: 400, lineRule: "exact" } },
      },
      heading1: {
        run: { font: FONT_HEAD, size: 32, bold: true, color: BLACK },
        paragraph: { spacing: { before: 320, after: 180, line: 480, lineRule: "atLeast" } },
      },
      heading2: {
        run: { font: FONT_HEAD, size: 28, bold: true, color: BLACK },
        paragraph: { spacing: { before: 240, after: 120, line: 420, lineRule: "atLeast" } },
      },
      heading3: {
        run: { font: FONT_HEAD, size: 24, bold: true, color: BLACK },
        paragraph: { spacing: { before: 200, after: 100, line: 400, lineRule: "atLeast" } },
      },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, bottom: 1440, left: 1800, right: 1800, header: 851, footer: 992 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, font: FONT_BODY })],
        })],
      }),
    },
    children: cover.concat(c),
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = "项目总结报告_循智EcoSort.docx";
  fs.writeFileSync(out, buf);
  console.log("done:", out);
});

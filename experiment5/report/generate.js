/* 实验5 项目总结报告（版式对齐实验1-4：三线表、GB参考文献、无中英空格） */
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

/* 删除中英文/数字与汉字之间的空格（保留纯英文之间与纯中文之间的空格） */
const CJKSET = "\\u4e00-\\u9fff\\u3400-\\u4dbf";
function noSpace(t) {
  let s = String(t);
  s = s.replace(new RegExp("([" + CJKSET + "）】」》])\\s+([A-Za-z0-9（【「《])", "g"), "$1$2");
  s = s.replace(new RegExp("([A-Za-z0-9（【「《])\\s+([" + CJKSET + "）】」》])", "g"), "$1$2");
  return s;
}

/* ---------- 组件 ---------- */
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
function body(text, opts) {
  const o = opts || {};
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: o.noIndent ? undefined : { firstLine: 480 },
    spacing: { line: 400, lineRule: "exact" },
    children: [new TextRun({ text: noSpace(text), size: 24, color: BLACK, font: FONT_BODY })],
  });
}
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 80, after: 120, line: 300, lineRule: "atLeast" },
    children: [new TextRun({ text: noSpace(text), size: 21, bold: true, color: BLACK, font: FONT_BODY })],
  });
}
const tableTitle = caption;
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
/* 三线表：顶线粗、表头下细线、底线粗，无竖线无内横线 */
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

/* ---------- 封面（复刻实验4版式） ---------- */
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
    new TextRun({ text: "大模型Agent部署训练实验指导", bold: true, size: 40, color: BLACK, underline: {}, font: FONT_BODY }),
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
  ["2610321131", "孟琦", "AgentChat聊天组件、图片上传与检测框画布"],
  ["2610321146", "杜路明", "Agent API服务（8001）、统一错误码与重试机制"],
  ["2610321114", "张浩", "前端全屏自适应布局与浏览器/移动端验证"],
  ["2610320013", "邵英豪", "五类检测模型升级接入与多后端加载回退"],
  ["2610320010", "屈欣皓", "文本词表五类重组与知识库检索适配"],
  ["2610321139", "姚瑞航", "微调数据构建、LoRA训练与一键部署脚本"],
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

/* 一 */
c.push(h1("一、实验目的"));
c.push(body("本实验在实验一的数据整理、实验二的LoRA参数高效微调、实验三的量化加速与实验四的Web前后端成果之上，构建循智EcoSort的大模型Agent层：以DeepSeek云端大模型作为意图理解大脑，将实验四的图像检测、文本问答接口封装为LangChain工具，并以LoRA指令微调训练本地小模型补充工具路由能力，形成数据-微调-框架集成-部署交互的完整闭环。"));
c.push(body("交互方式由实验四的手动选择功能页面，升级为自然语言对话：用户上传照片或输入文字描述，Agent自主决定调用图像检测工具或文本问答工具，并结合多轮上下文组织回答。具体目标包括：完成微调数据集构建与本地小模型的LoRA训练和量化；基于create_agent集成实验四API为工具；Agent服务以FastAPI独立部署并接入实验四前端；10轮工具调用准确率不低于90%，端到端响应不超过5秒。"));

/* 二 */
c.push(h1("二、实验环境"));
c.push(body("开发与部署验证在集显笔记本上完成，检测推理全程使用CPU；LoRA微调训练使用组员提供的NVIDIA RTX 5070 Laptop GPU完成。主要配置见表1。"));
c.push(tableTitle("表1 软硬件与主要依赖"));
c.push(dataTable(
  ["项目", "任务书要求", "实际配置"],
  [
    ["操作系统与主机", "CPU不低于4核，内存不低于8GB", "Windows11 26200；i7-14650HX；集显开发机+RTX5070训练机"],
    ["GPU与驱动", "未指定", "训练机RTX5070 Laptop 8GB；开发机无独立显卡，CPU推理"],
    ["Python", "3.12+（Anaconda）", "3.12.14 / 3.12.16（conda环境ml、agent）"],
    ["Agent框架", "LangChain>=1.0", "LangChain1.4.9；LangGraph1.2.20；langchain-openai1.7.4"],
    ["LLM服务", "DeepSeek/GLM API", "DeepSeek deepseek-chat（OpenAI兼容接口）"],
    ["微调工具", "SFTTrainer、量化", "TRL+PEFT、bitsandbytes LLM.int8、Qwen2.5-0.5B-Instruct"],
    ["后端推理", "FastAPI>=0.130", "FastAPI0.162.2；Uvicorn0.54.0；ultralytics8.4.175；ONNXRuntime1.31.1"],
    ["前端", "React18+、Node24+", "React19.3.1；AntD6.6.8；Axios1.21.0；Vite8.3.5；Node25.2.1"],
    ["检测模型", "实验二/三成果", "YOLO11s五类（新，mAP50为74.52%）/YOLO11n十类（旧，24.28%）"],
  ],
  [18, 32, 50],
));

/* 三 */
c.push(h1("三、实验内容与步骤"));
c.push(h2("3.1 需求分析"));
c.push(body("系统面向三类使用场景：用户上传照片并以自然语言询问，Agent应调用图像检测工具，汇报目标数量、材质类别与投放建议；用户以文字描述物品，Agent调用文本问答工具，给出材质判断与知识库依据；用户在多轮对话中以代词回指此前内容，Agent应结合上下文回答而不重复调用工具。"));
c.push(body("非功能需求包括：单次端到端响应不超过5秒；10轮测试中工具选择准确率不低于90%；接口错误采用与实验四一致的{code,result,msg}统一结构；错误码复用400参数错与500服务错，新增404 ToolNotFound；工具调用内置3次重试并记录详细日志；聊天页在桌面与移动端视口下均可正常使用。检测体系沿用实验二交接后的五类口径（塑料、纸及纸板、金属、玻璃、食物残余），类别表在后端加载时与模型权重核对。"));
c.push(h2("3.2 设计思路"));
c.push(body("系统在实验四前后端分离架构上叠加Agent层，整体结构见图1。前端在原React工程内新增AgentChat聊天组件；Agent服务（8001端口）以LangChain的create_agent构建，注册图像检测与文本问答两个工具；工具返回结构化JSON，由前端绘制检测框画布与结果卡片，大模型只负责自然语言总结；对话历史由前端维护并整段传入，支持多轮上下文与断点续聊。"));
c.push(figure("assets/fig1_architecture.png", 560));
c.push(figCaption("图1 循智EcoSort实验5闭环架构"));
c.push(body("一次对话请求的流程为：前端把消息和历史POST到/api/v1/agent/chat；Agent服务经LangChain调用DeepSeek，大模型依据用户输入选择detect_trash或classify_text工具；工具以3次重试调用实验四后端的/detect或/text接口，把JSON结果交回大模型组织成自然语言回复；响应携带回复文本、工具调用轨迹、结构化工具结果与延迟。"));
c.push(h2("3.3 代码实现"));
c.push(body("实现按环境准备、微调数据与训练、Agent服务、前端集成、联调测试五步推进。微调与Agent服务使用两套独立conda环境（ml、agent），通过本机HTTP接口解耦。"));
c.push(h2("3.3.1 微调数据构建与训练"));
c.push(body("材质分类指令数据由make_finetune_data.py生成：以实验四text_service.py的LEXICON关键词表为种子，按12种句式模板组合出100条训练描述与5条测试描述，五类每类均衡，输出标签复刻advice模块判定规则，并内置污染语义与上海地区口径变体；测试集条目与训练组合互斥。意图路由数据463条由组员参照真实问法构建，标注带图查询期望detect、文字描述期望advice。"));
c.push(body("意图路由LoRA微调基于Qwen2.5-0.5B-Instruct，沿用实验二的rank=8、alpha=16，低秩适配层作用于注意力q/k/v/o投影，可训练参数1,081,344个，占总参数的0.22%；3个epoch后损失收敛至0.037。训练与量化在CUDA环境完成，量化采用bitsandbytes LLM.int8并保留未量化语言模型头，同时导出ONNX与int8检查点。"));
c.push(h2("3.3.2 Agent服务与工具封装"));
c.push(body("agent_api.py创建FastAPI应用，暴露POST /api/v1/agent/chat与GET /api/v1/agent/health，返回体沿用{code,result,msg}统一结构；消息上限1000字，最多携带20条历史。tools.py将实验四的/detect与/text封装为两个LangChain工具，返回结构化JSON；调用失败时重试3次，最终失败返回友好提示字符串。启动时构建Agent并写入日志，响应记录用户查询、工具轨迹与延迟。"));
c.push(h2("3.3.3 前端集成"));
c.push(body("前端在实验四工程内新增AgentChat组件：支持文字输入与图片上传（JPG/PNG、不超过10MB，前端预校验后以multipart提交），检测结果卡片复用实验四的DetectionCanvas画布按640坐标系叠加检测框与材质标签，下方以彩色置信度条与投放建议标签逐目标展示；助手文字只做简短总结，避免表格排版混乱。Vite代理将/agent-api转发至8001并重写路径，浏览器仅访问5173。聊天面板高度按视口自适应，输入框贴底。"));
c.push(figure("assets/fig2_agent_chat.png", 540));
c.push(figCaption("图2 Agent聊天页：上传图片自动调用检测工具并绘制检测框"));
c.push(h2("3.4 测试与优化"));
c.push(body("测试按五层组织，自底向上逐层验证：工具层直接调用两个LangChain工具，验证实验四后端链路与异常提示；接口层验证chat、health接口与错误码；上传链路层验证multipart提交、非法格式拦截与临时文件清理；端到端层覆盖单轮文本、单轮图像与多轮上下文三场景；专项层统计10轮工具选择准确率。此外，实验四后端保留12个pytest用例作回归测试，在五类切换与新权重接入后同步更新断言并全部重跑。各层脚本与覆盖情况见表2。"));
c.push(tableTitle("表 2 分层测试脚本与覆盖"));
c.push(dataTable(
  ["测试脚本", "层次", "覆盖内容", "结果"],
  [
    ["pytest tests/", "实验四回归", "健康、404、格式、检测、文本、匹配、任务12用例", "12项通过"],
    ["test_tools.py", "工具层", "检测/文本工具直调、找不到图片的异常路径", "3项通过"],
    ["test_agent_api.py", "接口层", "chat、health、空消息与超长400、多轮历史", "5项通过"],
    ["test_upload.py", "上传链路", "multipart检测、GIF与超大文件拦截、临时文件清理", "4项通过"],
    ["test_agent_e2e.py", "端到端层", "单轮文本、单轮图像、多轮上下文", "3场景通过"],
    ["test_tool_accuracy.py", "专项层", "10轮工具选择准确率与延迟", "100%，10/10"],
  ],
  [24, 16, 44, 16],
));
c.push(body("优化集中在阈值与稳定性：检测置信度阈值由0.25提高到0.40以抑制低置信误检，误检样例图待替换为新数据集验证集图片；健康检查离线时每5秒重试直至在线；Agent聊天面板在检测页之外复用同一套阈值口径，保证两处结果一致。"));

/* 四 */
c.push(h1("四、实验关键技术与难点"));
c.push(h2("4.1 工具意图路由的LoRA微调"));
c.push(body("任务书的微调示例是文本分类，本实验把微调目标调整为与Agent主题直接相关的工具路由：训练本地小模型判断一条用户输入应交给检测工具还是问答工具。评估用15条问法用例，基座零样本仅5条正确，LoRA微调后14条正确。该路线使微调产物与Agent调度直接衔接，材质分类知识仍由检测模型与知识库承担。"));
c.push(h2("4.2 类别体系由十类切换到五类"));
c.push(body("实验二交接把检测体系从十类改为五类并更换YOLO11s权重，涉及后端类别表、投放规则、关键词表、类别核对、前端常量、Agent提示词与微调数据共约10处联动修改。后端加载模型时核对类别名称和顺序，旧十类ONNX因核对不一致被自动拒绝，防止新旧体系混用；文本评分数组等硬编码长度改为按类别表动态取值，避免越界。"));
c.push(h2("4.3 检测框与聊天画布的坐标对齐"));
c.push(body("检测工具返回640×640坐标框，聊天画布复用实验四的DetectionCanvas，图片按contain方式显示在正方形区域内，与实验一的等比缩放加灰边规则一致，框按百分比叠加即可对齐任意比例的原始照片。助手气泡不再重复渲染原图缩略图，避免与带框画布混淆。"));
c.push(h2("4.4 集显环境的CPU推理与多后端回退"));
c.push(body("开发机无独立显卡，后端按TensorRT、PyTorch、ONNX顺序加载，TensorRT因需要NVIDIA GPU被自动跳过，请求回退到PyTorch或ONNX；新权重通过ECOSORT_PT与ECOSORT_ONNX环境变量接入，不修改任何代码。CPU下单图检测总耗时约213毫秒，满足聊天交互的响应预算。"));
c.push(h2("4.5 跨域代理与中英文编码"));
c.push(body("开发阶段Vite把/agent-api代理到8001并重写前缀，浏览器只访问5173；Windows命令行的GBK编码会使中文参数在curl与conda run中损坏，联调统一改用UTF-8脚本文件发请求；cmd的PATH中不存在node，部署脚本改用node.exe完整路径。三处问题均已在联调中定位并修复。"));
c.push(h2("4.6 意图路由的适用范围"));
c.push(body("路由模型依赖训练数据的问法分布，对偏离分布的问法可能误路由；当前系统以云端DeepSeek为主路由，本地模型作为能力储备与降级方案。烟蒂、电池等旧类别物品在五类体系下不再映射，文本入口会返回未识别并引导用户换个说法或提供图片。"));

/* 五 */
c.push(h1("五、实验结果与分析"));
c.push(h2("5.1 功能与接口测试"));
c.push(body("三类端到端场景全部通过：单轮文本自动调用文本工具并给出污染结论，端到端耗时2.8秒；单轮图像自动调用检测工具，样例图中3个高置信目标（2金属1塑料）的框、材质与建议正确，耗时2.6秒；多轮上下文正确理解指代且未重复调用工具，耗时0.9秒。上传链路验证通过：JPG图片上传后正常触发检测，GIF格式与超过10MB的图片均被400拦截，临时上传文件处理完成后零残留。"));
c.push(tableTitle("表 3 端到端场景测试"));
c.push(dataTable(
  ["场景", "输入", "期望工具", "结果", "耗时"],
  [
    ["单轮文本", "沾了油的外卖塑料餐盒", "classify_text", "塑料，污染后投其他垃圾", "2.8s"],
    ["单轮图像", "000005.png图片路径", "detect_trash", "3个高置信目标：金属×2、塑料×1", "2.6s"],
    ["多轮上下文", "刚才那张图里的东西怎么投放", "不调工具", "正确汇总上轮检测结果", "0.9s"],
  ],
  [16, 26, 18, 26, 14],
));
c.push(body("实验四后端的pytest回归测试在权重迭代中同步更新样例断言：十类旧权重断言6个目标金属0.598，首版五类权重断言4个目标塑料0.86，v3容器补充重训权重断言5个目标金属0.86；带ECOSORT_PT环境变量重跑12个用例全部通过，耗时11.5秒，说明实验四的既有功能未受模型升级影响。"));
c.push(body("Agent接口的实际响应片段如下，工具调用轨迹、结构化结果与延迟随回复一并返回，前端据此渲染检测框画布与结果卡片。"));
c.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  indent: { left: 360 },
  spacing: { line: 300, lineRule: "atLeast" },
  children: [new TextRun({ text: "POST /api/v1/agent/chat  {\u201cmessage\u201d:\u201c沾了油的外卖塑料餐盒应该扔哪个垃圾桶？\u201d}", size: 18, color: BLACK, font: { ascii: "Courier New", eastAsia: "SimSun" } })],
}));
c.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  indent: { left: 360 },
  spacing: { line: 300, lineRule: "atLeast" },
  children: [new TextRun({ text: "{\"code\":200,\"msg\":\"ok\",\"result\":{\"reply\":\"这属于塑料材质，但因为沾了油污，投放建议是其他垃圾\",", size: 18, color: BLACK, font: { ascii: "Courier New", eastAsia: "SimSun" } })],
}));
c.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  indent: { left: 360 },
  spacing: { line: 300, lineRule: "atLeast" },
  children: [new TextRun({ text: "\"tool_calls\":[\"调用classify_text({'text':'沾了油的外卖塑料餐盒'})\"],\"tool_results\":[{\"ok\":true,\"class_id\":0,\"name_zh\":\"塑料\",\"prob\":0.874,\"bin_zh\":\"其他垃圾\"}],\"latency_ms\":2886.3}}", size: 18, color: BLACK, font: { ascii: "Courier New", eastAsia: "SimSun" } })],
}));
c.push(tableTitle("表 4 异常与边界用例"));
c.push(dataTable(
  ["用例", "期望行为", "实测结果"],
  [
    ["空消息", "400参数错", "400，消息为空，请输入内容"],
    ["消息超过1000字", "400参数错", "400，提示具体字数上限"],
    ["上传GIF图片", "400格式错误", "400，仅支持JPG/PNG"],
    ["上传超过10MB图片", "400大小限制", "400，提示实际大小与上限"],
    ["工具后端不可用", "3次重试后友好提示", "提示图像检测服务暂时不可用"],
    ["找不到图片路径", "不抛异常", "返回找不到文件提示，Agent引导用户"],
    ["上传临时文件", "处理完删除", "uploads目录零残留"],
  ],
  [24, 26, 50],
));
c.push(h2("5.2 工具调用准确率与延迟"));
c.push(body("按任务书要求执行10轮工具选择测试：5轮文本查询与5轮图像查询交叉进行，逐轮核对Agent实际调用的工具。该测试在v4权重、0.40置信度阈值与修订后系统提示词下执行，10轮全部正确，准确率100%，超过90%的目标；文本类平均延迟1.89秒，图像类平均延迟2.36秒，均低于5秒要求，明细保存于tool_accuracy.json。"));
c.push(tableTitle("表 5 工具调用准确率与延迟"));
c.push(dataTable(
  ["任务类型", "轮数", "正确选择", "准确率", "平均延迟"],
  [
    ["文本查询（期望classify_text）", "5", "5", "100%", "1.89s"],
    ["图像查询（期望detect_trash）", "5", "5", "100%", "2.36s"],
    ["合计", "10", "10", "100%", "—"],
  ],
  [36, 12, 16, 16, 20],
));
c.push(h2("5.3 微调效果与量化分析"));
c.push(body("意图路由微调基于15条问法用例评估：基座零样本仅5条正确，LoRA微调后14条正确，准确率由33.3%提升至93.3%；int8量化后保持14条正确，精度无损。三个epoch的训练损失分别为0.0372、0.0032与0.0055，第二个epoch起即收敛。显存方面，fp16占用988MB，int8占用631MB，下降36%。与实验二对比：实验二在YOLO卷积上做LoRA，可训练参数478,862个、占全部参数18.15%，收益体现在检测精度的资源取舍；本实验在语言模型注意力投影上做LoRA，可训练参数占比仅0.22%，收益体现在路由准确率大幅提升，两者共同验证了参数高效微调在不同结构上的适配方法。"));
c.push(tableTitle("表 6 意图路由微调前后对比（15条评估用例）"));
c.push(dataTable(
  ["模型形态", "正确数", "准确率", "GPU显存占用"],
  [
    ["基座零样本", "5 / 15", "33.3%", "fp16 988MB"],
    ["LoRA微调后", "14 / 15", "93.3%", "LoRA训练占用988MB"],
    ["int8量化后", "14 / 15", "93.3%（无损）", "631MB（较fp16下降36%）"],
  ],
  [30, 20, 25, 25],
));
c.push(h2("5.4 检测模型升级对比"));
c.push(body("检测模型迭代后，同一张样例图000005.png的检测由旧十类模型的6个目标（置信度27%至60%）收敛为v4权重的3个高置信目标（置信度76%至91%），冰箱场景中隔层误检消失，路边纸杯以0.69的置信度被正确判定为纸及纸板。文本问答在新词表下对典型问法全部正确：沾油餐盒返回塑料并按污染改投其他垃圾，牛奶盒返回纸及纸板，烟头、电池按五类口径调用工具后返回未识别并引导补充信息。"));
c.push(tableTitle("表 7 检测模型升级前后对比"));
c.push(dataTable(
  ["对比项", "旧模型（YOLO11n十类）", "新模型（YOLO11s五类）"],
  [
    ["测试集mAP50", "24.28%", "74.52%"],
    ["测试集mAP50-95", "17.46%", "60.03%"],
    ["样例图000005检测", "6个目标，置信度27%~60%", "4个目标，置信度67%~86%"],
    ["类别体系", "十类，稀有类样本不足", "五类合并，比例均衡"],
  ],
  [24, 38, 38],
));
c.push(h2("5.5 布局与跨端验证"));
c.push(body("聊天面板高度按视口自适应，桌面端撑满剩余高度且输入框贴底，在1280×720、1440×900两种桌面视口与390×844移动视口下验证均无横向滚动，如图3所示；助手在线状态标签离线时每5秒重试直至恢复。"));
c.push(figure("assets/fig3_layout.png", 500));
c.push(figCaption("图3 聊天面板全屏自适应布局（1440×900）"));
c.push(h2("5.6 问题与解决"));
c.push(tableTitle("表 8 开发中的典型问题"));
c.push(dataTable(
  ["问题", "原因", "处理方法", "验证"],
  [
    ["numpy/opencv ABI冲突", "旧版opencv基于numpy1编译", "升级opencv-python至5.0", "导入与推理正常"],
    ["代理转发404", "Vite代理未重写/agent-api前缀", "代理配置增加rewrite", "经代理访问200"],
    ["中文参数乱码", "Windows shell默认GBK", "改用UTF-8脚本文件传参", "接口解析正常"],
    ["构建时报node不存在", "cmd的PATH无node", "部署脚本改用node.exe完整路径", "构建通过"],
    ["聊天页图片遮挡画框", "助手气泡重复渲染原图", "原图仅在用户气泡渲染", "画框画布正常显示"],
    ["文本接口500", "评分数组硬编码长度10", "改为按类别表长度动态", "五类文本全部识别"],
    ["低置信度误检", "样例图属旧数据集域", "阈值0.40并待换样例图", "高置信框为主"],
  ],
  [22, 24, 32, 22],
));
c.push(h2("5.7 局限与讨论"));
c.push(body("检测模型mAP50-95为60.03%，复杂场景仍有漏检与误检，当前以置信度阈值0.40缓解，样例图待替换为新数据集验证集图片；文本关键词基线覆盖有限，烟蒂、电池等旧类别物品不再映射，会返回未识别；意图路由模型依赖训练问法分布，当前以云端DeepSeek为主路由、本地模型作为降级储备；端到端延迟主要受大模型API网络往返影响，弱网环境下可能超出预期。"));

/* 六 */
c.push(h1("六、实验总结与展望"));
c.push(body("实验五在实验四可操作的Web应用之上完成了大模型Agent层：LangChain Agent以DeepSeek为大脑、以实验四接口为工具，经FastAPI服务与React聊天组件对外交付；面向工具路由的LoRA微调把本地小模型的路由准确率从33.3%提升到93.3%，并以int8量化将显存占用降低36%且精度无损；检测模型同步升级为五类YOLO11s，mAP50提升50个百分点。全部功能在集显CPU环境一键部署跑通，10轮工具调用准确率100%，端到端延迟2.2至3.1秒。"));
c.push(body("后续工作包括：用新数据集验证集图片替换前端样例图，使演示场景与模型训练域一致；将本地路由模型接入Agent服务作为API不可用时的降级大脑；以五类标注数据训练文本分类器替换关键词基线；引入Docker Compose完成一体化部署，并在iOS真机上补充移动端实测。"));

/* 七 */
c.push(h1("七、参考文献"));
const refs = [
  "[1] HU E J, SHEN Y, WALLIS P, et al. LoRA: low-rank adaptation of large language models[C]//The Tenth International Conference on Learning Representations. 2022.",
  "[2] DeepSeek. DeepSeek API documentation[EB/OL]. [2026-11-14]. https://platform.deepseek.com/api-docs.",
  "[3] QWEN TEAM. Qwen2.5: a party of foundation models[EB/OL]. (2024-12-19)[2026-11-14]. https://arxiv.org/abs/2412.15115.",
  "[4] LANGCHAIN. LangChain Python documentation[EB/OL]. [2026-11-14]. https://python.langchain.com/docs/.",
  "[5] VON WERRA L, BECQUART L, BEKMAN E, et al. TRL: transformer reinforcement learning[EB/OL]. [2026-11-14]. https://github.com/huggingface/trl.",
  "[6] DETTMERS T, PAGNONI A, HOLTZMAN A, et al. QLoRA: efficient finetuning of quantized LLMs[C]//Advances in Neural Information Processing Systems 36. 2023: 10088-10115.",
  "[7] JOCHER G, QIU J. Ultralytics YOLO11[EB/OL]. (2024)[2026-11-14]. https://docs.ultralytics.com/models/yolo11/.",
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
  const out = "实验五报告_循智EcoSort_v3.docx";
  fs.writeFileSync(out, buf);
  console.log("done:", out);
});

"""Build the course report from recorded measurements; run with bundled document Python."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR'] = str(ROOT / '.matplotlib')
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    bench = read('outputs/benchmark/summary.json')
    env = read('records/environment.json')
    structure = read('records/model_structure.json')
    export = read('records/export.json')
    audit = read('records/original_files_verification.json')
    if not audit['passed']:
        raise RuntimeError('Original-files audit failed')
    results = {(split,name):read(f'outputs/evaluation/{split}/{name}/summary.json')
               for split in ('val','test') for name in ('pytorch_fp32','tensorrt_fp16')}
    figures = ROOT / 'reports/figures'
    measurements=bench['measurements']
    a,b=results['test','pytorch_fp32'],results['test','tensorrt_fp16']
    output=ROOT/'reports/实验三报告_循智EcoSort.docx'
    document=Document()
    sec=document.sections[0]
    sec.page_width,sec.page_height=Inches(8.27),Inches(11.69)
    sec.top_margin,sec.bottom_margin=Inches(.72),Inches(.72)
    sec.left_margin,sec.right_margin=Inches(.82),Inches(.82)
    for sty in ('Normal','Title','Subtitle','Heading 1','Heading 2','Caption'):
        style=document.styles[sty]
        style.font.name='Microsoft YaHei';style.font.color.rgb=RGBColor(0,0,0)
        style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei')
    normal=document.styles['Normal'];normal.font.size=Pt(10)
    normal.paragraph_format.line_spacing=1.2;normal.paragraph_format.space_after=Pt(6)
    document.styles['Title'].font.size=Pt(21)
    document.styles['Heading 1'].font.size=Pt(14)
    document.styles['Heading 1'].paragraph_format.space_before=Pt(12)
    document.styles['Heading 1'].paragraph_format.space_after=Pt(7)
    markdown=[]

    def title(text):
        document.add_paragraph(text,'Title');markdown.extend(['# '+text,''])

    def heading(text):
        document.add_paragraph(text,'Heading 1');markdown.extend(['## '+text,''])

    def paragraph(text):
        document.add_paragraph(text);markdown.extend([text,''])

    def table(headers,rows,widths=None):
        t=document.add_table(rows=1, cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER
        t.autofit=False
        for c,h in zip(t.rows[0].cells,headers):c.text=str(h)
        for row in rows:
            for c,v in zip(t.add_row().cells,row):c.text=str(v)
        for i,row in enumerate(t.rows):
            props=row._tr.get_or_add_trPr()
            if i==0:
                repeat=OxmlElement('w:tblHeader');props.append(repeat)
            cant=OxmlElement('w:cantSplit');props.append(cant)
            for j,cell in enumerate(row.cells):
                if widths:cell.width=Inches(widths[j])
                cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                tcpr=cell._tc.get_or_add_tcPr()
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E7EDF2' if i==0 else ('F6F8FA' if i%2==0 else 'FFFFFF'));tcpr.append(shade)
                borders=OxmlElement('w:tcBorders')
                for edge in ('top','left','bottom','right'):
                    el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
                tcpr.append(borders)
                margins=OxmlElement('w:tcMar')
                for edge in ('top','left','bottom','right'):
                    el=OxmlElement('w:'+edge);el.set(qn('w:w'),'70');el.set(qn('w:type'),'dxa');margins.append(el)
                tcpr.append(margins)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(2)
                    p.paragraph_format.line_spacing=1.1
                    if j>0:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    for run in p.runs:run.font.size=Pt(9);run.bold=i==0
        document.add_paragraph('').paragraph_format.space_after=Pt(1)
        markdown.extend(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |'])
        markdown.extend('| '+' | '.join(map(str,row))+' |' for row in rows);markdown.append('')

    def figure(filename,caption,width=6.4):
        document.add_picture(str(figures/filename),width=Inches(width))
        p=document.add_paragraph(caption,'Caption');p.paragraph_format.space_after=Pt(7)
        markdown.extend([f'![{caption}](figures/{filename})',''])

    def page():document.add_page_break()

    title('循智 EcoSort 实验三算法优化报告')
    paragraph('AI全栈开发实验  第8组  2026年10月26日')
    heading('实验内容与主要结果')
    test_loss=(a['map50_95']-b['map50_95'])*100
    cmp_model=next(c for c in bench['comparisons'] if c['scope']=='model' and c['batch']==1)
    cmp_pipe=next(c for c in bench['comparisons'] if c['scope']=='pipeline' and c['batch']==1)
    paragraph(f'本实验完成任务3.1.4推理加速优化，使用实验二已训练的YOLO11n A组主模型，通过ONNX转换和TensorRT FP16构建优化引擎。在同一张RTX 4070 SUPER上，单图模型推理延迟降低{cmp_model["latency_reduction_percent"]:.2f}%，含预处理与后处理的单图流程延迟降低{cmp_pipe["latency_reduction_percent"]:.2f}%。测试集mAP50-95由{a["map50_95"]*100:.4f}%变为{b["map50_95"]*100:.4f}%，绝对损失为{test_loss:.4f}个百分点。')
    paragraph('本轮只开展阶段一的该项优化，不重新训练，不开展量化、剪枝、蒸馏及阶段二异构部署。所有代码、配置、模型副本、数据副本和输出均位于experiment3。')
    heading('小组成员与分工')
    paragraph('成员名单沿用实验二。下表列出实验三建议分工，实际分工由成员确认；建议不作为成员已独立完成相应工作的事实记录。')
    members=[['2610321131','孟琦','环境配置与导出验证'],['2610321146','杜路明','ONNX及TensorRT引擎构建'],['2610321114','张浩','实验记录与报告整理'],['2610320013','邵英豪','检测精度与逐类分析'],['2610320010','屈欣皓','预测流程与案例核对'],['2610321139','姚瑞航','测速与输入完整性校验']]
    table(['学号','姓名','实验三建议分工'],members,[1.5,.8,4.0])

    page();heading('实验环境与数据')
    table(['项目','实际运行配置'],[
        ['操作系统',env['platform']],['Python',env['python'].split(' (')[0]],['GPU',env['gpu']],
        ['显存与驱动',f'{env["gpu_memory_bytes"]/1024**3:.2f} GiB；{env["nvidia_smi"].split(",")[-1].strip()}'],
        ['PyTorch与CUDA',f'{env["packages"]["torch"]}；CUDA {env["cuda"]}'],
        ['Ultralytics',env['packages']['ultralytics']],['TensorRT',export['tensorrt_version']],
        ['输入', 'RGB 640×640；batch=1和32；单GPU']], [1.4,4.9])
    paragraph('本轮环境独立于实验二历史训练环境。速度比较均在当前电脑重新测量，没有将RTX 5060 Laptop GPU的历史耗时与当前桌面GPU对比。模型来自实验二A组best.pt，输入副本逐文件进行SHA256校验。')
    table(['子集','图片数','目标数','用途'],[['验证集','1,053','14,725','运行验证及测速输入'],['测试集','1,053','12,536','固定方案最终精度对比']],[1.2,1.0,1.0,3.1])
    paragraph('本任务是十类多目标检测，使用mAP50-95、mAP50、Precision和Recall替代任务书分类示例中的Top-1准确率。精度损失目标解释为mAP50-95绝对损失不超过1个百分点，并同时报告相对变化。训练数据不参与本轮优化：FP16引擎不需要INT8校准，也不需要重新训练。')
    heading('优化方法与控制变量')
    paragraph('从同一checkpoint导出ONNX，再构建TensorRT FP16动态引擎，最大batch为32，workspace上限4 GiB，NMS保留在统一的后处理流程。TensorRT可执行算子融合和计算策略选择；允许部分层保留FP32，不将整个引擎描述为所有算子均FP16。')
    paragraph('两种后端使用相同图像、类别顺序和后处理参数。完整精度评估固定conf=0.001、NMS IoU=0.7、max_det=300、rect=False、batch=32、workers=0，不启用测试时增强。方案在测试评估前固定，未根据测试结果调整阈值或模型。')

    page();heading('推理延迟与吞吐量')
    speed_rows=[]
    for r in measurements:
        speed_rows.append(['模型' if r['scope']=='model' else '流程',str(r['batch']),
                           'FP32' if r['backend']=='pytorch_fp32' else 'TRT FP16',
                           f'{r["mean_ms_per_batch"]:.3f}',f'{r["p95_ms_per_batch"]:.3f}',
                           f'{r["throughput_images_per_second"]:.1f}'])
    table(['口径','Batch','后端','均值 ms/批','P95 ms/批','吞吐量 图/秒'],speed_rows,[.55,.55,1.15,1.35,1.35,1.35])
    paragraph('模型口径从GPU驻留输入到网络原始输出，不含输入上传、预处理和NMS。流程口径从已解码CPU图片开始，包含预处理、输入上传、模型推理、NMS及Results封装，不含磁盘读取、绘图和保存。两种口径均使用CUDA同步的主机计时，不将异步提交耗时当作完成耗时。')
    figure('01_latency.png','图1 同机不同batch与测量口径下的平均批次延迟')
    paragraph('每个条件执行3轮，各轮开始预热30次；模型口径每轮B1测100次、B32测40次，流程口径分别测50次、20次。轮间交替后端顺序。均值用于延迟与吞吐量计算，同时保存中位数、P95、标准差及全部逐次记录；这些重复是运行计时重复，不是独立训练重复。')

    page();heading('目标核对与检测精度')
    target_rows=[]
    for c in bench['comparisons']:
        target_rows.append([('模型' if c['scope']=='model' else '流程')+f' B{c["batch"]}',
                            f'{c["latency_reduction_percent"]:.2f}%',f'{c["throughput_increase_percent"]:.2f}%',
                            '达到' if c['latency_target_pass'] and c['throughput_target_pass'] else '未全部达到'])
    table(['条件','延迟降低 目标≥40%','吞吐提升 目标≥50%','判断'],target_rows,[1.0,1.8,1.8,1.5])
    paragraph('批量32的模型推理加速没有等比例传导到完整流程。流程还包含预处理、上传、NMS和接口管理等共同开销；本轮未逐项剖析，不能精确归因到某一项。该条件的流程加速目标未达到，不能将模型计时替代为整体应用速度。')
    accuracy=[]
    for (split,name),r in results.items():
        accuracy.append([('验证' if split=='val' else '测试')+' '+('FP32' if name=='pytorch_fp32' else 'TRT FP16'),
                         *[f'{r[k]*100:.4f}%' for k in ('precision','recall','map50','map50_95')]])
    table(['子集与后端','Precision','Recall','mAP50','mAP50-95'],accuracy,[1.6,1.15,1.15,1.15,1.15])
    relative=(a['map50_95']-b['map50_95'])/a['map50_95']*100
    paragraph(f'测试集mAP50-95绝对损失{test_loss:.4f}个百分点，相对变化为{-relative:+.4f}%。按绝对损失≤1个百分点的口径，精度目标{"达到" if test_loss<=1 else "未达到"}。Precision和Recall为框架选择工作点的类别平均值，不能用单一Precision排名替代检测AP比较。')
    paragraph('实验二历史评估使用rect=True、batch=16，本轮统一rect=False、batch=32，历史mAP不作为本轮基线。PyTorch关闭TF32，TensorRT采用默认策略，个别层可能保留FP32或TF32。')

    page();heading('逐类精度与误差分布')
    class_rows=[]
    for ca,cb in zip(a['per_class'],b['per_class']):
        class_rows.append([ca['class_name_zh'],str(ca['instances']),f'{ca["ap50_95"]*100:.3f}%',
                           f'{cb["ap50_95"]*100:.3f}%',f'{(cb["ap50_95"]-ca["ap50_95"])*100:+.4f}'])
    table(['类别','目标数','FP32 AP','FP16 AP','变化 百分点'],class_rows,[1.6,.7,1.2,1.2,1.5])
    figure('04_error_distribution.png','图2 各类别AP50-95变化热力图 FP16减FP32')
    paragraph('热力图表示检测AP的变化分布，不是分类错误率，也不是量化噪声的直接测量。食物残余和玻璃等类别样本很少，细小的数值变化不能证明少数类泛化能力改善。各类既有误差和FP16转换带来的差异需要分开解释。')

    page();heading('混淆变化与数据特点分析')
    figure('05_confusion_change.png','图3 测试集列归一化混淆矩阵变化 FP16减FP32',6.0)
    paragraph('混淆矩阵纵轴为预测、横轴为真实类别。各矩阵先按真实类别列归一化，再计算差值；背景行反映漏检，背景列反映误检的类别分布。框架混淆矩阵采用其独立默认统计阈值，不等同于整条PR曲线的AP或表中P/R工作点。')
    paragraph('实验一同时包含工业分拣与户外垃圾，类别分布偏向塑料和复合包装。多目标、小目标、遮挡和材质外观相近等特点增加检测难度。FP16减少数值精度，可能使临界置信度或IoU附近的候选框发生变化；本实验通过逐类AP和混淆差值观察结果，未开展逐层误差消融，因此不将某一结构或样本因素认定为变化的确定原因。')

    page();heading('模型资源与结论')
    table(['项目','PyTorch FP32','TensorRT FP16'],[
        ['逻辑网络参数量',f'{structure["parameters"]:,}','相同网络'],
        ['理论计算量 640输入',f'{structure["gflops_at_640"]:.3f} GFLOPs','相同算法计算量'],
        ['序列化文件大小',f'{structure["checkpoint_bytes"]/1024**2:.3f} MiB',f'{export["engine_bytes"]/1024**2:.3f} MiB']], [2.1,2.1,2.1])
    paragraph('结构统计采用未融合原网络；两种后端均使用推理时融合。本次采用执行精度和推理引擎优化，未进行结构剪枝，不能宣称参数量或理论FLOPs减少。原始.pt中的权重存储精度与运行FP32不同，且引擎包含执行策略和元数据，两种文件大小仅按实际部署产物报告，不用于证明权重压缩率。PyTorch内存统计不覆盖TensorRT外部分配，本实验不据此报告总显存节省比例。')
    all_speed=all(c['latency_target_pass'] and c['throughput_target_pass'] for c in bench['comparisons'])
    paragraph(f'本轮完成模型导出、真实图片预测、完整验证与测试评估，以及两种batch、两种口径的推理测速。速度目标{"均达到" if all_speed else "存在未达项，见目标核对表"}；测试集精度损失目标{"达到" if test_loss<=1 else "未达到"}。本次结果支持在当前GPU和固定输入配置下采用TensorRT FP16加速，不代表跨GPU、CPU或校园新场景的性能保证。')
    paragraph(f'原文件保护检查覆盖实验一和实验二共{audit["files_checked"]:,}个文件，新增、缺失或内容变化为0。完整输入校验清单、环境版本、导出记录、评估数据和逐次耗时均在experiment3保存。')
    heading('复现与参考资料')
    paragraph('运行顺序为initialize、export、smoke、val、test、benchmark，详见experiment3/README.md；使用本目录.venv解释器和requirements-lock.txt固定环境。已存在结果时脚本拒绝覆盖，复现实验应使用新的目录。TensorRT引擎需匹配GPU架构与运行时，新机器应重新构建。')
    paragraph('1 实验3任务书，第2页3.1模块及第4至5页任务3.1.4。')
    paragraph('2 Ultralytics TensorRT集成文档 https://docs.ultralytics.com/integrations/tensorrt/ 访问日期2026年10月26日。')
    paragraph('3 NVIDIA TensorRT最佳实践 https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/best-practices.html')
    paragraph('4 本实验实现依据为固定安装的Ultralytics 8.4.175源码；具体导出参数以configs/protocol.json及records/export.json为准。')
    # Remove inherited title/paragraph rules from the stock OOXML styles.
    for element in (document.element, document.styles.element):
        for border in element.xpath('.//w:pBdr'):
            border.getparent().remove(border)
    document.save(output)
    (ROOT/'reports/experiment3_results.md').write_text('\n'.join(markdown),encoding='utf-8')
    summary={'test_map_loss_percentage_points':test_loss,'test_map_relative_change_percent':-relative,
             'accuracy_target_pass':test_loss<=1,'all_speed_targets_pass':all_speed,
             'comparisons':bench['comparisons'],'originals_unchanged':audit['passed']}
    (ROOT/'reports/completion_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(output)


if __name__=='__main__':main()

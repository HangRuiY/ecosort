"""Remove draft instructions from the current report without rebuilding it."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import json, shutil, hashlib, re

ROOT = Path(__file__).resolve().parent
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
EDITS = {
    '本轮已完成真实GPU导出': [('同时保留批量32完整流程仅降低0.94%的未达标结果，避免把模型内核加速直接写成整个应用等比例加速。', '批量32完整流程的延迟仅降低0.94%，未达到速度目标，表明模型执行加速与应用整体加速存在差异。')],
    '总体流程为': [('验证集用于确认运行链路', '验证集用于检查运行链路')],
    '动态profile由': [('不能把“支持动态形状”写成已验证任意分辨率或任意batch的性能。', '本轮性能结论仅适用于上述输入尺寸和批量设置。')],
    'quantize=16是': [('更换版本后需要重新验证导出接口，不能把本次通过的结果无条件移植到其他框架版本。', '本次导出接口与运行结果对应锁定的框架版本，其他版本的接口兼容性不属于本轮测试范围。')],
    '首先用验证集按文件名': [('小样本检查只用于确认链路可运行及发现明显异常', '小样本检查用于检验链路运行情况及发现明显异常')],
    '报告整理只读取正式实验记录': [('报告整理只读取正式实验记录，没有为扩写正文重新训练、导出模型、重复查看测试结果调参或重跑正式测速。新增的案例统计从已经保存的预测JSON与相应验证标签计算，额外图表也由原始CSV、摘要和混淆矩阵生成，从而将报告修订与实验结果变化分开。', '实验分析使用已保存的正式运行记录。案例统计由预测JSON与对应验证标签计算，延迟图表由逐次计时CSV汇总生成，精度对照和混淆差值由完整评估摘要及混淆矩阵计算得到。各项图表与原始记录保持对应，便于复核实验结果。')],
    '原始模型和流程计时来自': [('后续若针对批量流程改进，应另存验证方案并增加分阶段profile；本轮将未达标项作为结果保留，不通过隐藏该条件或更换测试样本获得表面上的全项达标。', '本轮记录反映了批量流程加速有限的现象，但不提供各处理阶段的独立耗时；因此，未达标结论与具体瓶颈归因分别处理。')],
    '数据准备阶段保存实验一': [('该措施既落实文件隔离要求，也便于确认本轮改动只属于实验三，没有意外改变前两次实验的权重或报告。', '校验结果表明本轮改动仅发生在实验三，前两次实验的权重和报告保持不变。')],
    '模型副本SHA256与': [('真实预测生成的可视化和JSON进一步确认优化引擎能够进入完整Python调用流程。', '真实预测生成的可视化和JSON表明优化引擎已接入完整Python调用流程。')],
    'batch=32流程从': [('两种后端的P95和轮间波动也需要同时查看；均值差异较小，本轮没有统计检验，不将其写成稳定、显著的批量整体性能改善。', '结合两种后端的P95与轮间波动，均值差异较小，且本轮未进行统计检验，现有结果不足以支持稳定、显著的批量整体性能改善。')],
    '此结果对工程判断很重要': [('此结果对工程判断很重要：后续若主要处理单张上传图片，当前方案已有明确收益；若主要以32张组成批次，则不能只根据纯模型吞吐量部署并承诺相同比例的总体提速。需要进一步检查调用和数据处理过程，但该后续工作没有在本轮完成，也没有被写成现有成果。', '从应用场景看，当前方案在单张图片处理方面已有明确收益；在32张图片组成批次时，完整流程的提升有限，纯模型吞吐量不能代表整体处理速度。本轮未测量调用和数据处理各阶段的独立耗时，因此批量流程瓶颈尚无直接的分阶段计时依据。')],
    '图中变化为后端执行差异': [('本轮可以确认完整指标差异很小、局部混淆有变化；不能进一步认定某一层、某种材质反光或某个数据来源是已经证明的原因。', '本轮结果表明完整指标差异很小、局部混淆存在变化；现有证据不支持将变化归因于某一网络层、材质反光或特定数据来源。')],
    '后续若继续优化': [('后续若继续优化，应先在新的验证安排下对批量流程增加分阶段profile，定位实际开销，再比较预处理组织、内存搬运和后处理实现。其他优化方向、CPU或边缘部署、多设备对照及新增训练实验均留待后续任务，不列为本轮已完成内容。继续调整时应使用新的结果目录，保留当前固定方案的最终记录，不根据已查看的测试案例反复修改阈值并混用结论。', '后续优化方向主要包括批量流程的分阶段性能分析，以及预处理组织、内存搬运和后处理实现的改进。CPU或边缘部署、多设备对照与新增训练实验属于后续研究范围。本轮结论以当前固定模型、输入设置和完整评估记录为依据。')],
}


def main():
    report = ROOT / 'reports/实验三报告_循智EcoSort.docx'
    records = ROOT / 'records/final_language_review'
    records.mkdir(exist_ok=True)
    backup = records / 'before.docx'
    if not backup.exists(): shutil.copy2(report, backup)
    with ZipFile(report) as z:
        entries = [(info, z.read(info.filename)) for info in z.infolist()]
    xml = etree.fromstring(dict((i.filename, v) for i, v in entries)['word/document.xml'])
    changes = []
    for prefix, replacements in EDITS.items():
        matches = [p for p in xml.xpath('.//w:p', namespaces=NS) if ''.join(p.xpath('.//w:t/text()', namespaces=NS)).startswith(prefix)]
        assert len(matches) == 1, prefix
        p = matches[0]
        assert not p.xpath('.//w:hyperlink|.//w:drawing', namespaces=NS)
        nodes = p.xpath('.//w:t', namespaces=NS)
        before = ''.join(n.text or '' for n in nodes)
        after = before
        for old, new in replacements:
            assert old in after, old
            after = after.replace(old, new)
        nodes[0].text = after
        for node in nodes[1:]: node.text = ''
        changes.append({'before': before, 'after': after})
    # Keep the verified member roster; remove the unverified suggested duties.
    cover = xml.xpath('.//w:tbl', namespaces=NS)[0]
    grid = cover.find(W + 'tblGrid')
    columns = list(grid)
    total = sum(int(c.get(W + 'w')) for c in columns)
    for c in columns: grid.remove(c)
    widths = [total // 2, total - total // 2]
    for width in widths: etree.SubElement(grid, W + 'gridCol', {W + 'w': str(width)})
    for row in cover.findall(W + 'tr'):
        cells = row.findall(W + 'tc')
        assert len(cells) == 3
        row.remove(cells[2])
        for cell, width in zip(cells[:2], widths):
            cell.find(W + 'tcPr').find(W + 'tcW').set(W + 'w', str(width))
    serialized = etree.tostring(xml, encoding='UTF-8', xml_declaration=True, standalone=True)
    temp = report.with_suffix('.review-tmp.docx')
    with ZipFile(temp, 'w') as z:
        for info, value in entries: z.writestr(info, serialized if info.filename == 'word/document.xml' else value)
    temp.replace(report)
    # Keep editable prose sources consistent without regenerating the user's DOCX.
    for source in [ROOT / 'build_report.py', ROOT / 'reports/experiment3_results.md']:
        content = source.read_text(encoding='utf-8')
        for replacements in EDITS.values():
            for old, new in replacements: content = content.replace(old, new)
        content = content.replace('第8组；2026年10月26日。封面名单沿用实验二，实验三分工为建议，需成员确认。', '第8组；2026年10月26日。')
        source.write_text(content, encoding='utf-8')
    result = {'paragraphs_revised': len(changes), 'removed_cover_suggested_duties': True, 'changes': changes,
              'output_sha256': hashlib.sha256(report.read_bytes()).hexdigest()}
    (records / 'revision.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print({'paragraphs_revised': len(changes), 'cover_columns': 2})


if __name__ == '__main__': main()

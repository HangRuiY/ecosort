"""Patch the user's current DOCX bibliography without rebuilding the report."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from copy import deepcopy
import ast,hashlib,json,re,shutil
from lxml import etree

ROOT=Path(__file__).resolve().parent
REV=ROOT/'records/reference_revision'
DOC=ROOT/'reports/实验三报告_循智EcoSort.docx'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W}

REFERENCES=[
    '[1] REDMON J, DIVVALA S, GIRSHICK R, et al. You Only Look Once: Unified, Real-Time Object Detection[C]//2016 IEEE Conference on Computer Vision and Pattern Recognition. 2016: 779-788. DOI: 10.1109/CVPR.2016.91.',
    '[2] PROENÇA P F, SIMÕES P. TACO: Trash Annotations in Context for Litter Detection[EB/OL]. (2020-03-16)[2026-10-26]. https://arxiv.org/abs/2003.06975. DOI: 10.48550/arXiv.2003.06975.',
    '[3] CHEN T, MOREAU T, JIANG Z, et al. TVM: An Automated End-to-End Optimizing Compiler for Deep Learning[C]//13th USENIX Symposium on Operating Systems Design and Implementation. USENIX Association, 2018: 578-594.',
    '[4] MICIKEVICIUS P, NARANG S, ALBEN J, et al. Mixed Precision Training[C/OL]//International Conference on Learning Representations. 2018[2026-10-26]. https://openreview.net/forum?id=r1gs9JgRZ.',
    '[5] PASZKE A, GROSS S, MASSA F, et al. PyTorch: An Imperative Style, High-Performance Deep Learning Library[C]//Advances in Neural Information Processing Systems. 2019, 32: 8024-8035.',
    '[6] BODLA N, SINGH B, CHELLAPPA R, et al. Soft-NMS—Improving Object Detection with One Line of Code[C]//2017 IEEE International Conference on Computer Vision. 2017: 5562-5570. DOI: 10.1109/ICCV.2017.593.',
    '[7] LIN T Y, MAIRE M, BELONGIE S, et al. Microsoft COCO: Common Objects in Context[C]//Computer Vision—ECCV 2014. Cham: Springer, 2014: 740-755. DOI: 10.1007/978-3-319-10602-1_48.',
    '[8] AMDAHL G M. Validity of the Single Processor Approach to Achieving Large Scale Computing Capabilities[C]//Proceedings of the April 18-20, 1967, Spring Joint Computer Conference. New York: ACM, 1967: 483-485. DOI: 10.1145/1465482.1465560.'
]

SOURCES=[
    {'id':1,'sources':['https://openaccess.thecvf.com/content_cvpr_2016/html/Redmon_You_Only_Look_CVPR_2016_paper.html','https://api.crossref.org/works/10.1109/CVPR.2016.91'],'supports':'YOLO family detection background; not a claim that the original paper describes YOLO11.'},
    {'id':2,'sources':['https://arxiv.org/abs/2003.06975','https://github.com/pedropro/TACO'],'supports':'TACO dataset background; explicitly an arXiv preprint, not journal publication.'},
    {'id':3,'sources':['https://www.usenix.org/conference/osdi18/presentation/chen','https://www.usenix.org/system/files/osdi18-chen.pdf'],'supports':'Graph/operator compiler optimization principles; TVM is not claimed to have been used. Pagination follows official USENIX BibTeX.'},
    {'id':4,'sources':['https://arxiv.org/abs/1710.03740','https://openreview.net/pdf?id=r1gs9JgRZ'],'supports':'FP16 numerical range and precision background; training results are not used to substantiate this inference speedup.'},
    {'id':5,'sources':['https://proceedings.neurips.cc/paper/2019/hash/bdbca288fee7f92f2bfa9f7012727740-Abstract.html','https://papers.neurips.cc/paper/9015-pytorch-an-imperative-style-high-performance-deep-learning-library.pdf'],'supports':'PyTorch framework background; does not substitute for the current API/runtime records.'},
    {'id':6,'sources':['https://api.crossref.org/works/10.1109/ICCV.2017.593','https://ieeexplore.ieee.org/document/8237855','https://arxiv.org/abs/1704.04503'],'supports':'NMS role and alternatives; the experiment does not claim to implement Soft-NMS. IEEE/Crossref pages 5562-5570 used; CVF PDF pagination differs.'},
    {'id':7,'sources':['https://api.crossref.org/works/10.1007/978-3-319-10602-1_48','https://link.springer.com/chapter/10.1007/978-3-319-10602-1_48'],'supports':'COCO detection-evaluation background.'},
    {'id':8,'sources':['https://api.crossref.org/works/10.1145/1465482.1465560','https://doi.org/10.1145/1465482.1465560','https://www.usenix.org/system/files/tech-schedule/icac13_full_proceedings.pdf'],'supports':'Unaccelerated components limit end-to-end speedup; no fitted bottleneck fraction is inferred. Crossref supplies first page 483; full range 483-485 cross-checked in scholarly references.'}
]


def text(element):return ''.join(element.xpath('.//w:t/text()',namespaces=NS))


def replace_span(p,needle,replacement):
    nodes=p.xpath('.//w:t',namespaces=NS);whole=''.join(n.text or '' for n in nodes)
    if whole.count(needle)!=1:raise RuntimeError('Non-unique text anchor: '+needle)
    start=whole.index(needle);end=start+len(needle);pos=0;inserted=False
    for node in nodes:
        value=node.text or '';lo,hi=pos,pos+len(value);pos=hi
        if hi<=start or lo>=end:continue
        keep_left=value[:max(0,start-lo)] if lo<start else ''
        keep_right=value[max(0,end-lo):] if hi>end else ''
        node.text=keep_left+(replacement if not inserted else '')+keep_right
        node.set('{http://www.w3.org/XML/1998/namespace}space','preserve');inserted=True
    assert text(p)==whole.replace(needle,replacement,1)


def main():
    snapshot=json.loads((REV/'input_snapshot.json').read_text(encoding='utf-8'))
    if hashlib.sha256(DOC.read_bytes()).hexdigest()!=snapshot['sha256']:
        raise RuntimeError('The report changed after inspection; inspect the latest user version first.')
    with ZipFile(DOC) as z:original={i.filename:(i,z.read(i.filename)) for i in z.infolist()}
    tree=etree.fromstring(original['word/document.xml'][1]);body=tree.find('w:body',NS)
    paragraphs=body.findall('w:p',NS)
    heading=next(p for p in paragraphs if text(p).strip()=='七 参考文献')
    heading_pos=list(body).index(heading)
    body_paragraphs=[p for p in paragraphs if list(body).index(p)<heading_pos]
    changes=[]

    def change(prefix,old,new):
        p=next(p for p in body_paragraphs if text(p).startswith(prefix))
        before=text(p);replace_span(p,old,new);changes.append({'before':before,'after':text(p)})

    change('EcoSort的输入不是单一垃圾类别图片','模型需要输出每个目标的类别、置信度及边界框。','模型需要输出每个目标的类别、置信度及边界框[1]。')
    change('公共数据延续实验一的固定划分','TACO正式数据、TACO社区数据和SortWaste','TACO正式数据、TACO社区数据[2]和SortWaste')
    change('PyTorch FP32基线按32位浮点运行网络',
           'PyTorch FP32基线按32位浮点运行网络，TensorRT方案允许合适的算子采用16位浮点计算，并通过计算图优化和执行策略选择减少运行开销。',
           'PyTorch FP32基线按32位浮点运行网络，TensorRT方案允许合适的算子采用16位浮点计算。图级与算子级优化是深度学习编译的重要思路[3]，本轮通过TensorRT转换考察此类执行优化的实际效果。')
    change('PyTorch FP32基线按32位浮点运行网络','缩短推理时间[1-2]。','缩短推理时间。')
    change('FP16具有更低的数值精度','低精度计算后可能产生舍入差异。','低精度计算后可能产生舍入差异[4]。')
    change('动态profile由固定版本Ultralytics导出器创建','移动到新机器时应重新构建[1]。','移动到新机器时应重新构建。')
    change('脚本以自身目录解析相对路径','模型加载时核对固定十类名称和顺序',
           'PyTorch为GPU张量计算和模型执行提供框架支持[5]。模型加载时核对固定十类名称和顺序')
    change('预测入口使用OpenCV解码图片','按类别NMS。默认展示阈值',
           '按类别NMS。关于NMS处理重复候选框的作用及不同策略，可参见文献[6]。默认展示阈值')
    change('AP由精确率—召回率曲线计算','AP由精确率—召回率曲线计算。',
           '本实验采用COCO风格的目标检测评价体系[7]。AP由精确率—召回率曲线计算。')
    change('CUDA操作通常由CPU异步提交','保证记录包含该次工作的完成等待[3]。','保证记录包含该次工作的完成等待。')
    change('完整调用除了网络计算','共同开销也可能限制总流程改善。','共同开销也可能限制总流程改善[8]。')

    old_refs=[p for p in paragraphs if list(body).index(p)>heading_pos and text(p).strip().startswith('[')]
    template=deepcopy(old_refs[0]);reference_paragraphs=[]
    for entry in REFERENCES:
        p=deepcopy(template)
        for child in list(p):
            if child.tag!='{'+W+'}pPr':p.remove(child)
        run=etree.SubElement(p,'{'+W+'}r')
        rpr=template.find('w:r/w:rPr',NS)
        if rpr is not None:run.append(deepcopy(rpr))
        node=etree.SubElement(run,'{'+W+'}t');node.text=entry
        node.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
        reference_paragraphs.append(p)
    for child in list(body)[heading_pos+1:]:
        if child.tag!='{'+W+'}sectPr':body.remove(child)
    for i,p in enumerate(reference_paragraphs):body.insert(heading_pos+1+i,p)
    all_cited=[]
    for p in body_paragraphs:
        all_cited.extend(int(n) for n in re.findall(r'\[(\d+)\]',text(p)))
    assert set(all_cited)==set(range(1,9))
    assert all(not any(bad in ref for bad in ['课程实验资料','EcoSort项目组','实验一报告','实验二报告','任务书','Installed Source Code']) for ref in REFERENCES)
    assert text(list(body)[-2])==REFERENCES[-1] and list(body)[-1].tag=='{'+W+'}sectPr'

    # Keep future report generation consistent, without rebuilding the user's DOCX now.
    builder=ROOT/'build_report.py';source=builder.read_text(encoding='utf-8')
    for change_record in changes:
        old,new=change_record['before'],change_record['after']
        if source.count(old)!=1:raise RuntimeError('Generator paragraph anchor changed')
        source=source.replace(old,new,1)
    left=source.index('    refs=[');right=source.index('    for text in refs:',left)
    source=source[:left]+'    refs='+repr(REFERENCES)+'\n'+source[right:]
    left=source.index("    record_paragraph=para('结果文件定位：")
    right=source.index('\n\n    output=',left)
    source=source[:left]+source[right:]
    ast.parse(source)
    shutil.copy2(builder,REV/'build_report_before_reference_revision.py')
    xml=etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
    pending=REV/'revised_report.docx'
    with ZipFile(pending,'w',ZIP_DEFLATED) as z:
        for name,(info,data) in original.items():z.writestr(info,xml if name=='word/document.xml' else data)
    with ZipFile(pending) as z:
        assert all(z.read(name)==data for name,(_,data) in original.items() if name!='word/document.xml')
    shutil.copy2(pending,DOC)
    builder.write_text(source,encoding='utf-8')
    markdown=ROOT/'reports/experiment3_results.md';md=markdown.read_text(encoding='utf-8')
    for change_record in changes:md=md.replace(change_record['before'],change_record['after'])
    marker='# 七 参考文献'
    assert marker in md
    md=md.split(marker)[0]+marker+'\n\n'+'\n\n'.join(REFERENCES)+'\n'
    markdown.write_text(md,encoding='utf-8')
    report={'references':REFERENCES,'source_mapping':SOURCES,'in_text_changes':changes,
            'all_eight_references_cited':True,'citation_order':all_cited,
            'only_docx_package_part_modified':'word/document.xml',
            'post_bibliography_user_deletion_preserved':True,
            'output_sha256':hashlib.sha256(DOC.read_bytes()).hexdigest()}
    (REV/'reference_revision.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Replaced 8 bibliography entries; all 8 cited in order; user-deleted tail preserved.')


if __name__=='__main__':main()

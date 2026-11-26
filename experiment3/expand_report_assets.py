"""Read existing results only and prepare additional report figures and case audits."""
from pathlib import Path
from collections import Counter
import json, csv, os

ROOT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(ROOT/'.matplotlib')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image


def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))


def iou(a,b):
    w=max(0,min(a[2],b[2])-max(a[0],b[0]));h=max(0,min(a[3],b[3])-max(a[1],b[1]))
    intersection=w*h
    return intersection/max(1e-12,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


def coords(p):return [p['box'][k] for k in ['x1','y1','x2','y2']]


def main():
    out=ROOT/'reports/figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'axes.unicode_minus':False,'font.size':10,'savefig.dpi':220,
                         'axes.spines.top':False,'axes.spines.right':False})
    bench=read('outputs/benchmark/summary.json')
    for scope,title in [('model','模型推理批次延迟'),('pipeline','完整流程批次延迟')]:
        fig,ax=plt.subplots(figsize=(7.2,3.5),layout='constrained')
        x=np.arange(2)
        for j,(backend,label,color) in enumerate([('pytorch_fp32','PyTorch FP32','#4A6984'),('tensorrt_fp16','TensorRT FP16','#C88B46')]):
            rows=[next(r for r in bench['measurements'] if r['scope']==scope and r['batch']==batch and r['backend']==backend) for batch in [1,32]]
            bars=ax.bar(x+(j-.5)*.32,[r['mean_ms_per_batch'] for r in rows],.32,label=label,color=color)
            ax.bar_label(bars,fmt='%.3f',padding=3,fontsize=9)
        ax.set_xticks(x,['Batch 1','Batch 32']);ax.set_ylabel(title+' ms');ax.legend(frameon=False)
        ax.set_ylim(0,max(r['mean_ms_per_batch'] for r in bench['measurements'] if r['scope']==scope)*1.24)
        fig.savefig(out/f'06_{scope}_latency.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.2,3.7),layout='constrained')
    with (ROOT/'outputs/benchmark/iterations.csv').open(encoding='utf-8-sig') as f:raw=list(csv.DictReader(f))
    conditions=[(s,b) for s in ['model','pipeline'] for b in [1,32]]
    for backend,label,color in [('pytorch_fp32','FP32','#4A6984'),('tensorrt_fp16','TRT FP16','#C88B46')]:
        for index,(scope,batch) in enumerate(conditions):
            ys=[np.mean([float(r['latency_ms']) for r in raw if r['scope']==scope and int(r['batch'])==batch and r['backend']==backend and int(r['round'])==rnd]) for rnd in [1,2,3]]
            ax.plot(np.array([1,2,3])+index*4,ys,marker='o',color=color,label=label if index==0 else None)
    ax.set_xticks([2,6,10,14],['模型 B1','模型 B32','流程 B1','流程 B32'])
    ax.set_ylabel('各轮平均批次延迟 ms');ax.legend(frameon=False)
    fig.savefig(out/'07_round_stability.png');plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.2,2.3),layout='constrained');ax.set_xlim(0,10);ax.set_ylim(0,3);ax.axis('off')
    labels=['A组最佳权重\n独立复制与哈希','ONNX\n统一640输入','TensorRT FP16\n构建推理引擎','验证与测试\n精度一致性','B1与B32测速\n模型和流程']
    for i,label in enumerate(labels):
        x=i*2+.05;box=FancyBboxPatch((x,.95),1.78,1.0,boxstyle='round,pad=0.04',edgecolor='#4A6984',facecolor='#F1F4F6')
        ax.add_patch(box);ax.text(x+.89,1.45,label,ha='center',va='center',fontsize=9)
        if i<4:ax.annotate('',xy=(x+1.98,1.45),xytext=(x+1.79,1.45),arrowprops={'arrowstyle':'->','color':'#4A6984'})
    ax.text(5,.38,'同一模型  固定数据划分  统一后处理  全部结果写入experiment3',ha='center',fontsize=10)
    fig.savefig(out/'08_workflow.png');plt.close(fig)

    saved={name:{r['source']:r['detections'] for r in read(f'outputs/smoke_predictions/{name}/predictions.json')}
           for name in ['pytorch_fp32','tensorrt_fp16']}
    cases=[]
    for source in saved['pytorch_fp32']:
        gt=[]
        for line in (ROOT/'data/labels/val'/Path(source).with_suffix('.txt')).read_text().splitlines():
            cls,cx,cy,w,h=map(float,line.split());gt.append({'class':int(cls),'xyxy':[(cx-w/2)*640,(cy-h/2)*640,(cx+w/2)*640,(cy+h/2)*640]})
        case={'source':source,'ground_truth':len(gt),'backends':{}}
        for name in saved:
            preds=saved[name][source];used=set();tp=0
            for p in sorted(preds,key=lambda p:-p['confidence']):
                candidates=[(iou(coords(p),g['xyxy']),j) for j,g in enumerate(gt) if j not in used and p['class']==g['class']]
                if candidates:
                    score,j=max(candidates)
                    if score>=.5:used.add(j);tp+=1
            case['backends'][name]={'predictions':len(preds),'tp':tp,'fp':len(preds)-tp,'fn':len(gt)-tp}
        used=set();pairs=[]
        for p in saved['pytorch_fp32'][source]:
            candidates=[(iou(coords(p),coords(q)),j,q) for j,q in enumerate(saved['tensorrt_fp16'][source]) if j not in used and p['class']==q['class']]
            if candidates:
                score,j,q=max(candidates,key=lambda t:t[0])
                if score>=.5:
                    used.add(j);pairs.append({'class_id':p['class'],'iou':score,
                                             'confidence_abs_diff':abs(p['confidence']-q['confidence']),
                                             'max_coordinate_abs_diff_pixels':max(abs(x-y) for x,y in zip(coords(p),coords(q)))})
        case['matched_predictions_between_backends']=pairs;cases.append(case)
        fig,axes=plt.subplots(1,2,figsize=(7.2,3.85),layout='constrained')
        for ax,name,title in zip(axes,saved,['PyTorch FP32','TensorRT FP16']):
            ax.imshow(Image.open(ROOT/f'outputs/smoke_predictions/{name}'/Path(source).with_suffix('.jpg')))
            ax.set_title(f'{title}  预测{len(saved[name][source])}框',fontsize=10);ax.axis('off')
        fig.savefig(out/f'09_case_{Path(source).stem}.png');plt.close(fig)
    summary={'method':'Saved validation predictions only; same-class confidence-ordered greedy GT matching at IoU >= 0.5.',
             'selection':'First 4 validation images sorted by path; not a representative or random sample.',
             'cases':cases}
    (ROOT/'reports/prediction_case_analysis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True))


if __name__=='__main__':main()

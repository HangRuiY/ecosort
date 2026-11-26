"""Build the course report from recorded measurements; run with bundled document Python."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR'] = str(ROOT / '.matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


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
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'savefig.dpi':200})
    measurements=bench['measurements']
    labels=['模型 B1','模型 B32','流程 B1','流程 B32']
    keys=[(s,b) for s in ('model','pipeline') for b in (1,32)]
    fig,ax=plt.subplots(figsize=(7.4,3.2),layout='constrained')
    x=np.arange(4)
    for j,(name,color,label) in enumerate((('pytorch_fp32','#4A6984','PyTorch FP32'),('tensorrt_fp16','#C88B46','TensorRT FP16'))):
        values=[next(r['mean_ms_per_batch'] for r in measurements if (r['scope'],r['batch'],r['backend'])==(s,b,name)) for s,b in keys]
        bars=ax.bar(x+(j-.5)*.34,values,.34,label=label,color=color)
        ax.bar_label(bars,fmt='%.2f',padding=3,fontsize=8)
    ax.set_xticks(x,labels); ax.set_ylabel('平均批次延迟 ms'); ax.legend(frameon=False)
    ax.set_ylim(0,max(r['mean_ms_per_batch'] for r in measurements)*1.24)
    fig.savefig(figures/'01_latency.png'); plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.4,3.1),layout='constrained')
    values=[r['latency_reduction_percent'] for r in bench['comparisons']]
    bars=ax.bar(labels,values,color=['#4A6984','#4A6984','#C88B46','#C88B46'])
    ax.axhline(40,ls='--',color='#555555',lw=1,label='任务目标 40%')
    ax.bar_label(bars,fmt='%.1f%%',padding=3)
    ax.set_ylabel('延迟降低比例 %');ax.set_ylim(0,max(100,max(values)*1.15));ax.legend(frameon=False)
    fig.savefig(figures/'02_latency_reduction.png');plt.close(fig)

    a,b=results['test','pytorch_fp32'],results['test','tensorrt_fp16']
    names=[c['class_name_zh'] for c in a['per_class']]
    ap_a=np.array([c['ap50_95'] for c in a['per_class']])*100
    ap_b=np.array([c['ap50_95'] for c in b['per_class']])*100
    delta=ap_b-ap_a
    fig,ax=plt.subplots(figsize=(7.4,3.6),layout='constrained')
    x=np.arange(10)
    ax.bar(x-.18,ap_a,.36,label='PyTorch FP32',color='#4A6984')
    ax.bar(x+.18,ap_b,.36,label='TensorRT FP16',color='#C88B46')
    ax.set_xticks(x,names,rotation=35,ha='right');ax.set_ylabel('测试集 AP50-95 %');ax.legend(frameon=False)
    fig.savefig(figures/'03_per_class_ap.png');plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.4,2.9),layout='constrained')
    limit=max(.01,float(np.max(np.abs(delta))))
    im=ax.imshow(delta[:,None],cmap='RdBu_r',vmin=-limit,vmax=limit,aspect='auto')
    ax.set_yticks(np.arange(10),names);ax.set_xticks([0],['TensorRT FP16 减 PyTorch FP32'])
    for i,d in enumerate(delta):ax.text(0,i,f'{d:+.4f}',ha='center',va='center',fontsize=8,color='black' if abs(d)<limit*.6 else 'white')
    fig.colorbar(im,ax=ax,label='AP50-95 变化 百分点')
    fig.savefig(figures/'04_error_distribution.png');plt.close(fig)

    matrices=[]
    for name in ('pytorch_fp32','tensorrt_fp16'):
        matrix=np.load(ROOT/f'outputs/evaluation/test/{name}/confusion_matrix.npy')
        matrices.append(matrix/(matrix.sum(axis=0,keepdims=True)+1e-9))
    diff=(matrices[1]-matrices[0])*100
    fig,ax=plt.subplots(figsize=(7.4,5.5),layout='constrained')
    limit=max(.01,float(np.max(np.abs(diff))))
    im=ax.imshow(diff,cmap='RdBu_r',vmin=-limit,vmax=limit)
    cn=names+['背景']
    ax.set_xticks(np.arange(11),cn,rotation=45,ha='right',fontsize=8)
    ax.set_yticks(np.arange(11),cn,fontsize=8)
    ax.set_xlabel('真实类别');ax.set_ylabel('预测类别')
    for i in range(11):
        for j in range(11):
            if abs(diff[i,j])>=.01:ax.text(j,i,f'{diff[i,j]:+.2f}',ha='center',va='center',fontsize=6)
    fig.colorbar(im,ax=ax,label='列归一化比例变化 百分点',shrink=.85)
    fig.savefig(figures/'05_confusion_change.png');plt.close(fig)
    np.savetxt(ROOT/'reports/confusion_change_percentage_points.csv',diff,delimiter=',',header=','.join(cn),comments='',encoding='utf-8-sig')



if __name__ == "__main__": main()

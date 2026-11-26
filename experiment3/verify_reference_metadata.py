"""Read Crossref DOI metadata, retaining evidence for the bibliography revision."""
import json,time,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'records/reference_revision';OUT.mkdir(parents=True,exist_ok=True)
entries=[('yolo','10.1109/CVPR.2016.91'),('coco','10.1007/978-3-319-10602-1_48'),
         ('soft_nms','10.1109/ICCV.2017.593'),('amdahl','10.1145/1465482.1465560')]
records=[]
for key,doi in entries:
    for attempt in range(3):
        try:
            request=urllib.request.Request('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''),headers={'User-Agent':'EcoSort-reference-verification/1.0'})
            with urllib.request.urlopen(request,timeout=30) as response:data=json.load(response)
            (OUT/(key+'_crossref.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            m=data['message']
            record={'key':key,'doi':doi,'title':m.get('title'),'authors':m.get('author'),
                    'container':m.get('container-title'),'year':m.get('published'),
                    'page':m.get('page'),'publisher':m.get('publisher'),'status':'resolved'}
            records.append(record);print(json.dumps(record,ensure_ascii=True),flush=True);break
        except Exception as e:
            if attempt==2:records.append({'key':key,'doi':doi,'status':'unavailable','error':str(e)});print(key,str(e),flush=True)
            else:time.sleep(2)
(OUT/'crossref_summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')

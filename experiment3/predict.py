"""Single-image/folder detection using experiment3's copied or optimized model."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from run_experiment import ROOT, MODELS, YOLO, cv2, np, precision_args, environment
from prepare_inputs import sha256, write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True,help='Image or folder; relative paths are relative to experiment3')
    parser.add_argument('--backend',choices=list(MODELS),default='tensorrt_fp16')
    parser.add_argument('--batch',type=int,choices=(1,32),default=1)
    parser.add_argument('--conf',type=float,default=.25)
    parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args()
    if not 0<args.conf<=1 or args.limit<0:parser.error('Invalid confidence or limit')
    source=Path(args.source).expanduser()
    source=source if source.is_absolute() else ROOT/source
    suffixes={'.png','.jpg','.jpeg','.bmp','.webp','.tif','.tiff'}
    files=[source] if source.is_file() else sorted(p for p in source.iterdir() if p.suffix.lower() in suffixes)
    if args.limit:files=files[:args.limit]
    if not files or any(p.suffix.lower() not in suffixes for p in files):raise ValueError('No supported images')
    environment()
    now=datetime.now(timezone(timedelta(hours=8)))
    out=ROOT/'outputs/predictions'/f'{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}'
    out.mkdir(parents=True,exist_ok=False)
    model=YOLO(str(MODELS[args.backend]),task='detect')
    records=[];start=time.perf_counter()
    for offset in range(0,len(files),args.batch):
        paths=files[offset:offset+args.batch]
        images=[cv2.imdecode(np.fromfile(p,np.uint8),cv2.IMREAD_COLOR) for p in paths]
        if any(im is None for im in images):raise ValueError('Image decoding failed')
        results=model.predict(source=images,imgsz=640,batch=args.batch,device=0,rect=False,
                              conf=args.conf,iou=.7,max_det=300,verbose=False,
                              **precision_args(args.backend=='tensorrt_fp16'))
        for index,(path,result) in enumerate(zip(paths,results),start=offset+1):
            annotated=out/f'{index:06d}_{path.stem}.jpg'
            result.save(filename=str(annotated))
            records.append({'source':str(path.resolve()),'source_sha256':sha256(path),
                            'annotated':annotated.name,'detections':json.loads(result.to_json())})
    write_json(out/'predictions.json',{'backend':args.backend,'model_sha256':sha256(MODELS[args.backend]),
               'input_count':len(files),'duration_seconds':time.perf_counter()-start,
               'note':'Includes file reading/drawing/export; not the controlled benchmark latency.',
               'images':records})
    print(out)


if __name__=='__main__':main()

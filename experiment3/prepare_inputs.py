"""Copy inputs into experiment3 and audit experiment1/2 without modifying them."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def snapshot():
    return {
        p.relative_to(PROJECT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha256(p)}
        for folder in ('experiment1', 'experiment2')
        for p in sorted((PROJECT / folder).rglob('*')) if p.is_file()
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare():
    audit = ROOT / 'records' / 'original_files_before.json'
    if audit.exists():
        raise FileExistsError('Inputs already prepared; do not replace the original audit.')
    write_json(audit, snapshot())
    records = []

    def copy(source, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(destination)
        shutil.copy2(source, destination)
        original_hash, copied_hash = sha256(source), sha256(destination)
        if original_hash != copied_hash:
            raise RuntimeError(f'Copy verification failed: {source}')
        records.append({'source': source.relative_to(PROJECT).as_posix(),
                        'copy': destination.relative_to(ROOT).as_posix(),
                        'bytes': source.stat().st_size, 'sha256': copied_hash})

    source_run = PROJECT / 'experiment2/outputs/baseline/yolo11n_baseline_amp'
    copy(source_run / 'weights/best.pt', ROOT / 'models/baseline.pt')
    for name in ('train_summary.json', 'args.yaml', 'resolved_config.yaml'):
        copy(source_run / name, ROOT / 'records/experiment2_source' / name)
    for split in ('val', 'test'):
        for kind in ('images', 'labels'):
            for p in sorted((PROJECT / 'data/split' / kind / split).iterdir()):
                if p.is_file():
                    copy(p, ROOT / 'data' / kind / split / p.name)
        copy(PROJECT / f'data/split/{split}.json', ROOT / f'data/{split}.json')
    copy(PROJECT / 'data/split/data.yaml', ROOT / 'records/source_data.yaml')
    copy(PROJECT / 'experiment2/src/metrics.py', ROOT / 'src/metrics.py')
    (ROOT / 'src/__init__.py').touch()
    write_json(ROOT / 'records/input_manifest.json', {
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'copy_method': 'independent byte copies, no hardlinks or symlinks',
        'files': records,
    })
    print(f'Copied and SHA256-verified {len(records)} files; original snapshot saved.', flush=True)


def verify_originals():
    before = json.loads((ROOT / 'records/original_files_before.json').read_text(encoding='utf-8'))
    after = snapshot()
    changes = [k for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)]
    result = {'passed': not changes, 'files_checked': len(before), 'changes': changes}
    write_json(ROOT / 'records/original_files_verification.json', result)
    print(result)
    if changes:
        raise RuntimeError('Original files changed')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-originals', action='store_true')
    args = parser.parse_args()
    verify_originals() if args.verify_originals else prepare()

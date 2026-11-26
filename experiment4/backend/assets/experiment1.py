"""实验一：检查与处理输入数据，导出实验二的 COCO/YOLO 数据。

默认保留输入标注中的分组划分；--augment 可重新生成仅训练增强。
输入是已清洗、未增强的640像素工作数据，不是来源原分辨率图片。
"""
import argparse
import copy
import csv
import hashlib
import html
import json
import math
import os
import random
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageEnhance

try:
    from torch.utils.data import Dataset as BaseDataset
except ImportError:
    BaseDataset = object  # 实验一不要求安装torch；实验二安装后自动继承Dataset。

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
SPLITS = ('train', 'val', 'test')
SEED = 20261003
CLASS_NAMES_ZH = ['硬质塑料', '软质塑料', '形态不明塑料', '纸及纸板', '复合包装',
                  '金属', '玻璃', '食物残余', '烟蒂', '特殊及不明垃圾']


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def clean_box(box, width, height):
    """排除非法框，按图像边界裁剪xywh框。"""
    try:
        values = list(map(float, box))
    except (TypeError, ValueError):
        return None
    if len(values) != 4 or not all(math.isfinite(x) for x in values):
        return None
    x, y, w, h = values
    if w <= 0 or h <= 0:
        return None
    x1, y1 = max(0., x), max(0., y)
    x2, y2 = min(float(width), x + w), min(float(height), y + h)
    return [x1, y1, x2 - x1, y2 - y1] if x2 > x1 and y2 > y1 else None


def to_yolo(box, width, height):
    x, y, w, h = box
    return [(x + w / 2) / width, (y + h / 2) / height, w / width, h / height]


def frozen_or_group_split(images):
    """保留已验证的划分；无划分的新输入按整组确定约8:1:1。"""
    if all(r.get('split') in SPLITS for r in images):
        return {r['id']: r['split'] for r in images}
    groups = defaultdict(list)
    for r in images:
        groups[r.get('group_id', r['id'])].append(r)
    keys = list(groups)
    random.Random(SEED).shuffle(keys)
    assignment = {r['id']: 'train' for r in images}
    target = round(len(images) * .1)
    for split in ('val', 'test'):
        count = 0
        for key in keys:
            rows = groups[key]
            if assignment[rows[0]['id']] != 'train' or not all(r.get('annotation_reviewed', True) for r in rows):
                continue
            if abs(target - count - len(rows)) < abs(target - count):
                for r in rows:
                    assignment[r['id']] = split
                count += len(rows)
            if count == target:
                break
    return assignment


def link_or_copy(source, target):
    """相同像素优先使用硬链接，避免原始输入与划分目录重复占空间。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def remove_generated_folder(path):
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise ValueError('禁止清理链接输出目录')
    resolved = path.resolve()
    if resolved.parent != DATA.resolve() or resolved.name not in ('.split_build', '.split_previous'):
        raise ValueError(f'禁止删除非脚本输出目录：{resolved}')
    shutil.rmtree(resolved)


def write_config(output):
    categories = load_json(output / 'train.json')['categories']
    config = {'path': str((DATA / 'split').resolve()), 'train': 'images/train',
              'val': 'images/val', 'test': 'images/test',
              'names': {c['id']: c['name'] for c in categories}}
    (output / 'data.yaml').write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')


def prepare_features(table):
    """仅用真实训练图拟合数值范围，再转换三个子集，避免统计泄漏。"""
    ranges = {}
    for key in ('object_count', 'distinct_classes', 'brightness_mean', 'brightness_std',
                'entropy', 'laplacian_variance'):
        train = [float(r[key]) for r in table if r['split'] == 'train' and r.get(key) is not None]
        if not train:
            continue
        low, high = min(train), max(train)
        ranges[key] = {'min': low, 'max': high}
        for r in table:
            value = r.get(key)
            r[key + '_normalized'] = None if value is None else min(1., max(0., (float(value) - low) / (high - low))) if high > low else 0.
    return ranges


def prepare_documents(documents):
    """合并文本清洗与字符TF-IDF；不依赖外部服务，不把文本当图像真值。"""
    records, seen = [], set()
    for record in documents:
        text = html.unescape(re.sub(r'<[^>]*>', '', record['text']))
        text = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip()
        if 35 <= len(text) <= 1500 and text not in seen:
            records.append({**record, 'text': text})
            seen.add(text)
    bags = [Counter(text[i:i+n] for n in (2, 3, 4) for i in range(len(text)-n+1))
            for text in (r['text'].lower() for r in records)]
    frequencies, total = Counter(), Counter()
    for bag in bags:
        frequencies.update(bag.keys())
        total.update(bag)
    vocabulary = sorted(total, key=lambda t: (-total[t], t))[:6000]
    positions = {token: index for index, token in enumerate(vocabulary)}
    vectors = []
    for bag in bags:
        vector = {positions[t]: n * (1 + math.log((1 + len(records)) / (1 + frequencies[t])))
                  for t, n in bag.items() if t in positions}
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1.
        vectors.append({str(i): round(v / norm, 8) for i, v in vector.items()})
    return {'input_records': len(documents), 'output_records': len(records), 'records': records,
            'tfidf': {'method': 'character 2-4 grams, smoothed IDF, L2 normalization',
                      'vocabulary': vocabulary, 'sparse_rows': vectors},
            'usage': 'retrieval-only corpus; not image labels or held-out model evaluation'}


def process(augment=False, size=640):
    source = load_json(DATA / 'raw/annotations.json')
    category_ids = {c['id'] for c in source['categories']}
    if category_ids != set(range(len(source['categories']))):
        raise ValueError('YOLO类别必须从0开始连续编号')
    input_ids = [r['id'] for r in source['images']]
    input_id_set = set(input_ids)
    if len(input_ids) != len(input_id_set):
        raise ValueError('输入图像ID重复')
    if any(Path(r['file_name']).name != r['file_name'] for r in source['images']):
        raise ValueError('输入图片应直接放在raw/images下')
    annotation_ids = [a['id'] for a in source['annotations']]
    if len(annotation_ids) != len(set(annotation_ids)):
        raise ValueError('输入目标ID重复')
    if augment and (any(i >= 1000000 for i in input_ids) or any(i >= 1000000 for i in annotation_ids)):
        raise ValueError('增强保留1000000以上ID，请先调整输入ID')
    grouped = defaultdict(list)
    for a in source['annotations']:
        if a['image_id'] not in input_id_set:
            raise ValueError('目标引用了不存在的图像')
        grouped[a['image_id']].append(a)
    missing = [r['file_name'] for r in source['images'] if not (DATA / 'raw/images' / r['file_name']).is_file()]
    if missing:
        raise FileNotFoundError(f'缺少{len(missing)}张输入图片；没有修改已有划分数据')
    output = DATA / '.split_build'
    if output.exists():
        raise FileExistsError('存在未完成的data/.split_build，请先检查该临时目录')
    output.mkdir()
    assignment = frozen_or_group_split(source['images'])
    images = {s: [] for s in SPLITS}
    annotations = {s: [] for s in SPLITS}
    counters = Counter()
    table = []
    used_annotations = set()
    try:
        for number, record in enumerate(source['images'], 1):
            if Path(record['file_name']).name != record['file_name']:
                raise ValueError('输入图片应直接放在raw/images下')
            path = DATA / 'raw/images' / record['file_name']
            with Image.open(path) as picture:
                picture.load()
                old_w, old_h = picture.size
                if (old_w, old_h) != (record['width'], record['height']):
                    raise ValueError(f'像素与输入标注尺寸不一致：{path.name}')
                had_exif = bool(picture.getexif())
                scale = min(size / old_w, size / old_h)
                new_w, new_h = round(old_w * scale), round(old_h * scale)
                px, py = (size - new_w) // 2, (size - new_h) // 2
                sx, sy = new_w / old_w, new_h / old_h
                unchanged = picture.mode == 'RGB' and picture.size == (size, size) and not had_exif
                canvas = picture.convert('RGB')
                if canvas.size != (new_w, new_h):
                    canvas = canvas.resize((new_w, new_h), Image.Resampling.LANCZOS)
                if not unchanged:
                    result = Image.new('RGB', (size, size), (114, 114, 114))
                    result.paste(canvas, (px, py))
                    canvas = result
                canvas = Image.fromarray(np.asarray(canvas))
            rows = []
            seen = set()
            for original in grouped[record['id']]:
                box = clean_box(original['bbox'], old_w, old_h)
                if box is None or original['category_id'] not in category_ids:
                    counters['invalid_objects_removed'] += 1
                    continue
                signature = (original.get('raw_category_id', original['category_id']), *box)
                if signature in seen:
                    counters['duplicate_objects_removed'] += 1
                    continue
                seen.add(signature)
                if original['id'] in used_annotations:
                    raise ValueError('输入目标ID重复；需先修复原标注')
                used_annotations.add(original['id'])
                row = copy.deepcopy(original)
                x, y, w, h = box
                row['bbox'] = [x * sx + px, y * sy + py, w * sx, h * sy]
                counters['clipped_objects'] += not np.allclose(box, original['bbox'])
                polygons = []
                for polygon in original.get('segmentation', []):
                    points = np.asarray(polygon, dtype=float)
                    if len(points) < 6 or len(points) % 2 or not np.isfinite(points).all():
                        counters['invalid_polygons_removed'] += 1
                        continue
                    points = points.reshape(-1, 2)
                    points[:, 0] = np.clip(points[:, 0] * sx + px, 0, size)
                    points[:, 1] = np.clip(points[:, 1] * sy + py, 0, size)
                    polygons.append(points.ravel().tolist())
                row['segmentation'] = polygons
                if not unchanged:
                    row['area'] = sum(abs(np.dot(p[::2], np.roll(p[1::2], -1)) - np.dot(p[1::2], np.roll(p[::2], -1))) / 2 for p in polygons) if polygons else row['bbox'][2] * row['bbox'][3]
                rows.append(row)
            if not rows:
                counters['empty_images_removed'] += 1
                continue
            split = assignment[record['id']]
            filename = f"{record['id']:06d}.png"
            target = output / 'images' / split / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            if unchanged:
                link_or_copy(path, target)
            else:
                canvas.save(target, compress_level=1)
            counters['input_images_with_exif'] += had_exif
            item = {**record, 'file_name': filename, 'width': size, 'height': size,
                    'split': split, 'is_augmented': False, 'input_sha256': sha256(path)}
            images[split].append(item)
            annotations[split].extend(rows)
            table.append({'image_id': item['id'], 'file_name': filename, 'split': split,
                          'source_dataset': item.get('source_dataset'), 'object_count': len(rows),
                          'distinct_classes': len({a['category_id'] for a in rows}),
                          'group_id': item.get('group_id'), 'is_augmented': False,
                          **{k: item.get(k) for k in ('capture_date_known', 'individual_license_known',
                              'brightness_mean', 'brightness_std', 'entropy', 'laplacian_variance')}})
            if augment and split == 'train':
                rng = random.Random(SEED + record['id'])
                augmented = canvas.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                augmented = ImageEnhance.Brightness(augmented).enhance(rng.uniform(.9, 1.1))
                augmented = ImageEnhance.Contrast(augmented).enhance(rng.uniform(.9, 1.1))
                new_id = record['id'] + 1000000
                new_name = f'{new_id:07d}.png'
                augmented.save(output / 'images/train' / new_name, compress_level=1)
                images['train'].append({**item, 'id': new_id, 'file_name': new_name,
                                        'is_augmented': True, 'parent_image_id': record['id']})
                for row in rows:
                    a = copy.deepcopy(row)
                    x, y, w, h = a['bbox']
                    a.update(id=a['id'] + 1000000, image_id=new_id, bbox=[size - x - w, y, w, h])
                    a['segmentation'] = [np.column_stack([size - np.asarray(p).reshape(-1, 2)[:, 0], np.asarray(p).reshape(-1, 2)[:, 1]])[::-1].ravel().tolist() for p in a['segmentation']]
                    annotations['train'].append(a)
            if number % 1000 == 0:
                print(f'已处理 {number}/{len(source["images"])} 张图片', flush=True)
        for split in SPLITS:
            (output / 'images' / split).mkdir(parents=True, exist_ok=True)
            label_dir = output / 'labels' / split
            label_dir.mkdir(parents=True, exist_ok=True)
            by_image = defaultdict(list)
            for a in annotations[split]:
                by_image[a['image_id']].append(a)
            for item in images[split]:
                lines = [str(a['category_id']) + ' ' + ' '.join(f'{v:.8f}' for v in to_yolo(a['bbox'], size, size)) for a in by_image[item['id']]]
                (label_dir / Path(item['file_name']).with_suffix('.txt')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
            save_json(output / f'{split}.json', {'images': images[split], 'annotations': annotations[split],
                                               'categories': source['categories']})
        feature_ranges = prepare_features(table)
        with (output / 'images.csv').open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(table[0]) if table else ['image_id'])
            writer.writeheader()
            writer.writerows(table)
        summary = {'input_images': len(source['images']), 'input_objects': len(source['annotations']),
                   'real_images': len(table), 'real_objects': sum(r['object_count'] for r in table),
                   'split_images': {s: len(images[s]) for s in SPLITS},
                   'multi_class_images': sum(r['distinct_classes'] > 1 for r in table),
                   'class_counts': dict(Counter(a['category_id'] for s in SPLITS for a in annotations[s] if a['image_id'] in input_id_set)),
                   'augmentation_enabled': augment, 'processing_audit': dict(counters),
                   'feature_ranges_train_only': feature_ranges,
                   'text_processing': prepare_documents(source.get('documents', [])),
                   'input_annotation_sha256': sha256(DATA / 'raw/annotations.json'),
                   'input_state': source.get('info', {}).get('input_state'),
                   'historical_cleaning': source.get('info', {}).get('historical_cleaning_audit')}
        save_json(output / 'summary.json', summary)
        write_config(output)
        check(output, verify_images=False)
        previous = DATA / '.split_previous'
        if previous.exists():
            raise FileExistsError('存在data/.split_previous，请先检查此前输出')
        final = DATA / 'split'
        if final.exists():
            final.rename(previous)
        try:
            output.rename(final)
        except BaseException:
            if previous.exists():
                previous.rename(final)
            raise
        if previous.exists():
            remove_generated_folder(previous)
        print(json.dumps({k: summary[k] for k in ('real_images', 'real_objects', 'split_images',
                                                'augmentation_enabled', 'processing_audit')}, ensure_ascii=False, indent=2), flush=True)
    except BaseException:
        if output.exists():
            remove_generated_folder(output)
        raise


def check(output=None, verify_images=True):
    output = output or DATA / 'split'
    raw = load_json(DATA / 'raw/annotations.json')
    original_ids = {r['id'] for r in raw['images']}
    id_sets, group_sets, source_hash_sets = [], [], []
    annotation_ids = []
    count = Counter()
    real_ids, real_objects, class_counts = set(), 0, Counter()
    for split in SPLITS:
        d = load_json(output / f'{split}.json')
        assert d['categories'] == raw['categories']
        expected = set()
        by_image = defaultdict(list)
        for a in d['annotations']:
            by_image[a['image_id']].append(a)
            annotation_ids.append(a['id'])
        for r in d['images']:
            if r.get('is_augmented'):
                assert split == 'train' and r['parent_image_id'] in original_ids
            else:
                assert r['id'] in original_ids
                assert r['id'] not in real_ids
                real_ids.add(r['id'])
                real_objects += len(by_image[r['id']])
                class_counts.update(a['category_id'] for a in by_image[r['id']])
            assert r['split'] == split
            assert r.get('annotation_reviewed', True) or split == 'train'
            image = output / 'images' / split / r['file_name']
            label = output / 'labels' / split / Path(r['file_name']).with_suffix('.txt')
            assert image.is_file() and label.is_file(), str(image)
            if verify_images:
                with Image.open(image) as picture:
                    assert picture.size == (r['width'], r['height'])
                    picture.verify()
            lines = label.read_text(encoding='utf-8').splitlines()
            assert len(lines) == len(by_image[r['id']]) > 0
            for line, a in zip(lines, by_image[r['id']]):
                fields = line.split()
                assert int(fields[0]) == a['category_id']
                assert len(fields) == 5 and a['category_id'] in range(len(d['categories']))
                assert clean_box(a['bbox'], r['width'], r['height']) is not None
                assert np.allclose(list(map(float, fields[1:])), to_yolo(a['bbox'], r['width'], r['height']), atol=1e-7)
                x, y, w, h = a['bbox']
                assert x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= r['width'] + 1e-7 and y + h <= r['height'] + 1e-7
            expected.add(r['file_name'])
            count[split] += 1
        assert {p.name for p in (output / 'images' / split).glob('*.png')} == expected
        assert {p.name for p in (output / 'labels' / split).glob('*.txt')} == {Path(n).with_suffix('.txt').name for n in expected}
        assert len(expected) == len(d['images'])
        assert len({r['id'] for r in d['images']}) == len(d['images'])
        assert set(by_image) == {r['id'] for r in d['images']}
        id_sets.append({r['id'] for r in d['images']})
        group_sets.append({r.get('group_id', r['id']) for r in d['images']})
        source_hash_sets.append({r['source_sha256'] for r in d['images'] if r.get('source_sha256')})
    assert len(annotation_ids) == len(set(annotation_ids))
    for values in (id_sets, group_sets, source_hash_sets):
        for i in range(3):
            for j in range(i):
                assert not values[i] & values[j], '划分存在交叉'
    result = {'passed': True, 'split_images': dict(count), 'objects': len(annotation_ids)}
    summary = load_json(output / 'summary.json')
    assert summary['split_images'] == dict(count)
    assert summary['real_images'] == len(real_ids) and summary['real_objects'] == real_objects
    assert summary['class_counts'] == {str(k): v for k, v in class_counts.items()}
    assert summary['input_images'] == len(raw['images']) and summary['input_objects'] == len(raw['annotations'])
    summary['validation'] = result
    save_json(output / 'summary.json', summary)
    print('数据检查通过：' + json.dumps(result, ensure_ascii=False), flush=True)
    return result


class DetectionDataset(BaseDataset):
    """模块级类支持Windows多进程加载；每图保留可变数量的目标。"""
    def __init__(self, split='train', data_dir=None):
        import torch
        self.root = Path(data_dir) if data_dir else DATA / 'split'
        self.split = split
        d = load_json(self.root / f'{split}.json')
        self.images = d['images']
        self.annotations = defaultdict(list)
        for a in d['annotations']:
            self.annotations[a['image_id']].append(a)

    def __len__(self):
        return len(self.images)

    def __getitem__(self, index):
        import torch
        r = self.images[index]
        with Image.open(self.root / 'images' / self.split / r['file_name']) as picture:
            array = np.asarray(picture.convert('RGB'), dtype=np.float32) / 255.
        rows = self.annotations[r['id']]
        boxes = [[x, y, x + w, y + h] for x, y, w, h in (a['bbox'] for a in rows)]
        target = {'boxes': torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4),
                  'labels': torch.tensor([a['category_id'] for a in rows], dtype=torch.int64),
                  'image_id': torch.tensor([r['id']])}
        return torch.from_numpy(array.transpose(2, 0, 1)), target


def create_torch_dataset(split='train', data_dir=None):
    """实验二自定义PyTorch模型可直接调用此加载器。"""
    return DetectionDataset(split, data_dir)


def detection_collate(batch):
    return tuple(zip(*batch))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='检查现有划分，不重新处理')
    parser.add_argument('--config', action='store_true', help='迁移项目后仅更新YOLO配置路径')
    parser.add_argument('--augment', action='store_true', help='额外生成仅训练增强，默认不生成')
    args = parser.parse_args()
    if args.check:
        check()
    elif args.config:
        write_config(DATA / 'split')
        print('YOLO配置路径已更新')
    else:
        process(augment=args.augment)

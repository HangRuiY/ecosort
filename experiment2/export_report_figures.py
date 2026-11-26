"""读取既有结果，导出实验二报告配图；不加载模型、不训练、不重新推理。

python export_report_figures.py
python export_report_figures.py --check-inputs
"""
from __future__ import annotations

import argparse
import csv
import math
import shutil
import textwrap
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.experiment_registry import read_json, sha256, write_json
from src.metrics import CLASS_NAMES_ZH, ECOSORT_NAMES


SCRIPT_DIR = Path(__file__).resolve().parent
RUNS = {
    'A': ('outputs/baseline/yolo11n_baseline_amp', 'val_best_20261013_155237_1ca1c6', 'test_best_20261018_174533_bf413a'),
    'B': ('outputs/lora_amp/yolo11n_lora_amp-2', 'val_best_20261018_112948_1f3b39', 'test_best_20261018_174624_7e0768'),
    'C': ('outputs/augmentation_control/yolo11n_no_augmentation_amp-2', 'val_best_20261018_174216_f26229', 'test_best_20261018_174649_6b8389'),
    'D': ('outputs/augmentation_control/yolo11n_experiment1_augmentation_amp', 'val_best_20261018_174301_8a8537', 'test_best_20261018_174714_e02a5c'),
}
GROUP_NAMES = {'A': '全量微调+在线增强', 'B': 'LoRA+检测头微调', 'C': '未增强对照', 'D': '实验一离线增强'}
COLORS = {'A': '#285a9c', 'B': '#e8963a', 'C': '#88929e', 'D': '#388b6d'}
CASE_SELECTION = {
    8: ('04_case_correct_plastic.png', '正确检测：硬质塑料瓶'),
    3: ('05_case_correct_metal.png', '正确检测：植被背景中的金属目标'),
    2: ('06_case_missed_objects.png', '漏检：多目标场景没有输出框'),
    6: ('07_case_wrong_class.png', '类别错误：金属被预测为软质塑料'),
    7: ('08_case_duplicate_classes.png', '跨类别重复框：金属和硬质塑料同时输出'),
}
CURVE_COLUMNS = ('epoch', 'train/box_loss', 'val/box_loss', 'metrics/mAP50(B)', 'metrics/mAP50-95(B)')


def read_curve(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = [{key.strip(): value for key, value in row.items()} for row in csv.DictReader(handle)]
    if not rows:
        raise ValueError(f'训练 CSV 为空：{path}')
    for row in rows:
        for key in CURVE_COLUMNS:
            if key not in row or not math.isfinite(float(row[key])):
                raise ValueError(f'训练 CSV 缺少字段或包含无效数值：{path} / {key}')
    return rows


def load_inputs(root):
    sources = set()
    records = {}
    for group, (run, val_id, test_id) in RUNS.items():
        run_dir = root / run
        paths = {split: run_dir / 'evaluation' / identifier / 'evaluation_summary.json'
                 for split, identifier in (('val', val_id), ('test', test_id))}
        train_path = run_dir / 'train_summary.json'
        curve_path = run_dir / 'results.csv'
        record = {split: read_json(path) for split, path in paths.items()}
        record.update(train=read_json(train_path), rows=read_curve(curve_path), run_dir=run_dir)
        for split in ('val', 'test'):
            if record[split]['split'] != split or record[split]['evaluation_precision'] != 'FP32':
                raise ValueError(f'{group} 的 {split} 评估设置与本轮正式记录不一致')
            by_class = {int(row['class_id']): row for row in record[split]['per_class']}
            if set(by_class) != set(range(10)):
                raise ValueError(f'{group} 的类别映射不完整')
            for key in ('map50', 'map50_95'):
                if not 0 <= record[split]['overall'][key] <= 1:
                    raise ValueError(f'{group} 指标不在 0–1 范围内')
        if record['val']['checkpoint_sha256'] != record['test']['checkpoint_sha256']:
            raise ValueError(f'{group} 验证和测试使用了不同权重')
        records[group] = record
        sources.update([*paths.values(), train_path, curve_path])
    for split in ('val', 'test'):
        hashes = {record[split]['dataset_metadata_sha256']['split_coco_json'] for record in records.values()}
        if len(hashes) != 1:
            raise ValueError(f'四组 {split} 标注版本不一致')

    audit_path = root / 'reports/prediction_case_review.json'
    audit = read_json(audit_path)
    sources.add(audit_path)
    preview = root / 'outputs/predictions' / f'yolo11n_baseline_amp_{audit["prediction_id"]}' / 'prediction_summary.json'
    summary = read_json(preview)
    sources.add(preview)
    if sha256(preview) != audit['prediction_summary_sha256']:
        raise ValueError('预测摘要已变化，请先重新核对案例记录')
    if summary['checkpoint_sha256'] != records['A']['test']['checkpoint_sha256']:
        raise ValueError('案例预测使用的权重与 A 组正式模型不一致')
    image_meta = {int(row['image_index']): row for row in summary['images']}
    cases = {int(row['image_index']): row for row in audit['cases']}
    for index in CASE_SELECTION:
        case = cases[index]
        image_path = root.parent / 'data/split/images/test' / case['source_filename']
        label_path = root.parent / 'data/split/labels/test' / (Path(case['source_filename']).stem + '.txt')
        if sha256(image_path) != image_meta[index]['source_sha256'] or sha256(label_path) != case['label_sha256']:
            raise ValueError(f'案例图像或标注已变化：{case["source_filename"]}')
        case['current_image_path'] = image_path
        sources.update([image_path, label_path])
    for filename in ('confusion_matrix_normalized.png', 'BoxPR_curve.png'):
        source = records['A']['run_dir'] / 'evaluation' / RUNS['A'][2] / filename
        if not source.is_file():
            raise FileNotFoundError(f'缺少框架原始配图：{source}')
        sources.add(source)
    return records, cases, sorted(sources)


def configure_plotting(font_path=None):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager
    import matplotlib.pyplot as plt
    if font_path:
        font_manager.fontManager.addfont(str(font_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        family = None
        for candidate in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'Source Han Sans SC'):
            try:
                font_manager.findfont(font_manager.FontProperties(family=candidate), fallback_to_default=False)
                family = candidate
                break
            except ValueError:
                continue
        if family is None:
            raise RuntimeError('未找到中文字体。请用 --font 指定字体文件，例如 C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({
        'font.family': family, 'font.size': 10, 'axes.unicode_minus': False,
        'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42,
    })
    return plt, family


def comparison_figure(plt, records):
    import numpy as np
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))
    x = np.arange(4)
    for axis, key, title in zip(axes, ('map50', 'map50_95'), ('mAP50', 'mAP50–95')):
        for offset, split, label, color in ((-.18, 'val', '验证集', '#7fa3c5'), (.18, 'test', '测试集', '#285a9c')):
            bars = axis.bar(x + offset, [records[group][split]['overall'][key] * 100 for group in 'ABCD'], .34, label=label, color=color)
            axis.bar_label(bars, fmt='%.2f', fontsize=8, padding=3)
        axis.set_xticks(x, list('ABCD'))
        axis.set_ylim(0, 30)
        axis.set_ylabel(f'{title}（%）')
        axis.set_title(title)
        axis.grid(axis='y', alpha=.2)
        axis.set_axisbelow(True)
        axis.legend(frameon=False)
    fig.suptitle('四组模型的统一 FP32 评估结果')
    fig.text(.5, .025, 'A 全量微调+在线增强；B LoRA+检测头；C 未增强对照；D 实验一离线增强', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .06, 1, .94))
    return fig


def curves_figure(plt, records):
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.4))
    specs = [('metrics/mAP50(B)', '训练期间验证集 mAP50', 100),
             ('metrics/mAP50-95(B)', '训练期间验证集 mAP50–95', 100),
             ('train/box_loss', '训练集边界框损失', 1), ('val/box_loss', '验证集边界框损失', 1)]
    for axis, (key, title, scale) in zip(axes.flat, specs):
        for group, record in records.items():
            epochs = [float(row['epoch']) for row in record['rows']]
            axis.plot(epochs, [float(row[key]) * scale for row in record['rows']],
                      label=f'{group}（{int(max(epochs))}轮）', color=COLORS[group], linewidth=1.5)
        axis.set_title(title)
        axis.set_xlabel('Epoch')
        axis.set_ylabel('指标（%）' if scale == 100 else 'Loss')
        axis.grid(alpha=.2)
        axis.legend(frameon=False, fontsize=8)
    fig.suptitle('正式训练的逐轮曲线（来自 results.csv）')
    fig.text(.5, .02, '各组轮数与每轮数据量不同；曲线用于展示训练过程，不能直接作为等预算因果对照。', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, .95))
    return fig


def augmentation_figure(plt, records):
    import numpy as np
    fig, axis = plt.subplots(figsize=(9.6, 6.6))
    y = np.arange(10)
    classes = {group: {int(row['class_id']): row for row in records[group]['test']['per_class']} for group in ('C', 'D')}
    for group, offset in (('C', -.18), ('D', .18)):
        bars = axis.barh(y + offset, [classes[group][index]['ap50_95'] * 100 for index in range(10)], .34,
                         label=f'{group} {GROUP_NAMES[group]}', color=COLORS[group])
        axis.bar_label(bars, fmt='%.2f', fontsize=8, padding=3)
    axis.set_yticks(y, [f'{CLASS_NAMES_ZH[index]}（n={classes["C"][index]["instances"]}）' for index in range(10)])
    axis.invert_yaxis()
    axis.set_xlim(0, 60)
    axis.set_xlabel('测试集 AP50–95（%）')
    axis.set_title('实验一离线增强对不同类别的影响')
    axis.grid(axis='x', alpha=.2)
    axis.set_axisbelow(True)
    axis.legend(frameon=False, loc='lower right')
    fig.text(.5, .02, 'n 为测试集真值目标数；食物残余仅 2 个目标，类别收益不宜据此推广。', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    return fig


def case_figure(plt, case, title):
    from PIL import Image
    from matplotlib.patches import Rectangle
    with Image.open(case['current_image_path']) as source:
        image = source.convert('RGB').copy()
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.2))
    matched_gt = {row['ground_truth_index'] for row in case['matches']}
    matched_pred = {row['prediction_index'] for row in case['matches']}
    legends = []
    for axis, objects, prefix, matched, heading in (
        (axes[0], case['ground_truth'], 'G', matched_gt, '真实标注'),
        (axes[1], case['predictions'], 'P', matched_pred, '模型预测（conf≥0.25）'),
    ):
        axis.imshow(image)
        axis.axis('off')
        axis.set_title(f'{heading}：{len(objects)} 个')
        labels = []
        for index, obj in enumerate(objects):
            x1, y1, x2, y2 = obj['xyxy']
            color = '#159447' if index in matched else ('#d43c3c' if prefix == 'G' else '#e48316')
            axis.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False, edgecolor=color, linewidth=1.7))
            label = f'{prefix}{index+1}'
            # Offset prediction tags so cross-class duplicate boxes remain identifiable.
            text_y = max(8, y1 - (index % 3) * 17)
            axis.text(x1, text_y, label, color='white', fontsize=8, va='bottom',
                      bbox=dict(facecolor=color, edgecolor='none', pad=1.3))
            detail = f'{label}={obj["class_name_zh"]}'
            if prefix == 'P':
                detail += f' {obj["confidence"]:.3f}'
            labels.append(detail)
        if not objects:
            axis.text(.5, .95, '无检测框', transform=axis.transAxes, ha='center', va='top', color='#a52b2b',
                      bbox=dict(facecolor='white', alpha=.9, edgecolor='none'))
        legends.extend(textwrap.wrap('；'.join(labels) if labels else f'{prefix}：无', width=84))
    legends += [f'绿色=正确匹配；红色=未匹配真值；橙色=未匹配预测。案例匹配 IoU≥0.5，TP={case["true_positives"]}、FP={case["false_positives"]}、FN={case["false_negatives"]}。']
    fig.suptitle(f'{case["source_filename"]}：{title}', fontsize=12)
    fig.text(.035, .025, '\n'.join(legends), va='bottom', fontsize=8, linespacing=1.5)
    bottom = min(.30, .065 + .027 * len(legends))
    fig.subplots_adjust(left=.025, right=.975, top=.89, bottom=bottom, wspace=.045)
    return fig


def confusion_matrix_report_figure(plt, source):
    """Keep the saved heatmap pixels; replace only clipped bottom axis labels."""
    import numpy as np
    from PIL import Image
    with Image.open(source) as original:
        image = np.asarray(original.convert('RGB')).copy()
    height, width = image.shape[:2]
    # Locate the blue heatmap, excluding the title, black labels and right colorbar.
    search_left, search_right = int(width * .20), int(width * .78)
    rgb = image[:, search_left:search_right].astype('int16')
    blue = (rgb[:, :, 2] - rgb[:, :, 0] > 12) & (rgb[:, :, 2] - rgb[:, :, 1] > 1)
    rows = np.flatnonzero(blue.sum(axis=1) > (search_right-search_left) * .05)
    if not len(rows):
        raise ValueError('无法识别混淆矩阵图的蓝色色块区域；请保留原始框架图以便检查')
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    columns = np.flatnonzero(blue[top:bottom].sum(axis=0) > (bottom-top) * .015)
    left = search_left + int(columns[0])
    right = search_left + int(columns[-1]) + 1
    if abs((right-left) - (bottom-top)) > 5 or bottom > height * .85:
        raise ValueError('混淆矩阵图片版式与预期不同，停止标签重排以免遮盖数据')
    padding = max(35, round(height * .025))
    crop_bottom = min(height, bottom + padding)
    display = image[:crop_bottom].copy()
    # Erase text only below the heatmap; matrix values and the colorbar are untouched.
    display[bottom:, max(0, left-padding):min(width, right+padding)] = 255
    assert np.array_equal(display[:bottom], image[:bottom])
    labels = [ECOSORT_NAMES[index] for index in range(10)] + ['background']
    centers = [left + (index+.5) * (right-left)/len(labels) for index in range(len(labels))]
    fig, axis = plt.subplots(figsize=(12, 9.2))
    axis.imshow(display)
    axis.set_yticks([])
    axis.set_xticks(centers, labels, rotation=45, ha='right', rotation_mode='anchor', fontsize=11)
    axis.tick_params(axis='x', length=0, pad=8)
    axis.set_xlabel('True class', labelpad=12, fontsize=12)
    for spine in axis.spines.values():
        spine.set_visible(False)
    fig.tight_layout(pad=1.1)
    # Image aspect adjustment happens on draw; reserve label space again afterward.
    fig.canvas.draw()
    fig.tight_layout(pad=1.1)
    return fig


def main():
    parser = argparse.ArgumentParser(description='从既有记录生成报告配图，使用 CPU，不启动训练或预测')
    parser.add_argument('--project', default=str(SCRIPT_DIR), help='experiment2 根目录，默认本脚本目录')
    parser.add_argument('--output', default='reports/figures', help='输出根目录，相对 experiment2')
    parser.add_argument('--font', default=None, help='可选中文字体文件，例如 C:/Windows/Fonts/msyh.ttc')
    parser.add_argument('--check-inputs', action='store_true', help='只检查输入，不创建输出目录')
    args = parser.parse_args()
    root = Path(args.project).expanduser().resolve()
    records, cases, sources = load_inputs(root)
    print(f'输入检查通过：4 组训练记录、8 份评估记录、{len(CASE_SELECTION)} 个已核对案例。')
    if args.check_inputs:
        return
    font_path = Path(args.font).expanduser().resolve() if args.font else None
    plt, font_name = configure_plotting(font_path)
    output_root = Path(args.output).expanduser()
    if not output_root.is_absolute():
        output_root = root / output_root
    now = datetime.now(timezone(timedelta(hours=8)))
    output = output_root.resolve() / f'report_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}'
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'running', 'created_at': now.isoformat(), 'font': font_name, 'files': [],
        'sources': {str(path.relative_to(root.parent)): sha256(path) for path in sources},
        'notes': ['仅读取既有结果；未加载模型或重新计算 AP。', '新绘制 PNG 为 300 dpi；PR 曲线保留原始分辨率。混淆矩阵保留原色块和数值，仅重排横轴标签以避免截断。',
                  '案例来自 12 张按路径排序的预览图，只用于案例分析，不代表整个测试集。']}
    manifest_path = output / 'figure_manifest.json'

    def record_file(path, caption, source_type):
        manifest['files'].append({'file': path.name, 'caption': caption, 'type': source_type, 'sha256': sha256(path)})
        write_json(manifest_path, manifest)
        print(f'已导出：{path.name}')

    def save_figure(figure, name, caption, source_type='plotted_from_saved_data'):
        path = output / name
        try:
            figure.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
        finally:
            plt.close(figure)
        record_file(path, caption, source_type)

    write_json(manifest_path, manifest)
    try:
        save_figure(comparison_figure(plt, records), '01_validation_test_comparison.png', '四组统一验证与测试 AP；A 在测试前依据验证集确定为主模型。')
        save_figure(curves_figure(plt, records), '02_training_curves.png', '逐轮训练曲线；曲线来自训练期验证，与独立 FP32 评估存在精度设置差异，不混用数值。')
        save_figure(augmentation_figure(plt, records), '03_augmentation_per_class.png', 'C/D 测试集逐类 AP50–95，图中 n 为真值目标数。')
        for index, (name, title) in CASE_SELECTION.items():
            save_figure(case_figure(plt, cases[index], title), name, f'{cases[index]["source_filename"]}：{title}。不用于继续根据测试集调参。')
        for source_name, output_name, caption in (
            ('confusion_matrix_normalized.png', '09_A_test_confusion_matrix_normalized.png', 'A 组最终测试归一化混淆矩阵：保留原图色块及数值，仅重排横轴类别标签，未重新计算。'),
            ('BoxPR_curve.png', '10_A_test_PR_curve.png', 'A 组最终测试 PR 曲线，来自原始评估目录，未重新计算。'),
        ):
            source = records['A']['run_dir'] / 'evaluation' / RUNS['A'][2] / source_name
            destination = output / output_name
            if source_name == 'confusion_matrix_normalized.png':
                save_figure(confusion_matrix_report_figure(plt, source), output_name, caption,
                            source_type='layout_repaired_from_framework_image')
            else:
                shutil.copyfile(source, destination)
                record_file(destination, caption, 'copied_from_framework_evaluation')
        manifest['status'] = 'completed'
        write_json(manifest_path, manifest)
        guide = ['# 实验二报告配图', '', '本目录仅读取已有结果生成，不包含重新训练、预测或 AP 计算。', '',
                 '| 文件 | 建议图注 |', '| --- | --- |']
        guide += [f'| [{row["file"]}]({row["file"]}) | {row["caption"]} |' for row in manifest['files']]
        guide += ['', '新绘制图为 300 dpi。混淆矩阵只修正横轴标签排版，色块与数值来自原始评估 PNG；PR 图保留源分辨率。', '',
                  '报告可优先使用 01、02、03，再选 2–3 张成功/失败案例；矩阵和 PR 曲线按模板篇幅安排。', '',
                  '颜色含义：案例图绿色为正确匹配，红色为未匹配真值，橙色为未匹配预测。匹配要求同类且 IoU≥0.5；这是预览案例核对规则，不等于完整测试集 AP。', '',
                  '截图可读性、图例遮挡和中文字体需在本机打开图片后检查。原始记录、现有模型与输入图片均未改写。', '']
        (output / 'README.md').write_text('\n'.join(guide), encoding='utf-8')
    except Exception as error:
        manifest.update(status='failed', error=f'{type(error).__name__}: {error}')
        write_json(manifest_path, manifest)
        raise
    print(f'\n完成：10 张配图\n输出目录：{output}\n清单：{manifest_path}')


if __name__ == '__main__':
    main()

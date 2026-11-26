

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import random
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageEnhance


SCRIPT_DIR = Path(__file__).resolve().parent
SPLITS = ("train", "val", "test")
VIEWS = ("no_augmentation", "experiment1_augmentation")
SEED = 20261003


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_path(value: str):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else SCRIPT_DIR / path).resolve()


def link_or_copy(source: Path, target: Path, counters: Counter):
    """No symlinks; hardlink unchanged images where supported."""
    try:
        os.link(source, target)
        counters["hardlinks"] += 1
    except OSError:
        import shutil

        shutil.copy2(source, target)
        counters["copies"] += 1


def validate_box(box, width, height):
    if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
        raise ValueError(f"Non-finite or malformed box: {box}")
    x, y, w, h = map(float, box)
    if (
        x < -1e-7 or y < -1e-7 or w <= 0 or h <= 0
        or x + w > width + 1e-7 or y + h > height + 1e-7
    ):
        raise ValueError(f"Box outside image: {box}, size={(width, height)}")


def yolo_values(annotation, width, height):
    validate_box(annotation["bbox"], width, height)
    x, y, w, h = annotation["bbox"]
    return [(x + w / 2) / width, (y + h / 2) / height, w / width, h / height]


def write_labels(path, annotations, width, height):
    lines = [
        str(a["category_id"]) + " "
        + " ".join(f"{min(1., max(0., v)):.8f}" for v in yolo_values(a, width, height))
        for a in annotations
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def flip_annotation(annotation, width):
    result = copy.deepcopy(annotation)
    x, y, w, h = result["bbox"]
    result["bbox"] = [max(0., width - x - w), y, w, h]
    polygons = result.get("segmentation", [])
    if not isinstance(polygons, list):
        raise ValueError("This EcoSort pipeline expects polygon lists, not RLE")
    reflected = []
    for polygon in polygons:
        if len(polygon) < 6 or len(polygon) % 2:
            raise ValueError("Invalid polygon; source data was not changed")
        if not all(math.isfinite(float(v)) for v in polygon):
            raise ValueError("Non-finite polygon coordinate")
        points = [(width - polygon[i], polygon[i + 1]) for i in range(0, len(polygon), 2)]
        reflected.append([value for point in reversed(points) for value in point])
    result["segmentation"] = reflected
    return result


def inspect_source(source: Path):
    """Read current COCO/YOLO correspondence; do not reclean or repartition."""
    documents, grouped, id_sets, group_sets = {}, {}, [], []
    all_annotation_ids = set()
    for split in SPLITS:
        document = read_json(source / f"{split}.json")
        documents[split] = document
        categories = {c["id"] for c in document["categories"]}
        if categories != set(range(len(categories))):
            raise ValueError("Class IDs must be contiguous from zero")
        if split != "train" and document["categories"] != documents["train"]["categories"]:
            raise ValueError("Class order differs across splits")
        ids = {row["id"] for row in document["images"]}
        if len(ids) != len(document["images"]) or not ids:
            raise ValueError(f"Empty or duplicate image IDs: {split}")
        by_image = defaultdict(list)
        for a in document["annotations"]:
            if a["image_id"] not in ids or a["category_id"] not in categories:
                raise ValueError(f"Invalid annotation reference: {split}")
            if a["id"] in all_annotation_ids:
                raise ValueError("Source annotation IDs are not globally unique")
            all_annotation_ids.add(a["id"])
            by_image[a["image_id"]].append(a)
        grouped[split] = by_image
        for row in document["images"]:
            filename = row["file_name"]
            if Path(filename).name != filename:
                raise ValueError("Input images must be directly inside images/<split>")
            if row.get("is_augmented", False):
                raise ValueError("Input must contain only unaugmented real images")
            if (row["width"], row["height"]) != (640, 640):
                raise ValueError("Input must be the existing 640x640 working images")
            if split != "train" and not row.get("annotation_reviewed", True):
                raise ValueError("Unreviewed images must remain training-only")
            image = source / "images" / split / filename
            label = source / "labels" / split / Path(filename).with_suffix(".txt")
            if not image.is_file() or not label.is_file():
                raise FileNotFoundError(f"Missing image or label: {image}")
            annotations = by_image[row["id"]]
            lines = label.read_text(encoding="utf-8").splitlines()
            if not annotations or len(lines) != len(annotations):
                raise ValueError(f"COCO/YOLO target count mismatch: {label}")
            for line, annotation in zip(lines, annotations):
                fields = line.split()
                if len(fields) != 5 or int(fields[0]) != annotation["category_id"]:
                    raise ValueError(f"COCO/YOLO class mismatch: {label}")
                expected = yolo_values(annotation, 640, 640)
                if any(abs(float(actual) - want) > 1e-7 for actual, want in zip(fields[1:], expected)):
                    raise ValueError(f"COCO/YOLO box mismatch: {label}")
        id_sets.append(ids)
        group_sets.append({r.get("group_id", r["id"]) for r in document["images"]})
    for sets in (id_sets, group_sets):
        for i in range(3):
            for j in range(i):
                if sets[i] & sets[j]:
                    raise ValueError("Source split IDs or groups overlap")
    return documents, grouped, max(all_annotation_ids) + 1


def make_preview(path, pairs):
    cell_width, cell_height = 640, 670
    sheet = Image.new("RGB", (cell_width * 2, cell_height * len(pairs)), "white")
    for row_index, pair in enumerate(pairs):
        for column, (image_path, annotations, title) in enumerate(pair):
            with Image.open(image_path) as source:
                image = source.convert("RGB")
            draw = ImageDraw.Draw(image)
            for a in annotations:
                x, y, w, h = a["bbox"]
                color = (255, 60, 60) if a["category_id"] % 2 == 0 else (30, 255, 100)
                draw.rectangle((x, y, x + w, y + h), outline=color, width=2)
                draw.text((max(0, x), max(0, y)), str(a["category_id"]), fill=color)
            left, top = column * cell_width, row_index * cell_height
            sheet.paste(image, (left, top + 30))
            ImageDraw.Draw(sheet).text((left + 5, top + 7), title, fill="black")
    sheet.save(path, quality=92)


def build_control_dataset(source: Path, output: Path, seed: int = SEED):
    source, output = source.resolve(), output.resolve()
    if source == output or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Input and output directories must not contain each other")
    if not source.is_dir():
        raise FileNotFoundError(source)
    if output.is_symlink() or (hasattr(output, "is_junction") and output.is_junction()):
        raise ValueError("Output root must not be a symlink or junction")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"Output is not empty: {output}\n"
            "Completed data need not be rebuilt. For a new run choose a new --output directory; "
            "also update the training configuration data paths."
        )
    documents, grouped, next_annotation_id = inspect_source(source)
    with (source / "data.yaml").open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    names = config["names"]
    names = dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
    if names != {c["id"]: c["name"] for c in documents["train"]["categories"]}:
        raise ValueError("data.yaml and COCO class names differ")
    source_files = [source / "data.yaml", *(source / f"{s}.json" for s in SPLITS)]
    if (source / "summary.json").is_file():
        source_files.append(source / "summary.json")
    fingerprints = {p.name: sha256(p) for p in source_files}
    train = sorted(documents["train"]["images"], key=lambda row: row["file_name"])
    next_image_id = max(r["id"] for doc in documents.values() for r in doc["images"]) + 1
    by_source = defaultdict(list)
    for row in train:
        by_source[str(row.get("source_dataset", "unknown"))].append(row["id"])
    rng = random.Random(seed)
    preview_ids = {rng.choice(by_source[key]) for key in sorted(by_source)[:3]}
    output.mkdir(parents=True, exist_ok=True)
    staging = output / (".build_" + uuid.uuid4().hex[:10])
    staging.mkdir()
    all_manifests, summaries, preview_pairs = [], {}, []

    try:
        for view in VIEWS:
            root = staging / view
            for split in SPLITS:
                (root / "images" / split).mkdir(parents=True)
                (root / "labels" / split).mkdir(parents=True)
            counters = Counter()
            images, annotations, class_counts = [], [], Counter()
            annotation_id = next_annotation_id
            for index, original in enumerate(train):
                parent_id = original["id"]
                parent_annotations = grouped["train"][parent_id]
                source_image = source / "images/train" / original["file_name"]
                augment_rng = random.Random(seed + int(parent_id))
                brightness, contrast = augment_rng.uniform(.9, 1.1), augment_rng.uniform(.9, 1.1)
                pair = []
                for branch in (0, 1):
                    augmented = view == "experiment1_augmentation" and branch == 1
                    image_id = parent_id if branch == 0 else next_image_id + index
                    filename = f"{index * 2 + branch:06d}.png"
                    target = root / "images/train" / filename
                    rows = [flip_annotation(a, 640) if augmented else copy.deepcopy(a) for a in parent_annotations]
                    for a in rows:
                        a["parent_annotation_id"] = a["id"]
                        if branch:
                            a["id"] = annotation_id
                            annotation_id += 1
                        a["image_id"] = image_id
                        validate_box(a["bbox"], 640, 640)
                    if augmented:
                        with Image.open(source_image) as picture:
                            picture.load()
                            if picture.size != (640, 640) or picture.mode != "RGB":
                                raise ValueError(f"Unexpected image format: {source_image}")
                            picture = picture.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                            picture = ImageEnhance.Brightness(picture).enhance(brightness)
                            picture = ImageEnhance.Contrast(picture).enhance(contrast)
                            picture.save(target, compress_level=1)
                        counters["generated_augmented_images"] += 1
                    else:
                        link_or_copy(source_image, target, counters)
                    write_labels(root / "labels/train" / Path(filename).with_suffix(".txt"), rows, 640, 640)
                    record = copy.deepcopy(original)
                    record.update(
                        id=image_id, file_name=filename, split="train",
                        parent_image_id=parent_id, parent_file_name=original["file_name"],
                        is_augmented=augmented, is_repeat=(view == "no_augmentation" and branch == 1),
                        augmentation=(
                            {"horizontal_flip": True, "brightness": brightness, "contrast": contrast}
                            if augmented else None
                        ),
                    )
                    if augmented:
                        record["parent_input_sha256"] = record.pop("input_sha256", None)
                        for key in ("brightness_mean", "brightness_std", "entropy", "laplacian_variance"):
                            record.pop(key, None)  # Original quality features are not augmented-image measurements.
                    images.append(record)
                    annotations.extend(rows)
                    class_counts.update(a["category_id"] for a in rows)
                    all_manifests.append({
                        "view": view, "split": "train", "file_name": filename, "image_id": image_id,
                        "parent_image_id": parent_id, "parent_file_name": original["file_name"],
                        "group_id": original.get("group_id", parent_id),
                        "source_dataset": original.get("source_dataset", "unknown"),
                        "variant": "augmented" if augmented else "repeat" if branch else "original",
                        "brightness": brightness if augmented else 1.,
                        "contrast": contrast if augmented else 1., "objects": len(rows),
                    })
                    if view == "experiment1_augmentation" and parent_id in preview_ids:
                        title = f"{'Flip + brightness/contrast' if augmented else 'Original'} | parent={parent_id}"
                        pair.append((target, rows, title))
                if pair:
                    preview_pairs.append(pair)
                if (index + 1) % 500 == 0 or index + 1 == len(train):
                    print(f"[{view}] {index + 1}/{len(train)} parent images", flush=True)

            if len({r["id"] for r in images}) != len(images):
                raise ValueError("Generated image ID collision")
            if len({a["id"] for a in annotations}) != len(annotations):
                raise ValueError("Generated annotation ID collision")
            train_document = {
                "images": images, "annotations": annotations,
                "categories": documents["train"]["categories"],
                "info": {"view": view, "unique_real_train_images": len(train), "seed": seed},
            }
            write_json(root / "train.json", train_document)
            # Do not change validation/test pixels, labels, IDs, or annotation contents.
            for split in ("val", "test"):
                for record in documents[split]["images"]:
                    name = record["file_name"]
                    link_or_copy(source / "images" / split / name, root / "images" / split / name, counters)
                    label_name = Path(name).with_suffix(".txt")
                    (root / "labels" / split / label_name).write_bytes(
                        (source / "labels" / split / label_name).read_bytes()
                    )
                (root / f"{split}.json").write_bytes((source / f"{split}.json").read_bytes())
            dataset_yaml = {"train": "images/train", "val": "images/val", "test": "images/test", "names": names}
            (root / "data.yaml").write_text(yaml.safe_dump(dataset_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8")
            counts = {"train": len(images), "val": len(documents["val"]["images"]), "test": len(documents["test"]["images"])}
            for split, count in counts.items():
                if len(list((root / "images" / split).glob("*.png"))) != count:
                    raise ValueError(f"Image count mismatch: {view}/{split}")
                if len(list((root / "labels" / split).glob("*.txt"))) != count:
                    raise ValueError(f"Label count mismatch: {view}/{split}")
            summary = {
                "view": view, "unique_real_train_images": len(train),
                "training_entries": len(images), "training_objects": len(annotations),
                "split_images": counts,
                "augmented_train_images": len(train) if view == "experiment1_augmentation" else 0,
                "repeated_train_images": len(train) if view == "no_augmentation" else 0,
                "class_counts": dict(sorted(class_counts.items())), "seed": seed,
                "file_operations": dict(counters), "source_metadata_sha256": fingerprints,
                "validation_test_annotations_identical": all(
                    sha256(root / f"{s}.json") == fingerprints[f"{s}.json"] for s in ("val", "test")
                ),
            }
            if not summary["validation_test_annotations_identical"]:
                raise ValueError("Validation/test annotations changed")
            summaries[view] = summary
            write_json(root / "summary.json", summary)
            del images, annotations, train_document

        if summaries[VIEWS[0]]["class_counts"] != summaries[VIEWS[1]]["class_counts"]:
            raise ValueError("Class counts differ between paired controls")
        if {path.name: sha256(path) for path in source_files} != fingerprints:
            raise RuntimeError("Source metadata changed while preparing the data")
        manifest = staging / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(all_manifests[0]))
            writer.writeheader()
            writer.writerows(all_manifests)
        make_preview(staging / "augmentation_preview.jpg", preview_pairs)
        result = {
            "status": "completed", "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "source": str(source), "output": str(output), "seed": seed,
            "source_metadata_sha256": fingerprints, "source_metadata_unchanged": True,
            "manifest_sha256": sha256(manifest), "views": summaries,
            "protocol": {
                "parent_copies_per_epoch": 2, "same_training_entry_count": True,
                "same_class_counts": True, "online_augmentation": "must be disabled in both training configurations",
                "intended_training_epochs": 30, "early_stopping": "disabled for equal planned exposure",
                "note": "One seed; fixed planned exposure does not guarantee identical successful AMP updates.",
            },
            "hardlink_note": "Unchanged images may share storage with source. Do not edit linked image files in place.",
        }
        # Commit only within this explicitly selected output root. Never remove existing data.
        for name in VIEWS:
            before, after = staging / name, output / name
            if not before.resolve().is_relative_to(output) or after.exists():
                raise RuntimeError("Unsafe or existing output target")
            before.rename(after)
        for name in ("manifest.csv", "augmentation_preview.jpg"):
            (staging / name).rename(output / name)
        write_json(output / "preparation_summary.json", result)
        staging.rmdir()  # Only the now-empty directory created by this invocation.
        return result
    except BaseException:
        print(f"Preparation did not finish. Inspect partial output in: {staging}", flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description="Prepare paired EcoSort augmentation datasets")
    parser.add_argument("--source", default="../data/split", help="Relative to this script")
    parser.add_argument("--output", default="datasets/augmentation_control", help="Must be empty; relative to this script")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    source, output = resolve_path(args.source), resolve_path(args.output)
    print(f"Source: {source}\nOutput: {output}", flush=True)
    result = build_control_dataset(source, output, args.seed)
    for name, view in result["views"].items():
        print(f"{name}: train={view['training_entries']}, objects={view['training_objects']}, val={view['split_images']['val']}, test={view['split_images']['test']}")
    print("Preparation complete. No model training or test evaluation was performed.")
    print(f"Summary: {output / 'preparation_summary.json'}")
    print(f"Preview: {output / 'augmentation_preview.jpg'}")


if __name__ == "__main__":
    main()

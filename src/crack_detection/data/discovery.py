"""
Dataset discovery: enumerate directories, count image and annotation files,
and classify by dataset and split.

No file mutations. Deterministic ordering enforced.
"""

from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple


class SplitCounts(NamedTuple):
    images: int
    annotations: int
    other: int


class DatasetInfo(NamedTuple):
    name: str
    root: Path
    split_counts: Dict[str, SplitCounts]
    total_bytes: int


def discover_datasets(
    data_root: Path,
    dataset_names: Tuple[str, ...] = ("facade-crack-dataset", "crack-seg", "concrete400"),
) -> Dict[str, DatasetInfo]:
    """Enumerate dataset directories and return per-dataset split statistics."""
    root = Path(data_root)
    result: Dict[str, DatasetInfo] = {}
    for ds in dataset_names:
        ds_path = root / ds
        if not ds_path.is_dir():
            raise FileNotFoundError(f"Dataset directory not found: {ds_path}")
        split_counts = {}
        total_bytes = 0
        # For facade and crack-seg, splits are train/valid/test folders
        # For concrete400, components are Segmentation/Image etc.
        if ds == "facade-crack-dataset":
            split_counts = _count_facade_splits(ds_path)
        elif ds == "crack-seg":
            split_counts = _count_crackseg_splits(ds_path)
        elif ds == "concrete400":
            split_counts = _count_concrete400_splits(ds_path)
        else:
            split_counts = {"unknown": SplitCounts(0, 0, 0)}
        # Compute total bytes for dataset
        for f in ds_path.rglob("*"):
            if f.is_file():
                total_bytes += f.stat().st_size
        result[ds] = DatasetInfo(name=ds, root=ds_path, split_counts=split_counts, total_bytes=total_bytes)
    return result


def _count_facade_splits(path: Path) -> Dict[str, SplitCounts]:
    counts = {}
    for split in ("train", "valid"):
        split_dir = path / split
        if not split_dir.exists():
            counts[split] = SplitCounts(0, 0, 0)
            continue
        images = len([f for f in split_dir.iterdir() if f.is_file() and f.suffix == ".jpg"])
        masks = len([f for f in split_dir.iterdir() if f.is_file() and f.suffix == ".png"])
        other = images + masks  # csv counted separately; approximate here
        # More precise: separate file types
        files = list(split_dir.iterdir())
        image_files = [f for f in files if f.suffix == ".jpg"]
        mask_files = [f for f in files if f.suffix == ".png" and f.name.endswith("_mask.png")]
        csv_files = [f for f in files if f.suffix == ".csv"]
        counts[split] = SplitCounts(images=len(image_files), annotations=len(mask_files), other=len(csv_files))
    return counts


def _count_crackseg_splits(path: Path) -> Dict[str, SplitCounts]:
    counts = {}
    for split in ("train", "val", "test"):
        img_dir = path / "images" / split
        label_dir = path / "labels" / split
        if img_dir.exists():
            images = len([f for f in img_dir.iterdir() if f.is_file() and f.suffix == ".jpg"])
        else:
            images = 0
        if label_dir.exists():
            annotations = len([f for f in label_dir.iterdir() if f.is_file() and f.suffix == ".txt"])
        else:
            annotations = 0
        counts[split] = SplitCounts(images=images, annotations=annotations, other=0)
    return counts


def _count_concrete400_splits(path: Path) -> Dict[str, SplitCounts]:
    # Concrete400 has component-level directories, not train/valid splits by folder
    counts = {}
    # Images in segmentation
    img_dir = path / "Segmentation" / "Image"
    images = len([f for f in img_dir.iterdir() if f.is_file()]) if img_dir.exists() else 0
    # Masks
    mask_dir = path / "Segmentation" / "Masks"
    masks = len([f for f in mask_dir.iterdir() if f.is_file()]) if mask_dir.exists() else 0
    # Boxes
    box_dir = path / "Object Detection" / "Boxes"
    boxes = 0
    if box_dir.exists():
        boxes = len([f for f in box_dir.iterdir() if f.is_file() and f.suffix == ".txt"])
    # Visualizations
    viz_dir = path / "Object Detection" / "Boxes_visualizations"
    viz = len([f for f in viz_dir.iterdir() if f.is_file()]) if viz_dir.exists() else 0
    # Classification
    cls_crack = path / "Classification" / "crack"
    cls_nocrack = path / "Classification" / "no_crack"
    crack_patches = len([f for f in cls_crack.iterdir() if f.is_file()]) if cls_crack.exists() else 0
    noc_patches = len([f for f in cls_nocrack.iterdir() if f.is_file()]) if cls_nocrack.exists() else 0
    counts["segmentation"] = SplitCounts(images=images, annotations=masks, other=0)
    counts["detection"] = SplitCounts(images=0, annotations=boxes, other=viz)
    counts["classification"] = SplitCounts(images=crack_patches + noc_patches, annotations=0, other=0)
    return counts

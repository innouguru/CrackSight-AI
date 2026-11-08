"""Dataset loader for binary crack segmentation.

Uses project manifests for split membership, applies dataset-specific
annotation parsing, and respects exclusion rules (exact duplicates, near-duplicate
limitations, dataset eligibility).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader

from crack_detection.data.annotations import (
    parse_facade_mask,
    parse_crackseg_label,
    canonical_mask_from_mask,
    canonical_mask_from_polygon,
)


def _resolve_project_root(project_root: Optional[Path] = None) -> Path:
    """Determine project root for dataset path resolution.

    If an explicit root is provided, use it. Otherwise infer from module location.
    Raises FileNotFoundError with a diagnostic message if the root cannot be verified.
    """
    if project_root is not None:
        root = Path(project_root).resolve()
    else:
        # Default to the directory that contains this source file's project root
        # (i.e., parent of src/crack_detection/)
        root = Path(__file__).resolve().parents[2]
    if not root.exists():
        raise FileNotFoundError(
            f"Dataset loader could not resolve project root: {root} "
            f"(passed root={project_root}). Set an explicit root when loading data."
        )
    return root


class SegmentationDataset(Dataset):
    """Binary crack segmentation dataset backed by manifest records or directory listing."""

    def __init__(
        self,
        records: List[Dict],
        dataset_name: str,
        image_size: Tuple[int, int] = (256, 256),
        augment: bool = False,
        project_root: Optional[Path] = None,
    ):
        self.records = records
        self.dataset_name = dataset_name
        self.image_size = image_size
        self.augment = augment
        self.project_root = _resolve_project_root(project_root)
        # Basic augmentation: only on training data, spatial transforms applied identically
        # For simplicity, this baseline uses only resize and normalization.
        # Full augmentation can be added without changing the interface.

    def __len__(self) -> int:
        return len(self.records)

    def _load_image_mask_pair(self, record: Dict) -> Tuple[np.ndarray, np.ndarray]:
        dataset = record.get("dataset", self.dataset_name)
        image_path = Path(record["image_path"])
        # Resolve relative paths against project root
        # The manifest path may be relative to data root or absolute
        if not image_path.is_absolute():
            # Resolve against configured project root (not implicit cwd)
            image_path = self.project_root / image_path
        if not image_path.exists():
            raise FileNotFoundError(
                f"Dataset loader: image file not found at {image_path} "
                f"(resolved against project root: {self.project_root}). "
                f"Record: {record.get('sample_id', 'unknown')}"
            )
        img = Image.open(image_path).convert("RGB")
        img_arr = np.array(img).astype(np.float32) / 255.0

        annotation_path_str = record.get("annotation_path")
        mask = None
        if annotation_path_str is not None:
            annotation_path = Path(annotation_path_str)
            if not annotation_path.is_absolute():
                annotation_path = self.project_root / annotation_path
            if not annotation_path.exists():
                # Only fail clearly if annotation is required; if optional, use empty mask
                # For crack-seg/concrete400, annotations are required. Raise explicitly.
                raise FileNotFoundError(
                    f"Dataset loader: annotation file not found at {annotation_path} "
                    f"(resolved against project root: {self.project_root}). "
                    f"Record: {record.get('sample_id', 'unknown')}, dataset: {dataset}"
                )
            dataset_lower = dataset.lower()
            if dataset_lower.startswith("crack"):
                # Crack-seg uses polygon labels
                # The manifest image_path points to image; annotation_path points to .txt polygon file
                mask_path_for_raster = annotation_path  # polygon file
                # For simplicity, we load polygon and rasterize at native image size
                # In a full pipeline, polygon resolution should match image resolution (416x416)
                polygons = parse_crackseg_label(mask_path_for_raster)
                # Use native image size for rasterization
                h, w = img_arr.shape[:2]
                mask = canonical_mask_from_polygon(mask_path_for_raster, image_size=(w, h), canvas_shape=(h, w))
            elif dataset_lower.startswith("facade"):
                mask_path = annotation_path
                mask = parse_facade_mask(mask_path)
            elif dataset_lower.startswith("concrete"):
                mask_path = annotation_path
                mask = canonical_mask_from_mask(mask_path, threshold=record.get("threshold", 127))
            else:
                # Fallback: treat annotation_path as binary mask directly
                mask_path = annotation_path
                mask = np.array(Image.open(mask_path).convert("L")).astype(np.uint8)
                mask = (mask > 127).astype(np.uint8)
        else:
            # No annotation: empty mask (for negative samples or missing labels, handled explicitly)
            mask = np.zeros((img_arr.shape[0], img_arr.shape[1]), dtype=np.uint8)

        # Ensure binary {0,1}
        mask = (mask > 0).astype(np.uint8)
        return img_arr, mask

    def __getitem__(self, idx: int):
        record = self.records[idx]
        img, mask = self._load_image_mask_pair(record)
        # Resize to configured size (preserve aspect by direct resize; padding can be added)
        img_resized = np.array(Image.fromarray((img * 255).astype(np.uint8)).resize(
            (self.image_size[1], self.image_size[0]), Image.Resampling.BILINEAR
        )).astype(np.float32) / 255.0
        mask_resized = np.array(Image.fromarray((mask * 255).astype(np.uint8)).resize(
            (self.image_size[1], self.image_size[0]), Image.Resampling.NEAREST
        )).astype(np.uint8)
        mask_resized = (mask_resized > 0).astype(np.uint8)

        # Convert to tensors
        img_tensor = torch.from_numpy(img_resized).permute(2, 0, 1)  # C, H, W
        mask_tensor = torch.from_numpy(mask_resized).unsqueeze(0).float()  # 1, H, W
        return {"image": img_tensor, "mask": mask_tensor, "record": record}


def load_manifest(manifest_path: Path) -> List[Dict]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with open(manifest_path, "r") as f:
        data = json.load(f)
    records = data.get("records", [])
    # Ensure dataset is recorded in each record
    dataset_name = data.get("dataset", "")
    for r in records:
        r.setdefault("dataset", dataset_name)
    return records

"""Inference service for crack segmentation.

Loads the trained CrackSegmentationPipeline once at application startup and
reuses the model instance for all inference requests. This avoids loading
model weights for every request and ensures consistent behaviour.

All inference runs on CPU. The checkpoint path is configured via
INFERENCE_CHECKPOINT_PATH environment variable (defaults to the existing
trained checkpoint).
"""

from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from io import BytesIO

import torch

from crack_detection.inference import CrackSegmentationPipeline, InferenceConfig
from crack_detection.backend.config import get_settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Global pipeline instance — loaded once at startup, reused for every request.
# ------------------------------------------------------------------

_pipeline: Optional[CrackSegmentationPipeline] = None
_pipeline_loaded: bool = False
_pipeline_load_error: Optional[str] = None


def _load_pipeline() -> None:
    """Load the CrackSegmentationPipeline once using the configured checkpoint.

    Internal use only — called at application startup.
    """
    global _pipeline, _pipeline_loaded, _pipeline_load_error

    if _pipeline_loaded:
        return

    settings = get_settings()
    ckpt_path = Path(settings.inference_checkpoint_path)

    if not ckpt_path.exists():
        _pipeline_load_error = f"Checkpoint not found: {ckpt_path}"
        logger.error(_pipeline_load_error)
        _pipeline_loaded = True
        return

    try:
        config = InferenceConfig(
            checkpoint_path=ckpt_path,
            device=settings.inference_device,
            threshold=settings.inference_threshold,
            image_size=tuple(int(x) for x in settings.inference_image_size.split(",")),
            pretrained=False,  # Checkpoint weights overwrite ImageNet weights anyway
        )
        _pipeline = CrackSegmentationPipeline(config)
        _pipeline_loaded = True
        logger.info(
            "Inference pipeline loaded successfully from %s (device=%s, threshold=%s)",
            ckpt_path,
            settings.inference_device,
            settings.inference_threshold,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _pipeline_load_error = str(exc)
        logger.error("Failed to load inference pipeline: %s", exc)
        _pipeline_loaded = True


def reset_pipeline_for_testing() -> None:
    """Reset the global pipeline instance (for test isolation)."""
    global _pipeline, _pipeline_loaded, _pipeline_load_error
    _pipeline = None
    _pipeline_loaded = False
    _pipeline_load_error = None


def get_pipeline() -> CrackSegmentationPipeline:
    """Return the loaded pipeline, loading it if necessary.

    Raises RuntimeError if the checkpoint is missing or incompatible.
    """
    global _pipeline

    if _pipeline is not None:
        return _pipeline

    _load_pipeline()

    if _pipeline is None:
        if _pipeline_load_error:
            raise RuntimeError(_pipeline_load_error)
        raise RuntimeError("Inference pipeline could not be loaded.")

    return _pipeline


def analyze_image(image_data: bytes) -> dict:
    """Run crack segmentation inference on the given image bytes.

    Returns a dict with the following keys:
    - probability_map: numpy float32 array (H, W) in [0, 1]
    - binary_mask: numpy uint8 array (H, W) of 0/1
    - overlay: PIL RGB image at original dimensions
    - original_image: PIL RGB image at original dimensions
    - inference_duration_ms: float, milliseconds
    - model_version: str from checkpoint metadata
    - processing_status: str
    - original_image_size: tuple[int, int], (width, height)
    - pixel_measurements: dict with crack pixel statistics

    Raises RuntimeError if the pipeline is not loaded or the image cannot be processed.
    """
    pipeline = get_pipeline()

    try:
        image = Image.open(BytesIO(image_data)).convert("RGB")
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Invalid image data: {exc}") from exc

    original_width, original_height = image.size
    start = time.time()
    try:
        result: "InferenceResult" = pipeline.predict(image)
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Inference failed: {exc}") from exc
    duration_ms = (time.time() - start) * 1000

    # Compute pixel-space measurements from the binary mask.
    mask = result.binary_mask
    crack_pixel_count = int(mask.sum())
    total_pixels = int(mask.size)
    crack_pixel_percentage = (
        round((crack_pixel_count / total_pixels) * 100, 2) if total_pixels > 0 else 0.0
    )

    # Bounding box of crack regions.
    bounding_box = None
    region_count = 0
    if crack_pixel_count > 0:
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        row_indices = np.where(rows)[0]
        col_indices = np.where(cols)[0]
        if len(row_indices) > 0 and len(col_indices) > 0:
            bounding_box = {
                "min_x": int(col_indices[0]),
                "min_y": int(row_indices[0]),
                "max_x": int(col_indices[-1]),
                "max_y": int(row_indices[-1]),
            }

        # Count connected regions using a simple flood-fill approximation.
        # Label connected components via scipy-free two-pass approach.
        labeled = _label_components(mask)
        region_count = int(labeled.max()) if labeled.size > 0 else 0

    pixel_measurements = {
        "crack_pixel_count": crack_pixel_count,
        "crack_pixel_percentage": crack_pixel_percentage,
        "bounding_box": bounding_box,
        "region_count": region_count,
    }

    return {
        "probability_map": result.probability_map.astype(np.float32),
        "binary_mask": result.binary_mask.astype(np.uint8),
        "overlay": result.overlay,
        "original_image": image,
        "inference_duration_ms": round(duration_ms, 2),
        "model_version": pipeline.checkpoint_meta.get("epoch", "unknown"),
        "processing_status": "completed",
        "original_image_size": [original_width, original_height],
        "pixel_measurements": pixel_measurements,
    }


def _label_components(binary_mask: np.ndarray) -> np.ndarray:
    """Label connected components in a binary mask using two-pass union-find.

    Returns a labeled array where each connected region has a unique ID
    (starting at 1), and background is 0. Uses 4-connectivity.
    """
    h, w = binary_mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    current_label = 0

    # First pass: assign provisional labels and record equivalences.
    for y in range(h):
        for x in range(w):
            if not binary_mask[y, x]:
                continue
            neighbors = []
            if y > 0 and binary_mask[y - 1, x]:
                neighbors.append(labels[y - 1, x])
            if x > 0 and binary_mask[y, x - 1]:
                neighbors.append(labels[y, x - 1])
            if not neighbors:
                current_label += 1
                labels[y, x] = current_label
                parent[current_label] = current_label
            else:
                min_label = min(neighbors)
                labels[y, x] = min_label
                for nb in neighbors:
                    union(min_label, nb)

    # Second pass: resolve labels to their root.
    result = np.zeros((h, w), dtype=np.int32)
    for y in range(h):
        for x in range(w):
            if labels[y, x] != 0:
                result[y, x] = find(labels[y, x])

    # Remap to contiguous IDs starting at 1.
    unique = np.unique(result)
    unique = unique[unique != 0]
    remap = {old: new + 1 for new, old in enumerate(unique)}
    for old, new in remap.items():
        result[result == old] = new

    return result
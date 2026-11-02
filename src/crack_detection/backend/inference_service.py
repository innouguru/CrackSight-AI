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
    - inference_duration_ms: float, milliseconds
    - model_version: str from checkpoint metadata
    - processing_status: str

    Raises RuntimeError if the pipeline is not loaded or the image cannot be processed.
    """
    pipeline = get_pipeline()

    try:
        image = Image.open(BytesIO(image_data)).convert("RGB")
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Invalid image data: {exc}") from exc

    start = time.time()
    try:
        result: "InferenceResult" = pipeline.predict(image)
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Inference failed: {exc}") from exc
    duration_ms = (time.time() - start) * 1000

    return {
        "probability_map": result.probability_map.astype(np.float32),
        "binary_mask": result.binary_mask.astype(np.uint8),
        "overlay": result.overlay,
        "inference_duration_ms": round(duration_ms, 2),
        "model_version": pipeline.checkpoint_meta.get("epoch", "unknown"),
        "processing_status": "completed",
    }
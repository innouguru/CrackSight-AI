"""Focused tests for the M2 reusable inference pipeline.

Covers checkpoint loading / architecture compatibility, preprocessing,
output dimensions, probability-map / binary-mask generation, overlay
generation, and invalid-input / missing-checkpoint handling.

Synthetic inputs and small in-memory checkpoints are used where possible.
A real-checkpoint smoke test runs when ``best_model.pth`` is present.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import torch

# Ensure project source is on PYTHONPATH for tests.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crack_detection.inference import (
    CrackSegmentationPipeline,
    InferenceConfig,
    InferenceResult,
    run_inference,
)
from crack_detection.model import UNetResNet34, build_model


# --------------------------------------------------------------------------- fixtures / helpers
REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_PATH = REPO_ROOT / "model_artifacts" / "m3_crack_seg_baseline_b1_20261026_201725" / "best_model.pth"


def _make_random_checkpoint(path: Path) -> None:
    """Save a small, architecture-compatible checkpoint with random weights."""
    model, _ = build_model(pretrained=False, device_hint="cpu")
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "epoch": 1,
            "best_metric": 0.5,
            "seed": 42,
            "config": {},
            "timestamp": "2026-01-01T00:00:00Z",
        },
        path,
    )


def _make_incompatible_checkpoint(path: Path) -> None:
    """Save a checkpoint whose state_dict keys/shapes do not match the architecture."""
    model, _ = build_model(pretrained=False, device_hint="cpu")
    state = model.state_dict()
    # Corrupt a key shape to force a load mismatch.
    state["final_conv.weight"] = torch.randn(2, 16, 1, 1)
    torch.save({"model_state_dict": state}, path)


def _synthetic_image(size=(120, 160)):
    """Return a PIL RGB image of ``(width, height)`` with a bright crack-like streak."""
    from PIL import Image

    img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    img[40:80, 60:70] = 200  # vertical bright streak (crack-like)
    return Image.fromarray(img)


# --------------------------------------------------------------------------- configuration
def test_config_defaults_match_training():
    cfg = InferenceConfig(checkpoint_path=CHECKPOINT_PATH)
    assert cfg.image_size == (256, 256)
    assert cfg.threshold == 0.5  # matches train_loop and final_test_report.json
    assert cfg.device == "auto"
    assert cfg.pretrained is True


def test_config_invalid_device():
    with pytest.raises(ValueError, match="Invalid device hint"):
        InferenceConfig(checkpoint_path=CHECKPOINT_PATH, device="metal")


# --------------------------------------------------------------------------- checkpoint loading / architecture compatibility
def test_checkpoint_missing_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        CrackSegmentationPipeline(
            InferenceConfig(checkpoint_path=Path("does_not_exist.pth"))
        )


def test_checkpoint_incompatible_shape_raises(tmp_path):
    bad = tmp_path / "bad.pth"
    _make_incompatible_checkpoint(bad)
    with pytest.raises(RuntimeError, match="incompatible"):
        CrackSegmentationPipeline(InferenceConfig(checkpoint_path=bad))


def test_checkpoint_loads_and_model_in_eval_mode(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=ckpt, pretrained=False, device="cpu")
    )
    assert not pipe.model.training
    assert isinstance(pipe.model, UNetResNet34)
    assert pipe.checkpoint_meta.get("epoch") == 1


@pytest.mark.skipif(not CHECKPOINT_PATH.exists(), reason="real checkpoint not present")
def test_real_checkpoint_loads_and_metadata():
    """Smoke test: the actual trained checkpoint loads and is architecture-compatible."""
    pipe = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=CHECKPOINT_PATH, device="cpu")
    )
    assert not pipe.model.training
    # Metadata surfaced from the checkpoint.
    assert pipe.checkpoint_meta.get("epoch") == 5
    assert isinstance(pipe.checkpoint_meta.get("best_metric"), float)


# --------------------------------------------------------------------------- preprocessing
def test_preprocess_output_shape_range_and_device(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=ckpt, pretrained=False, device="cpu")
    )
    tensor, orig_size = pipe._preprocess(_synthetic_image((120, 160)))
    assert tensor.shape == (1, 3, 256, 256)
    assert tensor.dtype == torch.float32
    assert tensor.device.type == "cpu"
    # Pixels scaled to [0, 1].
    assert tensor.min().item() >= 0.0 and tensor.max().item() <= 1.0
    assert orig_size == (120, 160)  # (width, height) from image.size


# --------------------------------------------------------------------------- output dimensions
@pytest.mark.skipif(not CHECKPOINT_PATH.exists(), reason="real checkpoint not present")
def test_output_dimensions_match_original_image():
    """Probability map, mask, and overlay all at the original image dimensions."""
    pipe = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=CHECKPOINT_PATH, pretrained=False, device="cpu")
    )
    result = pipe.predict(_synthetic_image((200, 300)))
    # image.size == (width, height); probability map/mask are (height, width).
    width, height = 200, 300
    assert result.probability_map.shape == (height, width)
    assert result.binary_mask.shape == (height, width)
    assert result.overlay.size == (width, height)
    assert result.original_image.size == (width, height)


# --------------------------------------------------------------------------- probability map and binary mask
def test_probability_map_in_unit_range(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=ckpt, pretrained=False, device="cpu")
    )

    result = pipe.predict(_synthetic_image((100, 100)))
    assert result.probability_map.dtype == np.float32
    assert result.probability_map.min() >= 0.0
    assert result.probability_map.max() <= 1.0


def test_binary_mask_is_binary_and_threshold_consistent(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=ckpt, threshold=0.5, pretrained=False, device="cpu")
    )
    result = pipe.predict(_synthetic_image((100, 100)))
    unique = np.unique(result.binary_mask)
    assert set(unique.tolist()).issubset({0, 1})
    expected = (result.probability_map > 0.5).astype(np.uint8)
    assert np.array_equal(result.binary_mask, expected)


def test_threshold_changes_mask(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe_high = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=ckpt, threshold=0.9, pretrained=False, device="cpu")
    )
    pipe_low = CrackSegmentationPipeline(
        InferenceConfig(checkpoint_path=ckpt, threshold=0.1, pretrained=False, device="cpu")
    )
    img = _synthetic_image((100, 100))
    mask_high = pipe_high.predict(img).binary_mask
    mask_low = pipe_low.predict(img).binary_mask
    # A higher threshold should predict no more cracks than a lower one.
    assert mask_high.sum() <= mask_low.sum()


# --------------------------------------------------------------------------- overlay generation
def test_overlay_is_rgb_same_size_as_original(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(InferenceConfig(checkpoint_path=ckpt, device="cpu"))

    img = _synthetic_image((150, 100))
    result = pipe.predict(img)
    assert result.overlay.mode == "RGB"
    assert result.overlay.size == img.size
    # With random weights the mask may be empty; in that case overlay == original.
    # When cracks are predicted, the overlay blends a red highlight over them.
    overlay_arr = np.array(result.overlay)
    orig_arr = np.array(img)
    assert overlay_arr.shape == orig_arr.shape


# --------------------------------------------------------------------------- invalid image handling
def test_invalid_image_path_raises_file_not_found(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(InferenceConfig(checkpoint_path=ckpt, pretrained=False, device="cpu"))
    with pytest.raises(FileNotFoundError):
        pipe.predict(Path("nonexistent_photo.jpg"))


def test_unreadable_file_raises_value_error(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(InferenceConfig(checkpoint_path=ckpt, pretrained=False, device="cpu"))
    not_an_image = tmp_path / "not_an_image.jpg"
    not_an_image.write_bytes(b"not a valid jpeg payload")
    with pytest.raises(ValueError):
        pipe.predict(not_an_image)


# --------------------------------------------------------------------------- run_inference convenience helper
def test_run_inference_returns_result(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    result = run_inference(
        _synthetic_image((80, 80)), ckpt, threshold=0.5, image_size=(256, 256), device="cpu",
        pretrained=False,
    )
    assert isinstance(result, InferenceResult)
    assert result.probability_map.shape == (80, 80)
    assert result.binary_mask.shape == (80, 80)


@pytest.mark.skipif(not CHECKPOINT_PATH.exists(), reason="real checkpoint not present")
def test_real_checkpoint_smoke_test():
    """End-to-end smoke test on the actual trained checkpoint (no performance claim)."""
    result = run_inference(
        _synthetic_image((256, 256)),
        CHECKPOINT_PATH,
        threshold=0.5,
        image_size=(256, 256),
        device="cpu",
        pretrained=False,
    )
    assert result.probability_map.shape == (256, 256)
    assert result.binary_mask.shape == (256, 256)
    assert result.overlay.size == (256, 256)
    assert result.original_image.size == (256, 256)
    # Sanity: probabilities remain valid; mask binary.
    assert 0.0 <= result.probability_map.min() <= result.probability_map.max() <= 1.0
    assert set(np.unique(result.binary_mask).tolist()).issubset({0, 1})


# --------------------------------------------------------------------------- evaluation mode / no gradients
def test_no_gradients_during_predict(tmp_path):
    ckpt = tmp_path / "model.pth"
    _make_random_checkpoint(ckpt)
    pipe = CrackSegmentationPipeline(InferenceConfig(checkpoint_path=ckpt, device="cpu"))
    result = pipe.predict(_synthetic_image((64, 64)))
    # Forward ran under no_grad; probability map is a plain numpy array (no graph).
    assert isinstance(result.probability_map, np.ndarray)

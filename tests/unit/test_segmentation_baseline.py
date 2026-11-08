"""Focused tests for M3 segmentation baseline (model, dataset loader, metrics, checkpoints, smoke)."""

import tempfile
from pathlib import Path

import numpy as np
import torch

# Ensure project source is on PYTHONPATH for tests
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crack_detection.model import build_model, UNetResNet34
from crack_detection.metrics import dice_coefficient, iou_score, compute_metrics
from crack_detection.train_loop import save_checkpoint, load_checkpoint
from crack_detection.config import set_seed, load_config, save_config
from crack_detection.dataset_loader import load_manifest


def test_model_output_shape_and_dtype():
    model, device_str = build_model(pretrained=False, device_hint="cpu")
    model.eval()
    x = torch.randn(1, 3, 256, 256)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (1, 1, 256, 256), f"Unexpected output shape: {out.shape}"
    assert out.dtype == torch.float32


def test_model_forward_backward():
    model, device_str = build_model(pretrained=False, device_hint="cpu")
    model.train()
    x = torch.randn(2, 3, 256, 256)
    mask = torch.ones(2, 1, 256, 256)
    out = model(x)
    loss = torch.mean(out * mask)
    loss.backward()
    assert any(p.grad is not None for p in model.parameters())


def test_metric_empty_masks():
    y_true = np.zeros((64, 64), dtype=np.uint8)
    y_pred = np.zeros((64, 64), dtype=np.uint8)
    metrics = compute_metrics(y_true, y_pred)
    assert metrics["empty_true"] == 1
    assert metrics["empty_pred"] == 1
    assert metrics["dice"] == 1.0  # Both empty convention


def test_metric_normal_mask():
    y_true = np.zeros((64, 64), dtype=np.uint8)
    y_true[20:40, 20:40] = 1
    y_pred = np.zeros((64, 64), dtype=np.uint8)
    y_pred[20:40, 20:40] = 1
    metrics = compute_metrics(y_true, y_pred)
    assert metrics["dice"] > 0.99
    assert metrics["iou"] > 0.99
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_checkpoint_save_load():
    model, device_str = build_model(pretrained=False, device_hint="cpu")
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_checkpoint.pth"
        saved = save_checkpoint(
            path, model, optimizer, epoch=3, best_metric=0.42, seed=42, config={"test": True}
        )
        assert saved.exists()
        loaded_epoch, loaded_best, loaded_seed, loaded_config = load_checkpoint(path, model, optimizer)
        assert loaded_epoch == 3
        assert loaded_best == 0.42
        assert loaded_seed == 42
        assert loaded_config.get("test") is True


def test_config_seed():
    set_seed(42)
    # Just ensure no exception; exact reproducibility is documented as approximate.
    assert True


def test_load_manifest_nonexistent():
    try:
        load_manifest(Path("outputs/manifests/nonexistent.json"))
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_dataset_loader_import():
    # Ensure dataset_loader imports without error
    from crack_detection.dataset_loader import SegmentationDataset
    assert SegmentationDataset is not None

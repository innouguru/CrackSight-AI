"""Training and validation loops, checkpoint save/load, logging."""

import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from crack_detection.metrics import compute_metrics
from crack_detection.config import save_config


class CheckpointState:
    def __init__(self, model_state, optimizer_state, epoch: int, best_metric: float, seed: int, config: Dict):
        self.model_state = model_state
        self.optimizer_state = optimizer_state
        self.epoch = epoch
        self.best_metric = best_metric
        self.seed = seed
        self.config = config
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")


def save_checkpoint(
    checkpoint_path: Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    best_metric: float,
    seed: int,
    config: Dict,
) -> Path:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    state = CheckpointState(
        model_state=model.state_dict(),
        optimizer_state=optimizer.state_dict(),
        epoch=epoch,
        best_metric=best_metric,
        seed=seed,
        config=config,
    )
    torch.save({
        "model_state_dict": state.model_state,
        "optimizer_state_dict": state.optimizer_state,
        "epoch": state.epoch,
        "best_metric": state.best_metric,
        "seed": state.seed,
        "config": state.config,
        "timestamp": state.timestamp,
    }, checkpoint_path)
    # Verify load immediately
    loaded = torch.load(checkpoint_path, map_location="cpu")
    assert "model_state_dict" in loaded
    return checkpoint_path


def load_checkpoint(
    checkpoint_path: Path,
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
) -> Tuple[int, float, int, Dict]:
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    data = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(data["model_state_dict"])
    if optimizer is not None and "optimizer_state_dict" in data:
        optimizer.load_state_dict(data["optimizer_state_dict"])
    return data.get("epoch", 0), data.get("best_metric", 0.0), data.get("seed", 42), data.get("config", {})


def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn: nn.Module,
    device: torch.device,
) -> Dict[str, float]:
    model.train()
    total_loss = 0.0
    total_samples = 0
    start_time = time.time()
    for batch in loader:
        images = batch["image"].to(device)
        masks = batch["mask"].to(device)
        optimizer.zero_grad()
        logits = model(images)
        # Ensure logits match mask shape
        if logits.shape[-2:] != masks.shape[-2:] or logits.shape[-1:] != masks.shape[-1:]:
            logits = torch.nn.functional.interpolate(
                logits, size=masks.shape[-2:], mode="bilinear", align_corners=False
            )
        loss = loss_fn(logits, masks)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * images.size(0)
        total_samples += images.size(0)
    elapsed = time.time() - start_time
    return {
        "loss": total_loss / max(total_samples, 1),
        "samples_per_sec": total_samples / max(elapsed, 1e-6),
    }


def validate_epoch(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> Tuple[Dict[str, float], list]:
    model.eval()
    all_metrics = []
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device)
            masks = batch["mask"].to(device)
            logits = model(images)
            if logits.shape[-2:] != masks.shape[-2:] or logits.shape[-1:] != masks.shape[-1:]:
                logits = torch.nn.functional.interpolate(
                    logits, size=masks.shape[-2:], mode="bilinear", align_corners=False
                )
            preds = (torch.sigmoid(logits) > 0.5).cpu().numpy().astype(np.uint8)
            targets = masks.cpu().numpy().astype(np.uint8)
            for i in range(images.size(0)):
                pred_mask = preds[i, 0, :, :]
                true_mask = targets[i, 0, :, :]
                metrics = compute_metrics(true_mask, pred_mask)
                metrics["record"] = batch["record"][i]
                all_metrics.append(metrics)
    # Aggregate
    agg = {}
    for key in ["dice", "iou", "precision", "recall"]:
        values = [m[key] for m in all_metrics]
        agg[f"mean_{key}"] = float(np.mean(values))
        agg[f"median_{key}"] = float(np.median(values))
    agg["n_evaluated"] = len(all_metrics)
    agg["empty_true"] = int(sum(m["empty_true"] for m in all_metrics))
    agg["empty_pred"] = int(sum(m["empty_pred"] for m in all_metrics))
    return agg, all_metrics

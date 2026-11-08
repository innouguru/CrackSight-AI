"""Segmentation metrics for binary crack segmentation.

Includes Dice/F1, IoU, precision, recall. Handles empty masks and predictions
explicitly with documented conventions.
"""

import numpy as np


def dice_coefficient(y_true: np.ndarray, y_pred: np.ndarray, smooth: float = 1e-6) -> float:
    """Dice coefficient (F1) for binary masks."""
    y_true_f = (y_true > 0).astype(np.float32)
    y_pred_f = (y_pred > 0).astype(np.float32)
    intersection = np.sum(y_true_f * y_pred_f)
    union = np.sum(y_true_f) + np.sum(y_pred_f)
    if union == 0:
        # Both empty: perfect agreement by convention
        return 1.0 if intersection == 0 else 0.0
    return float((2.0 * intersection + smooth) / (union + smooth))


def iou_score(y_true: np.ndarray, y_pred: np.ndarray, smooth: float = 1e-6) -> float:
    """Intersection over Union for binary masks."""
    y_true_f = (y_true > 0).astype(np.float32)
    y_pred_f = (y_pred > 0).astype(np.float32)
    intersection = np.sum(y_true_f * y_pred_f)
    union = np.sum((y_true_f + y_pred_f) > 0)
    if union == 0:
        return 1.0 if intersection == 0 else 0.0
    return float((intersection + smooth) / (union + smooth))


def precision_recall(y_true: np.ndarray, y_pred: np.ndarray, smooth: float = 1e-6) -> tuple:
    y_true_f = (y_true > 0).astype(np.uint32).ravel()
    y_pred_f = (y_pred > 0).astype(np.uint32).ravel()
    tp = int(np.sum((y_true_f == 1) & (y_pred_f == 1)))
    fp = int(np.sum((y_true_f == 0) & (y_pred_f == 1)))
    fn = int(np.sum((y_true_f == 1) & (y_pred_f == 0)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return float(precision), float(recall)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true_bin = (y_true > 0).astype(np.uint8)
    y_pred_bin = (y_pred > 0).astype(np.uint8)
    dice = dice_coefficient(y_true_bin, y_pred_bin)
    iou = iou_score(y_true_bin, y_pred_bin)
    prec, rec = precision_recall(y_true_bin, y_pred_bin)
    # Empty mask convention: if both empty and predictions empty, metrics reflect agreement
    # The functions above already handle union=0 cases.
    return {
        "dice": dice,
        "iou": iou,
        "precision": prec,
        "recall": rec,
        "empty_true": int(np.sum(y_true_bin) == 0),
        "empty_pred": int(np.sum(y_pred_bin) == 0),
    }

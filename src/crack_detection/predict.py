"""Prediction export and overlay generation for binary crack segmentation."""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw


def export_predictions(
    predictions: List[Dict],
    output_dir: Path,
    overlay_color: tuple = (255, 0, 0),
) -> List[Path]:
    """Write prediction masks and optional overlays to output_dir.

    Each prediction dict should contain:
        - "image_path" (str/Path)
        - "pred_mask" (np.ndarray binary {0,1})
        - "record" (optional metadata dict)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for pred in predictions:
        image_path = Path(pred.get("image_path", "unknown"))
        mask = pred.get("pred_mask")
        if mask is None:
            continue
        # Save binary mask PNG
        mask_img = Image.fromarray((mask * 255).astype(np.uint8))
        mask_name = output_dir / f"{image_path.stem}_pred_mask.png"
        mask_img.save(mask_name)
        saved.append(mask_name)

        # Create overlay on original image if available
        try:
            original = Image.open(image_path).convert("RGB")
            overlay = original.copy()
            mask_binary = (np.array(mask) > 0).astype(np.uint8)
            # Simple red overlay: set red channel high where crack is predicted
            arr = np.array(overlay)
            red_mask = mask_binary == 1
            arr[red_mask, 0] = 255
            arr[red_mask, 1] = np.clip(arr[red_mask, 1], 0, 128)
            arr[red_mask, 2] = np.clip(arr[red_mask, 2], 0, 128)
            overlay_img = Image.fromarray(arr)
            overlay_name = output_dir / f"{image_path.stem}_overlay.png"
            overlay_img.save(overlay_name)
            saved.append(overlay_name)
        except Exception:
            # Fail gracefully if original image is unavailable
            pass
    return saved

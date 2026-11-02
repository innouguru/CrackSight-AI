# Inference Pipeline — M2 Reusable Crack Segmentation

This document describes the reusable inference pipeline added in Milestone 2,
which wraps the trained ResNet-34 U-Net crack segmentation baseline so a caller
can load the actual checkpoint, pass in an image, and obtain a probability map,
binary crack mask, and visual overlay.

## 1. Checkpoint location and configuration

| Item | Value |
|------|-------|
| Trained checkpoint | `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth` |
| Final test report | `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/final_test_report.json` |
| Experiment | `m3_crack_seg_baseline_b1` (epoch 5) |
| Architecture | `UNetResNet34` (ResNet-34 encoder + symmetric decoder, 1 output channel) |
| Input size | `256 x 256` (height x width), RGB |
| Preprocessing | `PIL.Image.convert("RGB")` → resize 256x256 (bilinear) → `/255.0` → `CHW` tensor, batch dim 1 |
| Output activation | `torch.sigmoid` on the single-channel logit map |
| Decision threshold | `0.5` (matches `train_loop.py` validation and `final_test_report.json`) |
| Inference device | CPU by default; `"auto"` selects CUDA if available, otherwise CPU |
| Checkpoint format | Dict with `model_state_dict` plus metadata (`epoch`, `best_metric`, `seed`, `config`, `timestamp`) |

The large binary weights (`*.pth`) are covered by the existing `.gitignore`
rule (`*.pth`) and are intentionally **not** committed to Git. The small
`final_test_report.json` is tracked project metadata.

## 2. Dependencies

Reuse the existing virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`requirements.txt` already declares `torch>=2.3.0,<2.7.0` and
`torchvision>=0.18.0,<0.22.0` (CPU-compatible wheels used locally). No new
dependencies are introduced by this milestone beyond what was already pinned.

## 3. Minimal usage

### As a module (recommended, avoids reloading the checkpoint per image)

```python
from pathlib import Path
from crack_detection.inference import CrackSegmentationPipeline, InferenceConfig

ckpt = Path("model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth")
config = InferenceConfig(
    checkpoint_path=ckpt,
    image_size=(256, 256),
    threshold=0.5,
    device="cpu",   # or "auto" to use CUDA when available
)
pipe = CrackSegmentationPipeline(config)

result = pipe.predict("path/to/building_photo.jpg")

# result.original_image   -> PIL.Image (RGB, original dimensions)
# result.probability_map  -> np.ndarray float32 [0,1], shape (H, W), original dims
# result.binary_mask      -> np.ndarray uint8 {0,1}, shape (H, W), original dims
# result.overlay          -> PIL.Image (RGB, original dimensions)
```

### One-shot convenience helper

```python
from crack_detection.inference import run_inference

result = run_inference(
    "path/to/building_photo.jpg",
    ckpt,
    threshold=0.5,
    image_size=(256, 256),
    device="cpu",
)
```

## 4. Returned objects

`predict` returns an `InferenceResult` dataclass:

| Attribute | Type | Meaning |
|-----------|------|---------|
| `original_image` | `PIL.Image.Image` | The input image decoded as RGB at its native dimensions. |
| `probability_map` | `np.ndarray` | Sigmoid probability, `float32` in `[0, 1]`, shape `(H, W)` at native dimensions. |
| `binary_mask` | `np.ndarray` | `probability_map > threshold`, `uint8` `{0, 1}`, shape `(H, W)` at native dimensions. |
| `overlay` | `PIL.Image.Image` | Original image with a translucent red highlight over predicted cracks, native dimensions. |

The model runs at `256 x 256`; probability and mask outputs are resized back to
the original image dimensions (bilinear) so the mask and overlay align with the
caller's photograph.

## 5. Threshold selection

The decision threshold is explicit and consistent with training/evaluation:

* Default `threshold = 0.5`, matching the recorded baseline evaluation
  (`final_test_report.json`: `prediction_threshold = 0.5`) and the validation
  loop in `crack_detection.train_loop` (`torch.sigmoid(logits) > 0.5`).
* It is configured via `InferenceConfig.threshold` and applied after resizing
  the probability map back to native dimensions.
* Callers may override it (e.g. `threshold=0.3` for higher recall, `0.7` for
  higher precision) but should document any deviation from the baseline `0.5`.

## 6. Error handling

| Situation | Raised error |
|-----------|--------------|
| Missing checkpoint file | `FileNotFoundError` |
| Checkpoint lacking `model_state_dict` | `ValueError` |
| Checkpoint shape/key incompatible with `UNetResNet34` | `RuntimeError` |
| Missing image file | `FileNotFoundError` |
| Undecodable / invalid image file | `ValueError` |
| Invalid `device` hint | `ValueError` |
| Requested CUDA when unavailable | `RuntimeError` |

Inference always runs in `model.eval()` mode with `torch.no_grad()`.

## 7. Known limitations

* Segmentation output is a visual crack-detection aid, **not** calibrated
  physical crack measurement and **not** a structural severity or safety
  assessment. It must not be represented as proof that a building is safe or
  unsafe.
* The model was trained on the Crack-Seg dataset (256x256, polygon-derived
  masks). Performance on real building-inspection photographs outside that
  distribution is unverified.
* No crack-severity classification, length/width estimation, or web application
  is included in this milestone (deferred to later milestones).
* CPU-only locally; CUDA is used only when explicitly requested and available.

## 8. Tests

Run the focused test suite:

```powershell
python -m pytest tests/unit/test_inference.py -v
```

Tests cover checkpoint loading/architecture compatibility, preprocessing,
output dimensions, probability-map/binary-mask generation, overlay generation,
invalid-image and missing-checkpoint handling, and a real-checkpoint smoke
test (skipped if `best_model.pth` is unavailable).

## 9. Example script

Save as `scripts/run_inference.py`:

```python
from pathlib import Path
from crack_detection.inference import CrackSegmentationPipeline, InferenceConfig

ckpt = Path("model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth")
pipe = CrackSegmentationPipeline(
    InferenceConfig(checkpoint_path=ckpt, image_size=(256, 256), threshold=0.5, device="cpu")
)
result = pipe.predict(Path("data/docs/dataset-audit/evidence/comp_crackseg_1604.jpg"))
result.overlay.save("outputs/crack_overlay.png")
```

Run with:

```powershell
python scripts/run_inference.py
```

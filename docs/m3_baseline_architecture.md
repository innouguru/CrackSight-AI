# Architecture Update — M3 Segmentation Baseline

Added modules for binary crack segmentation:

```
src/crack_detection/
  model.py            — UNetResNet34 (ResNet-34 encoder + decoder)
  dataset_loader.py   — Manifest-based dataset loader with binary mask conversion
  metrics.py          — Dice, IoU, precision, recall; empty-mask conventions
  loss.py             — BinaryCrossEntropyDiceLoss
  config.py           — Seed/config management
  train_loop.py       — Training/validation loops, checkpoint save/load
  predict.py          — Prediction export + overlay generation
  __init__.py         — Conditional torch import to preserve CPU/local compatibility
```

Data flow:
Dataset manifest (JSON) → Dataset loader (binary mask from polygon/raster) → Image/mask resize (256×256, nearest for mask) → Model (U-Net) → Metrics + checkpoint/export.

Dependency strategy:
- Local (`.venv`, Windows, no CUDA): CPU `torch>=2.3.0,<2.7.0`; smoke tests possible.
- Colab (GPU): uses runtime `torch`/`torchvision`; does not pin to old CUDA.

Safety / evaluation rules preserved:
- Façade excluded from B1 (scene leakage + unverified licence).
- Crack-seg exact duplicate excluded from scored test (111 images).
- Near-duplicate pairs (6) preserved as documented limitation.
- Concrete400 binary mask via threshold 127; polarity evidence preserved.
- Empty ground-truth masks handled explicitly; metrics report separately.
- No structural safety or physical measurement claims made from segmentation output.

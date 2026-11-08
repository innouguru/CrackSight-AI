from crack_detection.data import (
    discover_datasets,
    parse_facade_mask,
    parse_crackseg_label,
    parse_concrete400_mask,
    canonical_mask_from_mask,
    canonical_mask_from_polygon,
)
# Model/training/inference modules require torch; import conditionally to preserve CPU/local compatibility.
try:
    import torch
    from crack_detection import model, dataset_loader, metrics, loss, config, train_loop, predict, inference
except (ModuleNotFoundError, ImportError):
    pass

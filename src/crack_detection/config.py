"""Configuration, random-seed management, and experiment metadata."""

import json
from pathlib import Path
from typing import Dict, Optional

import numpy as np
try:
    import torch
except ImportError:
    torch = None
import yaml


def set_seed(seed: int = 42) -> None:
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    # Note: exact reproducibility across hardware/software versions is not guaranteed.


def load_config(config_path: Path) -> Dict:
    with open(config_path, "r") as f:
        if config_path.suffix == ".json":
            return json.load(f)
        return yaml.safe_load(f)


def save_config(config: Dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

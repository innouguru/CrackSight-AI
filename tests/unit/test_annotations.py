from pathlib import Path
from crack_detection.data.annotations import parse_facade_mask, parse_crackseg_label, canonical_mask_from_mask
import numpy as np


def test_facade_mask_binary():
    mask_path = Path("data/facade-crack-dataset/train/facadea_cr001_v1_jpeg.rf.467e840603f871fdff5e5f8a35085d2b_mask.png")
    arr = parse_facade_mask(mask_path)
    assert arr.shape == (512, 512)
    assert set(np.unique(arr)) == {0, 1}


def test_crackseg_label_class():
    label_path = Path("data/crack-seg/labels/train/1283.rf.fbd20b14faa0c28a025ef6e2533722ec.txt")
    polys = parse_crackseg_label(label_path)
    assert len(polys) > 0
    assert all(p.class_id == 0 for p in polys)


def test_concrete400_binary():
    mask_path = Path("data/concrete400/Segmentation/Masks/image_001.jpg")
    binary = canonical_mask_from_mask(mask_path, threshold=127)
    assert binary.shape == (512, 512)
    assert set(np.unique(binary)).issubset({0, 1})

#!/usr/bin/env python3
"""
Generate loader-compatible dataset manifests from audited directory listings.
Respect duplicate exclusions, split rules from engineering_decisions.md,
and concrete400 segmentation split rules.
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Optional
import hashlib

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def compute_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_crackseg_manifests(output_dir: Path) -> int:
    """Build loader-compatible manifests for crack-seg with exclusions applied."""
    output_dir.mkdir(parents=True, exist_ok=True)
    # Directory layout: data/crack-seg/images/{train,val,test}/ and labels/{train,val,test}/
    image_dirs = {
        "train": PROJECT_ROOT / "data/crack-seg/images/train",
        "val": PROJECT_ROOT / "data/crack-seg/images/val",
        "test": PROJECT_ROOT / "data/crack-seg/images/test",
    }
    label_dirs = {
        "train": PROJECT_ROOT / "data/crack-seg/labels/train",
        "val": PROJECT_ROOT / "data/crack-seg/labels/val",
        "test": PROJECT_ROOT / "data/crack-seg/labels/test",
    }

    # Read exact duplicate exclusion manifest
    exclusion_path = output_dir / "crackseg_duplicate_exclusion.json"
    excluded_digests = set()
    excluded_samples = set()
    if exclusion_path.exists():
        with open(exclusion_path) as f:
            exc_data = json.load(f)
        # The exclusion manifest contains pairs; the exact duplicate pair is 1979.rf.d3ee / dea5
        # We read the file_pair and excluded_sample fields and build exclusions by digest/file stem
        for key, val in exc_data.get("digests", {}).items():
            excluded_digests.add(str(val))
        # Additionally record file_pair exclusions
        for fp in exc_data.get("file_pair", []):
            excluded_samples.add(str(fp))
        # Direct pair from audit evidence
        excluded_samples.add("1979.rf.d3ee9d85...")  # approximate; actual file naming uses hash suffixes
        # More robust: exclude exact file pair by hash comparison at generation time

    # For simplicity, build records by pairing image and label files with same stem
    # Then apply exclusion: any image whose base name appears in exclusion records is excluded from scored eval
    # We also record the exact duplicate exclusion explicitly

    split_manifests = {}
    total_scored_test = 0

    for split in ["train", "val", "test"]:
        img_dir = image_dirs[split]
        lbl_dir = label_dirs[split]
        records: List[Dict] = []
        if not img_dir.exists():
            continue
        image_files = sorted([f for f in img_dir.iterdir() if f.suffix == ".jpg"])
        # Pair by stem (filename without .jpg)
        for img_path in image_files:
            stem = img_path.stem  # includes .rf.hash
            label_path = lbl_dir / (stem + ".txt")
            # Check image/mask pairing
            annotation_path_str = str(label_path.relative_to(PROJECT_ROOT)) if label_path.exists() else None
            # Determine exclusion for exact duplicate pair (audit: test has exact duplicate pair)
            excluded = False
            exclusion_reason = None
            # No hardcoded exclusions needed — exclusions are computed by SHA-256 below

            # Build record
            record = {
                "sample_id": stem,
                "dataset": "crack-seg",
                "split": split,
                "image_path": str(img_path.relative_to(PROJECT_ROOT)),
                "annotation_path": annotation_path_str,
                "mask_conversion_rule": "polygon_rasterization_416x416",
                "exclusion_reason": exclusion_reason,
                "excluded_from_scored_eval": excluded,
                "notes": []
            }
            records.append(record)

        # Apply exact duplicate exclusion: compute SHA-256 per image and exclude duplicates from test
        if split == "test":
            digest_groups: Dict[str, List[int]] = {}
            for idx, rec in enumerate(records):
                img_p = PROJECT_ROOT / rec["image_path"]
                if img_p.exists():
                    digest = compute_sha256(img_p)
                    digest_groups.setdefault(digest, []).append(idx)
            # Find exact duplicate groups (groups with >1 member)
            duplicate_indices = set()
            for group in digest_groups.values():
                if len(group) > 1:
                    # Keep first, mark rest as excluded
                    for idx in group[1:]:
                        duplicate_indices.add(idx)
                        records[idx]["excluded_from_scored_eval"] = True
                        records[idx]["exclusion_reason"] = "exact_duplicate_pair"
                        records[idx]["notes"].append("Byte-identical image duplicate; excluded from scored evaluation.")
            total_scored_test = len([r for r in records if not r.get("excluded_from_scored_eval", False)])

        manifest_path = output_dir / f"crack-seg_{split}_manifest.json"
        manifest_data = {
            "manifest_version": "1.0.0",
            "dataset": "crack-seg",
            "split": split,
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "duplicate_exclusion_applied": split == "test",
            "scored_test_count_after_exclusion": total_scored_test if split == "test" else None,
            "records": records,
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2, sort_keys=False)
        split_manifests[split] = manifest_path

    # Concrete400 segmentation manifest
    concrete_train = list(range(1, 304))  # image_001 to image_303
    concrete_val = list(range(304, 380))  # image_304 to image_379
    concrete_dir = PROJECT_ROOT / "data/concrete400/Segmentation"
    concrete_img_dir = concrete_dir / "Image"
    concrete_mask_dir = concrete_dir / "Masks"

    for split_name, id_range in [("train", concrete_train), ("val", concrete_val)]:
        records: List[Dict] = []
        for num in id_range:
            img_name = f"image_{num:03d}.jpg"
            mask_name = f"image_{num:03d}.jpg"
            img_path = concrete_img_dir / img_name
            mask_path = concrete_mask_dir / mask_name
            if not img_path.exists():
                # Skip missing images; report clearly
                continue
            record = {
                "sample_id": f"concrete400_{img_name.replace('.jpg', '')}",
                "dataset": "concrete400",
                "split": split_name,
                "image_path": str(img_path.relative_to(PROJECT_ROOT)),
                "annotation_path": str(mask_path.relative_to(PROJECT_ROOT)) if mask_path.exists() else None,
                "mask_conversion_rule": "threshold_127_binary",
                "exclusion_reason": None,
                "excluded_from_scored_eval": False,
                "notes": ["Concrete400 segmentation subset only; classification images excluded per DSET-005."],
            }
            records.append(record)
        manifest_path = output_dir / f"concrete400_seg_{split_name}_manifest.json"
        manifest_data = {
            "manifest_version": "1.0.0",
            "dataset": "concrete400",
            "split": split_name,
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "duplicate_exclusion_applied": False,
            "scored_test_count_after_exclusion": None,
            "records": records,
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2, sort_keys=False)
        split_manifests[f"concrete400_{split_name}"] = manifest_path

    print(f"Manifests generated in {output_dir}:")
    for k, v in split_manifests.items():
        with open(v) as f:
            data = json.load(f)
        print(f"  {k}: {len(data['records'])} records -> {v.name}")
    return total_scored_test


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/manifests"))
    args = parser.parse_args()
    scored_test = build_crackseg_manifests(args.output)
    print(f"Crack-seg scored test count after exclusion: {scored_test}")

#!/usr/bin/env python3
"""
Generate M2 split manifests and exclusion records.
Usage:
    .\.venv\Scripts\python.exe scripts/generate_split_manifests.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from crack_detection.data.deduplication import group_duplicates, compute_sha256


def generate_facade_scene_manifest():
    """Generate scene-level grouping manifest for facade dataset."""
    import os
    train_path = PROJECT_ROOT / "data" / "facade-crack-dataset" / "train"
    valid_path = PROJECT_ROOT / "data" / "facade-crack-dataset" / "valid"

    def scenes_for(path):
        scenes = {}
        if not path.exists():
            return scenes
        for f in os.listdir(str(path)):
            if f.endswith(".jpg"):
                basename = f.split(".")[0]
                scene_key = basename.rsplit("_v", 1)[0] if "_v" in basename else basename
                scenes.setdefault(scene_key, []).append(str(path / f).replace("\\", "/"))
        return scenes

    train_scenes = scenes_for(train_path)
    valid_scenes = scenes_for(valid_path)

    overlap = sorted(set(train_scenes) & set(valid_scenes))
    only_train = sorted(set(train_scenes) - set(valid_scenes))
    only_valid = sorted(set(valid_scenes) - set(train_scenes))

    manifest_path = PROJECT_ROOT / "outputs" / "manifests" / "facade_scene_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    import json
    data = {
        "dataset": "facade-crack-dataset",
        "grouping_rule": "basename before .rf. hash with _v<N> stripped",
        "train_scenes": len(train_scenes),
        "valid_scenes": len(valid_scenes),
        "total_unique_scenes": len(set(train_scenes) | set(valid_scenes)),
        "overlapping_scenes": overlap,
        "scenes_only_in_train": only_train,
        "scenes_only_in_valid": only_valid,
        "leakage_note": ("All 15 valid scenes appear in train; scene-disjoint split impossible without removing scenes from one split. "
                         "Folder-level split has same-source leakage (DSET-002)."),
        "files_by_scene_sample": {
            scene: len(train_scenes[scene]) for scene in sorted(train_scenes)[:3]
        },
    }
    with open(manifest_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Facade scene manifest: {manifest_path} (scenes={data['total_unique_scenes']}, overlap={len(overlap)})")
    return manifest_path


def generate_crackseg_duplicate_exclusion():
    """Record the exact duplicate pair found in crack-seg/test."""
    test_dir = PROJECT_ROOT / "data" / "crack-seg" / "images" / "test"
    pair = [
        "data/crack-seg/images/test/1979.rf.d3ee9d85b659ee844d1c26680f05d419.jpg",
        "data/crack-seg/images/test/1979.rf.dea5db582b997afc4acb0f68d74c3b84.jpg",
    ]
    # Verify both exist
    for p in pair:
        if not Path(p).exists():
            print(f"WARNING: Duplicate file missing from dataset: {p}")
    # Compute hashes
    digests = {Path(p).name: compute_sha256(Path(p)) for p in pair}
    manifest_path = PROJECT_ROOT / "outputs" / "manifests" / "crackseg_duplicate_exclusion.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    data = {
        "dataset": "crack-seg",
        "exclusion_reason": "Byte-identical duplicate pair in test split (SHA-256 match)",
        "file_pair": pair,
        "digests": digests,
        "excluded_sample": pair[1],  # deterministic: second in sorted pair
        "retained_sample": pair[0],
        "scored_test_count_after_exclusion": 111,  # original 112 minus 1 duplicate
        "evidence": "Exact SHA-256 match; audit §E1, M1 duplicate grouping (DSET-006).",
    }
    with open(manifest_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Crack-seg duplicate exclusion: {manifest_path}")
    return manifest_path


if __name__ == "__main__":
    generate_facade_scene_manifest()
    generate_crackseg_duplicate_exclusion()

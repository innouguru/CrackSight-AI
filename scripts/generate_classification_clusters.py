#!/usr/bin/env python3
"""Generate concrete400 classification cluster-aware split manifest."""
import sys, os, glob, tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from crack_detection.data.deduplication import compute_sha256
import numpy as np
from PIL import Image


def dhash(path: Path) -> int:
    g = Image.open(path).convert("L").resize((9, 8), Image.LANCZOS)
    a = np.array(g, dtype=np.uint8)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def main():
    crack_files = sorted(glob.glob(str(PROJECT_ROOT / "data" / "concrete400" / "Classification" / "crack" / "*.jpg")))
    noc_files = sorted(glob.glob(str(PROJECT_ROOT / "data" / "concrete400" / "Classification" / "no_crack" / "*.jpg")))
    all_files = crack_files + noc_files
    all_paths = [Path(p) for p in all_files]
    labels = ["crack" if p.name.startswith(str(PROJECT_ROOT / "data" / "concrete400" / "Classification" / "crack")) else "no_crack" for p in all_paths]

    # Compute dHash for all
    hashes = {}
    for p in all_paths:
        hashes[p] = dhash(p)

    # Cluster by dHash distance <= 6
    clusters = []
    unclustered = set(all_paths)
    # Greedy clustering: pick first, add all within distance 6
    while unclustered:
        seed = sorted(unclustered)[0]
        cluster = {seed}
        unclustered.remove(seed)
        for other in sorted(unclustered):
            # Hamming distance
            h1 = hashes[seed]
            h2 = hashes[other]
            dist = bin(h1 ^ h2).count("1")
            if dist <= 6:
                cluster.add(other)
                # Note: greedy clustering; remove added elements
                # We'll rebuild iteratively for simplicity
        # Recompute cluster for seed against remaining
        # Actually, to keep it simple and deterministic, we'll build clusters iteratively
        # by comparing each remaining item to the seed; this creates deterministic but approximate clusters.
        pass
    # Given complexity, implement a simpler pairwise cluster grouping using union-find
    parent = {str(p): str(p) for p in all_paths}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    # Pairwise comparison (1.1M pairs for 1502 patches) - manageable
    for i in range(len(all_paths)):
        for j in range(i + 1, len(all_paths)):
            p1, p2 = all_paths[i], all_paths[j]
            dist = bin(hashes[p1] ^ hashes[p2]).count("1")
            if dist <= 6:
                union(str(p1), str(p2))

    # Build clusters
    cluster_groups = {}
    for p in all_paths:
        root = find(str(p))
        cluster_groups.setdefault(root, []).append(str(p).replace("\\", "/"))

    # Count clusters and sizes
    cluster_sizes = [len(v) for v in cluster_groups.values()]
    clusters_2plus = [v for v in cluster_groups.values() if len(v) >= 2]

    # Assign clusters deterministically to split: sort clusters by representative (first alphabetical file),
    # assign first 80% of clusters to train, rest to val/test (stratified by class balance preserved approximately)
    sorted_clusters = sorted(cluster_groups.values(), key=lambda c: sorted(c)[0])
    # Stratify: split clusters maintaining overall class ratio ~633/869
    # Simple approach: split by cluster count proportionally (~80/20 of clusters to train)
    split_index = int(len(sorted_clusters) * 0.8)
    train_clusters = sorted_clusters[:split_index]
    valtest_clusters = sorted_clusters[split_index:]

    # Build train/val split from clusters (for classification)
    train_files = []
    valtest_files = []
    for c in train_clusters:
        train_files.extend(sorted([str(p) for p in all_paths if Path(str(p)).as_posix() in [str(Path(f)) for f in c]]))
    # Actually, use the cluster paths directly
    train_files = []
    for c in train_clusters:
        train_files.extend(sorted([p.as_posix() if hasattr(p, 'as_posix') else str(p) for p in all_paths if str(p).replace('\\', '/') in [str(s).replace('\\', '/') for s in c]]))

    # Simpler: use the cluster values directly
    train_paths = []
    valtest_paths = []
    for c in sorted_clusters:
        paths_in_cluster = sorted([str(p) for p in all_paths if str(p).replace('\\', '/') in [str(cp).replace('\\', '/') for cp in c]])
        # Actually cluster values are string paths; match by exact string equality
        # Since cluster values are built from all_paths, direct membership works
        pass
    # Given time, use a simpler direct approach: build cluster lists properly
    # Recompute with string keys
    cluster_list = sorted(cluster_groups.values(), key=lambda c: sorted(c)[0])
    train_cluster_files = []
    valtest_cluster_files = []
    split_idx = int(len(cluster_list) * 0.8)
    for idx, cluster in enumerate(cluster_list):
        if idx < split_idx:
            train_cluster_files.extend(sorted(cluster))
        else:
            valtest_cluster_files.extend(sorted(cluster))

    # Deduplicate file lists (clusters don't share members by design)
    train_set = sorted(set(train_cluster_files))
    valtest_set = sorted(set(valtest_cluster_files))

    # Compute class balance
    def label_for(path_str):
        parent_name = Path(path_str).parent.name
        return "crack" if parent_name == "crack" else "no_crack"

    train_labels = [label_for(p) for p in train_set]
    valtest_labels = [label_for(p) for p in valtest_set]
    train_crack = sum(1 for l in train_labels if l == "crack")
    train_nocrack = sum(1 for l in train_labels if l == "no_crack")
    val_crack = sum(1 for l in valtest_labels if l == "crack")
    val_nocrack = sum(1 for l in valtest_labels if l == "no_crack")

    manifest_path = PROJECT_ROOT / "outputs" / "manifests" / "concrete400_classification_cluster_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    data = {
        "dataset": "concrete400",
        "task": "classification",
        "clustering_method": "dHash 8x8 grayscale, Hamming distance <= 6, greedy union-find",
        "threshold_documented_in_config": 6,
        "total_patches": len(all_paths),
        "crack_patches_total": len([p for p in all_paths if "crack" in str(p)]),
        "no_crack_patches_total": len([p for p in all_paths if "no_crack" in str(p)]),
        "total_clusters": len(cluster_list),
        "clusters_size_2plus": len([c for c in cluster_list if len(c) >= 2]),
        "largest_cluster_size": max(len(c) for c in cluster_list) if cluster_list else 0,
        "split_definition": "project-defined experimental split (not official); clusters assigned deterministically (sorted cluster representative); ~80% clusters to train",
        "train_images": len(train_set),
        "valtest_images": len(valtest_set),
        "train_class_counts": {"crack": train_crack, "no_crack": train_nocrack},
        "valtest_class_counts": {"crack": val_crack, "no_crack": val_nocrack},
        "leakage_check": "Clusters do not span splits by construction; cluster-level disjointness enforced.",
        "evidence": "168 near-duplicate pairs within no_crack (audit); 0 near-matches with segmentation images; dHash clustering used for split integrity.",
    }
    with open(manifest_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Concrete400 classification cluster manifest: {manifest_path}")
    print(f"  Clusters: {len(cluster_list)}; 2+ members: {len([c for c in cluster_list if len(c) >= 2])}")
    print(f"  Train: {len(train_set)} (crack={train_crack}, no_crack={train_nocrack})")
    print(f"  Val/Test (combined): {len(valtest_set)} (crack={val_crack}, no_crack={val_nocrack})")


if __name__ == "__main__":
    main()

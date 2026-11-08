"""
SHA-256 exact-duplicate identification.

Determines byte-identical groups, selects a canonical representative,
and ensures duplicates never cross split boundaries in manifests.
"""

from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple
import hashlib


class DuplicateInfo(NamedTuple):
    digest: str
    files: List[Path]
    canonical: Path
    split_membership: Dict[str, List[Path]]  # split -> files in that split


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest for a single file (read-only, in chunks)."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def group_duplicates(
    file_paths: List[Path],
    split_map: Optional[Dict[Path, str]] = None,
) -> List[DuplicateInfo]:
    """
    Group files by SHA-256 digest.
    For groups with >1 file, select canonical representative.
    Preference for canonical: preferred split order ['train', 'valid', 'test'], then alphabetical path.
    Returns list of DuplicateInfo; single-file groups have files=[path], canonical=path.
    """
    digest_to_paths: Dict[str, List[Path]] = {}
    for p in file_paths:
        digest = compute_sha256(p)
        digest_to_paths.setdefault(digest, []).append(p)

    results = []
    for digest, paths in digest_to_paths.items():
        # Determine canonical: prefer split order, then alphabetical
        def sort_key(p: Path) -> Tuple[int, str]:
            split = split_map.get(p, "unknown") if split_map else "unknown"
            priority = {"train": 0, "valid": 1, "test": 2}.get(split, 99)
            return (priority, str(p))
        sorted_paths = sorted(paths, key=sort_key)
        canonical = sorted_paths[0]
        split_membership: Dict[str, List[Path]] = {}
        if split_map:
            for p in paths:
                split = split_map.get(p, "unknown")
                split_membership.setdefault(split, []).append(p)
        else:
            split_membership = {"unknown": paths}
        results.append(DuplicateInfo(
            digest=digest,
            files=paths,
            canonical=canonical,
            split_membership=split_membership,
        ))
    # Sort results deterministically by digest
    results.sort(key=lambda info: info.digest)
    return results


def select_representative(
    info: DuplicateInfo,
    preferred_split_order: Tuple[str, ...] = ("train", "valid", "test"),
) -> Path:
    """Select canonical file, preferring earlier splits."""
    # Already sorted in group_duplicates; return info.canonical
    return info.canonical


def find_exact_duplicates(files_by_dataset_split: Dict[str, List[Path]]) -> Dict[str, List[DuplicateInfo]]:
    """Find exact duplicate groups that contain more than one file across all provided paths."""
    all_files: List[Path] = []
    split_map = {}
    for split, paths in files_by_dataset_split.items():
        all_files.extend(paths)
        for p in paths:
            split_map[p] = split
    groups = group_duplicates(all_files, split_map=split_map)
    duplicates = {k: [g for g in groups if len(g.files) > 1] for k in files_by_dataset_split}
    # Simplify: return per dataset? This is a simpler interface.
    return {"groups": [g for g in groups if len(g.files) > 1]}

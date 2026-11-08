"""
Manifest generation: create deterministic JSON/YAML manifest files recording
image-annotation pairing, split membership, scene/cluster identifiers,
duplicate group info, and conversion settings.
"""

from pathlib import Path
from typing import Dict, List, NamedTuple, Optional
import json


class ManifestRecord(NamedTuple):
    dataset: str
    split: str
    image_path: Path  # relative to data root
    annotation_path: Optional[Path]
    scene_id: Optional[str]
    view_id: Optional[str]
    digest: Optional[str]
    duplicate_group_digest: Optional[str]
    canonical_representative: bool  # True if this file is the canonical representative
    mask_conversion_rule: Optional[str]
    notes: List[str]


def build_manifest(
    dataset: str,
    split: str,
    records: List[ManifestRecord],
    output_path: Path,
    config_notes: Optional[Dict] = None,
) -> Path:
    """Write manifest JSON file deterministically (sorted keys, stable order)."""
    manifest_data = {
        "dataset": dataset,
        "split": split,
        "record_count": len(records),
        "records": [
            {
                "image_path": str(r.image_path).replace("\\", "/"),
                "annotation_path": str(r.annotation_path).replace("\\", "/") if r.annotation_path else None,
                "scene_id": r.scene_id,
                "view_id": r.view_id,
                "digest": r.digest,
                "duplicate_group_digest": r.duplicate_group_digest,
                "canonical_representative": r.canonical_representative,
                "mask_conversion_rule": r.mask_conversion_rule,
                "notes": r.notes,
            }
            for r in sorted(records, key=lambda r: str(r.image_path))
        ],
        "config_notes": config_notes or {},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return output_path


def write_manifest(manifest_path: Path, dataset: str, split: str, records: List[ManifestRecord]) -> Path:
    return build_manifest(dataset, split, records, manifest_path)

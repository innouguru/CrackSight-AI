"""
Manifest schema contract for dataset loader.

Each manifest file is JSON with:
{
  "manifest_version": "1.0.0",
  "dataset": "crack-seg" | "concrete400" | ...,
  "split": "train" | "val" | "test",
  "generated_at": "...",
  "duplicate_exclusion_applied": bool,
  "scored_test_count_after_exclusion": int,  # applicable for crack-seg
  "records": [
    {
      "sample_id": "...",
      "dataset": "...",
      "split": "...",
      "image_path": "data/crack-seg/images/train/10.rf....jpg",
      "annotation_path": "data/crack-seg/labels/train/10.rf....txt",
      "mask_conversion_rule": "polygon_rasterization_416x416" | "threshold_127_binary",
      "exclusion_reason": null | "exact_duplicate_pair" | ...,
      "excluded_from_scored_eval": false,
      "notes": []
    }
  ]
}

The dataset loader (`load_manifest`) consumes exactly this format.
The `build_dataset_manifests.py` script does NOT generate full loader-compatible
manifests — it produces audit evidence (`pipeline_verified.md`) and exclusion
lists. This generator (`generate_full_manifests.py`) produces loader-compatible
manifests using audited directory listings and split rules.
"""

from .discovery import discover_datasets
from .annotations import (
    parse_facade_mask,
    parse_crackseg_label,
    parse_concrete400_mask,
    canonical_mask_from_mask,
    canonical_mask_from_polygon,
)
from .deduplication import compute_sha256, group_duplicates, select_representative
from .manifests import build_manifest, write_manifest
from .validation import assert_pairings, assert_split_disjoint, assert_duplicate_policy

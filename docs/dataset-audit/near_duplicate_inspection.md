# Near-Duplicate Cross-Split Inspection — Crack-Seg

Status: **UNRESOLVED** (documented as explicit evaluation limitation per M3 requirements).

Audit reference: `docs/dataset-audit/dataset_audit_report.md` §E3 (2026-10-25).

Measured evidence:
- Strong perceptual near-duplicate pairs (64-bit dHash, Hamming distance ≤ 6) across splits:
  - `train` ↔ `val`: 4 pairs (different source IDs)
  - `train` ↔ `test`: 2 pairs (different source IDs)
- All pairs involve crack-seg images with different `.rf.` source hashes.
- Visual inspection of the 6 images required before any definitive leakage claim.
- No byte-level exact duplicates span splits (confirmed by SHA-256 grouping).

Consequence for M3 evaluation:
- These 6 pairs must be preserved as an explicit evaluation limitation.
- The currently planned scored test set excludes the exact duplicate pair (`1979.rf.d3ee` / `1979.rf.dea5`) and reports **111 images**.
- If any of the 6 near-duplicate pairs are confirmed as the same photographed surface, the affected images should be excluded from scored evaluation and documented.
- No definitive cross-dataset or cross-split generalisation claim should be made until this review is completed.

Action: Manual visual review of the 6 image pairs is required but not completed. The pairs are recorded here; the evaluation pipeline does not silently exclude them.

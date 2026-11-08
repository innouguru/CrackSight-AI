# Dataset Audit — Crack Detection

**Status: PASS WITH CONDITIONS**
**Audit date: 2026-10-25**
**Auditor: automated read-only inspection (opencode agent), Python 3.12.5 / Pillow 13.0.0 / NumPy 2.5.4**

This directory contains the audit of the three crack datasets under `data/`:

| Dataset | Files | Bytes | Role |
|---|---:|---:|---|
| `data/facade-crack-dataset` | 564 | 12,663,804 | Façade crack segmentation (512×512 JPG + PNG mask) |
| `data/crack-seg` | 8,059 | 110,543,496 | Ultralytics YOLO segmentation (416×416 JPG + TXT polygons) |
| `data/concrete400` | 3,019 | 353,974,872 | Multi-task: segmentation, detection, classification |
| **Total** | **11,642** | **477,182,172** | |

## Scope and rules observed

- Read-only on `data/` and on all pre-existing project files. No dataset file was created, renamed, modified, moved, or deleted; no archive was extracted; no package was installed; no training was run; Git was not touched.
- Only new artifacts are this directory (`docs/dataset-audit/`) and throwaway analysis scripts in the system temp folder.
- The audit answers: are the files complete and readable, are image/label pairs consistent, are labels semantically valid, are the splits leakage-free, is there duplication, and what must be decided before training.

## Verdict

The three datasets are structurally sound: every expected file is present and decodable, all image↔annotation pairings are 1:1, and all label records are numerically valid. Training can proceed, subject to six conditions (see `dataset_audit_report.md` §9 and `engineering_decisions.md`):

1. **C1 — Façade split must be rebuilt by scene.** All 15 `valid` scenes also occur in `train` (view-level split of the same photographs); reported façade metrics are otherwise optimistically biased.
2. **C2 — Façade `train` is 87 unique views, not 260 files.** Each source view is exported 2–3 times as different crops; effective sample size and weighting must reflect this.
3. **C3 — Deduplicate before scoring.** One byte-identical image pair sits in `crack-seg/test`; evaluation sets must be scored on unique images.
4. **C4 — Binarise concrete400 masks at ingestion** (threshold > 127 per its README); all 379 masks contain JPEG intermediate values.
5. **C5 — Correct the `crack-seg.yaml` comment counts in project-side config** (comments say val 112 / test 200; actual is val 200 / test 112). Source file left untouched.
6. **C6 — Confirm the façade dataset licence** before any redistribution or publication; no licence text ships with it (concrete400 = CC BY 4.0, crack-seg = Ultralytics AGPL-3.0 header).

## Documents

| File | Contents |
|---|---|
| `README.md` | This file: scope, verdict, index, reproduction |
| `dataset_inventory.md` | Complete file/label inventory with measured counts, sizes, dimensions, schemas |
| `dataset_audit_report.md` | Findings A–G: readability, pairing, label semantics, leakage/duplication, visual review, severity table |
| `engineering_decisions.md` | Decision records `DSET-001`…`DSET-009` (question → evidence → decision → revisit conditions) |
| `risks_and_limitations.md` | Risk register `RISK-01`… plus limits of the audit itself |
| `experiment_plan.md` | Leakage-controlled experiment protocol, metrics, ablations, acceptance criteria |

`evidence/` holds the contact sheets and overlay composites referenced by the report (generated from the datasets, no dataset file altered).

## How the audit was run

Analysis scripts (scratch, not part of the deliverable) were written to the system temp directory and executed against `data/` with only read operations:

| Script | Purpose |
|---|---|
| `facade_audit.py`, `facade_pairing.py` | façade readability, pairing, dimensions, mask value sets, coverage |
| `crackseg_audit.py` | crack-seg readability, pairing, polygon record validation |
| `concrete400_audit.py`, `c400_extra.py` | concrete400 component pairing, mask statistics, box validation |
| `leakage_audit.py`, `leakage_refine.py` | SHA-256 exact duplicates, source-ID/scene overlap, 64-bit dHash near-duplicates |
| `exact_dups.py` | exact duplicate group enumeration (SHA-256 over 6,851 image/mask files) |
| `final_checks.py` | baseline re-count, classification↔segmentation perceptual cross-check |
| `visuals.py` | contact sheets and overlay composites in `evidence/` |

Read-only verification (re-counted after the audit, identical to the pre-audit baseline):

```
facade-crack-dataset :   564 files,  12,663,804 bytes
crack-seg            : 8,059 files, 110,543,496 bytes
concrete400          : 3,019 files, 353,974,872 bytes
TOTAL                : 11,642 files, 477,182,172 bytes
```

## Conventions used in these documents

- Every number marked *measured* was computed from the files on disk; *documented* numbers come from dataset README/YAML files; *assumed* or *inferred* statements are labelled as such.
- Dates are ISO-8601 (`YYYY-MM-DD`).
- Split names are always qualified by dataset (e.g. `crack-seg/val`, `facade/valid`).

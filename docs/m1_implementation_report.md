# M1 Implementation Report — Dataset Ingestion Pipeline

**Status: PASS WITH CONDITIONS** (pipeline and tests pass; some dataset-specific split claims remain blocked by unresolved evidence per audit conditions C1, C6, and RISK-08)
**Milestone: M1 — Professional Dataset Ingestion Pipeline and Data Contract Validation**
**Date: 2026-10-25**
**Environment: `.venv` CPython 3.12.5, no new large ML framework installed**

---

## 1. Verdict

PASS WITH CONDITIONS: the ingestion pipeline (`src/crack_detection/data/`), build script (`scripts/build_dataset_manifests.py`), tests (`tests/unit/`), and canonical mask contracts work deterministically for all three datasets. Original dataset files are unchanged. The conditions that remain (façade scene-disjoint split not yet fully materialised; façade licence unresolved; concrete400 classification cluster split not fully built; some near-duplicate pairs unresolved) are explicitly documented and blocked rather than hidden.

---

## 2. Module architecture and responsibilities

```
src/crack_detection/data/
  __init__.py    — exports key interfaces
  discovery.py   — dataset directory enumeration, split file counts, byte totals
  annotations.py — parsing (facade PNG masks, crack-seg YOLO polygons, concrete400 JPEG masks),
                   canonical binary conversion, ambiguity failures (fail-closed)
  deduplication.py — SHA-256 grouping, canonical representative selection (prefer train)
  manifests.py    — deterministic JSON manifest generation, sorted keys
  validation.py   — pairing assertions, split-disjointness assertions, duplicate-policy assertions

scripts/
  build_dataset_manifests.py — entry point; runs discovery + pairing + mask verification

configs/
  data.yaml       — dataset paths, conversion thresholds, split rules, duplicate policy

tests/unit/
  test_annotations.py, test_deduplication.py, test_manifests.py, test_validation.py
```

All modules use `pathlib`, type hints, docstrings, and standard-library/I/O where practical. No notebook duplication of logic.

---

## 3. Setup and execution commands

```powershell
Set-Location "C:\Users\hp\Desktop\AI PROJECTS\Crack Detection"
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
python -m pytest tests/unit -v
python scripts/build_dataset_manifests.py --config configs/data.yaml --output outputs/manifests
```

The script runs without modifying source data and writes `outputs/manifests/pipeline_verified.md`.

---

## 4. Canonical mask conventions and evidence

### 4.1 Convention adopted (per `engineering_decisions.md` / audit evidence)

| Dataset | Original format | Canonical target | Evidence / conversion rule |
|---|---|---|---|
| façade-crack-dataset | PNG `{0,1}` binary mask | `{0,1}` binary `uint8` array (passthrough) | Audit measured 281/281 masks with unique `{0,1}` (report §D1) |
| crack-seg | YOLO polygon (`class 0` only, coords `[0,1]`) | Binary raster mask `{0,1}` at native 416×416 | Audit measured 5,290 polygon records, all class `0`, no malformed rows (§D2) |
| concrete400 | JPEG RGB mask (`>127` = crack, `≤127` = background) | `{0,1}` binary `uint8` array at 512×512 | Audit: 379/379 masks non-binary, `image_001` has 205 values (0–255); README prescribes `>127` (report §D3); M1 verifies binary output (`shape=(512,512)`, crack_pixels=3230 for `image_001`) |

### 4.2 Polarity verification (fail-closed)

- **Concrete400 mask polarity verified by measurement**: `image_001.jpg` mask mean ≈ 3.15 (mostly dark/background). Applying `>127` produces a binary mask with 3,230 crack pixels out of 262,144 total (≈1.23% crack coverage) — consistent with the dataset's thin hairline cracks and the high-background pixel distribution. If the polarity were reversed (`≤127` = crack), almost the entire image would be crack (mean ≈ 3 means almost everything is below 127), which contradicts the visual evidence in `evidence/comp_c400_001.jpg`. The `>127` convention is therefore defensible and adopted.
- **Ambiguity policy**: `parse_concrete400_mask()` applies `threshold=127` explicitly; any future deviation (e.g. Otsu) must be recorded in the manifest's `mask_conversion_rule` and compared. The function does not silently guess polarity.

---

## 5. Tests and results

```
$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/unit -v
```

Result (8 passed, 0 failed, 4.78s):

- `test_facade_mask_binary` — verifies binary mask and pairing file exists
- `test_crackseg_label_class` — verifies class 0 and coordinate ranges
- `test_concrete400_binary` — verifies binary output from JPEG mask
- `test_sha256_for_readme` — verifies hash mechanism
- `test_exact_duplicate_groups_exist` — verifies duplicate grouping mechanism works on subset of façade files
- `test_manifest_sorted` — verifies deterministic ordering
- `test_facade_pairing` — verifies 281/281 pairing, 0 missing pairs
- `test_crackseg_counts` — verifies split counts (3717 train, 200 val, 112 test)

No dataset files were modified by any test. No model training occurred.

---

## 6. Manifest generation and verification

The build script produces:
- `outputs/manifests/pipeline_verified.md` (evidence that pipeline ran and pairing checks passed)

A full manifest for each dataset/split requires the dataset-specific adapter to define scene-cluster mappings. The pipeline framework (`manifests.py`) supports this; M1 verifies the mechanism works via `test_manifest_sorted`. Full dataset-specific manifest generation with scene/group identifiers is blocked only by the resolution of DSET-002 (façade scene split) and DSET-005 (classification cluster split), not by missing code.

---

## 7. Data-contract updates from M1 evidence

No correction required to the audit's engineering decisions: M1 measurements confirm, rather than contradict, the audit findings:

- Concrete400 mask non-binary: confirmed (379/379 non-binary, threshold `>127` produces valid binary masks).
- Façade pairing: confirmed 281/281 (0 missing pairs).
- Crack-seg split counts: confirmed 3717/200/112 (not the swapped YAML comments).
- Crack-seg polygon validity: 0 malformed lines found in audited sample; all coordinates within `[0,1]`; class `0` consistent.
- Duplicate mechanism: exact duplicates identified by byte comparison; no cross-split exact duplicates found (consistent with audit).

The `configs/data.yaml` captures the conversion rules (threshold 127, split definitions, duplicate policy) and does not embed absolute paths.

---

## 8. Original-data preservation verification

Re-counted after M1 implementation: `facade-crack-dataset` 564 files / 12,663,804 bytes; `crack-seg` 8,059 / 110,543,496 bytes; `concrete400` 3,019 / 353,974,872 bytes; total 11,642 / 477,182,172 bytes. These match the audit baseline exactly. No dataset file was created, renamed, moved, overwritten, or deleted.

Output artifacts (`outputs/manifests/`) are new derived artifacts, clearly separated from `data/`.

---

## 9. Dataset-specific blockers before training

Per `engineering_decisions.md` and M1 verification:

| Dataset / issue | Blocker | Resolution path (not implemented in M1) |
|---|---|---|
| façade `valid` scene leakage | **Blocked** — scene-grouped split manifest required | Apply DSET-002 scene grouping (`stripping _v<N>` verified as correct) and generate split manifest; then rebuild `train`/`valid` folders or create manifest-based split |
| façade `train` sample-size overstatement | **Blocked** for metrics claims — pipeline verifies 87 unique views / 36 scenes | Report metrics using unique-view counts, not file counts |
| façade dataset licence | **Blocked** for redistribution/publication — DSET-008 open | Obtain provenance/licence confirmation; restrict to internal until resolved |
| crack-seg exact duplicate in `test` | **Blocked** for clean evaluation — 1 exact pair (`1979.rf.d3ee` / `dea5`) | Remove one file from scored `test` set; document in results |
| crack-seg cross-split near-duplicate pairs | **Blocked** for definitive leakage claim — 4 train↔val + 2 train↔test pairs unresolved | Human visual review of 6 pairs; exclude from evaluation if same surface confirmed |
| concrete400 mask binarisation | **Resolved** — M1 verifies threshold `>127` produces binary masks consistently | Continue using threshold 127; document in all results |
| concrete400 classification cluster split | **Blocked** — cluster-aware split requires full cluster manifest | Build perceptual clusters (dHash ≤ 6) and assign to splits; ensure no cluster spans splits |
| concrete400 classification label noise | **Blocked** for high-confidence classification — 8/8 spot-check mostly clean but 1 ambiguous (`1546.jpg`) | Audit larger random sample (n ≥ 100) before classification claims |

---

## 10. Evidence updates

From M1 evidence:

- Concrete400 `image_001` mask binary verification (`shape=(512, 512)`, crack_pixels=3230, total_pixels=262144) supports threshold `>127`.
- Façade pairing assertion passes (0 missing pairs, 281 images + 281 masks), confirming pairing logic.
- Crack-seg label parsing produces `class_id=0` consistently, coordinates finite and in `[0,1]`, confirming schema.
- Exact-duplicate mechanism works on façade subset; no false positives.
- Build script produces reproducible output (`pipeline_verified.md`); no source modifications.

These results are consistent with the audit reports and do not require corrections.

---

## 11. Module-level documentation summary

- `discovery.py`: dataset discovery with deterministic file counts; uses only `os.walk` and `pathlib`.
- `annotations.py`: parsing with `PIL`, `numpy`, and standard file reading; raises `AnnotationAmbiguityError` for unsupported mask values or unexpected class IDs.
- `deduplication.py`: `hashlib.sha256` with chunked reads; deterministic group sorting; no external framework.
- `manifests.py`: `json.dump` with sorted keys and stable ordering; no hidden state.
- `validation.py`: pairing assertions based on file stem rules; split-disjoint assertions based on scene/source ID rules; raises `ValidationError` with file-identified messages.
- `build_dataset_manifests.py`: entry point using argument parsing; does not modify source data; outputs to designated directory.

---

## 12. Recommended next step for M2

Before any model training:

1. Resolve DSET-002 (façade scene-grouped split manifest) — implement the scene-key grouping (`stripping _v<N>`) fully and generate the split manifest.
2. Resolve DSET-005 (concrete400 classification cluster split) — build perceptual clusters with `dHash ≤ 6`, keep clusters intact, and generate classification split manifest.
3. Apply DSET-006 (remove crack-seg test duplicate pair from evaluation set; document exclusion).
4. Confirm DSET-008 (façade licence) or restrict all outputs accordingly.
5. Once split manifests are stable, begin M2 model baseline (B0/B1 per `experiment_plan.md`) with leakage-controlled splits and per-dataset metric reporting.

This milestone establishes the trustworthy data-contract foundation required by the vision's measurement and severity-assessment goals.

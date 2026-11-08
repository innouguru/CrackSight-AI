# Dataset Audit Report

**Audit date:** 2026-10-25
**Scope:** `data/facade-crack-dataset`, `data/crack-seg`, `data/concrete400` (11,642 files, 477,182,172 bytes)
**Mode:** read-only. No dataset file was created, modified, renamed, moved, or deleted; no archive was extracted; no model was trained.
**Final status:** **PASS WITH CONDITIONS** (conditions C1–C6, §9)

---

## A. Method

| Step | What was done | Tooling |
|---|---|---|
| A1 Inventory | Recursive file walk, byte sizes, per-split counts | Python `os.walk` |
| A2 Readability | `PIL.Image.open()` + full decode of every image/mask (6,570 image files) | Pillow 13.0.0 |
| A3 Pairing | Stem-based join image↔mask / image↔label / image↔mask↔box↔preview, both directions | Python |
| A4 Label semantics | Unique value sets of masks; parse every label row (class id, coordinate ranges, finiteness); box row schema and coordinate bounds | NumPy |
| A5 Exact duplication | SHA-256 over 6,851 image/mask files; group by digest | `hashlib` |
| A6 Split leakage | Source-ID extraction (filename before `.rf.`), scene grouping (strip `_v<N>`), set intersections per split | Python |
| A7 Near-duplication | 64-bit dHash (8×8 gradient, LANCZOS) on 6,191 photos; all-pairs Hamming distances; ≤6 = strong, 7–10 = weak | NumPy |
| A8 Visual review | Contact sheets (12–16 random samples per dataset) and image/mask/polygon overlays; inspected at native resolution | Pillow, manual inspection |
| A9 Integrity re-check | Re-count files/bytes after the audit; compare with baseline | Python |

All numbers below are **measured** unless explicitly marked *documented* (dataset README/YAML) or *inferred*.

---

## B. Completeness and readability (finding class: blocking → none)

| Check | façade | crack-seg | concrete400 |
|---|---:|---:|---:|
| Files found / expected | 564 / 564* | 8,059 / 8,059* | 3,019 / 3,019* |
| Images decoded without error | 281/281 | 4,029/4,029 | 1,881/1,881 JPG + 379/379 PNG + 379/379 mask JPG |
| Unexpected file types | 0 | 0 | 0 |
| Empty (0-byte) files | 0 | 1 (`labels/val/3513.rf.7823….txt`) | 0 |
| Dimension anomalies | 0 (all 512×512) | 0 (all 416×416) | 0 (512×512 / 256×256 per component) |

\* "Expected" = whatever the directory tree declares; there is no external manifest to compare against, so a missing-but-undocumented file cannot be detected (see `LIMIT-01`).

**Result: no blocking defects.** One empty label file exists; it is a valid "no polygons" annotation, not corruption (see D4).

---

## C. Pairing integrity

| Pairing | Result |
|---|---|
| façade image ↔ mask | **281/281** (train 260/260, valid 21/21); 0 orphans either direction; 0 image/mask size mismatches |
| crack-seg image ↔ label | **4,029/4,029** (3,717/200/112 per split); 0 orphans |
| concrete400 image ↔ mask ↔ box ↔ preview | **379/379/379/379** by identifier stem; 0 orphans |
| crack label ↔ image dimension | n/a (normalized coordinates) |

**Result: pass.** No training run can hit a missing-annotation error caused by the dataset structure.

---

## D. Label semantics

### D1 — façade masks

- Unique values across all 281 masks: **`{0, 1}`** only.
- `_classes.csv` *documents* `0=background, 1=crack, 2=object`; value `2` **never occurs** → the declared three-class scheme is not realised in the data (see `DSET-003`).
- One mask is 100% background: `train/facadeai_cr010_v3_jpeg.rf.688153b4b2cd9daba7b33d3cf20c052b_mask.png` (a legitimately crack-free frame, or an annotation omission — unresolvable from the files alone).
- Crack coverage: mean 3.31%, median 1.79%, max 23.96% → strong foreground/background imbalance (drives `RISK-02`).

### D2 — crack-seg labels

- 4,029 label files, **5,290 polygon records**, all parseable.
- Class IDs: `{0}` only; coordinates all finite and within `[0, 1]`; 0 malformed rows, 0 out-of-range values.
- 823 images carry ≥2 polygons (max 18); polygon vertex counts 5–786.
- One empty label file (B) — image present, zero polygons.

### D3 — concrete400 masks

- 379/379 masks contain intermediate JPEG intensities (e.g. `image_001` has 205 distinct values over 0–255); **0 masks are strictly binary**.
- The dataset README *documents* this and prescribes `> 127` binarisation at ingestion. Non-binarised use would silently corrupt IoU/Dice.

### D4 — concrete400 boxes

- 511 rows over 379 files, schema `class_id instance_id x_min y_min x_max y_max`; `class_id = 1` everywhere; all coordinates integers in `[0, 511]`; 0 order violations; 0 empty files.
- Coordinates are pixel-space (not normalised) — a format mismatch against YOLO-normalised crack-seg labels (`DSET-004`).

**Result: pass with the documented caveats above.**

---

## E. Split integrity, duplication and leakage

### E1 — exact duplicates (SHA-256, 6,851 files)

**8 duplicate groups, all within-dataset; 0 cross-dataset groups.**

| # | Files | Where | Note |
|---|---|---|---|
| 1–3 | Photos: `facadeab_cr003_v1…2bd63a…` == `…b16d06…`, `facadeg_cr017_v1…379cab…` == `…8bb4c6…`, `facadej_cr020_v2…3572c8…` == `…96563d…`; each with its byte-identical mask pair (6 groups) | façade `train` | same source view exported twice, both copies kept |
| 4 | `facadep_cr026_v2…2af75b8e_mask.png` == `facadep_cr026_v3…90c6cb3c_mask.png` | façade `train` | identical mask on two *different* views (11,250 crack px each) |
| 5 | `crack-seg/images/test/1979.rf.d3ee9d85….jpg` == `1979.rf.dea5db58….jpg` | crack-seg `test` | identical image under two export hashes → double-counted in evaluation |

### E2 — source-ID and scene overlap

**crack-seg (clean):** 1,549 distinct source IDs (train 1,238 / val 200 / test 111); **0** source IDs shared between any two splits; 0 files belong to shared source IDs.

**façade (not clean):**

| Metric | train | valid |
|---|---:|---:|
| Files | 260 | 21 |
| Distinct source views | **87** | 21 |
| Distinct scenes | 36 | 15 |
| Views exported >1× | 87 (86×3, 1×2) | 0 |

- Source views shared across splits: **0** — but scenes shared across splits: **15 of 15 valid scenes**.
- Every `valid` image is a *different view of a wall whose other views are in `train`* (e.g. `facadea_cr001_v1`,`_v3` ∈ train, `_v2` ∈ valid). Confirmed visually: `evidence/comp_facade_a_cr001.jpg`, `evidence/comp_facade_ad_cr005.jpg`.
- The 260 `train` files are 87 unique views re-exported 2–3× as **different crops of the same photograph** (`evidence/facade_variants.jpg`); pairwise mean absolute grey-level difference between variants reaches 78/255, i.e. they are not re-encodings but crop/photometric variants.

**concrete400:** no physical split; README prescribes ID ranges `image_001–303` (train) / `image_304–379` (val) and warns that classification patches need a leakage-safe split built by the user.

### E3 — perceptual near-duplicates (64-bit dHash, 6,191 photos, 19.1 M pairs)

**Strong (Hamming ≤ 6): 925 pairs**

| Bucket | Pairs | Interpretation |
|---|---:|---|
| within `crack-seg/train` | 747 | mostly texture-level similarity between different source IDs; unresolved as true duplicates (`LIMIT-03`) |
| within `concrete400/no_crack` | 111 | patch-grid correlation (adjacent crops of large clean surfaces), consistent with `DSET-005` |
| within `facade/train` | 18 | the byte-identical/near-identical export variants of E1 |
| within `concrete400/crack` | 10 | adjacent patch crops |
| within `crack-seg/val` / `test` | 1 / 2 | includes the exact pair of E1 |
| **cross-split `crack-seg` train↔val** | **4** | different source IDs; possible shared surface or texture coincidence |
| **cross-split `crack-seg` train↔test** | **2** | same caveat |
| cross-dataset façade↔crack-seg | 26 | different sources; likely generic cracked-texture coincidence (`RISK-06`) |
| cross-dataset concrete400↔crack-seg | 4 | same caveat |

**Weak (7–10): 10,244 pairs** — includes cross-split façade train↔valid 1, `crack-seg` train↔val 111, train↔test 24, val↔test 19, concrete400 crack↔no_crack 9. Weak pairs are **not** treated as leakage; they are recorded as a sensitivity note.

**Cross-component check (measured this audit):** dHash distance ≤ 8 between the 1,502 concrete400 classification patches and the 379 segmentation images → **0 pairs**; façade ↔ concrete400 classification → **0 pairs**. The concrete400 components are effectively disjoint sources.

### E4 — config inconsistencies (*documented* vs measured)

`crack-seg.yaml` inline counts are swapped: comments claim `val … 112 images` and `test … 200 images`; disk holds val = 200, test = 112. Path entries are correct, so tooling that reads paths is unaffected; humans and count-based sanity checks are (`C5`).

---

## F. Visual review

Contact sheets and overlays in `evidence/` (random seeds fixed):

| Asset | Content | Observation |
|---|---|---|
| `sheet_facade_train.jpg` | 12 random façade train images | painted/rendered façade walls, stucco, visible hairline cracks, strong shadows; consistent with the declared task |
| `comp_facade_a_cr001.jpg`, `comp_facade_ad_cr005.jpg` | image \| mask overlay \| other-split view | mask aligns with the visible crack; the `valid` view is the same wall as the `train` view (E2) |
| `facade_variants.jpg` | 6 exports of 2 façade views | same photo, different crops — confirms view-level redundancy |
| `sheet_crackseg_train.jpg` | 12 random crack-seg train images | concrete/asphalt/brick/pavement, wide variety, cracks visible |
| `comp_crackseg_1604.jpg` | image + polygon overlay | polygon traces the crack correctly |
| `sheet_c400_seg.jpg` | 8 random concrete400 segmentation images | white-painted concrete with shadows, plus raw concrete/stone |
| `comp_c400_001.jpg` | image \| mask \| overlay | mask aligns with the crack; mask renders as grey-on-black because of JPEG intermediate values (D3) |
| `sheet_cls_big.jpg` | 8 `crack` + 8 `no_crack` patches | all 8 crack patches show clear cracks; 7/8 no-crack patches clean, 1 (`1546.jpg`) has an ambiguous hairline mark → small risk of label noise (`RISK-07`) |

Sampling caveat: 12–16 images per dataset is a sanity check, not a statistical quality estimate (`LIMIT-02`).

---

## G. Cross-dataset consistency

| Dimension | façade | crack-seg | concrete400 | Consequence |
|---|---|---|---|---|
| Resolution | 512×512 | 416×416 | 512×512 / 256×256 | resampling needed for joint training |
| Annotation | raster mask `{0,1}` | normalised polygons | JPEG mask + pixel boxes | three converters required |
| Class id | 1 (declared 0/1/2) | 0 | 1 (boxes) / folder names | unify to a single project class id |
| Surface type | façade render/stucco | mixed concrete/asphalt/brick | painted/raw concrete | domain shift between datasets |
| Licence | **unknown** | AGPL-3.0 header | CC BY 4.0 | distribution risk (`RISK-08`) |

---

## H. Findings register

| ID | Finding | Severity | Evidence | Condition/Decision |
|---|---|---|---|---|
| F1 | All 15 façade `valid` scenes also appear in `train` (view-level split) | **High** | §E2, overlays | C1 / `DSET-002` |
| F2 | Façade `train` = 260 files but 87 unique views (2–3 crops each) | **High** | §E2, `facade_variants.jpg` | C2 / `DSET-002` |
| F3 | concrete400 masks are non-binary JPEG (379/379) | **Medium** | §D3 | C4 / `DSET-003` |
| F4 | Byte-identical image pair in `crack-seg/test`; 3 duplicate pairs in façade `train` | **Medium** | §E1 | C3 / `DSET-006` |
| F5 | 6 strong cross-split near-duplicate pairs in crack-seg (train↔val 4, train↔test 2) | **Medium** | §E3 | `DSET-006`, `RISK-05` |
| F6 | `crack-seg.yaml` comment counts swapped (val/test) | **Low** | §E4 | C5 / `DSET-009` |
| F7 | façade class `2=object` declared but absent; 1 all-background mask; 1 empty label | **Low** | §D1, §D2 | `DSET-003`, `DSET-004` |
| F8 | façade dataset ships no licence statement | **Medium** (process) | §G | C6 / `DSET-008` |
| F9 | Possible hairline-crack label noise in concrete400 `no_crack` (1/8 spot-check) | **Low** | §F | `RISK-07` |
| F10 | Strong foreground imbalance (façade median crack coverage 1.79%) | **Medium** (modelling) | §D1 | `RISK-02` |

---

## I. Verdict

**PASS WITH CONDITIONS.**

The datasets are complete, decodable, correctly paired and internally valid; no structural defect blocks training. The conditions are about *how* they may be used:

- **C1** rebuild façade splits by scene (or report façade results explicitly as view-level with the leakage caveat);
- **C2** treat façade `train` as 87 unique views/36 scenes for sizing, weighting and any "number of images" claim;
- **C3** exclude byte-identical duplicates from evaluation (at minimum `crack-seg/test/1979…` pair) and de-duplicate reported metrics;
- **C4** binarise concrete400 masks (`> 127`) at ingestion and document the threshold;
- **C5** correct the val/test counts in project-side configuration (source YAML left untouched);
- **C6** obtain a licence decision for the façade dataset before redistribution/publication.

A FAIL was considered and rejected: no finding makes the data unusable — every condition has a concrete, low-cost mitigation that can be applied at ingestion without touching the source files.

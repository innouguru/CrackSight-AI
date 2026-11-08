# Dataset Inventory

Audit date: 2026-10-25. All counts are **measured** from disk unless labelled *documented* (from a dataset README/YAML).

## 1. Totals

| Dataset | Files | Bytes | Photo files | Annotation files | Other |
|---|---:|---:|---:|---:|---:|
| `facade-crack-dataset` | 564 | 12,663,804 | 281 JPG | 281 PNG masks | 2 `_classes.csv` |
| `crack-seg` | 8,059 | 110,543,496 | 4,029 JPG | 4,029 TXT labels | 1 `crack-seg.yaml` |
| `concrete400` | 3,019 | 353,974,872 | 1,881 JPG | 379 JPEG masks + 379 TXT boxes | 379 PNG previews + 1 `README.md` |
| **Total** | **11,642** | **477,182,172** | **6,191** | **5,068** | **383** |

Row check: 564 = 281+281+2; 8,059 = 4,029+4,029+1; 3,019 = 1,881+379+379+379+1; columns sum to 6,191+5,068+383 = 11,642.

Baseline fingerprint (used to prove read-only behaviour; re-measured after the audit, unchanged):

```
facade-crack-dataset   564 files   12,663,804 bytes
crack-seg            8,059 files  110,543,496 bytes
concrete400          3,019 files  353,974,872 bytes
TOTAL               11,642 files  477,182,172 bytes
```

## 2. `data/facade-crack-dataset`

### 2.1 Structure and counts

| Split | JPG images | PNG masks | `_classes.csv` | Total |
|---|---:|---:|---:|---:|
| `train/` | 260 | 260 | 1 | 521 |
| `valid/` | 21 | 21 | 1 | 43 |
| **Total** | **281** | **281** | **2** | **564** |

### 2.2 Naming and pairing

- Image: `<source_view>.jpg`; mask: `<source_view>_mask.png` (e.g. `facadea_cr001_v1_jpeg.rf.467e…jpg` ↔ `…_mask.png`).
- Pairing **measured 260/260 in `train`, 21/21 in `valid`**; zero orphan images, zero orphan masks, zero cross-split basename collisions.
- Filename anatomy: `<scene>_v<N>_jpeg.rf.<32-hex>.jpg`, where `<scene>_v<N>` is the source view and `.rf.<hash>` is an export/version suffix.

### 2.3 Format and dimensions (measured, all 281 pairs)

| Property | Images | Masks |
|---|---|---|
| Dimensions | 512×512 (281/281) | 512×512 (281/281) |
| Mode | RGB | L (8-bit single channel) |
| Unreadable files | 0 | 0 |
| Image/mask dimension mismatches | 0 | — |
| Distinct pixel values | — | `{0, 1}` only (all 281 masks) |

### 2.4 Label semantics (`_classes.csv`, *documented*)

```
Pixel Value, Class
0, background
1, crack
2, object
```

Measured: value `2` never occurs — masks are effectively binary (background/crack).

### 2.5 Split composition (measured)

| Split | Files | Distinct source views | Distinct scenes | Views exported >1× |
|---|---:|---:|---:|---:|
| `train` | 260 | 87 | 36 | 87 (86 views ×3, 1 view ×2) |
| `valid` | 21 | 21 | 15 | 0 |

- Distinct pre-`.rf.` source-view IDs shared between splits: **0**.
- Distinct scenes (view suffix `_v<N>` stripped) shared between splits: **15 of 15 `valid` scenes** — every `valid` scene also appears in `train`.

### 2.6 Crack coverage (measured over 281 masks, fraction of pixels > 0)

| Mean | Median | Min | Max |
|---:|---:|---:|---:|
| 3.31% | 1.79% | 0.00% | 23.96% |

One mask is entirely background: `train/facadeai_cr010_v3_jpeg.rf.688153b4b2cd9daba7b33d3cf20c052b_mask.png`.

### 2.7 Provenance and licence

Roboflow-style export (`.rf.` hashes, `_classes.csv`). **No licence file or licence statement ships with the dataset** — status unknown (see `RISK-08`).

## 3. `data/crack-seg`

### 3.1 Structure and counts

| Split | `images/` | `labels/` | Pairing |
|---|---:|---:|---|
| `train` | 3,717 | 3,717 | 1:1 |
| `val` | 200 | 200 | 1:1 |
| `test` | 112 | 112 | 1:1 |
| **Total** | **4,029** | **4,029** | 0 orphans |

Plus `crack-seg.yaml` (dataset config). Total 8,059 files.

### 3.2 Format (measured)

- Images: 416×416 RGB JPG, **4,029/4,029 readable**, 0 dimension anomalies.
- Labels: YOLO segmentation lines `class x1 y1 x2 y2 …`; 4,029 files, **5,290 polygon records** total.
  - Class IDs present: `{0}` only (`crack`, per YAML `names: {0: crack}`).
  - All coordinates finite and within `[0, 1]`: 0 violations.
  - Malformed/short lines: 0. Empty (0-byte) label files: **1** — `labels/val/3513.rf.782300f38d0a008b3340e54b643e713e.txt`.
  - Polygons per image: 0→1, 1→3,205, 2→591, 3→137, 4→54, 5→19, 6→8, 7→5, 8→5, 9→1, 15→1, 16→1, 18→1. Images with ≥2 polygons: 823.
  - Vertices per polygon: 5–786.

### 3.3 `crack-seg.yaml` (*documented*, verbatim comments)

```yaml
path: crack-seg
train: images/train   # 3717 images   ← matches disk
val:   images/val     # 112 images    ← WRONG, disk has 200
test:  images/test    # 200 images    ← WRONG, disk has 112
```

Path entries are correct; only the inline counts are swapped. Header: `Ultralytics AGPL-3.0 License - https://ultralytics.com/license`; download URL `…/v0.0.0/crack-seg.zip`; docs URL `https://docs.ultralytics.com/datasets/segment/crack-seg/`.

### 3.4 Split hygiene (measured)

- Distinct source IDs (filename before `.rf.`): **1,549** — train 1,238, val 200, test 111.
- Source IDs appearing in more than one split: **0** (files per shared source ID: 0).

## 4. `data/concrete400`

### 4.1 Structure and counts (all *documented* values confirmed by measurement)

| Component | Path | Files | Format | Dimensions |
|---|---|---:|---|---|
| Segmentation images | `Segmentation/Image/` | 379 | JPEG | 512×512 |
| Segmentation masks | `Segmentation/Masks/` | 379 | JPEG | 512×512 |
| Detection boxes | `Object Detection/Boxes/` | 379 TXT / **511 boxes** | TXT | pixel coords |
| Box visualisations | `Object Detection/Boxes_visualizations/` | 379 | PNG | 512×512 |
| Classification crack | `Classification/crack/` | 633 | JPEG | 256×256 |
| Classification no-crack | `Classification/no_crack/` | 869 | JPEG | 256×256 |
| Documentation | `README.md` | 1 | Markdown | — |
| **Total** | | **3,019** | | |

Pairing by identifier stem: image ↔ mask ↔ box ↔ visualisation = **379/379/379/379**, 0 orphans.

### 4.2 Mask format (measured)

- Stored as JPEG, RGB mode but all three channels identical (grayscale content).
- **379/379 masks contain intermediate values** (none is strictly binary); `image_001.jpg` alone has 205 distinct values spanning 0–255.
- The dataset README *documents* this and prescribes binarisation: `crack = intensity > 127`, `background = ≤ 127`.

### 4.3 Box format (measured; schema *documented*)

Rows: `class_id instance_id x_min y_min x_max y_max` (space-separated integers).
- 511 rows across 379 files; `class_id` is `1` in every row.
- All coordinates integers in `[0, 511]`; 0 rows with `x_min ≥ x_max` or `y_min ≥ y_max`; 0 empty TXT files.

### 4.4 Classification (measured)

- All 1,502 patches are 256×256 RGB and readable; 0 unreadable.
- Basename overlap between `crack/` and `no_crack/`: **0**.
- Class balance: crack 633 (42.1%) vs no_crack 869 (57.9%).
- Filenames (`0.jpg`, `1176.jpg`, …) do **not** correspond to full-size identifiers (*documented* and confirmed: 0 perceptual near-matches between the 1,502 classification patches and the 379 segmentation images at dHash distance ≤ 8).

### 4.5 Split guidance (*documented* in README)

| Subset | Identifiers | Images |
|---|---|---:|
| Training | `image_001`–`image_303` | 303 |
| Validation | `image_304`–`image_379` | 76 |

Files are not physically split. No predefined split exists for the classification patches; the README explicitly warns about leakage when building one.

### 4.6 Provenance and licence (*documented*)

- Vietnam urban infrastructure (Hanoi), 2026, Zenodo v1, **DOI 10.5281/zenodo.21193945**, **CC BY 4.0**.
- Citation block and contact address ship inside `README.md`.

## 5. Cross-dataset comparison

| Property | façade-crack-dataset | crack-seg | concrete400 |
|---|---|---|---|
| Task coverage | segmentation | segmentation | segmentation + detection + classification |
| Resolution | 512×512 | 416×416 | 512×512 / 256×256 |
| Annotation type | raster mask (PNG, `{0,1}`) | normalized polygons (TXT) | JPEG mask (needs binarisation) + pixel boxes |
| Class scheme | 0/1/2 declared, 1 used | `0: crack` | `1: crack` (boxes), folder names (classification) |
| Provided splits | train/valid (view-level) | train/val/test (source-ID clean) | recommended ID ranges, not materialised |
| Physical splits | yes | yes | no |
| Licence in tree | **none found** | AGPL-3.0 header in YAML | CC BY 4.0 |
| Unique source views | 87 train + 21 valid | 1,549 source IDs | 379 images + 1,502 patches |

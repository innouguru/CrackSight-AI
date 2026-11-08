# Risks and Limitations

Audit date: 2026-10-25. Two parts: **RISK-nn** = risks the *dataset* poses to the project; **LIMIT-nn** = limitations of this *audit*. Likelihood/impact: Low / Medium / High.

## Part 1 — Risk register

### RISK-01 — Façade scene leakage produces optimistic metrics · High impact · High likelihood
- **Evidence:** all 15 `valid` scenes also occur in `train` (report §E2); overlays show same-wall crops (`evidence/comp_facade_a_cr001.jpg`).
- **Effect:** façade IoU/Dice measured on the shipped split overstates real-world generalisation to unseen buildings; a paper/review citing it would be wrong.
- **Mitigation:** DSET-002 scene-grouped split (condition C1); report per-dataset metrics with the grouping rule stated.
- **Residual:** scene keys are inferred from filenames; a scene not following `_v<N>` would be mis-grouped (checked, none found).

### RISK-02 — Foreground imbalance / vanishing-crack bias · Medium impact · High likelihood
- **Evidence:** façade crack coverage mean 3.31%, median 1.79%, min 0%; one all-background mask; crack-seg typical 1 polygon/image.
- **Effect:** models can score high accuracy by predicting background; naive losses under-weight thin cracks.
- **Mitigation:** Dice/Tversky/focal-style losses, per-image reporting, include the empty-mask image in training (not evaluation bias), report crack-only precision/recall.
- **Residual:** metrics still hide performance on sub-pixel cracks.

### RISK-03 — Binarisation/rasterisation threshold erases hairline cracks · Medium impact · Medium likelihood
- **Evidence:** concrete400 masks are JPEG with intermediate values (379/379, report §D3); polygons must be rasterised for the canonical representation (DSET-004).
- **Effect:** thin cracks (<1–2 px) may vanish at threshold 127 or between polygon vertices → systematically low recall on the hardest cases.
- **Mitigation:** threshold fixed and documented (C4); sensitivity ablation at 127 vs Otsu; supersampling for polygon rasterisation.
- **Residual:** irreducible for JPEG-mask data; only quantifiable via ablation.

### RISK-04 — Duplicate files inflate scores · Medium impact · Medium likelihood
- **Evidence:** byte-identical pair inside `crack-seg/test` (report §E1); 3 duplicate pairs in façade `train`.
- **Effect:** evaluation double-counts one image; training sees repeated samples.
- **Mitigation:** DSET-006 dedup at ingestion (condition C3); denominators recorded per run.
- **Residual:** perceptual near-duplicates across splits remain (see RISK-05).

### RISK-05 — Unresolved cross-split near-duplicates in crack-seg · Medium impact · Low/Medium likelihood
- **Evidence:** strong dHash pairs train↔val 4, train↔test 2, all with different source IDs (report §E3).
- **Effect:** if these are the same photographed surface (different crops), test scores are slightly optimistic; if they are just similar texture, no effect. **Currently unresolvable from files alone.**
- **Mitigation:** inspect the 6 pairs manually before publishing crack-seg results; exclude if confirmed same surface; treat as sensitivity analysis.
- **Residual:** judgement call, must be documented in any results write-up.

### RISK-06 — Cross-dataset perceptual matches mistaken for leakage · Low impact · Medium likelihood
- **Evidence:** 30 strong cross-dataset pairs (façade↔crack-seg 26, concrete400↔crack-seg 4) with no shared source IDs; 0 exact cross-dataset duplicates.
- **Effect:** over-aggressive deduplication could delete valid data; conversely, ignoring a true shared source would leak.
- **Mitigation:** DSET-006 keeps exact-only dedup; cross-dataset pairs are recorded, not deleted; spot-check a few before any cross-dataset claim.
- **Residual:** texture datasets make perceptual evidence inherently ambiguous (LIMIT-03).

### RISK-07 — Label noise in concrete400 classification · Low impact · Low/Medium likelihood
- **Evidence:** visual spot-check of 8 `no_crack` patches: 1 (`1546.jpg`) shows an ambiguous hairline mark; 8/8 `crack` patches clearly cracked (`evidence/sheet_cls_big.jpg`).
- **Effect:** small accuracy ceiling and noisy gradients for a classification head.
- **Mitigation:** treat classification as auxiliary; audit a larger random sample (n ≥ 100) before relying on it; consider soft labels or annotator review of disagreements.
- **Residual:** sample size 8 is far from a noise-rate estimate (LIMIT-02).

### RISK-08 — Unknown licence for the façade dataset · High impact (process) · Medium likelihood
- **Evidence:** no licence/README/provenance file anywhere in `data/facade-crack-dataset`; concrete400 = CC BY 4.0; crack-seg = AGPL-3.0 header.
- **Effect:** redistribution, public demo, or artifact packaging could infringe rights; publication may be delayed.
- **Mitigation:** DSET-008 — façade restricted to internal experiments until provenance is resolved; attribute the two licensed datasets correctly.
- **Residual:** not legal advice; upstream Roboflow project licence may itself be unclear.

### RISK-09 — Domain shift across datasets hides failures · Medium impact · High likelihood
- **Evidence:** façade render/stucco vs crack-seg mixed pavement/brick vs concrete400 painted concrete (contact sheets, report §G).
- **Effect:** a pooled model may look fine overall while failing on one domain (e.g. painted walls with shadows).
- **Mitigation:** DSET-007 mandatory per-dataset metrics; domain-balanced sampling; per-domain error analysis.
- **Residual:** small façade `valid` (21 images / 15 scenes) gives high metric variance.

### RISK-10 — Sample-size overstatement for façade · Medium impact · High likelihood
- **Evidence:** 260 `train` files = 87 unique views exported 2–3× (report §E2).
- **Effect:** power calculations, "trained on N images" claims and epoch weighting are wrong by ~3×; variant crops also act as unintended augmentation.
- **Mitigation:** condition C2 — quote 87 views/36 scenes; dedup byte-identical copies (DSET-006).
- **Residual:** variants are not identical, so "unique view" is the honest unit, not "unique image".

## Part 2 — Audit limitations

- **LIMIT-01 — No external manifest.** Completeness can only be checked against the directory tree itself; a file that was never shipped cannot be detected.
- **LIMIT-02 — Visual sampling is small.** 12–16 random images per dataset plus targeted overlays; sufficient for sanity checks, not for a statistical defect rate (label-noise rate in particular).
- **LIMIT-03 — Perceptual hashing is a heuristic.** 64-bit dHash on 8×8 grayscale is sensitive to crop/resize and blind to colour; on texture-dominated imagery it produces both false positives (similar concrete) and false negatives (same scene, different lighting/crop). All "near-duplicate" claims are *evidence*, not proof, and were qualified accordingly.
- **LIMIT-04 — No legal review.** Licence findings are file-inspection results, not legal advice.
- **LIMIT-05 — Annotation accuracy not verified.** Masks/polygons were checked for *format and gross alignment with the visible crack* (overlays), not pixel-perfect correctness against an independent annotator.
- **LIMIT-06 — Provenance of images not traced.** Whether crack-seg and façade images come from overlapping public sources cannot be determined from the files; 0 exact cross-dataset duplicates is the strongest available statement.
- **LIMIT-07 — Single-configuration environment.** All measurements come from one Python 3.12.5 / Pillow 13.0.0 / NumPy 2.5.4 run on 2026-10-25; decode results could differ marginally with other codecs, counts would not.
- **LIMIT-08 — Read-only boundary.** Because nothing was modified, this audit cannot *prove* the datasets match their upstream originals — only that they are internally consistent and unchanged during the audit (baseline re-count identical).

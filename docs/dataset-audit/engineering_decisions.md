# Engineering Decisions — Dataset

Each record: Status · Context (Question) · Evidence · Method · Result · Interpretation · Options/Alternatives · Decision · Consequences · Risks/Limitations · Revisit conditions / Follow-up.
Identifiers `DSET-nnn` are permanent; superseded records keep their ID and get `Status: Superseded by …`.
Audit date: 2026-10-25.

---

## DSET-001 — Acceptance of the three datasets for training

**Status:** Accepted (2026-10-25)
**Context:** May the three datasets under `data/` be used as the training basis at all?
**Evidence:** 11,642 files / 477,182,172 bytes; 6,570 image files decoded with 0 failures; pairings façade 281/281, crack-seg 4,029/4,029, concrete400 379/379/379/379; 5,290 polygon records and 511 box rows all numerically valid; 0 cross-dataset exact duplicates.
**Method:** Full decode + bidirectional stem joins + label parsing (report §B–§D).
**Result:** No blocking defect; one 0-byte label file (valid empty annotation), no orphan pairs, no unreadable file.
**Interpretation:** Structural quality is sufficient; remaining issues are usage-policy issues, not data defects.
**Alternatives:** (a) accept as-is; (b) reject and source new data; (c) accept only some datasets.
**Decision:** **Accept all three**, subject to conditions C1–C6 and the records below.
**Consequences:** Training can start; ingestion code must implement DSET-003/004/006.
**Risks/Limitations:** No external manifest exists, so "missing but never shipped" files cannot be detected (LIMIT-01).
**Revisit conditions:** Any dataset file changes (count/bytes differ from baseline), or new corruption found.

---

## DSET-002 — Façade split strategy (scene-level grouping)

**Status:** Accepted — required before any façade metric is reported (2026-10-25)
**Context:** The façade `valid` split shares **all 15 of its scenes** with `train`, and `train`'s 260 files are only **87 unique views** exported 2–3× as different crops. Do we keep the shipped split?
**Evidence:** Report §E2; `evidence/comp_facade_a_cr001.jpg`, `evidence/comp_facade_ad_cr005.jpg`, `evidence/facade_variants.jpg`; scene intersection = 15/15; variant pairs differ by up to 78/255 mean grey level.
**Method:** Source-ID and scene-key intersection, plus visual confirmation of same-wall crops.
**Result:** View-level identifiers are disjoint, but scene content is not → classic same-source leakage.
**Interpretation:** Metrics on the shipped split measure interpolation between views of known walls, not generalisation to unseen walls. The 260-file count also overstates sample size ~3×.
**Alternatives:**
  (a) keep shipped split and disclose the caveat;
  (b) re-split by scene (group `scene = id without _v<N>`), stratified by crack presence;
  (c) drop `valid` and use only `train` with cross-validation by scene;
  (d) discard the façade dataset.
**Decision:** **(b) rebuild splits grouped by scene** (fallback: (a) with explicit disclosure if re-splitting is deferred). Sample size claims must use 87 views/36 scenes for `train`.
**Consequences:** Shipped `train/valid` folder boundaries become advisory; a project-side split manifest file will define membership; all façade results must state the grouping rule.
**Risks/Limitations:** Re-splitting reduces training views (≈36-scene granularity); scene keys are inferred from filename patterns — a scene without `_v<N>` suffix would be mis-grouped (checked: all scene keys follow the pattern).
**Revisit conditions:** New façade data arrives; scene inference proves wrong; or metrics are needed before the manifest exists (then apply (a)).

---

## DSET-003 — Mask/label canonicalisation and binarisation

**Status:** Accepted (2026-10-25)
**Context:** Masks arrive in three incompatible encodings: façade PNG `{0,1}`, concrete400 JPEG with intermediate intensities (379/379 non-binary), crack-seg normalised polygons. façade also declares an unused class `2=object`. What does the pipeline treat as ground truth?
**Evidence:** Report §D1/D3; `_classes.csv` content; concrete400 README binarisation rule (`>127`); measured 205 distinct values in `image_001` mask.
**Method:** Unique-value histograms over all masks; comparison with *documented* schemas.
**Result:** Only façade masks are already binary; concrete400 requires thresholding; class `2` never occurs.
**Interpretation:** Uncritical use of concrete400 masks would inflate/deflate IoU unpredictably; declaring 3 classes would create an always-empty class.
**Alternatives:** (a) threshold 127 (publisher's rule); (b) Otsu per image; (c) ignore grey band (treat 127–200 as ignore-region); (d) repair masks manually.
**Decision:** **(a) threshold at >127 for concrete400**, `{0,1}` passthrough for façade, polygon rasterisation for crack-seg; canonical label set is binary `{background=0, crack=1}` — declared façade class `2` is dropped from the schema.
**Consequences:** One documented preprocessing step in the ingestion layer; evaluation is always on binarised masks; threshold value recorded in every results file.
**Risks/Limitations:** Threshold choice shifts thin-crack pixels (RISK-03); (c) would be more honest for ambiguous pixels but is harder to evaluate comparably.
**Revisit conditions:** Results become threshold-sensitive (run Otsu as an ablation); publisher releases a v2 with PNG masks.

---

## DSET-004 — Unified annotation schema and converters

**Status:** Accepted (2026-10-25)
**Context:** Three annotation formats (raster mask, YOLO-normalised polygons, pixel boxes with `class_id=1`) and two class-id conventions (`0` vs `1`) must feed one project.
**Evidence:** Report §D2/D4/G; concrete400 README box schema and YOLO conversion note; crack-seg YAML `names: {0: crack}`.
**Method:** Schema extraction from files + *documented* formats.
**Result:** Formats are individually well-formed; only conventions differ (normalisation, class id, instance id column).
**Interpretation:** This is a mapping problem, not a data problem.
**Alternatives:** (a) convert everything to YOLO-segmentation at load time; (b) convert everything to raster masks at load time; (c) maintain three loaders and unify only at metric time.
**Decision:** **(b) canonical internal representation = binary raster mask** at native resolution, with (a) as an export format for YOLO training; class id unified to project class `0 = crack` everywhere; box annotations converted to masks only where masks exist (all 379 do — boxes are auxiliary).
**Consequences:** Box-only training is not needed (masks supersede boxes); conversion code needs tests against the measured schemas.
**Risks/Limitations:** Polygon→raster rasterisation resolution affects thin cracks (RISK-03); box→mask conversion is not performed (boxes are regions, not pixel-accurate).
**Revisit conditions:** Detection becomes a primary task; or a dataset ships boxes without masks.

---

## DSET-005 — Using concrete400's three components

**Status:** Accepted (2026-10-25)
**Context:** concrete400 offers segmentation (379), detection (511 boxes) and classification (1,502 patches) with no physical splits. Are they one dataset or three, and how do we split classification safely?
**Evidence:** Report §E3 — 0 perceptual near-matches between classification patches and segmentation images (dHash ≤ 8); README recommends `image_001–303` / `image_304–379` and warns about classification leakage; measured 111 strong near-dup pairs *within* `no_crack` (adjacent patch crops).
**Method:** Cross-component perceptual hashing; README review; within-class near-dup clustering.
**Result:** Components are disjoint sources; classification patches cluster (adjacent crops of the same surface), so random splits can leak clusters.
**Interpretation:** Segmentation/detection can use the documented ID split; classification needs cluster-aware splitting.
**Alternatives:** (a) random classification split; (b) group patches by perceptual cluster, then split clusters; (c) exclude classification from the project.
**Decision:** **Segmentation/detection follow the documented `image_001–303`/`304–379` split; classification uses (b)** — build near-duplicate clusters (dHash ≤ 6) and assign whole clusters to splits, stratified to preserve the 633/869 class balance.
**Consequences:** Classification splits are reproducible only via the cluster manifest; the README's "document your strategy" requirement is satisfied.
**Risks/Limitations:** dHash clustering can merge distinct patches (texture similarity) or split true siblings (crop changes) — cluster count is a modelling choice, not ground truth.
**Revisit conditions:** Cluster-aware split proves too small/unbalanced; publisher ships an official classification split.

---

## DSET-006 — Duplicate and near-duplicate policy

**Status:** Accepted (2026-10-25)
**Context:** 8 byte-identical groups (incl. one inside `crack-seg/test`) and 925 strong perceptual pairs exist. Do we deduplicate, and how far?
**Evidence:** Report §E1/E3; exact groups listed; cross-split strong pairs: crack-seg train↔val 4, train↔test 2; façade 3 duplicate photo+mask pairs in `train`.
**Method:** SHA-256 grouping + all-pairs dHash.
**Result:** Exact duplicates are unambiguous; most of the 925 strong pairs are *within-split texture similarity*, not copies.
**Interpretation:** Deduplicating everything would delete legitimate data; ignoring exact duplicates inflates evaluation.
**Alternatives:** (a) dedup exact only; (b) dedup exact + perceptual ≤6; (c) dedup + exclude whole near-dup clusters; (d) no action.
**Decision:** **(a) for training and evaluation: remove byte-identical duplicates (keep one file per digest, preferring `train`), and exclude the `crack-seg/test` duplicate from scored metrics;** (b)/(c) rejected as over-aggressive — perceptual pairs are recorded (report §E3) and used only as a sensitivity analysis.
**Consequences:** Reported sample counts drop by 7 files (3 façade photo+mask pairs, 1 crack-seg image); evaluation denominators must be documented.
**Risks/Limitations:** If the 4+2 cross-split crack-seg pairs are genuinely the same photographed surface, small optimistic bias remains (RISK-05).
**Revisit conditions:** Cross-split pairs are confirmed as shared surfaces (then exclude from eval too); or new duplicates appear.

---

## DSET-007 — Multi-dataset mixing and domain reporting

**Status:** Accepted (2026-10-25)
**Context:** The three datasets differ in surface type (façade render vs mixed pavement vs painted concrete), resolution and annotation density. Pool them into one training set?
**Evidence:** Report §G; contact sheets `evidence/sheet_*.jpg`; crack coverage medians: façade 1.79%, crack-seg 1–2 polygons/image typical, concrete400 per README.
**Method:** Cross-dataset comparison of format, resolution, content (visual), and label statistics.
**Result:** Shared task (binary crack segmentation) but clear domain shift; 0 exact cross-dataset duplicates; 30 cross-dataset strong perceptual pairs (likely texture coincidence).
**Interpretation:** Joint training is feasible but a single pooled score would hide per-domain failures.
**Alternatives:** (a) pool with per-dataset metrics; (b) train per dataset and ensemble; (c) pretrain on one, fine-tune on another; (d) domain-balanced sampling.
**Decision:** **(a) pool with mandatory per-dataset/per-split reporting**, plus domain-balanced batch sampling; (b)/(c) reserved as ablations (see `experiment_plan.md`).
**Consequences:** Every results table carries façade/crack-seg/concrete400 columns; no single "overall" number without qualification.
**Risks/Limitations:** Balancing requires the façade scene-grouped manifest (DSET-002) to be meaningful.
**Revisit conditions:** Negative transfer observed (pooled model worse than per-domain on any dataset).

---

## DSET-008 — Licensing and provenance gate

**Status:** **Open — blocking for redistribution/publication, not for internal experiments** (2026-10-25)
**Context:** May the data be redistributed, demoed publicly, or included in a published artifact?
**Evidence:** concrete400 `README.md`: CC BY 4.0, DOI 10.5281/zenodo.21193945; crack-seg YAML header: Ultralytics AGPL-3.0 + download URL; façade dataset: **no licence file, no README, no licence header found anywhere in the tree**.
**Method:** Full-tree text/file search for licence/readme/provenance files; README review.
**Result:** Two of three datasets carry clear terms; façade carries none.
**Interpretation:** Absence of a licence means "all rights reserved" by default — internal research use is a risk decision, redistribution is not permissible without a grant.
**Alternatives:** (a) trace origin (Roboflow project) and obtain the licence; (b) restrict façade to internal experiments; (c) replace façade with a licensed alternative; (d) ignore.
**Decision:** **(b) now, with (a) as the follow-up:** façade stays in internal experiments only; nothing from it is redistributed or embedded in public artifacts until (a) resolves. (d) rejected.
**Consequences:** Public deliverables may exclude façade-derived samples/screenshots; attribution text prepared for concrete400 (CC BY 4.0) and crack-seg (AGPL-3.0).
**Risks/Limitations:** Licence of the *source* Roboflow project may itself be ambiguous; this is not legal advice (LIMIT-04).
**Revisit conditions:** Licence found/obtained (then Status: Accepted); or publication requires data release.

---

## DSET-009 — Handling upstream config errors

**Status:** Accepted (2026-10-25)
**Context:** `crack-seg.yaml` comments claim `val 112` / `test 200` while disk holds val 200 / test 112. Do we edit the dataset file?
**Evidence:** Report §E4 (verbatim YAML vs measured counts); path entries are correct.
**Method:** File read + directory count.
**Result:** Only human-readable comments are wrong; programmatic paths are right.
**Interpretation:** Editing source data would break the read-only guarantee and diverge from the upstream artifact.
**Alternatives:** (a) leave source untouched, correct in project config + docs; (b) patch the YAML; (c) ignore.
**Decision:** **(a)** — project-side config carries the corrected counts; this audit records the discrepancy; source file untouched.
**Consequences:** Anyone reading the raw YAML still sees wrong counts (documented here); count-based scripts must read directories, not comments.
**Risks/Limitations:** Documentation drift if upstream fixes it silently.
**Revisit conditions:** Dataset re-downloaded or updated.

---

## Decision index

| ID | Topic | Status |
|---|---|---|
| DSET-001 | Dataset acceptance | Accepted |
| DSET-002 | Façade scene-level split | Accepted (blocking for façade metrics) |
| DSET-003 | Mask binarisation + class schema | Accepted |
| DSET-004 | Canonical annotation representation | Accepted |
| DSET-005 | concrete400 component/split policy | Accepted |
| DSET-006 | Deduplication policy | Accepted |
| DSET-007 | Mixing & per-domain reporting | Accepted |
| DSET-008 | Licensing gate | **Open** (internal-only for façade) |
| DSET-009 | Upstream config errors | Accepted |

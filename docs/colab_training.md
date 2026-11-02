# Colab Training Workflow — M3 Crack Segmentation Baseline

## Purpose
Run a reproducible binary crack-segmentation baseline (B1: U-Net ResNet-34) using Google Colab GPU, importing the actual project modules rather than duplicating model/training logic.

## Prerequisites
- Google Colab account.
- GPU runtime selected (`Runtime > Change runtime type > Hardware accelerator > GPU`).
- Project source archive uploaded and extracted (see Section 4 in notebook).
- Dataset files placed in persistent storage (recommended: Google Drive) or uploaded.

## Source code transfer (no Git repository)
This project is not a public Git repository. Do not initialize Git or invent a URL. Use one of:
1. **Archive**: zip `src/`, `tests/unit/`, `configs/`, `scripts/`, `docs/`, `notebooks/` locally (exclude `.venv`, caches, secrets, raw datasets unless required). Upload archive to Colab; extract to `/content/project/`.
2. **Drive mount**: place the folder in `MyDrive/crack-detection-project/` and set `sys.path` accordingly.

Excluded from archive: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`, temporary output files.

## Dependency strategy
- **Local (`.venv`, Windows CPU)**: `torch>=2.3.0,<2.7.0`, `torchvision>=0.18.0,<0.22.0` (CPU-compatible).
- **Colab**: uses the runtime-provided `torch` + `torchvision`. We do not pin Colab to an old CUDA version merely to match local. Only install missing packages (`Pillow`, `numpy`, `PyYAML`, `pytest`, `matplotlib`).

## Dataset access
- Generate loader-compatible manifests before training: `python scripts/generate_full_manifests.py --output outputs/manifests`. Verify the output JSON files contain `records` arrays with `image_path`, `annotation_path`, `dataset`, `split`, `mask_conversion_rule`, and `excluded_from_scored_eval`. Confirm crack-seg scored test = 111.
- `build_dataset_manifests.py` produces audit evidence (`pipeline_verified.md`) and exclusion lists, not full loader-compatible manifests.
- Do not upload all datasets automatically; explain placement in the notebook.
- Do not include façade dataset in this B1 experiment (blocked by scene leakage and unverified licence).
- Validate manifests and binary conversion before training (`docs/dataset-audit/near_duplicate_inspection.md` documents the 6 unresolved near-duplicate pairs).

## Selecting GPU
1. `Runtime > Change runtime type > Hardware accelerator > GPU`.
2. Confirm `torch.cuda.is_available()` is `True`.
3. If unavailable, the notebook stops with a clear error and requires explicit user confirmation before any long CPU run.

## Notebook sections
1. Purpose / prerequisites / eligibility / limitations.
2. Environment detection (Python, PyTorch, CUDA, GPU name, memory).
3. GPU selection verification.
4. Source archive upload / extraction.
5. Dependency installation.
6. Dataset configuration and placement.
7. Manifest and binary mask validation.
8. Small smoke test (1 epoch, small subset).
9. Full experiment configuration (`configs/experiment_config.yaml`).
10. Validation and final test evaluation stage rules.
11. Export predictions, overlays, metrics, logs, checkpoints.
12. Verify persistent storage of outputs.
13. Resume and reproduction instructions.

## Failure handling
- Environment failure: clear error message (GPU unavailable, manifest missing, dataset missing).
- Smoke-test failure: stop; fix code or paths before full run.
- Full-training failure: document error; do not hide repeated failures; recover by reducing batch size/image size and restarting from the last valid checkpoint.

## Safety and reporting rules
- Never claim structural safety or physical measurements from segmentation outputs alone.
- Report actual scored sample counts (crack-seg test = 111 after exact-duplicate exclusion).
- Report unresolved near-duplicate limitations explicitly.
- Record exclusions, exclusions reasons, and evaluation conventions in experiment metadata.
- Keep results for Crack-Seg and Concrete400 segmentation separate; do not combine into a single headline score.

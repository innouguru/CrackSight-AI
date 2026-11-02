# DEVELOPMENT RULES

## General Development Practices

1. **Inspect before modifying.** Always read existing code before changing it.
2. **Follow existing architecture.** Use conventions established in `TECHNICAL_DESIGN.md` and `APP_SPECIFICATION.md`.
3. **Prefer modular, maintainable, reusable code.** Avoid duplication.
4. **Python modules are the source of truth.** Use notebooks primarily for exploration and visualization.
5. **Include explanatory comments** where they improve understanding (not redundant ones).
6. **Add or update tests for new functionality.** Never ship untested code.
7. **Run relevant tests and report actual results.** Do not claim tests passed unless executed successfully.
8. **Do not silently weaken tests** to make implementation pass.
9. **Avoid unnecessary dependencies and infrastructure.** Respect the limited development budget.
10. **Preserve unrelated modifications and existing artifacts.** Never discard someone else's work.
11. **Never expose secrets or modify environment files unnecessarily.**

## Git Rules

1. Inspect `git status` and exact diffs before committing.
2. Stage only files belonging to the completed milestone.
3. Preserve unrelated tracked modifications and untracked files.
4. Never reset, clean, or discard unrelated work.
5. Never push unless explicitly requested.
6. Do not initialize Git automatically.

## Project-Specific Constraints

1. **Application is an inspection aid, not a structural safety tool.** Never claim the system determines structural safety.
2. **Pixel measurements only.** No millimetres, centimetres, or physical dimensions without calibration.
3. **No manual segmentation-mask editing.**
4. **No reference-mask uploads.**
5. **No CSV research exports.**
6. **No model evaluation workspace.**
7. **No public shareable report links.**
8. **Existing model checkpoint is excluded from Git.** Do not change `.gitignore` for model weights.
9. **CPU inference initially.** Do not assume GPU availability.
10. **Inference service hosting unresolved.** Do not select a hosting provider without benchmarking.

## File Ownership

| Area | Files / Directories |
|---|---|
| Model code | `src/crack_detection/model.py`, `src/crack_detection/train_loop.py`, `src/crack_detection/metrics.py`, `src/crack_detection/loss.py` |
| Inference code | `src/crack_detection/inference.py` |
| Dataset code | `src/crack_detection/data/`, `scripts/` |
| Tests | `tests/unit/` |
| Application docs | `PROJECT_CONTEXT.md`, `APP_SPECIFICATION.md`, `TECHNICAL_DESIGN.md`, `ROADMAP.md` |
| Agent context | `AGENTS.md`, `agent_context/` |
| Project docs | `architecture.md`, `project_vision.md`, `environment.md`, `docs/` |

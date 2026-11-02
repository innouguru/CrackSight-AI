# CrackSight AI — AI-Assisted Building Inspection

**Status:** Context and documentation milestone complete. Application development has not yet started.

CrackSight AI is an AI-assisted building inspection platform that helps users detect visible cracks in photographs of structural components. It is designed as an inspection aid for ordinary users — not a replacement for professional structural engineering assessment.

## What CrackSight AI Addresses

Building inspectors and maintenance professionals regularly need to document visible cracks in walls, beams, and columns. CrackSight AI provides AI-powered crack segmentation from photographs, producing original images, predicted crack masks, visual overlays, and pixel-level measurements to assist inspection workflows.

## Capabilities (Planned)

- Upload or capture photographs of walls, beams, and columns
- AI-assisted crack detection using a U-Net with ResNet-34 encoder
- Predicted crack mask and overlay for each photograph
- Pixel measurements (image-space only, no physical calibration in the initial version)
- Inspection lifecycle: create inspections, save results, manually verify detections, mark inspections as Completed
- Professional PDF inspection reports (branded, with disclaimers, page numbers, and clear AI vs inspector observation distinctions)
- Guest analysis (limited per-session) and registered-user saved inspection history
- Responsive interface for desktop, tablet, and mobile

## Existing Implementation (Verified)

- **Trained model:** U-Net with ResNet-34 encoder (`UNetResNet34`) — checkpoint at `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth`
- **Baseline evaluation:** Mean Dice 0.7242 | Mean IoU 0.5884 | Precision 0.7379 | Recall 0.7758 (111 scored test records)
- **Reusable inference pipeline:** `src/crack_detection/inference.py` (`CrackSegmentationPipeline`, `run_inference()`)
- **Preprocessing matches training exactly:** RGB → resize 256×256 (bilinear) → `/255.0` → CHW tensor → batch dimension
- **Dataset ingestion pipeline:** `src/crack_detection/data/` — manifest-based contracts, binary mask conversion, deduplication, validation
- **Unit tests:** `tests/unit/test_inference.py` and dataset pipeline tests verified passing
- **Documentation:** `APP_SPECIFICATION.md`, `TECHNICAL_DESIGN.md`, `ROADMAP.md`, `PROJECT_CONTEXT.md`, `AGENTS.md`

## Planned Architecture (Not Yet Implemented)

- **Frontend:** React + TypeScript (responsive)
- **Main backend:** Python FastAPI (inspection management, authentication, PDF generation)
- **Private inference service:** Loads existing `UNetResNet34` checkpoint, performs CPU-only segmentation
- **Database:** Neon PostgreSQL
- **Object storage:** Cloudflare R2
- **Authentication:** Clerk (email/password + Google sign-in)

## Supported Components

Initial version supports: walls, beams, columns.

## Safety and Limitations

CrackSight AI is an AI-assisted inspection tool. It does **not** determine structural safety, provide engineering recommendations, or replace professional structural engineering inspections. Pixel measurements are reported in image-space pixels only; physical dimensions (millimetres, centimetres) require calibration that is out of scope for the initial version.

No manual segmentation mask editing is provided. No structural severity classifications are included. Reports clearly distinguish AI-generated predictions from inspector-recorded observations and include a safety disclaimer.

## Project Constraints

- Limited budget; free-tier services preferred where practical
- CPU inference initially; GPU not assumed
- Existing model checkpoint preserved; no retraining as part of this milestone
- No Git repository initialized (project deliberately not initialized yet)

## Repository Structure

- `AGENTS.md` — Persistent agent entry point and reading sequence
- `agent_context/` — Current state, active task, development rules, handoff, decisions, task history, templates
- `PROJECT_CONTEXT.md`, `APP_SPECIFICATION.md`, `TECHNICAL_DESIGN.md`, `ROADMAP.md` — Project documentation
- `src/crack_detection/` — Model architecture, inference pipeline, dataset loader, metrics, loss, training loop
- `tests/unit/` — Unit tests for inference and dataset pipeline
- `model_artifacts/` — Trained checkpoint and evaluation report (`.pth` excluded from version control by `.gitignore`)
- `docs/` — Technical documentation, architecture notes, experiment reports, dataset audit evidence
- `data/` — Dataset directories (`crack-seg`, `concrete400`, `facade-crack-dataset`)

## Development Milestones

See `ROADMAP.md` for the full milestone plan. The documentation and persistent context infrastructure is complete. Application implementation (backend, authentication, database, storage, frontend, PDF reports) has not started.

## References

- `APP_SPECIFICATION.md` — Full product requirements
- `TECHNICAL_DESIGN.md` — System architecture and unresolved technical decisions
- `ROADMAP.md` — Milestones and development direction
- `AGENTS.md` — How coding agents should use this repository
- `agent_context/CURRENT_STATE.md` — What is implemented vs planned

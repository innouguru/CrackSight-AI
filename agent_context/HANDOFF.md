# HANDOFF — Next Agent Summary

**Last updated:** 2026-11-02

## Project

CrackSight AI is an AI-assisted building inspection application for visible cracks in walls, beams, and columns. It is an inspection aid, not a structural safety assessment or engineering recommendation system. Pixel measurements are image-space only.

## Current State

- Model, data pipeline, and backend Milestones 2–5 are implemented per `CURRENT_STATE.md`.
- A responsive React + TypeScript + Vite visual prototype is in `frontend/`.
- The prototype's build and lint pass; local browser review covered major routes, guest allowance, inspection lifecycle, and mobile navigation.
- The prototype is not connected to FastAPI, Clerk, storage, inference, or PDF generation. All records/actions are sample or in-memory values.
- The local development URL used for review is `http://127.0.0.1:5173/`; start it from `frontend/` using `npm run dev`.

## Most Recent Work

Completed the pre-Milestone 6 UI/UX direction and browser prototype:

- Design tokens, rationale, screen inventory, responsive/accessibility notes, mock boundaries, and integration transition plan: `docs/ui_ux_design.md`.
- Frontend run instructions: `frontend/README.md`.
- Sample photo and paired mask/overlay copies are in `frontend/public/demo/`.
- Updated `README.md`, `ROADMAP.md`, and agent context so the prototype is not mistaken for production frontend integration.

## Important Boundaries

- Do not modify the trained model, checkpoint, datasets, or inference pipeline for frontend work.
- The browser must call the FastAPI backend when live integration begins; it must never load the checkpoint or call the inference service directly.
- Continue to distinguish AI predictions from inspector observations.
- Do not imply structural safety, introduce severity classifications, or report physical dimensions without calibration.
- Preserve Draft/Completed workflow; Completed inspections are read-only until reopened.
- Do not overwrite or stage unrelated existing untracked project files.

## Known Follow-up Work

- Formal Milestone 6: typed API client and integration with existing FastAPI response contracts.
- Integrate Clerk React SDK while retaining backend JWT verification.
- Connect guest session validation, upload, photo analysis, ownership, loading/retry/error handling, and persistent inspection history to backend.
- Replace report placeholders with the actual PDF generation workflow when available.
- Resolve backend upload size/dimension configuration and production external-service setup separately.

## Recommended Next Step

Start formal Milestone 6 from `ROADMAP.md`. Read `docs/ui_ux_design.md` for design and mock boundaries, `TECHNICAL_DESIGN.md` for architecture/API context, and `agent_context/CURRENT_STATE.md` for implemented-versus-planned status.

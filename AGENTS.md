# AGENTS.md — Persistent Coding-Agent Context

## Purpose

This file is the mandatory entry point for any coding agent working on the Crack Detection project. Because new models may start every session with no prior conversation history, this repository maintains a persistent, model-independent context environment so any agent can understand the project, identify its current state, and continue development reliably.

## Required Reading Sequence

1. `PROJECT_CONTEXT.md` — Project purpose, product direction, tech stack, existing work, constraints
2. `agent_context/CURRENT_STATE.md` — Current implementation snapshot (what is built vs planned)
3. `agent_context/ACTIVE_TASK.md` — The task the agent should work on now
4. `agent_context/HANDOFF.md` — What was most recently completed and what comes next
5. `agent_context/DEVELOPMENT_RULES.md` — Mandatory development practices

Consult these only when relevant to your specific task:
- `APP_SPECIFICATION.md` — Product requirements and functional specification
- `TECHNICAL_DESIGN.md` — System architecture and technical decisions
- `ROADMAP.md` — Milestones and development direction
- `agent_context/DECISIONS.md` — Historical technical/product decisions

## Document Authority

| Question type | Authoritative source |
|---|---|
| What should the application do? | `APP_SPECIFICATION.md` |
| How should it be built? | `TECHNICAL_DESIGN.md` |
| What milestone comes next? | `ROADMAP.md` |
| What is already implemented vs planned? | `agent_context/CURRENT_STATE.md` |
| What should I work on now? | `agent_context/ACTIVE_TASK.md` |
| What was recently completed? | `agent_context/HANDOFF.md` |
| What development rules must I follow? | `agent_context/DEVELOPMENT_RULES.md` |

## Mandatory Behaviors

### Before any implementation
- Inspect existing code before modifying it.
- Read `agent_context/CURRENT_STATE.md` to distinguish implemented functionality from planned functionality.
- Do not assume planned functionality has been implemented.
- Follow the architecture and conventions in `TECHNICAL_DESIGN.md`.
- Do not expand application scope beyond `APP_SPECIFICATION.md`.

### After completing any task
- Summarize actual changes made.
- Report tests executed and their actual results (never invent results).
- Update `agent_context/CURRENT_STATE.md` if implementation state changed.
- Update `agent_context/TASK_HISTORY.md` with a completion record.
- Update `agent_context/HANDOFF.md` so a new model can continue.
- Update `agent_context/ACTIVE_TASK.md` to mark completion or indicate next task.
- Update `agent_context/DECISIONS.md` only when a meaningful decision was actually made.
- Never update every file mechanically when nothing relevant changed.

### Git rules
- Do not initialize Git automatically.
- Inspect `git status` and exact diffs before committing.
- Stage only files belonging to the completed milestone.
- Never reset, clean, or discard unrelated work.
- Never push unless explicitly requested.

### Preservation rules
- Do not modify model architecture, training code, datasets, or checkpoints.
- Do not retrain the model.
- Do not install dependencies or deploy anything.
- Preserve all existing files and documentation.
- Never expose secrets or modify environment files unnecessarily.

## Context Reliability

Context documents distinguish these states:
- **Implemented and verified** — code exists and tests pass
- **Implemented but not verified** — code exists, tests not run
- **Partially implemented** — code exists but incomplete
- **Planned** — described in docs, no code yet
- **Blocked** — cannot proceed without resolution
- **Not implemented** — no code, no plan

If you discover outdated or contradictory context, correct the document or explicitly flag the discrepancy.

## Context Maintenance

- Use ordinary Markdown files at the repository level (no provider-specific memory).
- Keep mandatory instructions short and explicit.
- Detailed information lives in supporting documents.
- Update context files only when project state materially changes.

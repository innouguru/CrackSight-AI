# CrackSight AI frontend prototype

This React + TypeScript + Vite app is a visual UX prototype. It is intentionally not connected to the FastAPI backend, Clerk, storage, or live inference. See [the UI/UX design notes](../docs/ui_ux_design.md) for screen inventory, design tokens, mock boundaries, and the Milestone 6 transition plan.

## Run locally

Requirements: Node.js 20.19+ or 22.12+.

```powershell
npm install
npm run dev
```

Open <http://localhost:5173/>. To expose the dev server on your local network, run `npm run dev -- --host 0.0.0.0`.

## Useful routes

- `/` — public landing page
- `/try` — guest upload and sample analysis flow
- `/try/results` — sample result comparison
- `/app` — registered-user dashboard
- `/app/history` — inspection history and filters
- `/app/inspections/new` — create a local draft
- `/app/reports` — sample PDF report preview
- `/app/access-denied` — access-control example state

All inspection changes are held in memory and reset on refresh. Uploaded images remain in the browser as a preview. The bundled mask and overlay are sample outputs and are not generated from user-uploaded images. No account, upload, report, or analysis operation reaches a backend.

## Checks

```powershell
npm run build
npm run lint
```

# CrackSight AI — UI/UX Direction and Prototype

## Purpose and status

This document records the visual direction and the browser-review prototype built ahead of formal Milestone 6 frontend integration. The React application demonstrates the main product screens and interaction patterns; it is not connected to the FastAPI backend, Clerk, storage, or live inference.

## Design direction

CrackSight should read as a calm, credible inspection workspace rather than a generic AI dashboard. The interface favors clear labeling, neutral surfaces, practical image controls, and a persistent distinction between model output and inspector judgment. The design intentionally avoids severity scoring, safety conclusions, decorative gradients, and physical measurements without calibration.

### Design tokens

| Token | Value | Use |
|---|---|---|
| Structural navy | `#18313B` | App shell, headings, branded surfaces |
| Teal | `#167F78` | Primary actions, active navigation, image-analysis affordances |
| Canvas | `#F5F7F6` | Workspace background |
| Surface | `#FFFFFF` | Cards, forms, image controls |
| Ink | `#1D2B33` | Primary text |
| Muted text | `#718087` | Descriptions, metadata |
| Divider | `#E4E9E7` | Borders and separators |
| Draft | `#FBF3E7` | Draft state only; not a severity indicator |
| Verified | `#EAF5F0` | Human verification status |
| Error | `#FAEEEC` | Input and operation errors |

Typography uses a system stack (`Segoe UI`, Arial, sans-serif) so the app renders without a remote font dependency. Headings use a tighter tracking and stronger weight than metadata. The spacing rhythm is based on 4 px increments (4, 8, 12, 16, 24, 32, 40 px). Cards use a 1 px neutral border, 8–10 px corner radius, and restrained shadow. Buttons have primary teal, outlined secondary, and quiet/ghost treatments, with visible keyboard focus.

### Product-language rules

- Label outputs as **AI prediction** and manual notes as **Inspector observation**.
- Use “predicted crack pixels” and “image-space measurement”; never imply millimetres or centimetres.
- Include the notice: “AI predictions require human review and do not assess structural safety or replace a qualified engineer.”
- Use only Draft and Completed for inspection lifecycle states. Completed records are read-only until reopened.
- Do not use severity labels or structural-safety scores.

## Screen inventory and routes

| Screen / state | Route | Prototype coverage |
|---|---|---|
| Public landing | `/` | Value proposition, workflow, capabilities, sign-in/registration links, responsible-use notice |
| Sign-in | `/sign-in` | Email/password, Google-compatible action, Clerk integration placeholder, demo-workspace route |
| Registration | `/sign-up` | Account form and Clerk integration placeholder |
| Dashboard | `/app` | Navigation, sample KPIs, recent inspections, quick actions |
| Guest analysis | `/try` | File selection, camera capture control, drag/drop, preview, format/size validation, stage progression, 3-analysis allowance |
| Guest result | `/try/results` | Original/mask/overlay tabs, pixel measurement, model metadata, downloads, human-review notice |
| Inspection history | `/app/history` | Search, date/status/component filters, list/card views, empty-filter state |
| New inspection | `/app/inspections/new` | Draft creation form, required title, optional building details/notes, structure type |
| Inspection details | `/app/inspections/:inspectionId` | Sample image results, observations, verification state, draft/completed actions, read-only completed state |
| Report preview/history | `/app/reports` | Sample report list, report sheet preview, generation/download placeholders |
| Access-denied example | `/app/access-denied` | Ownership/access error presentation |
| Not found | `*` | Friendly recovery route |
| Guest support states | `/try` | Invalid file, oversize file, sample analysis failure, expired guest session, allowance exhausted, in-progress stages |
| Authentication error | `/sign-in`, `/sign-up` | Local explanatory notice when non-integrated auth controls are used |

Use the sidebar and page links to move among registered-user screens. The landing page and guest workflow have their own compact header. The workspace sidebar becomes a dismissible drawer on narrow screens.

## Component architecture

The prototype is a standalone Vite app under `frontend/`, separate from the Python package.

- `src/App.tsx`: route table and prototype provider.
- `src/layout/AppShell.tsx`: responsive workspace shell, navigation, allowance display, and disclaimer footer.
- `src/components/`: reusable brand, buttons/notices/status pills, image-result viewer, and inspection card.
- `src/pages/`: public landing, auth, dashboard, guest analysis/results, history, create/details, reports, access-denied, and not-found screens.
- `src/data/mockData.ts`: typed sample records and demo-image paths.
- `src/data/PrototypeContext.tsx`: in-memory inspection and guest-allowance state; no persistence.
- `src/styles/`: responsive shell, component, and screen styling.

## Prototype data and integration boundary

Sample UI data is defined in `src/data/mockData.ts`. The sample wall photograph and paired baseline output assets are copies of project validation artifacts:

- `public/demo/crack-wall.jpg`: sample source photograph.
- `public/demo/crack-mask.png`: sample predicted mask.
- `public/demo/crack-overlay.png`: sample overlay.
- `public/demo/crack-probability.png`: sample probability output.

All rows, identities, locations, reports, measurements, and timing shown in the interface are sample values. File selection reads a browser-local preview only; no image is uploaded. The guest analysis stage sequence is an interaction prototype and does not execute inference. When the uploaded image differs from the bundled example, the result screen says that the bundled mask/overlay are illustrative and were not generated from the upload.

Create/status/guest allowance state is kept in React memory and resets on refresh. Authentication buttons do not authenticate. Report generation/download is a placeholder. No frontend request is made to the FastAPI backend, Clerk, R2, or any third-party service.

## Responsive and accessibility behavior

- Desktop workspace has a fixed navigation rail and content canvas.
- Tablet and mobile layouts collapse columns and turn the rail into a navigation drawer.
- Forms use explicit labels, errors use alert/status semantics, and image tabs expose tab roles and selection state.
- All interactive controls are keyboard reachable and use a visible focus outline.
- Layouts support 320 px viewport widths; image controls retain useful minimum sizes and horizontal table overflow is contained.

## Local visual review

Requirements: Node.js 20.19+ (or 22.12+).

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/`. For a LAN-accessible development server, run `npm run dev -- --host 0.0.0.0`. Build verification: `npm run build`.

## Transition into formal Milestone 6

1. Keep the screen hierarchy, design tokens, accessible status language, and sample image viewer patterns.
2. Replace the in-memory data provider with typed API services mapped to the existing FastAPI response models.
3. Integrate Clerk’s React SDK for sign-in/sign-up/Google while continuing backend JWT verification.
4. Implement guest-session create/validate/consume endpoints and enforce the three-analysis, 24-hour limit using backend responses.
5. Connect uploads and photo analysis to the backend without loading the checkpoint or calling the inference service from the browser.
6. Replace sample dashboard/history/report records with owned backend records; preserve Draft/Completed read-only behavior.
7. Add API-driven loading, retry, ownership, expiry, and error states; retain only the visual assets that are approved for product use.
8. Revisit upload size/dimension limits and report-generation availability against backend configuration before release.

## Known prototype limitations

- No real authentication, backend API, database persistence, upload, inference, or PDF output.
- Guest session expiry and allowance are simulated in client memory.
- The result model outputs belong to the bundled sample image; they are not recalculated for user uploads.
- Sample report and inspection data are fictional.
- Image upload currently previews one image at a time; production batch handling is outside this design prototype.

# CrackSight AI frontend

This React + TypeScript + Vite app is the production frontend foundation for CrackSight AI (Milestone 6). It preserves the approved UI/UX prototype design and integrates with the existing FastAPI backend and Clerk authentication.

## Run locally

Requirements: Node.js 20.19+ or 22.12+.

```powershell
npm install
npm run dev
```

Open <http://localhost:5173/>. To expose the dev server on your local network, run `npm run dev -- --host 0.0.0.0`.

## Environment configuration

Copy `frontend/.env.example` to `frontend/.env` and fill in your values:

```powershell
Copy-Item .env.example .env
```

| Variable | Description | Required |
|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | Clerk publishable key from Clerk dashboard | Yes (for auth) |
| `VITE_API_URL` | FastAPI backend URL (default: `http://127.0.0.1:8000`) | No |

Never commit `.env` with real credentials.

## Routes

- `/` — public landing page
- `/sign-in` — email/password sign-in (Clerk)
- `/sign-up` — email/password registration (Clerk)
- `/try` — guest upload and analysis flow (guest session connected to backend)
- `/try/results` — guest analysis results
- `/app` — registered-user dashboard (protected route)
- `/app/history` — inspection history (protected route)
- `/app/inspections/new` — create inspection (protected route)
- `/app/inspections/:id` — inspection details (protected route)
- `/app/reports` — PDF reports (protected route)
- `/app/access-denied` — access-denied example state
- `*` — 404 not found

## Authentication

Clerk handles email/password sign-in, registration, and Google OAuth. The frontend:
- Resolves auth session on app load with loading states
- Protects `/app/*` routes (redirects unauthenticated users to `/sign-in`)
- Redirects authenticated users away from `/sign-in`/`/sign-up` to `/app`
- Passes Clerk JWT as `Authorization: Bearer <token>` on API requests
- Supports sign-out

## Guest users

Guests can access `/try` without registration. The frontend:
- Creates a guest session via `POST /guest/session` on the backend
- Validates the session via `GET /guest/session/validate`
- Tracks analyses remaining (max 3 per session)

Guest upload, analysis, and results are prototype placeholders — they will be connected to the backend in Milestone 7.

## API integration

The typed API client (`src/services/api.ts`) communicates with the FastAPI backend:
- Clerk bearer token via `Authorization: Bearer <token>`
- Guest session token via `X-Guest-Session-Token` header
- 30-second request timeout
- Structured `ApiError` error handling matching the backend's error format
- All endpoint paths verified against backend Pydantic schemas

## Backend integration status

| Feature | Status |
|---|---|
| Health check (`GET /live`) | Connected |
| Guest session create/validate/consume | Connected |
| Clerk token verify | Available |
| Inspection CRUD | Available via API client |
| Photograph CRUD + analysis | Available via API client |
| Report generation | Available via API client |
| Upload/analysis results | Prototype placeholder (Milestone 7) |
| PDF download | Prototype placeholder (Milestone 10) |

## Checks

```powershell
npm run build    # TypeScript + Vite production build
npm run lint     # oxlint
npm run test     # vitest
```

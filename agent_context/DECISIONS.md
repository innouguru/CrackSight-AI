# DECISIONS

**Last updated:** 2026-11-02

## Technical Decisions

### Architecture
1. **Two-tier API:** Public FastAPI backend + private inference service for isolation and scalability.
2. **CPU-first inference:** Runs on CPU; "auto" selects CUDA if available but no GPU assumption.
3. **No ORM:** Straightforward database access for maintainability.
4. **Existing inference pipeline reused:** The application inference service wraps `src/crack_detection/inference.py` without independent preprocessing or prediction logic.
5. **Prediction versioning:** Preserve previous predictions as separate versions during reanalysis rather than overwriting.

### Product Scope
6. **Inspection-focused:** Not a model research/evaluation platform.
7. **Pixel measurements only:** No physical calibration (mm/cm) in initial version.
8. **Simple lifecycle:** Two statuses (Draft, Completed).
9. **No manual mask editing.**
10. **Safety boundary:** AI predictions require professional structural engineering review; no safety certification.

### Infrastructure
11. **Neon PostgreSQL:** Already selected for application database.
12. **Cloudflare R2:** Already selected for object storage.
13. **Clerk:** Already selected for authentication (email/password + Google).
14. **Frontend:** React + TypeScript, responsive.
15. **Inference hosting:** Unresolved — requires research and benchmarking before selection.

### Authentication Decisions
16. **Clerk JWT verification via JWKS:** Backend verifies Clerk JWTs by fetching Clerk's JWKS endpoint (`https://<issuer>/.well-known/jwks.json`) and validating signatures using `python-jose[cryptography]`. Keys are cached with a 1-hour TTL to handle key rotation.
17. **Guest session management:** Guest sessions are stored in PostgreSQL (`guest_sessions` table) with unique session tokens, 24-hour expiration, and per-session analysis counters. Guest sessions are isolated from registered users and cannot access registered-user resources.
18. **Guest analysis limit:** Maximum 3 photo analyses per guest session, enforced atomically at the database level using `UPDATE ... SET analyses_count = analyses_count + 1 WHERE ... analyses_count < 3` to prevent race conditions.

## Product Decisions

16. **Hybrid access model:** Guests (3 analyses/session, 24-hour expiry) + Registered users (inspections, PDF reports, monthly allowance).
17. **Guest results not transferable:** Registered users must re-upload and re-analyze.
18. **No public shareable report links:** Reports are downloadable files only.
19. **No organization-level collaboration:** Initial scope is single-user.
20. **Structural components:** Walls, beams, columns only.

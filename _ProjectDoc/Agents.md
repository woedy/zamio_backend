# Agents.md — Working Context Index (ZamIO)

Purpose: a single, handy index of the most important docs across repos. Keep this open in your IDE so we can jump quickly to the right context while building, testing, and triaging.

See also: TestPlanOrder.md for the day-to-day visual test order.

## Quick Links
- Root Test Plan: TestPlanOrder.md
- Cross‑Repo QA Journeys: QA_VISUAL_USER_JOURNEYS.md

## Repo Docs
- Artist Web (zamio_frontend)
  - Checklist: zamio_frontend/zamio_frontend_checklist.md
  - Plan: zamio_frontend/zamio_frontend_plan.md
  - Constants: zamio_frontend/src/constants.tsx
- Backend API (zamio_backend)
  - Checklist: zamio_backend/backend_checklist.md
  - Overview/Plan: zamio_backend/backend_overview_plan.md
  - Local Dev: zamio_backend/LOCAL_DEVELOPMENT.md
  - Deployment Checklist: zamio_backend/DEPLOYMENT_CHECKLIST.md
- Admin Web (zamio_admin)
  - Checklist: zamio_admin/zamio_admin_checklist.md
  - Overview: zamio_admin/zamio_admin_overview.md
- Stations Web (zamio_stations)
  - Checklist: zamio_stations/stations_checklist.md
  - Plan: zamio_stations/stations_frontend_plan.md
- Publisher Web (zamio_publisher)
  - Plan: zamio_publisher/publishers_frontend_plan.md
- Capture App (zamio_app)
  - Checklist: zamio_app/zamio_app_checklist.md
  - Overview: zamio_app/zamio_app_overview.md

## Testing & QA
- Daily Smoke Run: TestPlanOrder.md (Golden Path)
- Deep Dives & Bug Template: QA_VISUAL_USER_JOURNEYS.md

## Environment & Config
- Frontend envs: set `VITE_API_BASE` in each repo’s `.env.local`
  - zamio_frontend/.env.local
  - zamio_admin/.env.local
  - zamio_publisher/.env.local
  - zamio_stations/.env.local
- Backend envs: zamio_backend/.env.local (see LOCAL_DEVELOPMENT.md)

## Conventions
- Ghana context: GHS currency, Ghana stations/regions, `Africa/Accra` timezone (backend).
- API casing: snake_case from backend → camelCase in frontend components.
- Errors: show skeletons for slow loads; toasts + inline messages for failures.

## Update Cadence
- Keep checklists in each repo updated as items move to [~]/[x].
- Update TestPlanOrder.md when routes or acceptance criteria change.

Owner: Engineering (shared). Last updated automatically by agent.

## Reciprocal Docs & QA
- Reciprocal Reference: `zamio_reciprocal_doc.md`
- Reciprocal Plan: `reciprocal_implementation.md`
- Reciprocal Scope: `reciprocal_info.md`
- Reciprocal QA Journeys: `QA_VISUAL_USER_JOURNEYS_RECIPROCAL.md`

# QA Visual Journeys — International Partners (Reciprocal)

Purpose: end-to-end, cross-repo test flows to validate reciprocal representation (e.g., ASCAP) in Ghana. Use alongside Root Test Plan (TestPlanOrder.md).

Legend: [ ] Planned  [~] In progress  [x] Done

Prerequisites
- Partner repertoire CSV: `zamio_backend/sample_partner_import.csv`
- Backend env: `PARTNER_EXPORT_DIR`, `DEFAULT_ADMIN_FEE_PERCENT` in `zamio_backend/.env.local`
- Ghana context: `TIME_ZONE=Africa/Accra`, currency GHS

Journey 1 — Foreign Track Detected → ASCAP Remittance
- Admin: Create Partner PRO (ASCAP) with default admin fee and reporting format (CSV)
- Admin: Create ReciprocalAgreement (territory GH, Active, dates)
- Admin: Import repertoire (CSV); confirm upsert counts; re-run import to verify idempotency
- Backend: Ensure there are PlayLogs containing foreign tracks expected in the CSV (seed or simulate)
- Admin: Open Royalty Cycle for date range; Close cycle; review RoyaltyLineItems (gross/admin/net)
- Admin: Generate Partner Export (CSV baseline); verify file saved under `PARTNER_EXPORT_DIR`
- Admin: Create Partner Remittance; set payment reference; mark Sent → Settled
- Acceptance: Export totals reconcile with cycle totals; remittance shows correct net payable

Journey 2 — Artist Visibility of Partner-Handled Usages
- Artist Web: Open Playlogs/Matchlogs page
- Validate: Partner attribution badge appears on partner-handled plays (Local | Partner)
- Validate: Statements show "Paid via Partner" note for reciprocal Ghana usage; payout action disabled for those lines

Journey 3 — Station Compliance & Downloads
- Stations Web: View dashboard with compliance notice: "ASCAP repertoire collected by ZamIO Ghana under reciprocal agreement"
- Stations Web: Download CSV; confirm essential fields present for reconciliation (station, timestamp, title, ISRC/ISWC, duration)

Edge Cases & QA
- Re-import same CSV → no duplicates (idempotent upsert)
- Close cycle with no partner usage → export is empty but valid
- Low-confidence attribution present → appears in QA queue; approve/reassign removes it from queue

Triage Notes & Bugs Template
- Title: [Reciprocal] Short description
- Area: Admin | Backend | Artist | Stations | Publisher
- Build/Env: commit, branch, env vars
- Steps:
  1) …
  2) …
- Expected:
- Actual:
- Evidence: screenshots, export file snippet, API response
- Severity/Priority:


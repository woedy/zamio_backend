# Test Plan Order — Visual Confirmation (ZamIO)

Purpose: a concise, high‑signal visual testing order across all apps (Artist, Admin, Stations, Publisher, Mobile) to confirm the core journeys work end‑to‑end while you continue fixing bugs. Keep this next to the code and check items off as you verify them.

Legend: [ ] Planned  [~] In progress  [x] Done

**Scope & Goal**
- Confirm users can log in, see data, navigate core pages, and perform key actions with Ghana‑specific context (GHS, Ghana stations/regions).
- Validate loading/empty/error states and that backend changes reflect in the UI.

**Prerequisites**
- Backend running at `http://localhost:8000` with at least: 1 Artist user, 1–2 tracks (one with cover & contributors), some playlogs/matchlogs, wallet balances (available/on‑hold/pending), 1 payout record (optional).
- Frontend envs configured with `VITE_API_BASE=http://localhost:8000` (or use Vite proxy) for Artist/Admin/Publisher/Stations.
- Mobile app can reach local API (emulator/device with correct host mapping).

**Environment Setup (reference commands)**
- Backend: `cd zamio_backend && pip install -r requirements.txt && python manage.py migrate && python manage.py runserver`
- Artist Web: `cd zamio_frontend && npm i && npm run dev`
- Admin Web: `cd zamio_admin && npm i && npm run dev`
- Publisher Web: `cd zamio_publisher && npm i && npm run dev`
- Stations Web: `cd zamio_stations && npm i && npm run dev`
- Mobile: `cd zamio_app && flutter pub get && flutter run`

## 1) Golden Path (90 minutes)

[x] Backend up → [x] Artist login → [x] Dashboard renders → [x] Songs page renders → [x] Upload page UI works → [x] Analytics charts render → [x] Payments wallet & history visible → [x] Notifications list visible → [x] Profile edit form opens

What to confirm at each step:
- Auth persists across refresh; 401 redirects to sign‑in.
- Ghana visuals: Ghana map, Ghana station names (Joy FM, Luv FM, etc.), currency in GHS with proper formatting.
- Tables and charts show clear loading/empty/error states; no NaN/undefined values.

## 2) Repo‑Specific Journeys (Order of Execution)

**Artist Web (zamio_frontend)**
- Login & Routing: [ ] Sign in at `/sign-in`; expect redirect to `/dashboard`. Token stored; refresh keeps session.
- Dashboard Bootstrap: [ ] `profile/me` hydrates `artist_id`; no JS errors.
- Song Manager: [ ] `/all-artist-songs` lists songs; search/sort/pagination work; empty/loading/error states visible.
- Upload Track (UI): [ ] `/add-track` shows picker, metadata form, progress UI; cover preview visible; contributors sum to 100%.
- Analytics: [ ] `/analytics` renders plays‑over‑time, station breakdown, top songs; Ghana map pins show Ghana stations; handles no‑data gracefully.
- Payments: [ ] `/royalty-payments` shows wallet (available/on‑hold/pending) with GHS formatting; sources show radio/streaming/distro; history paginates.
- Notifications & Profile: [ ] `/notifications` lists items with tabs; [ ] `/profile` edit form loads, validations work.
 - Withdrawals E2E: [ ] Submit MoMo withdrawal (number, network, name, amount); include idempotency key header; expect success toast + history update.
 - Notifications Actions: [ ] Mark read/delete/clear all; verify tab filters change counts and states.
 - Legal & Docs: [ ] Terms acceptance modal appears on version change; documents download (PDF) works.
 - Error States: [ ] 404/500 error pages render; error boundary fallback shows friendly message.
 - A11y & Performance: [ ] Keyboard navigation on forms/tables; heavy charts/maps lazy‑load without blocking UI.

Acceptance signals:
- Ghana currency via `Intl.NumberFormat('en-GH', { style: 'currency', currency: 'GHS' })`.
- API failures show inline errors/toasts; long fetches show skeletons/spinners.

**Admin Web (zamio_admin)**
- KYC Decision: [ ] Approve pending KYC for test artist; artist app reflects verified status (payments page gates lift).
- Withdrawal Decision: [ ] Approve a pending withdrawal; artist payment history reflects updated status.
- Content Oversight: [ ] Songs and logs are searchable/filterable; edits persist.
 - Notifications Broadcast: [ ] Send broadcast/segmented notification; verify it appears in Artist `/notifications`.
 - Documents & Versions: [ ] Upload new terms; force acceptance; Artist sees modal and acceptance persists.
 - Tariffs/Cycles/Remittance: [ ] Create a cycle and export statement (if implemented) to validate reporting flows.
 - Stream Ingestion Dashboard: [ ] Per‑station last sample time, error rate, and enable/disable toggle work.

**Stations Web (zamio_stations)**
- Auth & Submit: [ ] Log in; submit/upload a small sample log/audio; view processed/pending status.
- Cross‑check: [ ] Artist `/match-logs` shows new entries with per‑play earnings (GHS) and correct timestamps.
 - Dashboard KPIs: [ ] Totals and recent matches timeline render; filters adjust results.
 - Reports & Compliance: [ ] Export CSV/PDF; proof of compliance certificate download works.
 - Disputes: [ ] Create dispute from a detection row; update/resolve flow visible.
 - Realtime Behavior: [ ] WebSocket live updates fall back to polling with exponential backoff when WS unavailable.

**Publisher Web (zamio_publisher)**
- Catalog: [ ] Login; repertoire list renders (works, contributors, splits).
- Splits: [ ] Edit splits to 100% total; save persists; export/download split sheet (if implemented).
 - Earnings Reports: [ ] Filters and CSV export produce correct aggregates.
 - Payout Requests: [ ] Submit MoMo/bank payout request; status transitions visible in history.

**ZamIO Capture App (zamio_app / Flutter, station device)**
- Enrollment & Auth: [ ] Log in/enroll device to obtain `station_id` and token; persists across restarts.
- Capture & Upload: [ ] Start short capture; verify periodic 10–30s chunks upload to `POST /api/music-monitor/stream/upload/` (2xx on success, 200 on idempotent).
- Status & Resilience: [ ] App shows upload status/queue depth; simulate offline then reconnect and confirm retries/backoff behavior.

**Backend API (zamio_backend)**
- Health/Auth: [ ] Health endpoint 200; login/reset endpoints functional.
- Profiles: [ ] `GET api/profile/me` returns `artist_id` and details.
- Tracks: [ ] Create track (manual or via UI); retrieve/update ok.
- Analytics: [ ] `GET api/analytics/royalties/timeseries` returns chartable data (or empty state payloads).
- Wallet: [ ] `GET api/payments/artist/wallet?artist_id=` returns available/on‑hold/pending and sources { radio, streaming, distro }.
- Withdrawals: [ ] `POST api/payouts/withdrawals/` enforces min amount/KYC gate; optional idempotency header supported.
 - KYC: [ ] Endpoints to submit and approve KYC; Artist gating behavior enforced.
 - Notifications: [ ] `GET/POST api/notifications/` list, create, mark‑read; Artist app reflects updates.
 - Documents: [ ] List/download documents; terms version acceptance recorded and enforced.
 - Locale & Observability: [ ] `TIME_ZONE=Africa/Accra`, currency defaults GHS; error tracking/logging hooks present (if configured).

Online Stream Capture & Matching
- [ ] `POST /api/music-monitor/stream/upload/` receives AAC/WAV chunks and creates matches/playlogs.
- [ ] Stream ingestion service configured for station online stream URLs (if present) and feeds matcher periodically.

## 2a) International Partners (Reciprocal) E2E (Admin-first)

Prereqs
- [ ] Sample partner repertoire file available: `zamio_backend/sample_partner_import.csv`
- [ ] Backend env set: `PARTNER_EXPORT_DIR` and `DEFAULT_ADMIN_FEE_PERCENT` in `zamio_backend/.env.local`
- [ ] Timezone `Africa/Accra`; currency GHS

Admin (zamio_admin)
- [ ] Create Partner PRO (e.g., ASCAP) with default admin fee and reporting standard
- [ ] Create ReciprocalAgreement for territory `GH` (status Active; dates set)
- [ ] Import repertoire (CSV) and confirm upsert counts; re-run import to verify idempotency
- [ ] Review Usage QA (if any unmatched/low-confidence entries are surfaced)
- [ ] Open a Royalty Cycle for a date range with existing PlayLogs; then Close to produce line items
- [ ] Generate Partner Export (CSV baseline) and verify file saved under `PARTNER_EXPORT_DIR`
- [ ] Create Partner Remittance, set payment reference, mark Sent/Settled

Artist (zamio_frontend)
- [ ] Playlogs table shows attribution source badge: `Partner` for partner-handled works
- [ ] Statements show "Paid via Partner" note for Ghana usages under reciprocal agreement (payout disabled)

Stations (zamio_stations)
- [ ] Compliance notice visible: "ASCAP repertoire collected by ZamIO Ghana under reciprocal agreement"
- [ ] CSV downloads include basic fields used by Admin export reconciliation

Acceptance signals
- Partner export totals reconcile with Royalty Cycle totals (gross/admin/net)
- Import is repeatable without duplicates (idempotent upsert)
- Partner-handled usages are read-only for artist/publisher payout actions

## 3) Data Seeding (Optional, for rich visuals)
- Create 2–3 tracks (one with cover art), add 2–3 contributors totaling 100%.
- Insert playlogs/matchlogs across multiple Ghana stations (e.g., Joy FM, YFM Accra, Luv FM).
- Wallet: create transactions for available, on‑hold, pending; 1–2 payouts with differing statuses.

## 4) Common Acceptance Patterns
- Auth: token attached on API calls, 401 → sign‑in; protected routes blocked when unauthenticated.
- Loading: show skeleton/loader for >300ms; empty states with helpful copy.
- Errors: toast and inline messages with remediation; no raw stack traces in UI.
- Ghana‑specific: GHS currency formatting; Ghana station names; Ghana map regions.
- Usability: buttons disabled during submit; inputs have labels and keyboard/focus support.

## 6) Cross‑Repo Configuration
- Environments: [ ] Validate dev/staging/prod env vars across repos (`VITE_API_BASE`, media/ws bases; backend CORS/CSRF) and that each build picks them up.
- Feature Flags: [ ] Risky features (withdrawals, disputes) gated and toggles honored in UI/Backend.

## 5) Bug Reporting
- Use the template in `QA_VISUAL_USER_JOURNEYS.md` → “Triage Notes & Bugs Template”. Include screenshots and network traces where possible. Prioritize KYC/payments, then upload/matching, then analytics.

—
Keep this document updated as flows are verified. For daily smoke runs, execute section 1 (Golden Path) and one deep‑dive from section 2.

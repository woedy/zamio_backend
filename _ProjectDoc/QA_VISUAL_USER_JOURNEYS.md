# ZamIO — Cross-Repo Visual QA User Journeys

See also: [TestPlanOrder.md](TestPlanOrder.md) for the recommended day-to-day visual test order and acceptance checks.

Purpose: unified, realistic flows you can run while fixing bugs to visually confirm end-to-end behavior across Artist, Admin, Publisher, Stations, Mobile, and Backend. Check items off when the flow works end-to-end with clear UI states and correct API effects.

Legend: [ ] Planned  [~] In progress  [x] Done

Note: Keep API payloads camelCase in UI; convert snake_case from backend in services. Prefer optimistic UI where safe; always show explicit loading/empty/error states.

---

## 0) Environment & Test Data
- [ ] Backend up: Django dev server running on `http://localhost:8000`
- [ ] Frontends up: Artist/Admin/Publisher/Stations Vite dev servers
- [ ] Mobile: Flutter app builds and connects to local API
- [ ] Test user accounts created: Artist, Admin, Publisher, Station Ops
- [ ] Seed data: at least 2 songs, 1 with cover art, contributors set; some playlogs/matchlogs; wallet with sample balances; at least 1 payout record
- [ ] `.env.local` set for each frontend (`VITE_API_BASE=http://localhost:8000` or proxy)

Commands (reference)
- Backend: `cd zamio_backend && pip install -r requirements.txt && python manage.py migrate && python manage.py runserver`
- Artist Web: `cd zamio_frontend && npm i && npm run dev`
- Admin Web: `cd zamio_admin && npm i && npm run dev`
- Publisher Web: `cd zamio_publisher && npm i && npm run dev`
- Stations Web: `cd zamio_stations && npm i && npm run dev`
- Mobile App: `cd zamio_app && flutter pub get && flutter run`

---

## 1) Artist Web App (zamio_frontend)
Authentication & Onboarding
- [ ] Sign up: name, email, phone, password; client validation
- [ ] Login: email/phone + password; redirect to `/dashboard`
- [ ] Forgot password: request → OTP confirm → reset form works
- [ ] Profile completion prompt shows when bio/photo/genre missing
- [ ] Private routes guard; token expiry clears session and redirects

Artist Profile & Settings
- [ ] `/profile` edit: bio, genres, contact; image upload preview/crop
- [ ] KYC upload: shows Pending/Verified/Rejected badge states
- [ ] MoMo number: network picker (MTN/Vodafone/AirtelTigo) + validation
- [ ] Settings: change password, notifications, delete account flows
- [ ] UI feedback: toasts, disabled states, skeletons render correctly

Music Upload & Management
- [ ] `/add-track`: audio select, metadata, progress bar shows
- [ ] Cover art upload: constraints enforced, preview visible
- [ ] Contributors: roles and splits sum to 100%
- [ ] Fingerprint job triggers; per-track processing status visible
- [ ] `/all-artist-songs`: search, filter, sort, pagination
- [ ] Edit metadata via `/edit-track-details` persists
- [ ] View fingerprint details/status; certificate PDF download works

Playlogs & Match Logs
- [ ] `/match-logs`: tabs switch Playlogs/Matchlogs
- [ ] Debounced search; date range + station filters work
- [ ] Clear empty/loading/error states; earnings show formatted currency
- [ ] Export CSV button works (optional)

Analytics
- [ ] `/analytics`: plays over time chart; switch day/week/month
- [ ] Station breakdown chart; top songs chart/table
- [ ] Ghana regions airplay map renders; handles no-data state

Royalty & Payments
- [ ] `/royalty-payments`: wallet card shows available/on-hold/pending with `Intl.NumberFormat('en-GH', { style: 'currency', currency: 'GHS' })`
- [ ] Sources breakdown: radio, streaming, distro keys (stations → radio)
- [ ] Royalty breakdown: chart toggles to table with API data
- [ ] Withdrawal form: MoMo number, network, name, amount; min threshold
- [ ] Disabled when insufficient balance or KYC not verified
- [ ] Submit shows loading; success/error toasts; history table with status chips
- [ ] Idempotency header sent (UUID) if API supports

Notifications
- [ ] `/notifications`: tabs/filters (All, Airplay, Payouts)
- [ ] Mark read, delete, clear all; empty-state messages

Legal & Support
- [ ] Terms modal appears on version change and persists acceptance
- [ ] Documents list shows PDF downloads; split sheets accessible
- [ ] Help center (FAQ, payouts) + contact support form submits with context

Cross-cutting
- [ ] Error boundaries render friendly fallback
- [ ] Standardized toast and inline error patterns
- [ ] Loading skeletons for long fetches; accessible labels and focus
- [ ] Route code-splitting where heavy (charts/maps); performance acceptable

---

## 2) Admin Web App (zamio_admin)
Authentication & Access
- [ ] Admin login works; protected routes enforce role-based access

Artist & Content Oversight
- [ ] Artists list: search/filter; view artist details and KYC status
- [ ] Approve/reject KYC; updates reflect in Artist app restrictions
- [ ] Songs table: search/filter by artist/station/status; edit metadata
- [ ] Fingerprint job monitor: trigger reprocess; view errors

Playlogs/Matchlogs Oversight
- [ ] View aggregated playlogs; filter by date/station/artist
- [ ] Resolve matches/conflicts; audit history visible
- [ ] Export CSV for reporting

Payments & Royalties
- [ ] Wallet adjustments and corrections with reason codes
- [ ] Approve/reject withdrawal requests; status updates propagate
- [ ] Royalty rates management; preview impact; effective overrides visible

Notifications & Docs
- [ ] Broadcast notifications; targeted notifications to artist(s)
- [ ] Manage documents/agreements; upload/update version and force accept

---

## 3) Publisher Web App (zamio_publisher)
Authentication & Catalog
- [ ] Login + protected routes
- [ ] Catalog view: registered works, contributors, splits
- [ ] Add work: metadata, ISRC/ISWC if applicable, attach artists

Splits & Agreements
- [ ] Edit splits; sum validation; version history
- [ ] Generate split sheets; download PDFs; share links

Reporting & Earnings
- [ ] View earnings per work; filters; export CSV
- [ ] Payout requests (publisher-level) with MoMo/bank details

---

## 4) Stations Web App (zamio_stations)
Authentication & Feed
- [ ] Station user login
- [ ] Upload/batch submit logs; parse feedback on errors
- [ ] Live detection feed (if present) updates or polls

Logs & Compliance
- [ ] View submitted logs; status (processed, pending, errors)
- [ ] Correct/replace logs; reprocessing triggers

---

## 5) ZamIO Capture App (zamio_app / Flutter, station device)
Enrollment & Auth
- [ ] Log in/enroll device to obtain `station_id` and a scoped token
- [ ] Persists auth across app restarts

Capture & Upload
- [ ] Periodic short audio snippets (10–30s) captured on schedule
- [ ] Upload to `POST /api/music-monitor/stream/upload/` with fields: `file`, `station_id`, `chunk_id`, `started_at`, `duration_seconds`
- [ ] On 2xx, local file removed; on duplicate, 200 idempotent

Resilience & Diagnostics
- [ ] Offline queue retries with exponential backoff
- [ ] Upload status and backlog depth visible; basic error log screen
- [ ] Optional start-on-boot on Android; background audio mode on iOS

---

## 6) Backend API (zamio_backend)
Health & Auth
- [ ] `/api/health` (or root) returns 200
- [ ] Auth endpoints: login, password reset, OTP if enabled

Artists & Profiles
- [ ] `GET api/profile/me` returns artist_id and profile fields
- [ ] `PUT api/profile/` updates bio/genres/contact; image upload

Music & Fingerprinting
- [ ] `POST api/music/tracks/` creates track; file upload works
- [ ] Fingerprint job enqueued; status endpoint returns processing states
- [ ] `GET/PUT api/music/tracks/{id}` retrieves/updates metadata

Playlogs/Matchlogs
- [ ] `GET api/artists/playlogs/` pagination, filters (date/station)
- [ ] `GET api/artists/matchlogs/` as applicable

Analytics
- [ ] `GET api/analytics/royalties/timeseries` returns data for charts
- [ ] Other analytics endpoints return reasonable sample data/empty states

Wallet & Payments
- [ ] `GET api/payments/artist/wallet?artist_id=` returns available/on-hold/pending and sources { radio, streaming, distro }
- [ ] `POST api/payouts/withdrawals/` validates min amount, KYC gate; idempotency key supported
- [ ] `GET api/payouts/withdrawals/` paginates history with status

Notifications & Docs
- [ ] `GET/POST api/notifications/` list, mark read
- [ ] `GET api/documents/` lists agreements; signed/acceptance tracked

Admin Ops
- [ ] Endpoints for KYC decisions; wallet adjustments; rate overrides

---

## 7) Golden Path Visual Smoke (All Apps ~10–15 min)
1) Artist web: Login → Dashboard loads → Songs list renders → Upload track UI visible → Analytics charts render → Royalty/Payments wallet renders → Notifications tab works → Profile edit form opens
2) Admin web: Login → Artists list → Approve KYC → Approve a pending withdrawal → See update reflected in Artist app
3) Publisher web: Login → Catalog renders → Edit a split and save → Download split sheet
4) Stations web: Login → Submit a small sample log → Status shows processed
5) Mobile app: Login → Dashboard cards render → Notifications visible

Mark each step [x] only if UI states, validations, and API effects are visually confirmed.

---

## 8) Triage Notes & Bugs Template
- [ ] Title:
- [ ] Affected app(s): Artist/Admin/Publisher/Stations/Mobile/Backend
- [ ] Route/Endpoint:
- [ ] Expected vs Actual:
- [ ] Repro steps:
- [ ] Screenshots/console/network traces:
- [ ] Severity/Priority:
- [ ] Owner/Assignee:

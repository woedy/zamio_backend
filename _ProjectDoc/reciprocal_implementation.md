# Reciprocal Implementation & Execution Plan (International PROs)

Goal: Enable ZamIO to collect in Ghana on behalf of international PROs (ASCAP first, later PRS/BMI/SACEM), while preserving and enriching current artist, publisher, and station experiences. The plan is detailed, end-to-end, and testable by role.

Legend: [x] exists today • [~] partial • [ ] to build

## Personas & Portals

- Partner PRO (ASCAP, PRS, etc.) — via admin exports, later optional partner portal
- Admin/Operations — `zamio_admin`
- Station — `zamio_stations`
- Publisher (local) — `zamio_publisher`
- Artist — `zamio_frontend`

## International PRO Model (What’s New)

- [ ] PartnerPRO extends `publishers.PublisherProfile` (no duplicate publisher service)
- [ ] ReciprocalAgreement (territory GH, dates, admin fee, status, reporting cadence)
- [ ] External repertoire ingestion (CWR/DDEX/CSV) → ExternalWork/Recording/Writer/Publisher
- [ ] UsageAttribution links `music_monitor.PlayLog` to partner repertoire with confidence and method
- [ ] Royalty cycles (quarterly by default), line items, partner statements, remittances (GHS→USD), exports (CSV baseline, CWR snapshots, DDEX-style usage if requested)
- [ ] Mandate precedence resolution (local direct vs. reciprocal) with audit logs and data-quality flags

---

## Artist Journey — `zamio_frontend`

Registration & Login
- [x] Sign up/login
- [ ] 2FA support in settings/security

Onboarding
- [x] Profile, socials, contact, region/city/country
- [x] Payment setup (bank/momo); [ ] tax ID
- [x] Choose publisher: link to PublisherProfile or self-publish
- [x] Track upload (audio + cover art)
- [x] Contributors: writers/composers with roles and shares
- [ ] Identifiers: ISRC per recording, ISWC per composition; assist lookup/generation

Catalog Management
- [x] Tracks list/detail; edit metadata
- [x] Albums, genres, platforms availability
- [ ] Bulk edit identifiers and contributor splits
- [ ] Link multiple recordings to a work (ISRC↔ISWC mapping)

Fingerprinting & Matching
- [~] Fingerprinting pipeline produces MatchCache → PlayLog
- [ ] Track page shows fingerprint status, last sync, issues

Playlogs & Analytics
- [x] Plays/analytics base
- [ ] Full PlayLogs table: station, program, timestamp, duration, confidence, source (Local | Partner)
- [ ] Partner badge on partner-sourced Ghana plays

Claims, Disputes, QA
- [~] Dispute flows on PlayLog
- [ ] Attach evidence, status timeline, admin responses

Royalties, Statements, Payouts
- [x] Local statements/payouts
- [ ] For partner-represented works in GH: show “Paid via ASCAP/Partner” with usage evidence; disable payout action

Notifications & Settings
- [ ] Alerts for unmatched IDs, low confidence matches, partner mandate changes
- [ ] 2FA toggle if accounts supports

Logout
- [x] Existing

---

## Publisher Journey — `zamio_publisher`

Registration & Onboarding
- [x] PublisherProfile creation; company/tax/payment info
- [x] Invite/Link artists; upload agreements

Catalog & Splits
- [x] Manage tracks and writer/publisher shares
- [ ] Identifier hygiene dashboard (missing ISRC/ISWC, duplicates)
- [ ] Mandate view: show partner vs local handling by territory and date

Usage, Claims, Disputes
- [x] View playlogs/analytics for managed tracks
- [ ] CSV export with attribution source and confidence
- [ ] Disputes integrated with admin QA

Statements & Payouts
- [x] Local statements/payouts
- [ ] Partner-handled Ghana uses shown read-only with explanation

Logout
- [x] Existing

---

## Station Journey — `zamio_stations`

Registration & Licensing
- [x] Portal + auth
- [ ] Licensing wizard: station class, coverage, contacts, invoice prefs
- [ ] Stream links management; test connectivity

Monitoring & Compliance
- [~] Programs/streams exist
- [ ] Live capture status + last-seen signal
- [ ] PlayLogs by date/program; CSV downloads
- [ ] Compliance reports: monthly/quarterly pack (CSV + PDF summary)
- [ ] Notice: “ASCAP repertoire collected by ZamIO Ghana under reciprocal agreement”

Billing
- [ ] Tariff summary for class/time-of-day; invoice list; payment status

Logout
- [x] Existing

---

## Admin/Operations — `zamio_admin`

Partners & Agreements
- [ ] Create PartnerPRO (extends PublisherProfile) with reporting_standard, default admin fee
- [ ] Create ReciprocalAgreement (GH, dates, status, fee override, cadence)

Repertoire Ingestion
- [ ] Upload/import CWR/CSV/ERN; dry-run; stats; idempotent upsert
- [ ] Nightly sync (Celery) if API creds

Attribution QA
- [ ] Low-confidence queue: approve/reject/reassign
- [ ] Data quality: missing IDs, conflicts, outliers

Tariffs & Cycles
- [ ] Tariff tables by station class/time-of-day/usage
- [ ] Open/Close cycle; review LineItems (gross, admin, net)

Exports & Remittance
- [ ] Generate partner statements (CSV baseline; optional CWR/DDEX)
- [ ] Create remittance (GHS→USD), set payment_reference, mark Sent/Settled; attach statement
- [ ] Archive exports with checksum

Audit & Admin
- [ ] Audit trail for key transitions (cycle lock, remittance settle, QA decisions)
- [ ] User/role management; 2FA policy; API tokens

---

## Backend Work Breakdown (Django)

Models & Migrations (royalties app)
- [ ] PartnerPRO (multi-table inheritance from publishers.PublisherProfile)
- [ ] ReciprocalAgreement
- [ ] ExternalWriter, ExternalPublisher, ExternalWork, ExternalRecording (indexed iswc/isrc/title)
- [ ] UsageAttribution (FK PlayLog, FK external refs, origin_partner, confidence, method)
- [ ] RoyaltyCycle, RoyaltyLineItem, PartnerRemittance, PartnerReportExport
- [ ] DataQualityIssue, AuditLog

Services
- [ ] Repertoire importers (CSV v1; CWR/DDEX stubs)
- [ ] Attribution matcher (local→external fallback; thresholds; dedupe)
- [ ] Cycle close calculator (tariffs, splits, fees)
- [ ] Export generator (CSV baseline); Remittance creator
- [ ] Celery tasks + retries + alerts

APIs (admin-scoped)
- [ ] /api/partners, /agreements, /repertoire/import
- [ ] /api/royalties/cycles (open/close, get)
- [ ] /api/royalties/cycles/{id}/exports, /remittances
- [ ] /api/qa/attributions, /qa/issues

Integration Points
- [ ] Hook music_monitor PlayLog finalization → create/update UsageAttribution
- [ ] Surface partner-sourced usage in artist/publisher portals (read-only evidence)

---

## Repo Journeys & Backlogs (User Stories)

zamio_frontend (Artist Portal)
- Registration & Login
  - [Now] Sign up/login with email/password
  - [Later] 2FA toggle in settings
  - Test path: Create account, login, logout
- Onboarding
  - [Now] Profile, socials, contact, region/city/country
  - [Now] Payment setup (bank/momo)
  - [Now] Choose publisher (link PublisherProfile or self‑publish)
  - [Now] Upload track (audio + cover art); add contributors with roles/shares
  - [Later] Identifiers step: enter/validate ISRC (recording) and ISWC (work); assist lookup
  - Test path: Complete all steps; next‑step progression works; validation messages clear
- Catalog Management
  - [Now] View/edit tracks, albums, genres, platform availability
  - [Later] Bulk edit identifiers and contributor splits
  - [Later] Link multiple recordings to a work (ISRC↔ISWC mapping UI)
  - Test path: Edit metadata persists; mappings visible on track page
- Fingerprinting & Matching
  - [Now] Background fingerprinting to MatchCache → PlayLog
  - [Now] Track page shows fingerprint status, last sync, issues banner
  - Test path: Upload track → status updates from pending to completed
- Playlogs & Analytics
  - [Now] Plays/analytics summary widgets
  - [Now] Full PlayLogs table (station, program, timestamp, duration, confidence)
  - [Now] Partner badge on plays collected via reciprocal agreement (Local | Partner)
  - Test path: Filter by date/station; Partner badge visible for partner‑sourced plays
- Disputes & QA
  - [Now] Open dispute from a playlog; add comments
  - [Later] Attach evidence, status timeline, admin responses
  - Test path: Create dispute → status updates → resolution reflects in UI
- Statements & Payouts
  - [Now] Local statements/payouts view
  - [Now] For partner‑represented works in GH: show “Paid via Partner” note and usage evidence; disable payout
  - Test path: Statement displays net/local vs partner‑paid correctly
- Notifications & Settings
  - [Later] Alerts for unmatched IDs, low‑confidence matches, mandate changes
  - [Later] 2FA enable/disable

zamio_publisher (Local Publisher Portal)
- Registration & Onboarding
  - [Now] Create PublisherProfile; company/tax/payment info
  - [Now] Invite/link artists; upload agreements
  - Test path: Complete onboarding and link an artist/track
- Catalog & Agreements
  - [Now] Manage tracks and writer/publisher shares
  - [Later] Identifier hygiene dashboard (missing/duplicate ISRC/ISWC)
  - Test path: Edit splits; hygiene flags appear for missing IDs
- Mandates & Territory View
  - [Now] Mandate/exclusions dashboard: which works/territories handled by partner vs local
  - Test path: Work in GH marked as Partner when agreement active, Local otherwise
- Usage, Claims, Disputes
  - [Now] View playlogs/analytics for managed tracks with attribution source and confidence
  - [Later] CSV export per period with attribution source
  - Test path: Export matches on‑screen filters
- Statements & Payouts
  - [Now] Local statements/payouts
  - [Now] Partner‑handled Ghana uses shown read‑only with explanatory copy
  - Test path: Partner plays do not enable payout; copy clarifies route
- Partner Mode (Embedded Partner Portal)
  - [Now] Add partner_pro role with tenant scoping tied to PartnerPRO entity
  - [Now] Gate partner views via role‑based routes labeled “Partner Mode”
  - [Now] Views: Agreements (territory, fees, dates), Exports/Statements, Remittance status
  - [Later] Repertoire import triggers + logs; Approve statements; download archives with checksums
  - Test path: PartnerPro user sees partner mode only; cannot access local‑publisher‑only routes

zamio_stations (Station Portal)
- Registration & Licensing
  - [Now] Portal auth
  - [Later] Licensing wizard: station class, coverage, contacts, invoice prefs
  - Test path: Complete licensing; class stored and visible
- Streams Setup
  - [Later] Manage stream links; connectivity test status
  - Test path: Add stream URL → status shows reachable/unreachable
- Monitoring & Compliance
  - [Now] PlayLogs by date/program; CSV downloads
  - [Later] Compliance packs (monthly/quarterly CSV + PDF summary)
  - [Now] Notice: “ASCAP repertoire collected by ZamIO Ghana under reciprocal agreement”
  - Test path: Download CSV; partner note visible on dashboard
- Billing
  - [Later] Tariff summary and invoice list with payment status
  - Test path: Invoice appears after cycle close (admin‑driven)

zamio_admin (Admin/Operations)
- Login & Roles
  - [Now] Admin access; role management
- Partners & Agreements
  - [Now] Create PartnerPRO (extends PublisherProfile) with reporting_standard, admin fee
  - [Now] Create ReciprocalAgreement (GH, dates, status, fee override, cadence)
  - Test path: Agreement state transitions (Draft→Active→Suspended→Terminated)
- Repertoire Ingestion
  - [Now] Upload CSV; dry‑run; import with idempotent upsert; logs
  - [Later] CWR v3.x snapshot export; DDEX‑style usage importer/exporter
  - Test path: Re‑run same file → no duplicates; logs show upserts
- Attribution QA
  - [Now] Low‑confidence queue: approve/reject/reassign to work/recording
  - [Now] Data quality issues: missing IDs, conflicts, outliers
  - Test path: Approve item → attribution updates and disappears from queue
- Tariffs & Cycles
  - [Now] Tariff tables by station class/time‑of‑day/usage (basic)
  - [Now] Open/Close cycle; review LineItems (gross, admin, net)
  - Test path: Cycle lock prevents edits; totals reconcile with playlogs
- Exports & Remittance
  - [Now] Generate partner statements (CSV baseline); archive with checksum
  - [Now] Create remittance (GHS→USD), set payment_reference, mark Sent/Settled
  - Test path: Export file matches spec; remittance totals match LineItems
- Audit & Compliance
  - [Now] Audit trail for key transitions; retention policies tracked
  - [Later] SLA dashboard and retention controls UI

zamio_backend (Django Services)
- System Orchestration Scenarios (for QA)
  - [Now] Ingest partner CSV → ExternalWork/Recording upserted → logs created
  - [Now] Detect play → PlayLog created → external attribution created when local miss
  - [Now] Close cycle → LineItems computed (tariff, fee) → CSV export → Remittance created
  - [Later] CWR/DDEX specific exporters/importers, engine adapters, automation & alerts
  - Test path: Follow end‑to‑end from ingest to remittance; verify audit trail at each step

---

## Acceptance Criteria (Pilot with ASCAP)

- Import ≥5k works from ASCAP test CSV; idempotent re-runs; <1% rejects
- ≥X% match rate on top 10 GH stations; FP rate <Y%; 100% of low-confidence reviewed
- Close 1 quarterly cycle; generate ASCAP CSV; create remittance; full trace PlayLog → Attribution → LineItem → Remittance
- Artist portal shows partner badge and read-only partner usage for affected tracks
- Station portal provides compliance reports covering partner repertoire

---

## Risks & Mitigations

- Conflicting mandates → enforce precedence, surface conflicts, require admin resolution
- Missing identifiers → hygiene dashboards and QA; fuzzy matching capped by thresholds
- False positives → conservative thresholds; manual review for high-value detections
- FX, fees, tax errors → explicit remittance fields, dual-control approval, audit logs

---

## Repo Unification & Phasing

Overall phasing
- Phase 1 (Now): Data scaffolding, CSV importer, attribution fallback, admin workflows, partner mode basics, CSV exports, first cycle & remittance.
- Phase 2 (Soon): CWR/DDEX parsers, station compliance packs, identifier hygiene dashboards, QA tooling depth, tariffs UI, automation.
- Phase 3 (Later): Partner portal extraction (if needed), advanced matching vendor adapters, DDEX-DSR full, partner APIs, multi-territory.

zamio_backend (Django)
- [Now] Royalties models: PartnerPRO, ReciprocalAgreement, External*, UsageAttribution, RoyaltyCycle stack
- [Now] CSV importer v1 + idempotent upsert, import logs
- [Now] Attribution fallback (ISRC→ISWC→fuzzy) on PlayLog finalize
- [Now] CSV export generator + PartnerRemittance creation
- [Now] Admin endpoints for partners/agreements/imports/cycles/exports/remittances/QA
- [Later] CWR v3.x snapshot export; DDEX-DSR-like usage
- [Later] Matching engine adapters + health checks; advanced tariffs modeling UI

zamio_frontend (Artist)
- [Now] PlayLogs table with partner badge; statements note for partner-paid works
- [Now] Track fingerprint status surface
- [Later] Identifiers editor (ISRC/ISWC) + bulk splits edit
- [Later] Dispute form enhancements with evidence timeline

zamio_publisher (Publisher)
- [Now] Mandate/exclusions dashboard
- [Now] Partner Mode: role-based routes, tenant scoping, agreements/read-only exports access
- [Later] Identifier hygiene dashboard and conflict alerts
- [Later] Approve statements flow; archives with checksums

zamio_stations (Station)
- [Now] PlayLogs and CSV compliance downloads
- [Later] Licensing wizard, streams connectivity diagnostics
- [Later] Billing summaries and invoices list

zamio_admin (Admin)
- [Now] Partners/Agreements CRUD; Imports UI; QA queue; Cycles; Exports; Remittances; Audit logs
- [Later] Tariffs configuration UI; SLA dashboards; retention controls

## Security & Compliance

- [ ] DPA alignment: document data processor roles, lawful basis, partner DPAs.
- [ ] Encryption: TLS in transit; encryption at rest for exports/remittances; secret rotation.
- [ ] PII minimization: limit exported fields to required set; mask where possible.
- [ ] Access control: role-based access (admin, partner_pro, station, publisher, artist); least privilege.
- [ ] Retention: usage raw audio/logs N days, detections M months, statements/remittances per finance policy; purge jobs.
- [ ] Audit retention: append-only logs for critical state changes with retention ≥ 7 years.

## Export Specs v1

- CSV Baseline (per partner per cycle):
  - station_id, station_name, played_at_utc, timezone, program(optional)
  - isrc, iswc, recording_title, work_title, artist_name
  - duration_seconds, confidence, match_method, attribution_source(Local|Partner)
  - gross_amount, admin_fee_amount, net_amount, currency, cycle_name
  - partner_id, agreement_id
- CWR Snapshot (optional): ownership snapshot for involved works (version 3.x); scope limited to impacted works.
- DDEX-style usage (optional/partner-specific): configurable fields mapped from CSV; versioned templates per partner.

## SLAs & KPIs (placeholders)

- Monitoring coverage: ≥ 85% of national audience across stations in scope.
- Reporting latency: monthly usage report delivered by T+7 days; quarterly statements T+14 days.
- QA turnaround: low-confidence queue triaged within 48 hours.
- Match quality: ≥ X% recall on top stations with ≤ Y% false positive rate (pilot targets).

## Remittance Details

- Fields: fx_rate, fx_source, fx_date, withholding_tax_percent, bank_fees_amount, admin_fee_percent, net_payable_currency.
- Process: compute gross → admin_fee → withholdings/fees → net; store FX used for conversion and notes.
- Dual control: require two-step approval (generate, approve/send) with audit entries.

## Matching Engine Abstraction

- Adapter interface to support vendor (ACRCloud/BMAT) or Chromaprint.
- Configurable thresholds per station/class; health checks and fallbacks.
- Deduplication logic across remixes/edits; ISRC↔ISWC mapping cache.

## Notes / Decisions

- PartnerPRO extends PublisherProfile (confirmed)
- CSV first for speed; add CWR/DDEX after pilot sign-off
- Clearly surface international-collection context in artist/publisher portals (read-only evidence for partner-paid usage)

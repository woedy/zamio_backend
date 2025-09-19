PROMPT FOR CODEX AGENT

You have full access to this Django + React (Tailwind) repository for ZamIO. The app currently onboards artists, fingerprints tracks, matches radio/TV plays, and returns payments + reports. Extend the system to support Reciprocal Representation with foreign PROs (starting with ASCAP). Treat “ASCAP” as the first external partner, but architect it to support multiple partners in the future (PRS, BMI, SACEM, etc.).

High-level goals

Add Reciprocal Agreements: ZamIO acts as the local representative for foreign PROs in Ghana. We license broadcasters, detect usage, allocate royalties, deduct an admin fee, and remit to the partner with standardized reports.

Ingest partner repertoire data (works, recordings, splits, identifiers) and match against our fingerprinting results.

Implement quarterly (or configurable) royalty cycles, remittance workflows, and DDEX/CWR-style reporting exports.

Keep the current direct-artist onboarding workflow intact.

Backend (Django) – Data model & migrations

Create new apps/tables or extend existing ones.

1) Partners & Agreements

PartnerPRO (PublisherProfile):

id, name (e.g., “ASCAP”), country_code, contact_email, active: bool

reporting_standard (enum/string: e.g., “CWR”, “DDEX-DSR”, “CSV-Custom”)

default_admin_fee_percent: Decimal (e.g., 15.00)

metadata (JSONField) for partner-specific flags/fields (e.g., remittance bank info requirements)

ReciprocalAgreement:

FK partner → PartnerPRO(PublisherProfile)

territory (e.g., “GH”)

effective_date, expiry_date (nullable)

admin_fee_percent: Decimal (override partner default)

status (Draft | Active | Suspended | Terminated)

reporting_frequency (Quarterly | SemiAnnual | Annual | Custom cron)

notes: Text

2) Repertoire & Parties

ExternalWriter:

ipi_cae (nullable), name, roles (composer/lyricist), affiliated_pro (string), society_code (nullable)

ExternalPublisher: similar to ExternalWriter

ExternalWork (musical work):

iswc (nullable), title, alt_titles (Array/JSON)

M2M writers with share splits (use through model with share_percent)

origin_partner (FK PartnerPRO), work_metadata (JSON)

ExternalRecording:

isrc (nullable), title, FK work, duration, recording_metadata (JSON)

Add indices on iswc, isrc, title for matching.

3) Usage, Allocation, and Remittance

Leverage your existing PlayLog/Match models. Add:

UsageAttribution (NEW):

FK play_log (or equivalent), FK ExternalWork (or ExternalRecording)

confidence_score: Decimal, match_method (“fingerprint”, “metadata”)

territory: str, station_id, played_at, duration_seconds

RoyaltyCycle:

id, name (e.g., “2025-Q1 – Ghana”)

territory (str), period_start, period_end, status (Open | Locked | Invoiced | Remitted)

admin_fee_percent_default

RoyaltyLineItem:

FK royalty_cycle

FK partner (nullable if local artist), FK ExternalWork/Recording OR local Work

usage_count, total_duration_seconds, gross_amount, admin_fee_amount, net_amount

calculation_notes

PartnerRemittance:

FK partner, FK royalty_cycle

currency (GHS or agreed), gross_amount, admin_fee_amount, net_payable, payment_reference

statement_file (file path), status (Pending | Sent | Settled | Failed), sent_at, settled_at, notes

PartnerReportExport:

FK partner, FK royalty_cycle

format (CWR, DDEX-DSR, CSV), file (path), generated_at, checksum

Run migrations and ensure referential integrity.

Backend – Services & tasks

Create services in royalties/services/ (or suitable app):

Repertoire Ingestion

Implement a pluggable importer: import_partner_repertoire(partner_id, source_file|s3_path|api_creds):

Accept files in common formats: CWR, DDEX ERN/MEAD, or CSV mapping (title,iswc,isrc,writers,publishers,shares).

Normalize to ExternalWork, ExternalRecording, ExternalWriter, ExternalPublisher.

Idempotent upserts (by ISWC/ISRC; fallback to fuzzy title+writer matches).

Logging + dry-run mode.

Usage Attribution / Matching

When a PlayLog is finalized, create/update UsageAttribution by matching to:

Local catalog first (keep existing behavior).

If not found, query ExternalRecording by ISRC; fallback to ExternalWork by ISWC; fallback to fuzzy title/artist with thresholds.

Store confidence_score. Tag attributions coming from partner repertoire with origin_partner.

Royalty Calculation

close_royalty_cycle(territory, period_start, period_end, admin_fee_override?):

Aggregate UsageAttribution within period.

Apply the platform’s Ghana tariff formula (you already have rates; if not, create Tariff table configurable per broadcaster type).

Create RoyaltyLineItem per work/partner.

Deduct admin fee from gross to compute net.

Mark cycle as Locked.

Reporting & Remittance

generate_partner_statement(royalty_cycle_id, partner_id, format):

Export usage + financials:

CSV baseline (station, timestamp, ISRC/ISWC, duration, gross, fee, net).

CWR for works ownership snapshots (where applicable).

DDEX-style usage (DSR-like) if required by partner (configurable).

Save to /mnt/data/exports/<partner>/<cycle>/…

create_partner_remittance(royalty_cycle_id, partner_id):

Summarize RoyaltyLineItems → PartnerRemittance (gross/admin/net).

Generate a PDF/CSV statement and attach to remittance.

Mark remittance Sent after finance triggers the transfer (keep manual trigger first; design for webhook from payment gateway later).

Background jobs

Use Celery/RQ for:

Nightly repertoire syncs (if API creds are available).

Cycle closing on schedule (quarterly).

Report generation.

Add robust logging, retries, and email/slack alerts on failure.

Audit & Compliance

Add model change audit logs for RoyaltyCycle, RoyaltyLineItem, PartnerRemittance.

Add a data_quality_issues table for unmatched plays, conflicting splits, missing identifiers.

Backend – APIs (Django REST)

Create/extend endpoints (JWT/Session protected; staff or specific roles only where noted):

POST /api/partners/ (admin): create PartnerPRO

GET/PUT /api/partners/:id/

POST /api/partners/:id/agreements/ (create/activate ReciprocalAgreement)

POST /api/partners/:id/ingest-repertoire (upload file or point to S3 path)

POST /api/royalties/cycles (create cycle)

POST /api/royalties/cycles/:id/close (aggregate + lock)

GET /api/royalties/cycles/:id/line-items

POST /api/royalties/cycles/:id/partners/:partner_id/export (format param)

POST /api/royalties/cycles/:id/partners/:partner_id/remit

GET /api/remittances/:id (download statement)

GET /api/usage/unmatched (for ops reconciliation)

Add pagination, filtering by partner, period, territory, status. Include OpenAPI schema updates.

Permissions & Roles

Add RBAC:

Admin: all

Finance: create remittances, mark sent/settled, view exports

Ops: ingest repertoire, run matching, close cycles

Viewer: readonly reports

Frontend (React + Tailwind)

Create an “International Partners” admin area:

Partners List & Detail

List: name, country, active, latest cycle status, next report due.

Detail tabs:

Overview (agreement, admin fee, reporting frequency).

Repertoire (upload/sync, last sync date, counts of works/recordings).

Usage & Allocation (matched plays, unmatched items).

Royalty Cycles (list + statuses).

Remittances (history, download statements).

Actions:

Upload repertoire file (CSV/CWR/DDEX).

Start/Close Cycle.

Generate Export (CSV/CWR/DDEX).

Create Remittance.

Royalty Cycle Dashboard

Filters: territory, period, partner.

KPIs: total plays, matched %, gross collected, admin fee, net payable.

Tables:

Line items (sortable; columns: Work/Recording, ISWC/ISRC, usage count, duration, gross, fee, net).

Unmatched plays (with quick actions to resolve).

Remittance Detail

Summary totals, status timeline (Pending → Sent → Settled).

Download statement/report.

Notes activity feed.

Use your existing component library conventions; keep it clean and minimal.

Matching & Data Quality

Implement deterministic matching by ISRC/ISWC first.

Add fuzzy matching fallback (title + main writer/publisher) with tunable thresholds.

Expose data-quality issues to UI.

Add a manual “link play → work” override (audited).

Config & Secrets

.env additions (load via settings):

PARTNER_EXPORT_DIR, DEFAULT_ADMIN_FEE_PERCENT

Placeholders for future ASCAP API keys if applicable (don’t hardcode secrets).

Add settings to toggle which export formats are enabled per partner.

Testing

Unit tests for:

Repertoire ingestion parsers (CSV + mock CWR/DDEX fixtures).

Matching logic (ISRC/ISWC/fuzzy).

RoyaltyCycle close & fee calculations.

Export file generation checksums.

API tests for all endpoints (auth + role checks).

Smoke tests on React routes.

Provide sample fixtures in tests/fixtures/:

ascap_works_sample.csv

ascap_recordings_sample.csv

usage_sample.csv (play logs)

Acceptance criteria

I can create a Partner “ASCAP” with a reciprocal agreement for “GH”.

I can upload ASCAP repertoire (CSV fixture) and see normalized Works/Recordings in DB.

When I run a cycle for a date range with existing PlayLogs, the system:

Matches plays to external works/recordings,

Produces RoyaltyLineItems with correct gross/admin/net,

Locks the cycle.

I can export a partner report (CSV baseline) and a CWR/DDEX-like file (mocked).

I can create a PartnerRemittance, produce a downloadable statement (PDF/CSV), and mark it Sent/Settled.

Unmatched plays surface in UI and can be resolved.

All new models are covered by migrations and tests pass.

Nice-to-haves (if time permits)

Celery schedule to auto-close cycles quarterly and email Finance.

S3 storage for exports + presigned URLs.

Basic currency conversion support (if future partners request USD/EUR settlement).

Webhook receiver to automatically mark remittances “Settled”.

Important notes

Do not break current artist onboarding and direct payout flow.

Keep everything partner-agnostic; ASCAP is just the first instance.

Favor explicit logging, auditable state transitions, and idempotent batch jobs.

Please implement this end-to-end with clean code, docstrings, type hints (where applicable), and update the README with setup steps, new env vars, and a short “International Partners” operations guide.
# ZamIO Reciprocal Representation — Reference Doc

This document describes how we are extending ZamIO to support reciprocal representation with foreign PROs/CMOs (starting with ASCAP) while preserving current ZamIO functionality for Ghanaian artists, stations, and publishers.

## Scope Summary

- ZamIO acts as the local representative for foreign PROs in Ghana: detects radio/TV usage, applies Ghana tariffs, allocates royalties, deducts an admin fee, and remits net to the partner with standardized reports.
- Keep the existing direct artist/publisher onboarding and monitoring workflows intact.
- Design for multi‑partner support (ASCAP first; later PRS, BMI, SACEM, etc.).

## Current State (Relevant Pieces)

- Apps: `artists`, `stations`, `music_monitor`, `publishers`, `bank_account`, `mr_admin`, `notifications`, `fan`, `activities`.
- Monitoring: `music_monitor.PlayLog`, `MatchCache`, `FailedPlayLog` already track detections with confidence, durations, stations, and royalty_amount fields.
- Publishers: `publishers.PublisherProfile`, `PublishingAgreement` for local publisher/artist splits, onboarding steps, payment info.
- Stations: models + views for stations, programs, streams.

## New Domain Model (Royalties App)

PartnerPRO (extends PublisherProfile)
- Motivation: a partner is operationally a publisher entity; reuse publisher services. Use Django multi‑table inheritance (or OneToOne) to extend `publishers.PublisherProfile` with partner‑specific fields.
- Fields (additive to PublisherProfile):
  - name (display), country_code, contact_email, active
  - reporting_standard (enum: CWR | DDEX-DSR | CSV-Custom)
  - default_admin_fee_percent (Decimal)
  - metadata (JSONField) for partner‑specific flags (e.g., remittance banking requirements)

ReciprocalAgreement
- partner (FK PartnerPRO)
- territory (e.g., "GH"), effective_date, expiry_date (nullable)
- admin_fee_percent (override), reporting_frequency (Quarterly | SemiAnnual | Annual | Custom)
- status (Draft | Active | Suspended | Terminated), notes

External Repertoire
- ExternalWriter: name, roles, ipi_cae (nullable), affiliated_pro, society_code (nullable)
- ExternalPublisher: same pattern
- ExternalWork: iswc (nullable), title, alt_titles (JSON), origin_partner (FK), m2m writers with share_percent, work_metadata (JSON)
- ExternalRecording: isrc (nullable), title, work (FK), duration, recording_metadata (JSON)
- Indices: iswc, isrc, normalized title

Attribution, Cycles, and Remittance
- UsageAttribution: play_log (FK), external_work or external_recording (FK), origin_partner (FK), confidence_score, match_method, territory, station_id, played_at, duration_seconds
- RoyaltyCycle: name, territory, period_start, period_end, status (Open | Locked | Invoiced | Remitted), admin_fee_percent_default
- RoyaltyLineItem: royalty_cycle (FK), partner (nullable), work/recording ref (external or local), usage_count, total_duration_seconds, gross_amount, admin_fee_amount, net_amount, calculation_notes
- PartnerRemittance: partner (FK), royalty_cycle (FK), currency, gross_amount, admin_fee_amount, net_payable, payment_reference, statement_file, status (Pending | Sent | Settled | Failed), sent_at, settled_at, notes
- PartnerReportExport: partner (FK), royalty_cycle (FK), format, file, generated_at, checksum

Mandate & Precedence
- Honor territory + effective dates of ReciprocalAgreement and any direct publisher deals.
- Precedence: Local direct deals > Active reciprocal mandate > Expired/none. Log conflicts to data_quality_issues and surface in admin QA.

## Core Flows

1) Partner Repertoire Ingestion
- Input: CWR, DDEX ERN/MEAD, or mapped CSV. API creds if provided.
- Process: Parse → normalize → upsert ExternalWork/Recording/Writer/Publisher. Idempotent (by ISWC/ISRC), with fuzzy fallback for title+writers.
- Output: Import log with counts, conflicts, missing IDs.

2) Detection and Usage Attribution
- Keep local catalog matching first (existing behavior).
- If unmatched, try ExternalRecording by ISRC → ExternalWork by ISWC → fuzzy title/artist.
- Create UsageAttribution with confidence and match_method (fingerprint | metadata). Tag origin_partner when matched to partner catalog.
- Route low‑confidence attributions to a manual review queue.

3) Royalty Cycle Close
- Input: territory + date range; optional admin fee override.
- Aggregate UsageAttribution within window; apply Ghana tariffs per station class/time of day/usage type when available.
- Create RoyaltyLineItems per work/partner; compute gross → admin_fee → net.
- Lock the cycle when validated.

4) Reporting & Remittance
- Generate partner statements (CSV baseline; CWR ownership snapshots where required; DDEX‑style usage on demand).
- Create PartnerRemittance with totals and attach the statement; mark Sent when finance transfers funds; mark Settled on confirmation.

5) Audit & Data Quality
- Audit logs for RoyaltyCycle, LineItem, Remittance state changes.
- data_quality_issues table: unmatched plays, ownership conflicts, missing identifiers, outlier amounts.

## APIs (Admin/Staff)
- POST /api/partners/ — create PartnerPRO (staff)
- POST /api/partners/{id}/agreements — create ReciprocalAgreement (staff)
- POST /api/partners/{id}/repertoire/import — upload file or trigger sync (staff)
- POST /api/royalties/cycles — open/close cycles; GET details
- POST /api/royalties/cycles/{id}/exports — generate reports (CSV/CWR/DDEX)
- POST /api/royalties/cycles/{id}/remittances — create/send remittance
- GET /api/qa/attributions — list low‑confidence items for review

## Frontend Surfaces

- Admin (zamio_admin): Partners & Agreements, Repertoire Imports, Usage QA, Royalty Cycles, Exports & Remittances, Audit.
- Stations (zamio_stations): License status and coverage, compliance reports download, possibly station playlogs view.
- Publishers (zamio_publisher): Existing flows remain; add visibility for mandate exclusions and partner‑handled works.
- Artists (zamio_frontend): Existing onboarding and dashboards remain; add society badge where relevant (read‑only).

## Reporting Formats
- CSV Baseline: station, timestamp, ISRC/ISWC, title, duration, gross, fee, net, confidence, station_id.
- CWR: ownership snapshots when requested by partner.
- DDEX‑DSR‑like: configurable, depending on partner.

## Security & Compliance
- Data protection agreements with partners; encrypt at rest/in transit; PII minimization.
- Full audit trail from detection → claim → statement → remittance.
- FX handling, fees, withholding taxes captured on remittance.

## Rollout Plan (Phases)
- Phase 0: Align with partner on data formats, SLAs, tariffs; sign MoU.
- Phase 1: Pilot on 5–10 stations; build importers, attribution, QA; manual cycle run.
- Phase 2: Formal cycles + exports + remittance; expand coverage; admin workflows.
- Phase 3: Automate jobs (Celery), harden QA and audits; multi‑partner readiness.

## Key Decisions
- PartnerPRO as extension of PublisherProfile (approved) to avoid duplicate publisher services.
- Conservative matching thresholds with manual review for high‑value detections.
- Agreement precedence and conflict resolution policy.


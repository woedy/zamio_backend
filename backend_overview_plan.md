# Backend Overview Plan

This is the living roadmap and guide for bringing the ZamIO backend to production. It complements `backend_checklist.md` (features tracking) by focusing on phases, sequencing, defaults, and decision context.

## Objectives
- Deliver reliable audio detections from radio streams and uploads.
- Convert detections to audited playlogs and royalties with clear rules.
- Provide secure APIs for artists, stations, admins, and streaming clients.
- Operate safely in production with observability, scheduling, and idempotency.

## Architecture Snapshot (Current)
- Django apps: `accounts`, `artists`, `stations`, `music_monitor`, `bank_account`, `notifications`, `publishers`, `fan`.
- Fingerprinting: `artists/utils/fingerprint_tracks.py` (librosa + peaks + xxhash64).
- Matching: `music_monitor/utils/match_engine.py` (clip + streaming) and `stream_monitor.py` (ffmpeg).
- Detections: `MatchCache` → `PlayLog`/`StreamLog`; Disputes; Royalty on `PlayLog`.
- Ledger: `BankAccount` + `Transaction` as internal wallet.
- Infra: Docker Compose (Postgres, Redis, Celery, Daphne/ASGI), token auth, CORS-ready.

## Phases & Milestones

### Phase 0 — Baseline Stabilization
- Fix return-type mismatch in streaming monitor vs matcher.
- Normalize fingerprint storage (prefer 64-bit int) and add migration plan.
- Ensure seeding flows (generate artists/tracks) work with Postgres and Celery.
- Validate Docker local stack and environment defaults; tidy settings for prod.

Deliverables:
- Working end-to-end local flow: upload/seed → matched `MatchCache` → converted `PlayLog` with royalty → wallet entries.

### Phase 1 — Fingerprinting Pipeline Automation
- Management command: `fingerprint_tracks` to fingerprint any unprocessed tracks.
- Celery task: background fingerprinting on upload, with idempotency and `engine_version` metadata.
- Metrics: counts per track, duration processed, error logging.

Deliverables:
- `Track.fingerprinted=True` reliably; dedupe via `unique_together(track, offset, hash)`.

### Phase 2 — Stream Monitoring Service
- Convert thread monitor to a management command or sidecar process.
- Persist sessions in DB (start/stop/status), not globals; attach to `Station`.
- ffmpeg capture tuning: chunk length, hop, max retry/backoff, timeouts.

Deliverables:
- Start/stop via API; durable sessions; recent matches visible; safe restarts.

### Phase 3 — Detections → PlayLogs + Royalty Ledger
- Celery task to aggregate `MatchCache` windows into `PlayLog` with min duration (≥30s), confidence filters, and merge logic.
- Post ledger entries atomically: station debit → artist credit (configurable base GHS/sec).
- Idempotency keys and batch IDs to avoid double-paying.

Deliverables:
- Daily/Batched processing with audit-ready transactions.

### Phase 4 — Dispute Workflow
- Role-based transitions: Pending → Verified → Resolving → Review → Resolved.
- Evidence attachments; comments; audit entries with actor + timestamp.
- Optional: hold payouts on disputed items; reconciliation actions.

Deliverables:
- APIs and admin tools to manage disputes end-to-end.

### Phase 5 — Program Schedules & Attribution
- Models/APIs for station schedules; infer `station_program` by time window.
- Fallback + manual override with audit trail.

Deliverables:
- PlayLogs reliably tagged to programs.

### Phase 6 — Analytics
- Aggregations: daily/weekly/monthly for artists, stations, tracks.
- Endpoints for leaderboards, trends, and payouts.

Deliverables:
- Efficient queries and cached summaries for dashboards.

### Phase 7 — Wallet Withdrawals & Approvals
- Withdrawal requests with min threshold; admin approval flow.
- Optional MoMo connector stub with callback handling and reconciliation.

Deliverables:
- Safe payout request lifecycle; basic export/report.

### Phase 8 — Notifications & Security/Deployment
- Email + optional SMS hooks for detections, payouts, disputes.
- Hardened permissions; throttling; prod-ready settings; health checks.

Deliverables:
- Production profile with observability and secure defaults.

## Defaults & Decisions
- Fingerprint Hash: xxhash64 stored as BigInt (or fixed 16-char hex). Index `(hash, track_id)`.
- Matching Thresholds: Min hashes and confidence; tune per environment.
- DB: Postgres primary; Redis for Celery + channels.
- Background Jobs: Celery + Celery Beat (Redis broker).
- Auth: DRF Token for now; plan JWT migration if needed.
- Media: Local in dev; plan for S3-compatible storage in prod.

## Environments & URLs
- Local compose: Postgres (9003), Redis (9004), API (9001), frontends (9002, 9005).
- Ensure `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` include all frontends.

## QA & Observability
- Minimal unit tests for critical pipelines (fingerprinting, matching, royalty calc).
- Structured logging; error tracking placeholder (e.g., Sentry) for prod.
- Health checks for API and workers; periodic job status metrics.

## Risks & Mitigations
- False positives/negatives: tighten thresholds; store confidence; support disputes.
- Double payments: strict idempotency and batch keys; audit logs.
- Stream capture instability: retries/backoff; session persistence; alerting.

## Near-Term Next Steps (Sprint Focus)
1) Phase 0 fixes: matcher/monitor alignment, fingerprint storage decision, settings tidy.
2) Phase 1 command + Celery task for fingerprinting; mark `Track` states; simple metrics.
3) Phase 3 minimal pipeline: convert recent `MatchCache` to `PlayLog` with base royalty; atomic ledger entries.

This plan is iterative—update as we learn from data and usage.

— How to use: treat this as the single source of truth for the artist app scope. Keep checkboxes updated in PRs.

## Stream Scans (Server‑Side)

Goal
- Periodically sample each active station stream URL, decode to PCM, fingerprint and match, and persist results to `MatchCache`/`PlayLog` with confidence and timestamps.

Design
- Source: `stations.StationStreamLink(active=True)`.
- Scheduler: Celery Beat triggers `music_monitor.tasks.scan_station_streams` at a safe cadence (e.g., every 1–5 minutes); subtask per active link.
- Capture: ffmpeg captures 20–30s, mono @ 44.1kHz (or 16kHz) to stdout (WAV/PCM).
- Decode: librosa loads bytes to samples at target sample rate.
- Match: `music_monitor.utils.match_engine.simple_match` or `simple_match_mp3` against precomputed fingerprints.
- Persist: create `MatchCache` with station, matched_at, and avg_confidence_score; optional `PlayLog` when rules met.
- Resilience: timeouts, error handling, retry with backoff for failing links.

Operational Notes
- Prefer short Celery tasks over long‑lived threads in web workers.
- Bound concurrency to avoid CPU/ffmpeg contention; limit active scans per worker.
- Metrics: scans attempted/succeeded, last match per station, decode/match errors.
- Idempotency: time‑bucketed windows to avoid double‑count within overlapping captures.

Acceptance
- Each active link produces periodic captures and writes matches when present.
- Failures logged with station/link context; no unbounded retries; admin can view latest scan status.

# Backend Checklist

See also: [TestPlanOrder.md](../TestPlanOrder.md) for the cross-repo visual test flow and backend acceptance checks.

This checklist tracks the core backend features across modules. We’ll mark items [x] as we implement/verify them. Keep this file updated as work progresses.

## 1) users (Authentication & Core Profiles)
- [x] Custom user model with roles (artist, station, admin)
- [x] Token auth (DRF Token) wired in APIs
- [ ] JWT auth option (optional)
- [ ] OTP via SMS (Twilio/SMS gateway)
- [x] User profiles (name, phone, email, role)
- [ ] Admin roles/permissions (superadmin, support, finance), per-endpoint enforcement

## 2) artists (Artist-Specific Data)
- [x] Artist model (bio, socials, location)
- [ ] KYC verification model (ID, MoMo, tax ID)
- [x] Contributor splits (Contributor model with percent_split)
- [~] Upload tracker/status (Track.status present; expand as needed)

## 3) stations (Radio Station Models)
- [x] Station model (name, region, country)
- [x] Stream URLs (StationStreamLink)
- [ ] Station stats (detections, playback aggregates)
- [ ] Compliance docs (monthly reports uploads)
- [~] Dispute actions (Dispute model exists; refine station flow)

## 4) tracks (Upload, Metadata & Management)
- [x] Track model (title, genre, ISRC optional, cover)
- [x] File storage fields (mp3/wav; local for now)
- [x] Contributors link (M2M via Contributor model)
- [~] Fingerprint on upload (pipeline exists; automate via Celery)

## 5) fingerprinting (Audio Hashing & Matching)
- [x] Fingerprint generator (librosa + xxhash)
- [x] Matcher engine (clip + streaming)
- [x] Radio snippet processor (ffmpeg capture)
- [~] Match confidence score storage (avg_confidence_score on MatchCache)
- [x] Scheduled tasks (Celery Beat for periodic stream scans)

## 6) detections (Match Logs & Airplay Events)
- [x] Match log model (MatchCache)
- [x] Airplay/stream playlog model (PlayLog, StreamLog)
- [x] Detection timestamps + duration
- [x] Dispute model + status fields
- [ ] Confidence override/admin adjudication fields
- [ ] Analytics API (daily/weekly/monthly rollups)

## 7) royalties (Play Tracking & Revenue Distribution)
- [~] Royalty rule engine (base per-second rate; configurable)
- [x] Royalty amount on PlayLog
- [ ] Monthly aggregation per artist/song
- [ ] Contributor split resolver (allocate by percent_split)
- [ ] Report generator (CSV/PDF per artist/station/month)

## 8) wallets (Payouts & MoMo Integration)
- [x] Wallet model (BankAccount) and transactions
- [ ] Withdrawal requests + min threshold
- [ ] Admin approval flow
- [ ] MoMo API connector (MTN/Voda/AirtelTigo)
- [x] Payout history (Transaction records)

## 9) streaming (Fan-Facing Stream & Playback Data)
- [x] Play event model (StreamLog)
- [ ] Streaming analytics (top songs/artists, charts)
- [ ] Guest play tracking (IP/device)
- [ ] Fan favorites/likes
- [ ] Recommender-ready models (listens/skips/replays)

## 10) stream capture (Station Online Streams)
- [~] Stream ingestion service configured for station stream URLs
- [~] Periodic sampling → fingerprint & match pipeline
- [ ] Health/metrics: last sample time, error rate per station
- [ ] Admin controls to enable/disable per station

## 11) core/common (Shared Services)
- [~] Notification app scaffold (email configured; SMS pending)
- [x] Email backend (file/email; env-configurable)
- [ ] SMS service integration
- [ ] Logging & auditing (admin actions, changes)
- [~] Scheduled jobs (Celery + Beat configured; tasks to add)
- [ ] Utility services (PDF generator, image processors as needed)

## Cross-Cutting Concerns
- [ ] Security hardening (permissions, throttling, rate limits)
- [ ] CORS/CSRF for all frontends (artists/stations/admin/publishers)
- [ ] Deployment profiles (env-based, prod safe defaults)
- [ ] Observability (structured logging, error tracking)
- [ ] Data migrations for schema changes (fingerprint storage)
- [ ] Default TIME_ZONE set to `Africa/Accra`; currency fields default `GHS`

Legend: [x]=done, [~]=partial/in-progress, [ ]=pending

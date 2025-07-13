from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from music_monitor.models import MatchCache, PlayLog
from decimal import Decimal
from celery import shared_task

ROYALTY_PER_SECOND = Decimal("0.005")  # Adjust to your pricing logic


@shared_task
def run_matchcache_to_playlog():
    convert_matches_to_playlogs()



def convert_matches_to_playlogs():
    
    # Get matches from the last 30 minutes
    recent_matches = MatchCache.objects.filter(
        matched_at__gte=timezone.now() - timedelta(minutes=30)
    ).select_related('track', 'station', 'station_program')

    for match in recent_matches:
        track = match.track
        station = match.station

        # Prevent duplicate logging: skip if this track already has a PlayLog recently
        recent_log_exists = PlayLog.objects.filter(
            track=track,
            station=station,
            played_at__gte=match.matched_at - timedelta(minutes=10)
        ).exists()

        if recent_log_exists:
            continue

        # Try to get duration from Track model
        duration = track.duration

        # If not available, estimate from other nearby MatchCache entries
        if not duration:
            nearby_matches = MatchCache.objects.filter(
                track=track,
                station=station,
                matched_at__gte=match.matched_at - timedelta(minutes=5),
                matched_at__lte=match.matched_at + timedelta(minutes=5)
            ).order_by('matched_at')

            if nearby_matches.count() > 1:
                start_time = nearby_matches.first().matched_at
                end_time = nearby_matches.last().matched_at
                duration = end_time - start_time
            else:
                # fallback to default if we can't estimate
                duration = timedelta(seconds=180)

        # Calculate royalty
        royalty_amount = Decimal(duration.total_seconds()) * ROYALTY_PER_SECOND

        # Create PlayLog
        PlayLog.objects.create(
            track=track,
            station=station,
            station_program=match.station_program,
            source='streaming',
            played_at=match.matched_at,
            start_time=match.matched_at,
            stop_time=match.matched_at + duration,
            duration=duration,
            royalty_amount=royalty_amount
        )

        print(f"[✓] Logged play: {track.title} ({station.name}) - {duration.total_seconds()}s - ${royalty_amount:.2f}")

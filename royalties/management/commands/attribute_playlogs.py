from django.core.management.base import BaseCommand
from django.db import transaction

from music_monitor.models import PlayLog
from royalties.models import ExternalRecording, UsageAttribution


class Command(BaseCommand):
    help = "Attribute PlayLogs to partner repertoire by ISRC when available."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1000, help="Max playlogs to process")

    @transaction.atomic
    def handle(self, *args, **options):
        limit = options["limit"]
        processed = 0
        created = 0

        qs = PlayLog.objects.select_related("track", "station").order_by("-created_at")
        for pl in qs[:limit]:
            # Skip if already attributed
            if UsageAttribution.objects.filter(play_log=pl).exists():
                continue
            isrc = getattr(pl.track, "isrc_code", None)
            if not isrc:
                continue
            rec = ExternalRecording.objects.filter(isrc=isrc).select_related("origin_partner").first()
            if not rec:
                continue

            UsageAttribution.objects.create(
                play_log=pl,
                external_recording=rec,
                origin_partner=rec.origin_partner,
                confidence_score=95.0,
                match_method="metadata",
                territory="GH",
                station_id=pl.station_id,
                played_at=pl.played_at,
                duration_seconds=int(pl.duration.total_seconds()) if pl.duration else None,
            )
            created += 1
            processed += 1

        self.stdout.write(self.style.SUCCESS(f"Attributed playlogs created={created}, scanned={processed}"))


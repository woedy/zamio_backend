from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from django.db.models import Count, Avg

from bank_account.models import BankAccount
from music_monitor.models import MatchCache, PlayLog, FailedPlayLog
from artists.models import Track

from django.core.mail import send_mail
from django.conf import settings


def send_sms(to: str, message: str):
    print(f"SMS to {to}: {message}")


ROYALTY_RATE_PER_SECOND = Decimal('0.005')  # GHS per second

class Command(BaseCommand):
    help = 'Generate PlayLogs from MatchCaches and deposit royalties'

    def handle(self, *args, **kwargs):
        grouped_matches = (
            MatchCache.objects
            .filter(processed=False)
            .values('track_id', 'station_id')
            .annotate(count=Count('id'))
        )

        if not grouped_matches:
            self.stdout.write(self.style.WARNING("⚠️ No unprocessed MatchCaches to process."))
            return

        for group in grouped_matches:
            if group['count'] < 3:
                continue

            matches = MatchCache.objects.filter(
                track_id=group['track_id'],
                station_id=group['station_id'],
                processed=False
            )

            if not matches.exists():
                continue

            try:
                with transaction.atomic():
                    track = Track.objects.get(id=group['track_id'])
                    station = matches.first().station
                    artist = track.artist
                    artist_user = artist.user
                    station_user = station.user

                    start_time = matches.earliest('matched_at').matched_at
                    stop_time = matches.latest('matched_at').matched_at
                    duration = stop_time - start_time

                    if duration.total_seconds() < 30:
                        matches.update(processed=True, failed_reason="Match duration too short (<30s)")
                        continue

                    royalty = round(duration.total_seconds() * ROYALTY_RATE_PER_SECOND, 2)

                    artist_account, _ = BankAccount.objects.get_or_create(user=artist_user, defaults={
                        "balance": Decimal('0.00'),
                        "currency": "Ghc"
                    })
                    station_account, _ = BankAccount.objects.get_or_create(user=station_user, defaults={
                        "balance": Decimal('0.00'),
                        "currency": "Ghc"
                    })

                    if not station_account.withdraw(royalty, f"Royalty payment for '{track.title}'"):
                        raise ValueError("Insufficient funds in station account")

                    artist_account.deposit(royalty, f"Royalty for '{track.title}' playlog")

                    avg_conf_score = matches.aggregate(avg=Avg('avg_confidence_score'))['avg'] or 0

                    PlayLog.objects.create(
                        track=track,
                        station=station,
                        station_program=matches.first().station_program,
                        played_at=start_time,
                        start_time=start_time,
                        stop_time=stop_time,
                        duration=duration,
                        royalty_amount=royalty,
                        avg_confidence_score=avg_conf_score,
                        source='streaming',
                        active=True,
                        flagged=False,
                        dispute_status=None,
                        disput_comments=None
                    )

                    matches.update(processed=True, failed_reason=None)

                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Logged play for '{track.title}' and deposited GHS {royalty:.2f} to {artist_user.username}"
                    ))

            except Exception as e:
                error_msg = str(e)
                FailedPlayLog.objects.create(
                    match=matches.first(),
                    reason=error_msg,
                    will_retry=True
                )
                matches.update(processed=False, failed_reason=error_msg)
                self.notify_station(station_user, matches.first(), error_msg)

                self.stdout.write(self.style.ERROR(
                    f"❌ Failed to process MatchCache for track ID {group['track_id']}: {error_msg}"
                ))

        self.stdout.write(self.style.SUCCESS("🎵 Finished processing all valid MatchCaches."))

    def notify_station(self, user, match, reason):
        subject = f"Royalty Payment Failed for Station {match.station.name}"
        message = (
            f"Dear {user.first_name},\n\n"
            f"We attempted to process royalty payments for your station for the track '{match.track.title}', "
            f"but the payment failed due to the following reason:\n\n{reason}\n\n"
            "Please ensure your station account has sufficient balance.\n\n"
            "Best regards,\nRoyalty Payments Team"
        )

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )

        try:
            send_sms(
                to=user.phone,
                message=f"Royalty payment failed for '{match.track.title}'. Top up your station account."
            )
        except Exception as sms_error:
            self.stdout.write(self.style.WARNING(f"⚠️ SMS failed: {sms_error}"))

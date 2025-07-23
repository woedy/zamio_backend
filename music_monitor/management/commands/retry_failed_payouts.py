# music_monitor/management/commands/retry_failed_payouts.py
from datetime import timedelta, timezone
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from bank_account.models import BankAccount
from music_monitor.models import FailedPlayLog, PlayLog

class Command(BaseCommand):
    help = 'Retry failed royalty payouts'

    def handle(self, *args, **kwargs):
        failed_entries = FailedPlayLog.objects.filter(will_retry=True)

        if not failed_entries.exists():
            self.stdout.write("No failed payouts to retry.")
            return

        for failed in failed_entries:
            match = failed.match
            if match.processed:
                # Already processed successfully elsewhere
                failed.will_retry = False
                failed.save()
                continue

            try:
                with transaction.atomic():
                    track = match.track
                    artist_user = track.artist.user
                    station_user = match.station.user

                    duration = track.duration or timedelta(seconds=180)
                    royalty = Decimal(str(round(duration.total_seconds() * float(0.005), 2)))

                    artist_account, _ = BankAccount.objects.get_or_create(user=artist_user, defaults={
                        "balance": Decimal('0.00'),
                        "currency": "Ghc"
                    })
                    station_account, _ = BankAccount.objects.get_or_create(user=station_user, defaults={
                        "balance": Decimal('0.00'),
                        "currency": "Ghc"
                    })

                    if not station_account.withdraw(royalty, f"Retry payout for '{track.title}'"):
                        raise ValueError(f"Station {station_user.username} still has insufficient funds")

                    artist_account.deposit(royalty, f"Retry royalty for '{track.title}'")

                    PlayLog.objects.create(
                        track=track,
                        station=match.station,
                        station_program=match.station_program,
                        played_at=timezone.now(),
                        start_time=timezone.now(),
                        stop_time=timezone.now() + duration,
                        duration=duration,
                        royalty_amount=royalty,
                        avg_confidence_score=match.avg_confidence_score,
                        source='streaming',
                        active=True,
                    )

                    match.processed = True
                    match.failed_reason = None
                    match.save()

                    failed.will_retry = False
                    failed.save()

                    self.stdout.write(self.style.SUCCESS(f"✅ Retried payout for MatchCache ID {match.id} succeeded."))

            except Exception as e:
                failed.reason = str(e)
                failed.save()
                self.stdout.write(self.style.ERROR(f"❌ Retry failed for MatchCache ID {match.id}: {str(e)}"))

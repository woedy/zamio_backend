from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from bank_account.models import BankAccount
from music_monitor.models import MatchCache, PlayLog

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import random

from bank_account.models import BankAccount
from datetime import timedelta

ROYALTY_RATE_PER_SECOND = Decimal('0.005')  # GHS per second

class Command(BaseCommand):
    help = 'Generate PlayLogs from MatchCaches and deposit royalties'

    def handle(self, *args, **kwargs):
        unprocessed_matches = MatchCache.objects.filter(processed=False)

        if not unprocessed_matches.exists():
            self.stdout.write(self.style.WARNING("⚠️ No unprocessed MatchCaches found."))
            return

        for match in unprocessed_matches:
            track = match.track
            artist = track.artist
            user = artist.user

            # Random duration if not provided
            duration = track.duration or timedelta(seconds=random.randint(120, 300))
            start_time = timezone.now() - timedelta(days=random.randint(0, 7))
            stop_time = start_time + duration

            # Convert to Decimal
            royalty = Decimal(str(round(duration.total_seconds() * float(ROYALTY_RATE_PER_SECOND), 2)))

            # Create PlayLog
            playlog = PlayLog.objects.create(
                track=track,
                station=match.station,
                station_program=match.station_program,
                played_at=start_time,
                start_time=start_time,
                stop_time=stop_time,
                duration=duration,
                royalty_amount=royalty,
                avg_confidence_score=match.avg_confidence_score,
                source='streaming',
                active=True,
                flagged=random.choice([True, False, False]),  # Less frequent
                dispute_status=random.choice(['Dispute', 'Review', 'Resolved', None]),
                disput_comments=random.choice([
                    None, "Incorrect metadata", "Wrong artist attribution", "Low confidence"
                ]),
            )

            # Create or fetch artist's bank account
            bank_account, _ = BankAccount.objects.get_or_create(user=user, defaults={
                "balance": Decimal('0.00'),
                "currency": "Ghc"
            })

            bank_account.deposit(
                amount=royalty,
                description=f"Royalty for playlog ID {playlog.id}"
            )

            # Mark MatchCache as processed
            match.processed = True
            match.save()

            self.stdout.write(self.style.SUCCESS(
                f"💸 Deposited GHS {royalty:.2f} to {user.username} for '{track.title}'"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Finished processing {unprocessed_matches.count()} MatchCaches."
        ))

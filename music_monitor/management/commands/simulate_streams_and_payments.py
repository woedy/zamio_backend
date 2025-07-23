from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from django.db.models import Count, Avg, Q, F, Sum
from django.core.mail import send_mail
from django.conf import settings
from collections import defaultdict
import random
import logging

from bank_account.models import BankAccount, Transaction
from music_monitor.models import MatchCache, PlayLog, FailedPlayLog
from artists.models import Track
from stations.models import Station

# Configure logging
logger = logging.getLogger(__name__)

def send_sms(to: str, message: str):
    print(f"SMS to {to}: {message}")

ROYALTY_RATE_PER_SECOND = Decimal('0.005')  # GHS per second
MIN_PLAY_DURATION = 30  # seconds
MIN_MATCHES_FOR_VALID_PLAY = 3

class Command(BaseCommand):
    help = 'Simulate realistic radio monitoring and process royalty payments (ASCAP/BMAT style)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simulate-only',
            action='store_true',
            help='Only simulate MatchCache entries without processing payments'
        )
        parser.add_argument(
            '--process-only',
            action='store_true',
            help='Only process existing MatchCache entries'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to simulate (default: 1)'
        )
        parser.add_argument(
            '--peak-hours',
            nargs=2,
            type=int,
            default=[7, 22],
            help='Peak listening hours (default: 7 22)'
        )

    def handle(self, *args, **options):
        self.simulate_only = options['simulate_only']
        self.process_only = options['process_only']
        self.days_to_simulate = options['days']
        self.peak_hours = options['peak_hours']
        
        if not self.process_only:
            self.simulate_realistic_radio_monitoring()
        
        if not self.simulate_only:
            self.process_matches_to_playlogs_bulk()

    def simulate_realistic_radio_monitoring(self):
        """Simulate realistic radio monitoring like ASCAP/BMAT systems"""
        tracks = list(Track.objects.select_related('artist__user').all())
        stations = list(Station.objects.select_related('user').all())

        if not tracks or not stations:
            self.stdout.write(self.style.ERROR("❌ No tracks or stations found"))
            return

        self.stdout.write(f"🎵 Simulating {self.days_to_simulate} days of radio monitoring...")
        
        # Calculate popularity weights (simulate hit songs vs deep cuts)
        track_weights = self._calculate_track_popularity_weights(tracks)
        
        now = timezone.now()
        created_count = 0
        batch_size = 1000
        match_cache_batch = []

        for day in range(self.days_to_simulate):
            day_start = now - timedelta(days=day + 1)
            
            for station in stations:
                # Generate realistic play schedule for this station
                plays_for_station = self._generate_station_play_schedule(
                    station, day_start, tracks, track_weights
                )
                
                for play_info in plays_for_station:
                    # Generate 3-5 MatchCache entries per play (realistic fingerprinting)
                    num_matches = random.randint(3, 5)
                    match_times = self._generate_match_timestamps(
                        play_info['start_time'], 
                        play_info['duration'], 
                        num_matches
                    )
                    
                    for match_time in match_times:
                        confidence = self._calculate_confidence_score(play_info['track'])
                        
                        match_cache_batch.append(MatchCache(
                            track=play_info['track'],
                            station=station,
                            station_program=None,
                            matched_at=match_time,
                            avg_confidence_score=confidence,
                            processed=False
                        ))
                        created_count += 1
                        
                        # Bulk create when batch is full
                        if len(match_cache_batch) >= batch_size:
                            MatchCache.objects.bulk_create(match_cache_batch)
                            match_cache_batch = []

        # Create remaining batch
        if match_cache_batch:
            MatchCache.objects.bulk_create(match_cache_batch)

        self.stdout.write(self.style.SUCCESS(f"✅ Created {created_count} MatchCache entries"))

    def _calculate_track_popularity_weights(self, tracks):
        """Calculate popularity weights for tracks (simulate chart positions)"""
        weights = {}
        for i, track in enumerate(tracks):
            # Simulate popularity distribution (80/20 rule)
            if i < len(tracks) * 0.2:  # Top 20% are hits
                weights[track.id] = random.uniform(0.7, 1.0)
            else:  # Bottom 80% are less popular
                weights[track.id] = random.uniform(0.1, 0.3)
        return weights

    def _generate_station_play_schedule(self, station, day_start, tracks, track_weights):
        """Generate realistic play schedule for a station"""
        plays = []
        current_time = day_start
        day_end = day_start + timedelta(days=1)
        
        while current_time < day_end:
            # More plays during peak hours
            hour = current_time.hour
            if self.peak_hours[0] <= hour <= self.peak_hours[1]:
                # Peak hours: 8-12 songs per hour
                minutes_until_next = random.randint(5, 8)
            else:
                # Off-peak: 6-10 songs per hour
                minutes_until_next = random.randint(6, 10)
            
            # Select track based on popularity weights
            track = self._select_weighted_track(tracks, track_weights)
            
            # Realistic song duration (2-6 minutes)
            duration_seconds = random.randint(120, 360)
            
            plays.append({
                'track': track,
                'start_time': current_time,
                'duration': duration_seconds
            })
            
            current_time += timedelta(minutes=minutes_until_next)
        
        return plays

    def _select_weighted_track(self, tracks, weights):
        """Select track based on popularity weights"""
        weighted_tracks = [(track, weights[track.id]) for track in tracks]
        total_weight = sum(weight for _, weight in weighted_tracks)
        
        random_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for track, weight in weighted_tracks:
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                return track
        
        return tracks[0]  # Fallback

    def _generate_match_timestamps(self, start_time, duration_seconds, num_matches):
        """Generate realistic match timestamps during song play"""
        timestamps = []
        play_duration = timedelta(seconds=duration_seconds)
        
        for i in range(num_matches):
            # Distribute matches throughout the song
            offset_seconds = (duration_seconds / num_matches) * i + random.randint(0, 20)
            offset_seconds = min(offset_seconds, duration_seconds - 10)  # Don't go past song end
            
            match_time = start_time + timedelta(seconds=offset_seconds)
            timestamps.append(match_time)
        
        return timestamps

    def _calculate_confidence_score(self, track):
        """Calculate realistic confidence score based on track characteristics"""
        # Simulate factors affecting recognition confidence
        base_confidence = random.uniform(75, 95)
        
        # Simulate audio quality factors
        quality_factor = random.uniform(0.9, 1.1)
        
        return min(99, max(60, base_confidence * quality_factor))

    def process_matches_to_playlogs_bulk(self):
        """Process MatchCache entries to PlayLogs with bulk operations"""
        self.stdout.write("🔄 Processing MatchCache entries to PlayLogs...")
        
        # Get grouped matches efficiently
        grouped_matches = (
            MatchCache.objects
            .filter(processed=False)
            .values('track_id', 'station_id')
            .annotate(count=Count('id'))
            .filter(count__gte=MIN_MATCHES_FOR_VALID_PLAY)
        )

        if not grouped_matches:
            self.stdout.write(self.style.WARNING("⚠️ No valid MatchCache groups to process"))
            return

        self.stdout.write(f"📦 Processing {len(grouped_matches)} valid groups...")

        # Batch process groups
        processed_count = 0
        failed_count = 0
        total_royalties = Decimal('0.00')
        
        # Ensure stations have sufficient funding before processing
        self._bulk_update_bank_accounts()
        
        # Collect all payment operations for potential bulk processing
        payment_operations = []
        successful_playlogs = []
        
        for group in grouped_matches:
            try:
                result = self._process_single_group(group, payment_operations)
                if result:
                    processed_count += 1
                    total_royalties += result['royalty']
                    successful_playlogs.append(result)
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing group {group}: {e}")
                failed_count += 1

        # Process all payments (currently individual, can be optimized for bulk later)
        self._execute_payment_operations(payment_operations)

        # Show final statistics
        self.get_processing_stats()

        self.stdout.write(self.style.SUCCESS(
            f"✅ Processed {processed_count} PlayLogs, "
            f"Failed: {failed_count}, "
            f"Total Royalties: GHS {total_royalties:.2f}"
        ))

    def _execute_payment_operations(self, payment_operations):
        """Execute payment operations (placeholder for bulk optimization)"""
        # For now, payments are processed individually in _process_single_group
        # This method can be enhanced for bulk payment processing in the future
        pass

    def _process_single_group(self, group, payment_operations):
        """Process a single group of MatchCache entries"""
        matches = MatchCache.objects.filter(
            track_id=group['track_id'],
            station_id=group['station_id'],
            processed=False
        ).select_related('track__artist__user', 'station__user')

        if not matches.exists():
            return None

        # Get first match for basic info
        first_match = matches.first()
        track = first_match.track
        station = first_match.station
        
        # Calculate play duration
        start_time = matches.earliest('matched_at').matched_at
        stop_time = matches.latest('matched_at').matched_at
        duration = stop_time - start_time

        if duration.total_seconds() < MIN_PLAY_DURATION:
            matches.update(processed=True, failed_reason="Duration too short")
            return None

        # Calculate royalty
        royalty = Decimal(str(duration.total_seconds())) * ROYALTY_RATE_PER_SECOND
        royalty = royalty.quantize(Decimal('0.01'))

        artist_user = track.artist.user
        station_user = station.user

        try:
            with transaction.atomic():
                # Get or create bank accounts with higher default balance for stations
                artist_account, _ = BankAccount.objects.get_or_create(
                    user=artist_user,
                    defaults={'balance': Decimal('0.00'), 'currency': 'Ghc'}
                )
                station_account, _ = BankAccount.objects.get_or_create(
                    user=station_user,
                    defaults={'balance': Decimal('10000.00'), 'currency': 'Ghc'}  # Higher default balance
                )

                # Process payment using existing model methods
                if not station_account.withdraw(royalty, f"Royalty for '{track.title}'"):
                    raise ValueError(f"Insufficient funds: {station_account.balance} < {royalty}")

                artist_account.deposit(royalty, f"Royalty for '{track.title}' from {station.name}")

                # Calculate average confidence
                avg_confidence = matches.aggregate(avg=Avg('avg_confidence_score'))['avg'] or 0

                # Create PlayLog
                playlog = PlayLog.objects.create(
                    track=track,
                    station=station,
                    station_program=first_match.station_program,
                    played_at=start_time,
                    start_time=start_time,
                    stop_time=stop_time,
                    duration=duration,
                    royalty_amount=royalty,
                    avg_confidence_score=avg_confidence,
                    source='Radio',
                    active=True,
                    flagged=(avg_confidence < 75)
                )

                # Mark matches as processed
                matches.update(processed=True, failed_reason=None)

                self.stdout.write(self.style.SUCCESS(
                    f"✅ {track.title} @ {station.name} - GHS {royalty:.2f} → {artist_user.username}"
                ))

                return {
                    'playlog': playlog,
                    'royalty': royalty,
                    'track': track,
                    'station': station
                }

        except Exception as e:
            error_msg = str(e)
            
            # Create failed play log
            FailedPlayLog.objects.create(
                match=first_match,
                reason=error_msg,
                will_retry=True
            )
            
            # Mark matches with failure reason
            matches.update(processed=False, failed_reason=error_msg)
            
            # Notify station
            self._notify_station_async(station_user, first_match, error_msg)
            
            self.stdout.write(self.style.ERROR(
                f"❌ Failed: {track.title} @ {station.name} - {error_msg}"
            ))
            
            return None

    def _bulk_update_bank_accounts(self):
        """Efficiently update bank account balances for stations"""
        # Ensure all stations have sufficient funding for testing
        stations = Station.objects.select_related('user').all()
        station_users = [station.user for station in stations]
        
        accounts_to_update = []
        minimum_balance = Decimal('10000.00')  # Ensure stations have enough funds
        
        for user in station_users:
            account, created = BankAccount.objects.get_or_create(
                user=user,
                defaults={'balance': minimum_balance, 'currency': 'Ghc'}
            )
            
            if not created and account.balance < Decimal('1000.00'):
                account.balance = minimum_balance
                accounts_to_update.append(account)
        
        if accounts_to_update:
            BankAccount.objects.bulk_update(accounts_to_update, ['balance'])
            self.stdout.write(f"💰 Updated {len(accounts_to_update)} station accounts with funding")
        
        return len(accounts_to_update)

    def _notify_station_async(self, user, match, reason):
        """Notify station asynchronously (in production, use Celery)"""
        try:
            subject = f"Royalty Payment Failed - {match.station.name}"
            message = (
                f"Dear {user.first_name or 'Station Manager'},\n\n"
                f"Royalty payment failed for '{match.track.title}'.\n"
                f"Reason: {reason}\n\n"
                f"Please ensure sufficient account balance.\n\n"
                f"Best regards,\nRoyalty System"
            )

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )

            send_sms(
                to=getattr(user, 'phone', ''),
                message=f"Royalty payment failed for '{match.track.title}'. Check your account balance."
            )
            
        except Exception as e:
            logger.error(f"Notification failed: {e}")

    def get_processing_stats(self):
        """Get current processing statistics"""
        stats = {
            'unprocessed_matches': MatchCache.objects.filter(processed=False).count(),
            'total_playlogs': PlayLog.objects.count(),
            'total_failed_logs': FailedPlayLog.objects.count(),
            'total_royalties_paid': PlayLog.objects.aggregate(
                total=Sum('royalty_amount')
            )['total'] or Decimal('0.00'),
        }
        
        self.stdout.write(f"📊 Processing Stats:")
        self.stdout.write(f"   Unprocessed Matches: {stats['unprocessed_matches']}")
        self.stdout.write(f"   Total PlayLogs: {stats['total_playlogs']}")
        self.stdout.write(f"   Failed Logs: {stats['total_failed_logs']}")
        self.stdout.write(f"   Total Royalties: GHS {stats['total_royalties_paid']:.2f}")
        
        return stats



#python manage.py simulate_streams_and_payments --days 7
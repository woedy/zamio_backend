from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta, datetime
from django.db.models import Count, Avg, Q, F, Sum, Min, Max
from django.core.mail import send_mail
from django.conf import settings
from collections import defaultdict
import random
import logging
import math
from calendar import monthrange

from bank_account.models import BankAccount, Transaction
from core.utils import unique_account_id_generator
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
    help = 'Simulate realistic radio monitoring and process royalty payments with historical data generation'

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
            '--months',
            type=int,
            default=None,
            help='Number of months to simulate (overrides days)'
        )
        parser.add_argument(
            '--historical',
            action='store_true',
            help='Generate historical data with realistic patterns and trends'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for historical data (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--peak-hours',
            nargs=2,
            type=int,
            default=[7, 22],
            help='Peak listening hours (default: 7 22)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing data before generating new data'
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=None,
            help='Random seed for reproducible simulations'
        )

    def handle(self, *args, **options):
        self.simulate_only = options['simulate_only']
        self.process_only = options['process_only']
        self.days_to_simulate = options['days']
        self.months_to_simulate = options['months']
        self.historical = options['historical']
        self.start_date = options['start_date']
        self.peak_hours = options['peak_hours']
        self.clear_existing = options['clear_existing']
        seed = options.get('seed')

        if seed is not None:
            random.seed(seed)
        
        if self.clear_existing:
            self.clear_existing_data()
        
        if not self.process_only:
            # Convenience: if requesting multi-day without --historical, treat as historical
            if (self.historical or self.months_to_simulate or (self.days_to_simulate and self.days_to_simulate > 1)):
                # Default to 12 months when historical requested without an explicit window
                if self.historical and not self.months_to_simulate and (not self.days_to_simulate or self.days_to_simulate == 1):
                    self.months_to_simulate = 12
                self.simulate_historical_data()
            else:
                # Single-day, near-real-time style simulation
                self.simulate_realistic_radio_monitoring()
        
        if not self.simulate_only:
            self.process_matches_to_playlogs_bulk()

    def clear_existing_data(self):
        """Clear existing simulation data"""
        self.stdout.write("🗑️ Clearing existing simulation data...")
        
        # Clear in order to avoid foreign key constraints
        FailedPlayLog.objects.all().delete()
        PlayLog.objects.all().delete()
        MatchCache.objects.all().delete()
        Transaction.objects.all().delete()
        
        # Reset bank account balances
        BankAccount.objects.all().update(balance=Decimal('0.00'))
        
        self.stdout.write(self.style.SUCCESS("✅ Existing data cleared"))

    def simulate_historical_data(self):
        """Generate historical data with realistic patterns and trends - OPTIMIZED"""
        # Pre-fetch all data with select_related to avoid N+1 queries
        tracks = list(Track.objects.select_related('artist__user').all())
        stations = list(Station.objects.select_related('user').all())

        if not tracks or not stations:
            self.stdout.write(self.style.ERROR("❌ No tracks or stations found"))
            return

        # Determine time range
        if self.months_to_simulate:
            total_days = self.months_to_simulate * 30  # Approximate
        else:
            total_days = self.days_to_simulate

        # Set start date
        if self.start_date:
            start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
            start_date = timezone.make_aware(start_date)
        else:
            start_date = timezone.now() - timedelta(days=total_days)

        self.stdout.write(f"🎵 Generating {total_days} days of historical data from {start_date.date()}...")
        
        # Pre-calculate all patterns to avoid repeated calculations
        track_popularity = self._initialize_track_popularity(tracks)
        station_growth = self._initialize_station_growth(stations)
        
        # Pre-calculate seasonal and weekly multipliers for all days
        daily_multipliers = self._precalculate_daily_multipliers(start_date, total_days)
        
        # Optimized batch processing
        created_count = 0
        batch_size = 5000  # Increased batch size for better performance
        match_cache_batch = []
        
        # Pre-calculate track weights for each day to avoid repeated calculations
        daily_track_weights = self._precalculate_track_weights(track_popularity, total_days)

        # Generate data day by day with realistic patterns
        for day in range(total_days):
            current_date = start_date + timedelta(days=day)
            
            # Use pre-calculated multipliers
            seasonal_multiplier = daily_multipliers[day]['seasonal']
            weekly_multiplier = daily_multipliers[day]['weekly']
            
            # Use pre-calculated track weights
            track_weights = daily_track_weights[day]
            
            # Generate plays for all stations in parallel-friendly way
            daily_plays = self._generate_daily_plays_optimized(
                stations, current_date, tracks, track_weights,
                seasonal_multiplier, weekly_multiplier, station_growth,
                day_index=day
            )
            
            # Process all plays for this day
            for play_info in daily_plays:
                # Generate matches more efficiently
                matches = self._generate_matches_optimized(play_info)
                match_cache_batch.extend(matches)
                created_count += len(matches)
                
                # Bulk create when batch is full (larger batches for better performance)
                if len(match_cache_batch) >= batch_size:
                    MatchCache.objects.bulk_create(match_cache_batch, batch_size=batch_size)
                    match_cache_batch = []

            # Progress update with memory usage info
            if day % 30 == 0:
                self.stdout.write(f"📅 Generated {day} days of data... ({created_count:,} entries)")

        # Create remaining batch
        if match_cache_batch:
            MatchCache.objects.bulk_create(match_cache_batch, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(f"✅ Created {created_count:,} historical MatchCache entries"))

    def _initialize_track_popularity(self, tracks):
        """Initialize track popularity with realistic distribution"""
        popularity = {}
        
        for i, track in enumerate(tracks):
            # Simulate different track types and their popularity evolution
            track_type = random.choice(['hit', 'steady', 'declining', 'rising'])
            
            if track_type == 'hit':
                # Chart-topping hits
                popularity[track.id] = {
                    'base_weight': random.uniform(0.8, 1.0),
                    'trend': random.uniform(-0.001, 0.001),  # Slight decline over time
                    'type': 'hit'
                }
            elif track_type == 'rising':
                # Rising tracks
                popularity[track.id] = {
                    'base_weight': random.uniform(0.2, 0.5),
                    'trend': random.uniform(0.001, 0.003),  # Growing popularity
                    'type': 'rising'
                }
            elif track_type == 'declining':
                # Declining tracks
                popularity[track.id] = {
                    'base_weight': random.uniform(0.5, 0.8),
                    'trend': random.uniform(-0.003, -0.001),  # Declining popularity
                    'type': 'declining'
                }
            else:
                # Steady tracks
                popularity[track.id] = {
                    'base_weight': random.uniform(0.3, 0.7),
                    'trend': random.uniform(-0.0005, 0.0005),  # Stable
                    'type': 'steady'
                }
        
        return popularity

    def _initialize_station_growth(self, stations):
        """Initialize station growth patterns"""
        growth = {}
        
        for station in stations:
            # Simulate different station growth patterns
            growth_type = random.choice(['growing', 'stable', 'declining'])
            
            if growth_type == 'growing':
                growth[station.id] = {
                    'base_activity': random.uniform(0.7, 1.0),
                    'growth_rate': random.uniform(0.002, 0.005),  # Growing audience
                    'type': 'growing'
                }
            elif growth_type == 'declining':
                growth[station.id] = {
                    'base_activity': random.uniform(0.8, 1.0),
                    'growth_rate': random.uniform(-0.003, -0.001),  # Declining audience
                    'type': 'declining'
                }
            else:
                growth[station.id] = {
                    'base_activity': random.uniform(0.6, 0.9),
                    'growth_rate': random.uniform(-0.001, 0.001),  # Stable
                    'type': 'stable'
                }
        
        return growth

    def _precalculate_daily_multipliers(self, start_date, total_days):
        """Pre-calculate seasonal and weekly multipliers for all days"""
        multipliers = {}
        
        for day in range(total_days):
            current_date = start_date + timedelta(days=day)
            multipliers[day] = {
                'seasonal': self._get_seasonal_multiplier(current_date),
                'weekly': self._get_weekly_multiplier(current_date)
            }
        
        return multipliers

    def _precalculate_track_weights(self, track_popularity, total_days):
        """Pre-calculate track weights for all days to avoid repeated calculations"""
        daily_weights = {}
        
        for day in range(total_days):
            weights = {}
            for track_id, data in track_popularity.items():
                # Calculate current weight for this day
                current_weight = max(0.1, 
                    data['base_weight'] + (data['trend'] * day)
                )
                # Add some randomness but cache it
                weights[track_id] = current_weight * random.uniform(0.9, 1.1)
            
            daily_weights[day] = weights
        
        return daily_weights

    def _generate_daily_plays_optimized(self, stations, date, tracks, track_weights,
                                       seasonal_multiplier, weekly_multiplier, station_growth,
                                       day_index: int):
        """Generate all plays for a single day across all stations - optimized"""
        all_plays = []
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Pre-calculate hourly patterns for the day
        hourly_patterns = self._precalculate_hourly_patterns(seasonal_multiplier, weekly_multiplier)
        
        for station in stations:
            base_activity = station_growth[station.id].get('base_activity', 0.8)
            growth_rate = station_growth[station.id].get('growth_rate', 0.0)
            # Evolve station activity over days for historical realism
            station_activity = base_activity + (growth_rate * day_index)
            station_activity = max(0.3, min(1.5, station_activity))
            
            # Generate plays for this station more efficiently
            station_plays = self._generate_station_plays_optimized(
                station, day_start, tracks, track_weights, 
                station_activity, hourly_patterns
            )
            all_plays.extend(station_plays)
        
        return all_plays

    def _precalculate_hourly_patterns(self, seasonal_multiplier, weekly_multiplier):
        """Pre-calculate hourly patterns for a day"""
        patterns = {}
        base_activity = seasonal_multiplier * weekly_multiplier
        
        for hour in range(24):
            if self.peak_hours[0] <= hour <= self.peak_hours[1]:
                # Peak hours
                patterns[hour] = base_activity * random.uniform(1.2, 1.5)
            elif 22 <= hour or hour <= 6:
                # Late night/early morning
                patterns[hour] = base_activity * random.uniform(0.4, 0.7)
            else:
                # Regular hours
                patterns[hour] = base_activity * random.uniform(0.8, 1.2)
        
        return patterns

    def _generate_station_plays_optimized(self, station, day_start, tracks, track_weights, 
                                         station_activity, hourly_patterns):
        """Generate plays for a single station - optimized"""
        plays = []
        current_time = day_start
        day_end = day_start + timedelta(days=1)
        
        # Pre-calculate weighted track selection data
        weighted_tracks = [(track, track_weights.get(track.id, 0.5)) for track in tracks]
        total_weight = sum(weight for _, weight in weighted_tracks)
        
        # Generate plays more efficiently
        while current_time < day_end:
            hour = current_time.hour
            hour_activity = hourly_patterns.get(hour, 1.0)
            
            # Calculate plays for this hour
            base_plays_per_hour = 8 * station_activity * hour_activity
            plays_this_hour = max(1, int(base_plays_per_hour))
            
            # Generate multiple plays for this hour at once
            for _ in range(plays_this_hour):
                if current_time >= day_end:
                    break
                
                # Optimized track selection
                track = self._select_track_optimized(weighted_tracks, total_weight)
                
                # Realistic song duration
                duration_seconds = random.randint(120, 360)
                
                plays.append({
                    'track': track,
                    'station': station,
                    'start_time': current_time,
                    'duration': duration_seconds
                })
                
                # Time until next song
                minutes_until_next = random.randint(4, 8)
                current_time += timedelta(minutes=minutes_until_next)
            
            # Move to next hour if needed
            next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            if current_time < next_hour:
                current_time = next_hour
        
        return plays

    def _select_track_optimized(self, weighted_tracks, total_weight):
        """Optimized track selection using pre-calculated weights"""
        if total_weight == 0:
            return weighted_tracks[0][0]
        
        random_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for track, weight in weighted_tracks:
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                return track
        
        return weighted_tracks[0][0]

    def _generate_matches_optimized(self, play_info):
        """Generate matches for a play more efficiently"""
        matches = []
        num_matches = random.randint(3, 5)
        
        # Calculate all timestamps at once
        duration_seconds = play_info['duration']
        start_time = play_info['start_time']
        
        for i in range(num_matches):
            # Distribute matches throughout the song
            offset_seconds = (duration_seconds / num_matches) * i + random.randint(0, 20)
            offset_seconds = min(offset_seconds, duration_seconds - 10)
            
            match_time = start_time + timedelta(seconds=offset_seconds)
            confidence = self._calculate_confidence_score(play_info['track'])
            
            matches.append(MatchCache(
                track=play_info['track'],
                station=play_info['station'],
                station_program=None,
                matched_at=match_time,
                avg_confidence_score=confidence,
                processed=False
            ))
        
        return matches

    def _get_seasonal_multiplier(self, date):
        """Get seasonal multiplier based on date"""
        month = date.month
        
        # Simulate seasonal patterns
        if month in [12, 1, 2]:  # Winter - higher indoor activity
            return random.uniform(1.1, 1.3)
        elif month in [6, 7, 8]:  # Summer - vacation patterns
            return random.uniform(0.8, 1.0)
        elif month in [9, 10, 11]:  # Fall - back to school/work
            return random.uniform(1.0, 1.2)
        else:  # Spring
            return random.uniform(0.9, 1.1)

    def _get_weekly_multiplier(self, date):
        """Get weekly multiplier based on day of week"""
        weekday = date.weekday()  # 0 = Monday, 6 = Sunday
        
        if weekday in [5, 6]:  # Weekend
            return random.uniform(1.2, 1.4)  # More listening on weekends
        elif weekday in [0, 4]:  # Monday, Friday
            return random.uniform(1.0, 1.1)
        else:  # Tuesday, Wednesday, Thursday
            return random.uniform(0.9, 1.0)

    def _generate_historical_play_schedule(self, station, date, tracks, track_popularity, station_activity):
        """Generate realistic play schedule with historical patterns"""
        plays = []
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        current_time = day_start
        
        # Base plays per hour adjusted by station activity
        base_plays_per_hour = 8 * station_activity
        
        while current_time < day_end:
            # Hourly patterns
            hour = current_time.hour
            if self.peak_hours[0] <= hour <= self.peak_hours[1]:
                # Peak hours
                plays_this_hour = int(base_plays_per_hour * random.uniform(1.2, 1.5))
            elif 22 <= hour or hour <= 6:
                # Late night/early morning
                plays_this_hour = int(base_plays_per_hour * random.uniform(0.4, 0.7))
            else:
                # Regular hours
                plays_this_hour = int(base_plays_per_hour * random.uniform(0.8, 1.2))
            
            # Generate plays for this hour
            for _ in range(plays_this_hour):
                if current_time >= day_end:
                    break
                
                # Select track based on current popularity
                track = self._select_weighted_historical_track(tracks, track_popularity)
                
                # Realistic song duration
                duration_seconds = random.randint(120, 360)
                
                plays.append({
                    'track': track,
                    'start_time': current_time,
                    'duration': duration_seconds
                })
                
                # Time until next song (including ads, DJ talk, etc.)
                minutes_until_next = random.randint(4, 8)
                current_time += timedelta(minutes=minutes_until_next)
            
            # Move to next hour if we haven't already
            next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            if current_time < next_hour:
                current_time = next_hour
        
        return plays

    def _select_weighted_historical_track(self, tracks, track_popularity):
        """Select track based on historical popularity weights"""
        weighted_tracks = []
        
        for track in tracks:
            weight = track_popularity[track.id].get('current_weight', 0.5)
            weighted_tracks.append((track, weight))
        
        total_weight = sum(weight for _, weight in weighted_tracks)
        if total_weight == 0:
            return random.choice(tracks)
        
        random_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for track, weight in weighted_tracks:
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                return track
        
        return tracks[0]  # Fallback

    def simulate_realistic_radio_monitoring(self):
        """Original simulation method for short-term data"""
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
        """Process MatchCache entries to PlayLogs with optimized bulk operations"""
        self.stdout.write("🔄 Processing MatchCache entries to PlayLogs...")
        
        # Use database-level grouping for better performance
        grouped_matches = (
            MatchCache.objects
            .filter(processed=False)
            .values('track_id', 'station_id')
            .annotate(
                count=Count('id'),
                earliest_match=Min('matched_at'),
                latest_match=Max('matched_at')
            )
            .filter(count__gte=MIN_MATCHES_FOR_VALID_PLAY)
            .order_by('earliest_match')  # Process chronologically
        )

        total_groups = grouped_matches.count()
        if total_groups == 0:
            self.stdout.write(self.style.WARNING("⚠️ No valid MatchCache groups to process"))
            return
        self.stdout.write(f"📦 Processing {total_groups:,} valid groups...")

        # Pre-fund all station accounts efficiently
        self._bulk_update_bank_accounts()
        
        # Process in optimized batches
        processed_count = 0
        failed_count = 0
        total_royalties = Decimal('0.00')
        
        # Use larger batch sizes for better performance
        batch_size = 500
        
        for i in range(0, total_groups, batch_size):
            batch = grouped_matches[i:i + batch_size]
            
            # Process batch with optimized database operations
            batch_results = self._process_batch_optimized(batch)
            
            processed_count += batch_results['processed']
            failed_count += batch_results['failed']
            total_royalties += batch_results['total_royalties']
            
            # Progress update
            if i % 2000 == 0:
                self.stdout.write(f"📊 Processed {i:,}/{total_groups:,} groups... "
                                f"Success: {processed_count:,}, Failed: {failed_count:,}")

        # Final statistics
        self.get_processing_stats()

        self.stdout.write(self.style.SUCCESS(
            f"✅ Processed {processed_count:,} PlayLogs, "
            f"Failed: {failed_count:,}, "
            f"Total Royalties: GHS {total_royalties:,.2f}"
        ))

    def _process_batch_optimized(self, batch):
        """Process a batch of groups with optimized database operations"""
        batch_results = {
            'processed': 0,
            'failed': 0,
            'total_royalties': Decimal('0.00')
        }
        
        # Pre-fetch all related objects for this batch
        track_ids = [group['track_id'] for group in batch]
        station_ids = [group['station_id'] for group in batch]
        
        # Bulk fetch related objects
        tracks_dict = {
            track.id: track 
            for track in Track.objects.select_related('artist__user').filter(id__in=track_ids)
        }
        stations_dict = {
            station.id: station 
            for station in Station.objects.select_related('user').filter(id__in=station_ids)
        }
        
        # Pre-fetch bank accounts
        user_ids = [track.artist.user.id for track in tracks_dict.values()] + \
                   [station.user.id for station in stations_dict.values()]
        bank_accounts_dict = {
            account.user_id: account 
            for account in BankAccount.objects.select_related('user').filter(user_id__in=user_ids)
        }
        
        # Process each group in the batch
        for group in batch:
            try:
                result = self._process_single_group_optimized(
                    group, tracks_dict, stations_dict, bank_accounts_dict
                )
                if result:
                    batch_results['processed'] += 1
                    batch_results['total_royalties'] += result['royalty']
                else:
                    batch_results['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing group {group}: {e}")
                batch_results['failed'] += 1
        
        return batch_results

    def _process_single_group_optimized(self, group, tracks_dict, stations_dict, bank_accounts_dict):
        """Process a single group with pre-fetched objects"""
        track = tracks_dict.get(group['track_id'])
        station = stations_dict.get(group['station_id'])
        
        if not track or not station:
            return None
        
        # Get matches for this group
        matches = MatchCache.objects.filter(
            track_id=group['track_id'],
            station_id=group['station_id'],
            processed=False
        ).select_related('track', 'station')

        if not matches.exists():
            return None

        # Use pre-calculated times from the group query
        start_time = group['earliest_match']
        stop_time = group['latest_match']
        duration = stop_time - start_time

        if duration.total_seconds() < MIN_PLAY_DURATION:
            # Fallback: estimate duration from match count when timestamps are too close
            # This commonly happens with simulated data where many matches share near-identical timestamps.
            match_count = group.get('count', matches.count())
            # Assume ~20s spacing between consecutive matches; cap to a reasonable max
            estimated_seconds = max((match_count - 1) * 20, MIN_PLAY_DURATION)
            # If still below threshold, mark as processed with reason
            if estimated_seconds < MIN_PLAY_DURATION:
                matches.update(processed=True, failed_reason="Duration too short")
                return None
            # Use estimated end time to proceed
            stop_time = start_time + timedelta(seconds=estimated_seconds)
            duration = stop_time - start_time

        # Calculate royalty
        royalty = Decimal(str(duration.total_seconds())) * ROYALTY_RATE_PER_SECOND
        royalty = royalty.quantize(Decimal('0.01'))

        artist_user = track.artist.user
        station_user = station.user

        try:
            with transaction.atomic():
                # Get bank accounts from pre-fetched dict
                artist_account = bank_accounts_dict.get(artist_user.id)
                station_account = bank_accounts_dict.get(station_user.id)
                
                # Create accounts if they don't exist
                if not artist_account:
                    artist_account, _ = BankAccount.objects.get_or_create(
                        user=artist_user,
                        defaults={'balance': Decimal('0.00'), 'currency': 'GHS'}
                    )
                
                if not station_account:
                    station_account, _ = BankAccount.objects.get_or_create(
                        user=station_user,
                        defaults={'balance': Decimal('50000.00'), 'currency': 'GHS'}
                    )

                # Process payment
                if not station_account.withdraw(royalty, f"Royalty for '{track.title}'"):
                    raise ValueError(f"Insufficient funds: {station_account.balance} < {royalty}")

                artist_account.deposit(royalty, f"Royalty for '{track.title}' from {station.name}")

                # Calculate average confidence efficiently
                avg_confidence = matches.aggregate(avg=Avg('avg_confidence_score'))['avg'] or 0

                # Create PlayLog
                playlog = PlayLog.objects.create(
                    track=track,
                    station=station,
                    station_program=None,
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

                return {
                    'playlog': playlog,
                    'royalty': royalty,
                    'track': track,
                    'station': station
                }

        except Exception as e:
            error_msg = str(e)
            
            # Create failed play log
            first_match = matches.first()
            if first_match:
                FailedPlayLog.objects.create(
                    match=first_match,
                    reason=error_msg,
                    will_retry=True
                )
            
            # Mark matches with failure reason
            matches.update(processed=False, failed_reason=error_msg)
            
            return None

    def _process_single_group(self, group):
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
                    defaults={'balance': Decimal('0.00'), 'currency': 'GHS'}
                )
                station_account, _ = BankAccount.objects.get_or_create(
                    user=station_user,
                    defaults={'balance': Decimal('50000.00'), 'currency': 'GHS'}  # Higher default for historical data
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
            
            return None

    def _bulk_update_bank_accounts(self):
        """Efficiently update bank account balances for stations with bulk operations"""
        self.stdout.write("💰 Ensuring sufficient funding for all stations...")
        
        # Get all stations and their users in one query
        stations_with_users = Station.objects.select_related('user').values_list('user_id', flat=True)
        
        # Get all artists and their users in one query
        artists_with_users = Track.objects.select_related('artist__user').values_list('artist__user_id', flat=True).distinct()
        
        # Combine all user IDs
        all_user_ids = set(stations_with_users) | set(artists_with_users)
        
        # Get existing bank accounts
        existing_accounts = {
            account.user_id: account 
            for account in BankAccount.objects.filter(user_id__in=all_user_ids)
        }
        
        # Prepare bulk operations
        accounts_to_create = []
        accounts_to_update = []
        minimum_station_balance = Decimal('50000.00')
        
        for user_id in all_user_ids:
            if user_id not in existing_accounts:
                # Determine if this is a station user (higher balance) or artist user
                is_station_user = user_id in stations_with_users
                initial_balance = minimum_station_balance if is_station_user else Decimal('0.00')
                
                accounts_to_create.append(BankAccount(
                    user_id=user_id,
                    balance=initial_balance,
                    currency='GHS'
                ))
            else:
                # Update existing accounts if needed
                account = existing_accounts[user_id]
                is_station_user = user_id in stations_with_users
                
                if is_station_user and account.balance < Decimal('10000.00'):
                    account.balance = minimum_station_balance
                    accounts_to_update.append(account)
        
        # Ensure unique account_id for bulk create (signals don't run on bulk operations)
        if accounts_to_create:
            for acc in accounts_to_create:
                # Generate until non-empty/unique value is returned
                acc.account_id = unique_account_id_generator(acc)
                while not acc.account_id:
                    acc.account_id = unique_account_id_generator(acc)

            # Bulk create new accounts
            BankAccount.objects.bulk_create(accounts_to_create, batch_size=1000)
            self.stdout.write(f"💳 Created {len(accounts_to_create)} new bank accounts")
        
        # Bulk update existing accounts
        if accounts_to_update:
            BankAccount.objects.bulk_update(accounts_to_update, ['balance'], batch_size=1000)
            self.stdout.write(f"💰 Updated {len(accounts_to_update)} station accounts with funding")
        
        return len(accounts_to_create) + len(accounts_to_update)

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


# Usage Examples for Historical Data Generation:

# Generate 6 months of historical data:
# python manage.py simulate__historical_streams_and_payments --historical --months 6 --start-date 2024-01-01

# Generate 1 year of historical data:
# python manage.py simulate__historical_streams_and_payments --historical --months 12 --start-date 2023-07-01

# Clear existing data and generate 6 months:
# python manage.py simulate__historical_streams_and_payments --historical --months 6 --start-date 2024-01-01 --clear-existing

# Generate data only (no processing):
# python manage.py simulate__historical_streams_and_payments --historical --months 6 --simulate-only

# Process existing data only:
# python manage.py simulate__historical_streams_and_payments --process-only


#python manage.py simulate__historical_streams_and_payment --historical --months 12 --start-date 2024-09-03 --clear-existing --seed 42

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta, datetime
from django.db.models import Count, Avg, Q, F, Sum
from django.core.mail import send_mail
from django.conf import settings
from collections import defaultdict
import random
import logging
import math
from calendar import monthrange

from bank_account.models import BankAccount, Transaction
from music_monitor.models import MatchCache, PlayLog, FailedPlayLog
from artists.models import Track
from stations.models import Station

# Configure logging
logger = logging.getLogger(__name__)

def send_sms(to: str, message: str):
    print(f"SMS to {to}: {message}")

ROYALTY_RATE_PER_SECOND = Decimal('0.005')  # GHS per second

MIN_MATCHES_FOR_VALID_PLAY = 2  # Change from 3 to 2
MIN_PLAY_DURATION = 15  # Change from 30 to 15 seconds

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
        # NEW ARGUMENTS FOR STATION LIMITING
        parser.add_argument(
            '--max-stations',
            type=int,
            default=4,
            help='Maximum number of stations to generate data for (default: 4)'
        )
        parser.add_argument(
            '--station-ids',
            nargs='*',
            type=str,
            help='Specific station IDs to generate data for (e.g., --station-ids 1 2 3)'
        )
        parser.add_argument(
            '--list-stations',
            action='store_true',
            help='List all available stations and their IDs'
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
        self.max_stations = options['max_stations']
        self.station_ids = options['station_ids']
        self.list_stations = options['list_stations']
        
        # Handle station listing
        if self.list_stations:
            self.list_available_stations()
            return
        
        if self.clear_existing:
            self.clear_existing_data()
        
        if not self.process_only:
            if self.historical or self.months_to_simulate:
                self.simulate_historical_data()
            else:
                self.simulate_realistic_radio_monitoring()
        
        if not self.simulate_only:
            self.process_matches_to_playlogs_bulk()

    def list_available_stations(self):
        """List all available stations with their IDs"""
        stations = Station.objects.select_related('user').all()
        
        if not stations:
            self.stdout.write(self.style.ERROR("❌ No stations found in database"))
            return
        
        self.stdout.write("📻 Available Stations:")
        self.stdout.write("-" * 50)
        
        for station in stations:
            user_info = f" (Owner: {station.user.get_full_name() or station.user.username})" if station.user else ""
            self.stdout.write(f"ID: {station.station_id:3d} | {station.name}{user_info}")
        
        self.stdout.write("-" * 50)
        self.stdout.write(f"Total: {stations.count()} stations")
        self.stdout.write("\nUsage examples:")
        self.stdout.write("  # Generate data for specific stations:")
        self.stdout.write("  python manage.py simulate_history_streams_and_payments --station-ids 1 2 3")
        self.stdout.write("  # Generate data for max 3 stations:")
        self.stdout.write("  python manage.py simulate_history_streams_and_payments --max-stations 3")

    def get_selected_stations(self):
        """Get the selected stations based on command arguments"""
        if self.station_ids:
            # Use specific station IDs
            stations = list(Station.objects.select_related('user').filter(station_id__in=self.station_ids))
            
            if not stations:
                self.stdout.write(self.style.ERROR(f"❌ No stations found with IDs: {self.station_ids}"))
                return []
            
            missing_ids = set(self.station_ids) - set(station.station_id for station in stations)
            if missing_ids:
                self.stdout.write(self.style.WARNING(f"⚠️ Station IDs not found: {missing_ids}"))
            
            self.stdout.write(f"🎯 Using specific stations: {[station.name for station in stations]}")
            
        else:
            # Use first N stations or random selection
            all_stations = list(Station.objects.select_related('user').all())
            
            if not all_stations:
                self.stdout.write(self.style.ERROR("❌ No stations found"))
                return []
            
            if len(all_stations) <= self.max_stations:
                stations = all_stations
                self.stdout.write(f"📻 Using all {len(stations)} available stations")
            else:
                # Randomly select stations for more realistic demo data
                stations = random.sample(all_stations, self.max_stations)
                self.stdout.write(f"🎯 Randomly selected {self.max_stations} stations for demo: {[station.name for station in stations]}")
        
        return stations

    def clear_existing_data(self):
        """Clear existing simulation data"""
        self.stdout.write("🗑️ Clearing existing simulation data...")
        
        # Clear in order to avoid foreign key constraints
        FailedPlayLog.objects.all().delete()
        PlayLog.objects.all().delete()
        MatchCache.objects.all().delete()
        Transaction.objects.all().delete()
        
        # Reset bank account balances
        BankAccount.objects.all().update(balance=Decimal('50000.00'))
        
        self.stdout.write(self.style.SUCCESS("✅ Existing data cleared"))

    def simulate_historical_data(self):
        """Generate historical data with realistic patterns and trends - OPTIMIZED for selected stations only"""
        # Pre-fetch all data with select_related to avoid N+1 queries
        tracks = list(Track.objects.select_related('artist__user').all())
        stations = self.get_selected_stations()  # MODIFIED: Use selected stations only

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
        self.stdout.write(f"📻 Selected {len(stations)} stations: {', '.join([station.name for station in stations])}")
        
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
            
            # Generate plays for selected stations only
            daily_plays = self._generate_daily_plays_optimized(
                stations, current_date, tracks, track_weights, 
                seasonal_multiplier, weekly_multiplier, station_growth
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

            # Progress update with more frequent updates for smaller datasets
            if day % 15 == 0:  # More frequent updates since we have fewer stations
                self.stdout.write(f"📅 Generated {day} days of data... ({created_count:,} entries)")

        # Create remaining batch
        if match_cache_batch:
            MatchCache.objects.bulk_create(match_cache_batch, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(f"✅ Created {created_count:,} historical MatchCache entries for {len(stations)} stations"))

    def simulate_realistic_radio_monitoring(self):
        """Original simulation method for short-term data - MODIFIED for selected stations"""
        tracks = list(Track.objects.select_related('artist__user').all())
        stations = self.get_selected_stations()  # MODIFIED: Use selected stations only

        if not tracks or not stations:
            self.stdout.write(self.style.ERROR("❌ No tracks or stations found"))
            return

        self.stdout.write(f"🎵 Simulating {self.days_to_simulate} days of radio monitoring...")
        self.stdout.write(f"📻 Selected {len(stations)} stations: {', '.join([station.name for station in stations])}")
        
        # Calculate popularity weights (simulate hit songs vs deep cuts)
        track_weights = self._calculate_track_popularity_weights(tracks)
        
        now = timezone.now()
        created_count = 0
        batch_size = 1000
        match_cache_batch = []

        for day in range(self.days_to_simulate):
            day_start = now - timedelta(days=day + 1)
            
            for station in stations:  # Now iterating over selected stations only
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

        self.stdout.write(self.style.SUCCESS(f"✅ Created {created_count} MatchCache entries for {len(stations)} stations"))

    def _bulk_update_bank_accounts(self):
        """Efficiently update bank account balances for selected stations with bulk operations"""
        self.stdout.write("💰 Ensuring sufficient funding for selected stations...")
        
        # Get selected stations and their users in one query
        selected_stations = self.get_selected_stations()
        stations_with_users = [station.user_id for station in selected_stations if station.user_id]
        
        # Get all artists and their users in one query (still need all artists for royalty payments)
        artists_with_users = Track.objects.select_related('artist__user').values_list('artist__user_id', flat=True).distinct()
        
        # Combine user IDs (selected stations + all artists)
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
                # Determine if this is a selected station user (higher balance) or artist user
                is_station_user = user_id in stations_with_users
                initial_balance = minimum_station_balance if is_station_user else Decimal('0.00')
                
                accounts_to_create.append(BankAccount(
                    user_id=user_id,
                    balance=initial_balance,
                    currency='Ghc'
                ))
            else:
                # Update existing accounts if needed
                account = existing_accounts[user_id]
                is_station_user = user_id in stations_with_users
                
                if is_station_user and account.balance < Decimal('10000.00'):
                    account.balance = minimum_station_balance
                    accounts_to_update.append(account)
        
        # Bulk create new accounts
        if accounts_to_create:
            BankAccount.objects.bulk_create(accounts_to_create, batch_size=1000)
            self.stdout.write(f"💳 Created {len(accounts_to_create)} new bank accounts")
        
        # Bulk update existing accounts
        if accounts_to_update:
            BankAccount.objects.bulk_update(accounts_to_update, ['balance'], batch_size=1000)
            self.stdout.write(f"💰 Updated {len(accounts_to_update)} station accounts with funding")
        
        return len(accounts_to_create) + len(accounts_to_update)

    # Keep all the other existing methods unchanged...
    # (All the helper methods from your original code remain the same)
    
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
                growth[station.station_id] = {
                    'base_activity': random.uniform(0.7, 1.0),
                    'growth_rate': random.uniform(0.002, 0.005),  # Growing audience
                    'type': 'growing'
                }
            elif growth_type == 'declining':
                growth[station.station_id] = {
                    'base_activity': random.uniform(0.8, 1.0),
                    'growth_rate': random.uniform(-0.003, -0.001),  # Declining audience
                    'type': 'declining'
                }
            else:
                growth[station.station_id] = {
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
                                       seasonal_multiplier, weekly_multiplier, station_growth):
        """Generate all plays for a single day across all stations - optimized"""
        all_plays = []
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Pre-calculate hourly patterns for the day
        hourly_patterns = self._precalculate_hourly_patterns(seasonal_multiplier, weekly_multiplier)
        
        for station in stations:
            station_activity = station_growth[station.station_id].get('current_activity', 0.8)
            station_activity = max(0.3, station_activity + (station_growth[station.station_id]['growth_rate'] * 180))  # Approximate day calculation
            
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
        
        # Ensure bank accounts are properly funded for selected stations only
        self._bulk_update_bank_accounts()
        
        # Get unprocessed matches with optimized query
        unprocessed_matches = MatchCache.objects.filter(processed=False)\
            .select_related('track__artist__user', 'station__user')\
            .order_by('matched_at')
        
        total_matches = unprocessed_matches.count()
        if total_matches == 0:
            self.stdout.write(self.style.WARNING("⚠️ No unprocessed matches found"))
            return
        
        self.stdout.write(f"📊 Processing {total_matches:,} MatchCache entries...")
        
        # Process in batches for memory efficiency
        batch_size = 5000
        processed_count = 0
        playlogs_created = 0
        failed_logs_created = 0
        transactions_created = 0
        
        # Batch process matches
        for batch_start in range(0, total_matches, batch_size):
            batch_end = min(batch_start + batch_size, total_matches)
            batch_matches = list(unprocessed_matches[batch_start:batch_end])
            
            # Group matches by track and station for play detection
            play_groups = self._group_matches_into_plays(batch_matches)
            
            # Prepare bulk operations
            playlogs_to_create = []
            failed_logs_to_create = []
            transactions_to_create = []
            match_ids_to_update = []
            
            for group_key, matches in play_groups.items():
                track, station = group_key
                
                # Validate play (minimum matches and duration requirements)
                play_result = self._validate_and_process_play(matches, track, station)
                
                if play_result['valid']:
                    # Create PlayLog
                    playlog = self._create_playlog_entry(play_result)
                    playlogs_to_create.append(playlog)
                    
                    # Create royalty transaction if artist has bank account
                    transaction = self._create_royalty_transaction(playlog, play_result)
                    if transaction:
                        transactions_to_create.append(transaction)
                    
                    # Mark matches as processed
                    match_ids_to_update.extend([m.id for m in matches])
                    
                else:
                    # Create FailedPlayLog
                    failed_log = self._create_failed_playlog_entry(play_result, matches)
                    if failed_log:
                        failed_logs_to_create.append(failed_log)
                    
                    # Still mark matches as processed
                    match_ids_to_update.extend([m.id for m in matches])
            
            # Execute bulk operations
            if playlogs_to_create:
                PlayLog.objects.bulk_create(playlogs_to_create, batch_size=1000)
                playlogs_created += len(playlogs_to_create)
            
            if failed_logs_to_create:
                FailedPlayLog.objects.bulk_create(failed_logs_to_create, batch_size=1000)
                failed_logs_created += len(failed_logs_to_create)
            
            if transactions_to_create:
                Transaction.objects.bulk_create(transactions_to_create, batch_size=1000)
                transactions_created += len(transactions_to_create)
                
                # Update bank account balances efficiently
                self._update_bank_balances_bulk(transactions_to_create)
            
            # Mark matches as processed
            if match_ids_to_update:
                MatchCache.objects.filter(id__in=match_ids_to_update).update(processed=True)
                processed_count += len(match_ids_to_update)
            
            # Progress update
            self.stdout.write(f"📈 Processed {batch_end:,}/{total_matches:,} matches...")
        
        # Final summary
        self.stdout.write(self.style.SUCCESS(f"✅ Processing complete!"))
        self.stdout.write(f"   🎵 PlayLogs created: {playlogs_created:,}")
        self.stdout.write(f"   ❌ Failed plays: {failed_logs_created:,}")
        self.stdout.write(f"   💰 Transactions created: {transactions_created:,}")
        self.stdout.write(f"   ✔️ Matches processed: {processed_count:,}")
        
        # Send summary notifications
        self._send_processing_summary(playlogs_created, transactions_created)

    def _group_matches_into_plays(self, matches):
        """Group MatchCache entries into potential plays"""
        play_groups = defaultdict(list)
        
        for match in matches:
            # Group by track and station
            group_key = (match.track, match.station)
            play_groups[group_key].append(match)
        
        # Further group by time proximity (matches within 10 minutes = same play)
        refined_groups = defaultdict(list)
        
        for group_key, group_matches in play_groups.items():
            # Sort by timestamp
            group_matches.sort(key=lambda x: x.matched_at)
            
            current_play_matches = []
            play_counter = 0
            
            for i, match in enumerate(group_matches):
                if not current_play_matches:
                    current_play_matches = [match]
                else:
                    # Check if this match is within 10 minutes of the first match in current play
                    time_diff = (match.matched_at - current_play_matches[0].matched_at).total_seconds()
                    
                    if time_diff <= 600:  # 10 minutes
                        current_play_matches.append(match)
                    else:
                        # Start new play group
                        refined_key = (group_key[0], group_key[1], play_counter)
                        refined_groups[refined_key] = current_play_matches
                        play_counter += 1
                        current_play_matches = [match]
            
            # Don't forget the last group
            if current_play_matches:
                refined_key = (group_key[0], group_key[1], play_counter)
                refined_groups[refined_key] = current_play_matches
        
        # Convert back to simple format for processing
        final_groups = {}
        for (track, station, counter), matches in refined_groups.items():
            final_groups[(track, station)] = matches
        
        return final_groups

    def _validate_and_process_play(self, matches, track, station):
        """Validate if matches constitute a valid play"""
        if len(matches) < MIN_MATCHES_FOR_VALID_PLAY:
            return {
                'valid': False,
                'reason': f'Insufficient matches ({len(matches)} < {MIN_MATCHES_FOR_VALID_PLAY})',
                'matches': matches,
                'track': track,
                'station': station
            }
        
        # Calculate play duration and other metrics
        matches_sorted = sorted(matches, key=lambda x: x.matched_at)
        play_start = matches_sorted[0].matched_at
        play_end = matches_sorted[-1].matched_at
        duration_seconds = (play_end - play_start).total_seconds()
        
        if duration_seconds < MIN_PLAY_DURATION:
            return {
                'valid': False,
                'reason': f'Play too short ({duration_seconds}s < {MIN_PLAY_DURATION}s)',
                'matches': matches,
                'track': track,
                'station': station,
                'duration': duration_seconds
            }
        
        # Calculate average confidence
        avg_confidence = sum(match.avg_confidence_score for match in matches) / len(matches)
        
        # Calculate royalty amount
        royalty_amount = self._calculate_royalty_amount(duration_seconds)
        
        return {
            'valid': True,
            'matches': matches,
            'track': track,
            'station': station,
            'play_start': play_start,
            'play_end': play_end,
            'duration': duration_seconds,
            'avg_confidence': avg_confidence,
            'royalty_amount': royalty_amount,
            'match_count': len(matches)
        }

    def _create_playlog_entry(self, play_result):
        return PlayLog(
            track=play_result['track'],
            station=play_result['station'],
            station_program=None,
            source='Radio',  # ADD THIS - required field
            played_at=play_result['play_start'],
            start_time=play_result['play_start'],  # ADD THIS
            stop_time=play_result['play_end'],     # ADD THIS  
            duration=timedelta(seconds=int(play_result['duration'])),  # FIX: use timedelta
            avg_confidence_score=play_result['avg_confidence'],
            royalty_amount=play_result['royalty_amount'],
            # Remove these fields - they don't exist in your PlayLog model:
            # duration_seconds=int(play_result['duration']),
            # match_count=play_result['match_count'],
            # payment_processed=False
        )

    def _create_failed_playlog_entry(self, play_result, matches):
        """Create a FailedPlayLog entry for invalid plays"""
        match = matches[0] if matches else None

        if match is None:
            self.stdout.write(self.style.WARNING("⚠️ No matches available to create FailedPlayLog. Skipping."))
            return None

        return FailedPlayLog(
            match=match,
            reason=play_result.get('reason', 'Unknown reason')
        )


    def _create_royalty_transaction(self, playlog, play_result):
        try:
            artist_account = BankAccount.objects.get(user=play_result['track'].artist.user)
            station_account = BankAccount.objects.get(user=play_result['station'].user)

            if station_account.balance >= play_result['royalty_amount']:
                return Transaction(
                    bank_account=artist_account,
                    transaction_type='Transfer',
                    amount=play_result['royalty_amount'],
                    description=f"Royalty for '{play_result['track'].title}' played on {play_result['station'].name}",
                    status='Requested',  # Start as requested, will be updated to Paid/Declined
                    requested_on=timezone.now()
                )
            else:
                return None

        except BankAccount.DoesNotExist:
            logger.warning(f"Bank account not found for transaction")
            return None
    

    def _calculate_royalty_amount(self, duration_seconds):
        """Calculate royalty amount based on play duration"""
        # Cap duration at reasonable maximum (e.g., 10 minutes)
        capped_duration = min(duration_seconds, 600)
        return Decimal(str(capped_duration)) * ROYALTY_RATE_PER_SECOND




    def _send_processing_summary(self, playlogs_created, transactions_created):
        """Send processing summary notifications"""
        if playlogs_created > 0:
            # Calculate total royalties paid
            total_royalties = Transaction.objects.filter(
                transaction_type='royalty_payment',
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            summary_message = (
                f"📊 Radio Monitoring Summary\n"
                f"🎵 Songs processed: {playlogs_created:,}\n"
                f"💰 Royalties paid: GHS {total_royalties:,.2f}\n"
                f"💳 Transactions: {transactions_created:,}"
            )
            
            # Send SMS to admin (you can customize this)
            try:
                if hasattr(settings, 'ADMIN_PHONE'):
                    send_sms(settings.ADMIN_PHONE, summary_message)
                logger.info(f"Processing summary: {summary_message}")
            except Exception as e:
                logger.error(f"Failed to send summary notification: {e}")

    def _get_processing_statistics(self):
        """Get current processing statistics for monitoring"""
        stats = {
            'total_plays': PlayLog.objects.count(),
            'total_failed_plays': FailedPlayLog.objects.count(),
            'unprocessed_matches': MatchCache.objects.filter(processed=False).count(),
            'total_royalties_paid': Transaction.objects.filter(
                transaction_type='royalty_payment'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'stations_with_activity': Station.objects.filter(
                matchcache__processed=True
            ).distinct().count(),
            'artists_with_plays': Track.objects.filter(
                playlog__isnull=False
            ).values('artist').distinct().count()
        }
        
        return stats

    def _cleanup_old_match_cache(self, days_to_keep=30):
        """Clean up old processed MatchCache entries to save space"""
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        old_matches = MatchCache.objects.filter(
            processed=True,
            matched_at__lt=cutoff_date
        )
        
        deleted_count = old_matches.count()
        if deleted_count > 0:
            old_matches.delete()
            self.stdout.write(f"🧹 Cleaned up {deleted_count:,} old MatchCache entries")
        
        return deleted_count


    def _handle_payment_failure(self, station, artist, amount, reason):
        """Handle payment failures with email/SMS notifications"""
        from django.core.mail import send_mail

        # Email to station
        try:
            send_mail(
                subject='Royalty Payment Failed',
                message=f'Payment of GHS {amount} to {artist.get_full_name()} failed. Reason: {reason}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[station.user.email],
            )

            # SMS to station (if phone number available)
            if hasattr(station.user, 'phone'):
                send_sms(station.user.phone, f'Royalty payment failed: GHS {amount}. {reason}')

        except Exception as e:
            logger.error(f"Failed to send payment failure notification: {e}")

    



    def _update_bank_balances_bulk(self, transactions):
        """
        Efficiently update bank account balances for royalty transactions
        Handles station-to-artist transfers with proper error handling and notifications
        """
        from django.core.mail import send_mail
        from django.conf import settings

        processed_count = 0
        failed_count = 0
        total_amount_transferred = Decimal('0.00')

        # Group transactions by station to minimize database queries
        station_transactions = defaultdict(list)

        for transaction in transactions:
            try:
                # Get the artist account (transaction.bank_account is the recipient)
                artist_account = transaction.bank_account

                # Find the corresponding station account
                # We need to get station info from the transaction description or context
                # Since transaction model doesn't directly link to station, we'll use a different approach

                # Get station from PlayLog context (you'll need to pass this info)
                # For now, let's extract it from the description
                station_name = self._extract_station_from_description(transaction.description)
                station = Station.objects.filter(name=station_name).first()

                if not station or not station.user:
                    logger.error(f"Could not find station for transaction: {transaction.description}")
                    failed_count += 1
                    continue

                station_account = BankAccount.objects.filter(user=station.user).first()

                if not station_account:
                    logger.error(f"No bank account found for station: {station.name}")
                    self._handle_payment_failure(
                        station, 
                        artist_account.user, 
                        transaction.amount, 
                        "Station bank account not found"
                    )
                    failed_count += 1
                    continue
                
                station_transactions[station_account.id].append({
                    'transaction': transaction,
                    'artist_account': artist_account,
                    'station': station,
                    'station_account': station_account
                })

            except Exception as e:
                logger.error(f"Error processing transaction {transaction}: {e}")
                failed_count += 1
                continue
            
        # Process transactions grouped by station
        for station_account_id, station_tx_list in station_transactions.items():
            try:
                # Get fresh station account balance
                station_account = BankAccount.objects.select_for_update().get(id=station_account_id)

                successful_transactions = []
                failed_transactions = []

                # Calculate total amount needed for this station
                total_needed = sum(tx['transaction'].amount for tx in station_tx_list)

                # Check if station has sufficient balance for all transactions
                if station_account.balance >= total_needed:
                    # Process all transactions for this station
                    for tx_info in station_tx_list:
                        try:
                            transaction = tx_info['transaction']
                            artist_account = tx_info['artist_account']
                            station = tx_info['station']

                            # Perform the transfer using your model's methods
                            if station_account.withdraw(
                                transaction.amount, 
                                f"Royalty payment to {artist_account.user.get_full_name()}"
                            ):
                                # Credit artist account
                                if artist_account.deposit(
                                    transaction.amount,
                                    f"Royalty from {station.name}"
                                ):
                                    successful_transactions.append(tx_info)
                                    total_amount_transferred += transaction.amount
                                    processed_count += 1

                                    # Update transaction status
                                    Transaction.objects.filter(id=transaction.id).update(
                                        status='Paid',
                                        paid_on=timezone.now(),
                                        date_processed=timezone.now()
                                    )

                                else:
                                    failed_transactions.append(tx_info)
                                    failed_count += 1
                                    # Reverse the withdrawal
                                    station_account.deposit(transaction.amount, "Reversal - failed artist credit")
                            else:
                                failed_transactions.append(tx_info)
                                failed_count += 1

                        except Exception as e:
                            logger.error(f"Error processing individual transaction: {e}")
                            failed_transactions.append(tx_info)
                            failed_count += 1

                else:
                    # Insufficient funds for all transactions
                    failed_transactions = station_tx_list
                    failed_count += len(station_tx_list)

                    # Notify station about insufficient funds
                    self._handle_insufficient_funds(
                        station_tx_list[0]['station'], 
                        total_needed, 
                        station_account.balance
                    )

                # Handle failed transactions
                for tx_info in failed_transactions:
                    self._handle_payment_failure(
                        tx_info['station'],
                        tx_info['artist_account'].user,
                        tx_info['transaction'].amount,
                        "Insufficient station funds or processing error"
                    )

                    # Update transaction status to declined
                    Transaction.objects.filter(id=tx_info['transaction'].id).update(
                        status='Declined',
                        declined_on=timezone.now(),
                        date_processed=timezone.now()
                    )

            except Exception as e:
                logger.error(f"Error processing station transactions for account {station_account_id}: {e}")
                failed_count += len(station_tx_list)

        # Log summary
        self.stdout.write(f"💰 Transfer Summary:")
        self.stdout.write(f"   ✅ Successful: {processed_count}")
        self.stdout.write(f"   ❌ Failed: {failed_count}")
        self.stdout.write(f"   💵 Total Transferred: GHS {total_amount_transferred:,.2f}")

        return {
            'processed': processed_count,
            'failed': failed_count,
            'total_amount': total_amount_transferred
        }

    def _extract_station_from_description(self, description):
        """Extract station name from transaction description"""
        try:
            # Example: "Royalty for 'Song Name' played on Station Name"
            if " played on " in description:
                return description.split(" played on ")[-1]
            return None
        except:
            return None

    def _handle_insufficient_funds(self, station, amount_needed, current_balance):
        """Handle insufficient funds notification"""
        try:
            subject = f"Insufficient Funds Alert - {station.name}"
            message = (
                f"Dear {station.user.get_full_name()},\n\n"
                f"Your station '{station.name}' has insufficient funds to process royalty payments.\n\n"
                f"Amount needed: GHS {amount_needed:,.2f}\n"
                f"Current balance: GHS {current_balance:,.2f}\n"
                f"Shortfall: GHS {(amount_needed - current_balance):,.2f}\n\n"
                f"Please top up your account to ensure timely royalty payments.\n\n"
                f"Best regards,\n"
                f"ZamIO Royalty System"
            )

            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@zamio.com'),
                recipient_list=[station.user.email],
                fail_silently=False
            )

            # Send SMS if phone available
            if hasattr(station.user, 'phone') and station.user.phone:
                sms_message = (
                    f"ZAMIO ALERT: Station {station.name} has insufficient funds "
                    f"(GHS {current_balance:,.2f}) for royalty payments "
                    f"(GHS {amount_needed:,.2f} needed). Please top up."
                )
                send_sms(station.user.phone, sms_message)

            logger.info(f"Sent insufficient funds notification to {station.name}")

        except Exception as e:
            logger.error(f"Failed to send insufficient funds notification to {station.name}: {e}")

    def _handle_payment_failure(self, station, artist, amount, reason):
        """Handle individual payment failures with notifications"""
        try:
            # Email to station
            station_subject = f"Royalty Payment Failed - {station.name}"
            station_message = (
                f"Dear {station.user.get_full_name()},\n\n"
                f"A royalty payment from your station '{station.name}' has failed.\n\n"
                f"Artist: {artist.get_full_name()}\n"
                f"Amount: GHS {amount:,.2f}\n"
                f"Reason: {reason}\n\n"
                f"Please ensure your account has sufficient funds and contact support if needed.\n\n"
                f"Best regards,\n"
                f"ZamIO Royalty System"
            )

            send_mail(
                subject=station_subject,
                message=station_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@zamio.com'),
                recipient_list=[station.user.email],
                fail_silently=False
            )

            # Email to artist
            artist_subject = f"Royalty Payment Delayed"
            artist_message = (
                f"Dear {artist.get_full_name()},\n\n"
                f"A royalty payment to your account has been delayed.\n\n"
                f"Station: {station.name}\n"
                f"Amount: GHS {amount:,.2f}\n"
                f"Reason: {reason}\n\n"
                f"We are working to resolve this issue. You will be notified once payment is processed.\n\n"
                f"Best regards,\n"
                f"ZamIO Royalty System"
            )

            send_mail(
                subject=artist_subject,
                message=artist_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@zamio.com'),
                recipient_list=[artist.email],
                fail_silently=False
            )

            # SMS notifications
            if hasattr(station.user, 'phone') and station.user.phone:
                station_sms = f"ZAMIO: Royalty payment failed. Amount: GHS {amount:,.2f}. Reason: {reason}"
                send_sms(station.user.phone, station_sms)

            if hasattr(artist, 'phone') and artist.phone:
                artist_sms = f"ZAMIO: Royalty payment delayed from {station.name}. Amount: GHS {amount:,.2f}"
                send_sms(artist.phone, artist_sms)

            logger.warning(f"Payment failure handled: {station.name} -> {artist.get_full_name()}, GHS {amount}")

        except Exception as e:
            logger.error(f"Failed to send payment failure notifications: {e}")


# Generate data for specific stations only
#python manage.py simulate_station_historical --station-ids ST-EFWQCCMLSM ST-YQJF15IYFG ST-OMWDOPLDMR --historical --months 3
# Generate data for max 4 random stations
#python manage.py simulate_station_historical --max-stations 4 --historical --months 2

# List available stations first
#python manage.py simulate_station_historical --list-stations

# Process only (no new data generation)
#python manage.py simulate_station_historical --process-only

#python manage.py simulate_station_historical --clear-existing




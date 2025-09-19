"""
Advanced Royalty Calculator for ZamIO Platform

This module implements sophisticated royalty calculation engine with:
- Multiple rate structures based on station class and time-of-day
- Contributor split resolution with publisher routing logic
- Currency conversion and international payment handling
- PRO integration for reciprocal agreements
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import (
    PartnerPRO, 
    ReciprocalAgreement, 
    RoyaltyCycle,
    RoyaltyLineItem,
    PartnerRemittance
)
from music_monitor.models import PlayLog, AudioDetection, RoyaltyDistribution
from artists.models import Track, Contributor, Artist
from stations.models import Station
from publishers.models import PublisherProfile

logger = logging.getLogger(__name__)


class StationClass(Enum):
    """Station classification for royalty rate calculation"""
    CLASS_A = "class_a"  # Major metropolitan stations
    CLASS_B = "class_b"  # Regional stations
    CLASS_C = "class_c"  # Local/community stations
    ONLINE = "online"    # Online-only stations
    COMMUNITY = "community"  # Community/non-profit stations


class TimeOfDayPeriod(Enum):
    """Time periods for rate multipliers"""
    PRIME_TIME = "prime_time"      # 6 AM - 10 AM, 4 PM - 8 PM
    REGULAR_TIME = "regular_time"  # 10 AM - 4 PM, 8 PM - 12 AM
    OFF_PEAK = "off_peak"         # 12 AM - 6 AM


@dataclass
class RoyaltyRate:
    """Royalty rate structure"""
    base_rate_per_second: Decimal
    station_class_multiplier: Decimal
    time_of_day_multiplier: Decimal
    currency: str = "GHS"
    effective_date: datetime = None


@dataclass
class ContributorSplit:
    """Contributor split information"""
    contributor: Contributor
    percentage: Decimal
    publisher: Optional[PublisherProfile]
    recipient_type: str  # 'artist', 'publisher', 'pro'
    routing_info: Dict[str, Any]


@dataclass
class RoyaltyCalculationResult:
    """Result of royalty calculation"""
    play_log: PlayLog
    total_gross_amount: Decimal
    distributions: List['RoyaltyDistributionResult']
    currency: str
    calculation_metadata: Dict[str, Any]
    pro_shares: Dict[str, Decimal]
    errors: List[str]


@dataclass
class RoyaltyDistributionResult:
    """Individual royalty distribution result"""
    recipient_id: int
    recipient_type: str
    gross_amount: Decimal
    net_amount: Decimal
    percentage_split: Decimal
    currency: str
    exchange_rate: Decimal
    pro_share: Decimal
    external_pro: Optional[PartnerPRO]
    routing_metadata: Dict[str, Any]


class CurrencyConverter:
    """Currency conversion service"""
    
    # Default exchange rates (in production, this would connect to a real API)
    DEFAULT_RATES = {
        'USD': Decimal('0.16'),  # 1 GHS = 0.16 USD
        'EUR': Decimal('0.15'),  # 1 GHS = 0.15 EUR
        'GBP': Decimal('0.13'),  # 1 GHS = 0.13 GBP
        'GHS': Decimal('1.00'),  # Base currency
    }
    
    @classmethod
    def convert(cls, amount: Decimal, from_currency: str, to_currency: str) -> Tuple[Decimal, Decimal]:
        """
        Convert amount from one currency to another
        Returns: (converted_amount, exchange_rate)
        """
        if from_currency == to_currency:
            return amount, Decimal('1.00')
        
        # Convert to GHS first if not already
        if from_currency != 'GHS':
            ghs_rate = cls.DEFAULT_RATES.get(from_currency, Decimal('1.00'))
            amount_in_ghs = amount / ghs_rate
        else:
            amount_in_ghs = amount
        
        # Convert from GHS to target currency
        if to_currency == 'GHS':
            return amount_in_ghs, Decimal('1.00')
        
        target_rate = cls.DEFAULT_RATES.get(to_currency, Decimal('1.00'))
        converted_amount = amount_in_ghs * target_rate
        
        return converted_amount.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP), target_rate


class RoyaltyCalculator:
    """
    Advanced royalty calculation engine with configurable rate structures
    """
    
    # Default rate structures
    DEFAULT_RATES = {
        StationClass.CLASS_A: {
            'base_rate_per_second': Decimal('0.015'),  # 1.5 cents per second
            'multipliers': {
                TimeOfDayPeriod.PRIME_TIME: Decimal('1.5'),
                TimeOfDayPeriod.REGULAR_TIME: Decimal('1.0'),
                TimeOfDayPeriod.OFF_PEAK: Decimal('0.7'),
            }
        },
        StationClass.CLASS_B: {
            'base_rate_per_second': Decimal('0.012'),  # 1.2 cents per second
            'multipliers': {
                TimeOfDayPeriod.PRIME_TIME: Decimal('1.3'),
                TimeOfDayPeriod.REGULAR_TIME: Decimal('1.0'),
                TimeOfDayPeriod.OFF_PEAK: Decimal('0.8'),
            }
        },
        StationClass.CLASS_C: {
            'base_rate_per_second': Decimal('0.008'),  # 0.8 cents per second
            'multipliers': {
                TimeOfDayPeriod.PRIME_TIME: Decimal('1.2'),
                TimeOfDayPeriod.REGULAR_TIME: Decimal('1.0'),
                TimeOfDayPeriod.OFF_PEAK: Decimal('0.9'),
            }
        },
        StationClass.ONLINE: {
            'base_rate_per_second': Decimal('0.010'),  # 1.0 cent per second
            'multipliers': {
                TimeOfDayPeriod.PRIME_TIME: Decimal('1.1'),
                TimeOfDayPeriod.REGULAR_TIME: Decimal('1.0'),
                TimeOfDayPeriod.OFF_PEAK: Decimal('0.9'),
            }
        },
        StationClass.COMMUNITY: {
            'base_rate_per_second': Decimal('0.005'),  # 0.5 cents per second
            'multipliers': {
                TimeOfDayPeriod.PRIME_TIME: Decimal('1.0'),
                TimeOfDayPeriod.REGULAR_TIME: Decimal('1.0'),
                TimeOfDayPeriod.OFF_PEAK: Decimal('1.0'),
            }
        }
    }
    
    def __init__(self, custom_rates: Optional[Dict] = None):
        """Initialize calculator with optional custom rates"""
        self.rates = custom_rates or self.DEFAULT_RATES
        self.currency_converter = CurrencyConverter()
    
    def get_station_class(self, station: Station) -> StationClass:
        """
        Determine station class based on station attributes
        In production, this would be a field on the Station model
        """
        # For now, use a simple heuristic based on station name/location
        # This should be replaced with actual station classification
        station_name = station.name.lower()
        
        if any(keyword in station_name for keyword in ['online', 'web', 'internet']):
            return StationClass.ONLINE
        elif any(keyword in station_name for keyword in ['community', 'local', 'campus']):
            return StationClass.COMMUNITY
        elif station.city and station.city.lower() in ['accra', 'kumasi', 'takoradi']:
            return StationClass.CLASS_A
        elif station.region:
            return StationClass.CLASS_B
        else:
            return StationClass.CLASS_C
    
    def get_time_of_day_period(self, played_at: datetime) -> TimeOfDayPeriod:
        """Determine time of day period for rate calculation"""
        hour = played_at.hour
        
        # Prime time: 6 AM - 10 AM, 4 PM - 8 PM
        if (6 <= hour < 10) or (16 <= hour < 20):
            return TimeOfDayPeriod.PRIME_TIME
        # Off-peak: 12 AM - 6 AM
        elif 0 <= hour < 6:
            return TimeOfDayPeriod.OFF_PEAK
        # Regular time: everything else
        else:
            return TimeOfDayPeriod.REGULAR_TIME
    
    def calculate_base_royalty(self, play_log: PlayLog) -> Tuple[Decimal, Dict[str, Any]]:
        """
        Calculate base royalty amount before splits
        Returns: (amount, calculation_metadata)
        """
        station_class = self.get_station_class(play_log.station)
        time_period = self.get_time_of_day_period(play_log.played_at)
        
        rate_config = self.rates[station_class]
        base_rate = rate_config['base_rate_per_second']
        time_multiplier = rate_config['multipliers'][time_period]
        
        # Calculate duration in seconds
        if play_log.duration:
            duration_seconds = Decimal(str(play_log.duration.total_seconds()))
        else:
            # Fallback to track duration or default
            duration_seconds = Decimal('180')  # 3 minutes default
            if play_log.track and play_log.track.duration:
                duration_seconds = Decimal(str(play_log.track.duration.total_seconds()))
        
        # Calculate gross amount
        gross_amount = base_rate * duration_seconds * time_multiplier
        gross_amount = gross_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        metadata = {
            'station_class': station_class.value,
            'time_period': time_period.value,
            'base_rate_per_second': str(base_rate),
            'time_multiplier': str(time_multiplier),
            'duration_seconds': str(duration_seconds),
            'calculation_timestamp': timezone.now().isoformat(),
        }
        
        return gross_amount, metadata
    
    def resolve_contributor_splits(self, track: Track) -> List[ContributorSplit]:
        """
        Resolve contributor splits with publisher routing logic
        """
        contributors = track.contributors.filter(active=True)
        splits = []
        
        for contributor in contributors:
            # Determine recipient and routing
            if contributor.publisher:
                # Route through publisher
                recipient_type = 'publisher'
                routing_info = {
                    'publisher_id': contributor.publisher.id,
                    'publisher_name': contributor.publisher.company_name,
                    'artist_id': contributor.user.id,
                    'routing_method': 'publisher'
                }
            elif hasattr(contributor.user, 'artists') and contributor.user.artists.exists():
                artist = contributor.user.artists.first()
                if not artist.self_published and artist.publisher:
                    # Artist has publisher relationship
                    recipient_type = 'publisher'
                    routing_info = {
                        'publisher_id': artist.publisher.id,
                        'publisher_name': artist.publisher.company_name,
                        'artist_id': contributor.user.id,
                        'routing_method': 'artist_publisher'
                    }
                else:
                    # Self-published artist
                    recipient_type = 'artist'
                    routing_info = {
                        'artist_id': contributor.user.id,
                        'routing_method': 'direct'
                    }
            else:
                # Direct to contributor
                recipient_type = 'artist'
                routing_info = {
                    'contributor_id': contributor.user.id,
                    'routing_method': 'direct'
                }
            
            splits.append(ContributorSplit(
                contributor=contributor,
                percentage=contributor.percent_split,
                publisher=contributor.publisher,
                recipient_type=recipient_type,
                routing_info=routing_info
            ))
        
        return splits
    
    def calculate_pro_shares(self, play_log: PlayLog, audio_detection: Optional[AudioDetection] = None) -> Dict[str, Decimal]:
        """
        Calculate PRO shares for reciprocal agreements
        """
        pro_shares = {}
        
        if audio_detection and audio_detection.pro_affiliation:
            # Check if this is a foreign PRO that requires reciprocal payment
            try:
                partner_pro = PartnerPRO.objects.get(
                    pro_code=audio_detection.pro_affiliation.upper(),
                    is_active=True
                )
                
                # Check for active reciprocal agreement
                agreement = ReciprocalAgreement.objects.filter(
                    partner=partner_pro,
                    status='Active',
                    effective_date__lte=play_log.played_at.date()
                ).first()
                
                if agreement:
                    # Calculate PRO share based on agreement
                    admin_fee_percent = agreement.admin_fee_percent or partner_pro.default_admin_fee_percent
                    pro_share_percent = Decimal('100') - admin_fee_percent
                    
                    pro_shares[partner_pro.pro_code] = {
                        'partner_pro': partner_pro,
                        'agreement': agreement,
                        'share_percentage': pro_share_percent,
                        'admin_fee_percentage': admin_fee_percent
                    }
                    
            except PartnerPRO.DoesNotExist:
                logger.warning(f"Unknown PRO affiliation: {audio_detection.pro_affiliation}")
        
        return pro_shares
    
    def calculate_royalties(self, play_log: PlayLog, audio_detection: Optional[AudioDetection] = None) -> RoyaltyCalculationResult:
        """
        Calculate comprehensive royalty distribution for a play log
        """
        errors = []
        
        try:
            # Calculate base royalty amount
            gross_amount, calculation_metadata = self.calculate_base_royalty(play_log)
            
            # Get track and validate
            if not play_log.track:
                errors.append("No track associated with play log")
                return RoyaltyCalculationResult(
                    play_log=play_log,
                    total_gross_amount=Decimal('0'),
                    distributions=[],
                    currency='GHS',
                    calculation_metadata=calculation_metadata,
                    pro_shares={},
                    errors=errors
                )
            
            # Validate contributor splits
            is_valid, total_splits = play_log.track.validate_contributor_splits()
            if not is_valid:
                errors.append(f"Invalid contributor splits: total {total_splits}%")
            
            # Resolve contributor splits
            contributor_splits = self.resolve_contributor_splits(play_log.track)
            
            # Calculate PRO shares
            pro_shares = self.calculate_pro_shares(play_log, audio_detection)
            
            # Calculate individual distributions
            distributions = []
            
            for split in contributor_splits:
                # Calculate split amount
                split_amount = gross_amount * (split.percentage / Decimal('100'))
                split_amount = split_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
                # Determine currency and conversion
                target_currency = 'GHS'  # Default currency
                exchange_rate = Decimal('1.00')
                
                # Check if international payment is required
                external_pro = None
                pro_share = Decimal('0')
                
                if pro_shares and split.recipient_type != 'publisher':
                    # This might be subject to PRO routing
                    for pro_code, pro_info in pro_shares.items():
                        pro_share = split_amount * (pro_info['share_percentage'] / Decimal('100'))
                        external_pro = pro_info['partner_pro']
                        split_amount = split_amount - pro_share
                        break
                
                # Create distribution result
                distribution = RoyaltyDistributionResult(
                    recipient_id=split.contributor.user.id,
                    recipient_type=split.recipient_type,
                    gross_amount=split_amount + pro_share,
                    net_amount=split_amount,
                    percentage_split=split.percentage,
                    currency=target_currency,
                    exchange_rate=exchange_rate,
                    pro_share=pro_share,
                    external_pro=external_pro,
                    routing_metadata=split.routing_info
                )
                
                distributions.append(distribution)
            
            return RoyaltyCalculationResult(
                play_log=play_log,
                total_gross_amount=gross_amount,
                distributions=distributions,
                currency='GHS',
                calculation_metadata=calculation_metadata,
                pro_shares=pro_shares,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Error calculating royalties for play log {play_log.id}: {str(e)}")
            errors.append(f"Calculation error: {str(e)}")
            
            return RoyaltyCalculationResult(
                play_log=play_log,
                total_gross_amount=Decimal('0'),
                distributions=[],
                currency='GHS',
                calculation_metadata={'error': str(e)},
                pro_shares={},
                errors=errors
            )
    
    @transaction.atomic
    def create_royalty_distributions(self, calculation_result: RoyaltyCalculationResult) -> List[RoyaltyDistribution]:
        """
        Create RoyaltyDistribution records from calculation result
        """
        distributions = []
        
        for dist_result in calculation_result.distributions:
            try:
                # Get recipient user
                from django.contrib.auth import get_user_model
                User = get_user_model()
                recipient = User.objects.get(id=dist_result.recipient_id)
                
                # Create distribution record
                distribution = RoyaltyDistribution.objects.create(
                    play_log=calculation_result.play_log,
                    audio_detection=getattr(calculation_result, 'audio_detection', None),
                    recipient=recipient,
                    recipient_type=dist_result.recipient_type,
                    gross_amount=dist_result.gross_amount,
                    net_amount=dist_result.net_amount,
                    currency=dist_result.currency,
                    exchange_rate=dist_result.exchange_rate,
                    percentage_split=dist_result.percentage_split,
                    pro_share=dist_result.pro_share,
                    external_pro=dist_result.external_pro,
                    calculation_metadata=dist_result.routing_metadata,
                    status='calculated'
                )
                
                distributions.append(distribution)
                
            except Exception as e:
                logger.error(f"Error creating distribution record: {str(e)}")
                continue
        
        return distributions
    
    def batch_calculate_royalties(self, play_logs: List[PlayLog]) -> List[RoyaltyCalculationResult]:
        """
        Calculate royalties for multiple play logs efficiently
        """
        results = []
        
        for play_log in play_logs:
            # Get associated audio detection if available
            audio_detection = None
            if hasattr(play_log, 'audio_detections'):
                audio_detection = play_log.audio_detections.first()
            
            result = self.calculate_royalties(play_log, audio_detection)
            results.append(result)
        
        return results


class RoyaltyCycleManager:
    """
    Manager for royalty cycle operations and audit trails
    """
    
    def __init__(self, calculator: Optional[RoyaltyCalculator] = None):
        self.calculator = calculator or RoyaltyCalculator()
    
    @transaction.atomic
    def process_royalty_cycle(self, cycle: RoyaltyCycle) -> Dict[str, Any]:
        """
        Process a complete royalty cycle with audit trails
        """
        logger.info(f"Processing royalty cycle: {cycle.name}")
        
        # Get play logs for the cycle period
        play_logs = PlayLog.objects.filter(
            played_at__date__gte=cycle.period_start,
            played_at__date__lte=cycle.period_end,
            track__isnull=False
        ).select_related('track', 'station')
        
        # Calculate royalties for all play logs
        calculation_results = self.calculator.batch_calculate_royalties(list(play_logs))
        
        # Create distribution records
        total_distributions = 0
        total_amount = Decimal('0')
        errors = []
        
        for result in calculation_results:
            if result.errors:
                errors.extend(result.errors)
                continue
            
            distributions = self.calculator.create_royalty_distributions(result)
            total_distributions += len(distributions)
            total_amount += result.total_gross_amount
        
        # Update cycle status
        cycle.status = 'Locked'
        cycle.save()
        
        return {
            'cycle_id': cycle.id,
            'play_logs_processed': len(play_logs),
            'distributions_created': total_distributions,
            'total_amount': str(total_amount),
            'currency': 'GHS',
            'errors': errors,
            'processed_at': timezone.now().isoformat()
        }
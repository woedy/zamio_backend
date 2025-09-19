"""
Management command for setting up default royalty rate structures

Usage:
    python manage.py setup_royalty_rates
    python manage.py setup_royalty_rates --update-existing
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from royalties.models import RoyaltyRateStructure, CurrencyExchangeRate


class Command(BaseCommand):
    help = 'Set up default royalty rate structures and exchange rates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing rate structures'
        )
        
        parser.add_argument(
            '--territory',
            type=str,
            default='GH',
            help='Territory code for rate structures (default: GH)'
        )

    def handle(self, *args, **options):
        territory = options['territory']
        update_existing = options['update_existing']
        
        self.stdout.write(f'Setting up royalty rates for territory: {territory}')
        
        # Default rate structures
        rate_structures = [
            # Class A - Major Metropolitan Stations
            {
                'name': 'Class A Prime Time',
                'station_class': 'class_a',
                'time_period': 'prime_time',
                'base_rate_per_second': Decimal('0.015'),
                'multiplier': Decimal('1.5'),
            },
            {
                'name': 'Class A Regular Time',
                'station_class': 'class_a',
                'time_period': 'regular_time',
                'base_rate_per_second': Decimal('0.015'),
                'multiplier': Decimal('1.0'),
            },
            {
                'name': 'Class A Off Peak',
                'station_class': 'class_a',
                'time_period': 'off_peak',
                'base_rate_per_second': Decimal('0.015'),
                'multiplier': Decimal('0.7'),
            },
            
            # Class B - Regional Stations
            {
                'name': 'Class B Prime Time',
                'station_class': 'class_b',
                'time_period': 'prime_time',
                'base_rate_per_second': Decimal('0.012'),
                'multiplier': Decimal('1.3'),
            },
            {
                'name': 'Class B Regular Time',
                'station_class': 'class_b',
                'time_period': 'regular_time',
                'base_rate_per_second': Decimal('0.012'),
                'multiplier': Decimal('1.0'),
            },
            {
                'name': 'Class B Off Peak',
                'station_class': 'class_b',
                'time_period': 'off_peak',
                'base_rate_per_second': Decimal('0.012'),
                'multiplier': Decimal('0.8'),
            },
            
            # Class C - Local/Community Stations
            {
                'name': 'Class C Prime Time',
                'station_class': 'class_c',
                'time_period': 'prime_time',
                'base_rate_per_second': Decimal('0.008'),
                'multiplier': Decimal('1.2'),
            },
            {
                'name': 'Class C Regular Time',
                'station_class': 'class_c',
                'time_period': 'regular_time',
                'base_rate_per_second': Decimal('0.008'),
                'multiplier': Decimal('1.0'),
            },
            {
                'name': 'Class C Off Peak',
                'station_class': 'class_c',
                'time_period': 'off_peak',
                'base_rate_per_second': Decimal('0.008'),
                'multiplier': Decimal('0.9'),
            },
            
            # Online Stations
            {
                'name': 'Online Prime Time',
                'station_class': 'online',
                'time_period': 'prime_time',
                'base_rate_per_second': Decimal('0.010'),
                'multiplier': Decimal('1.1'),
            },
            {
                'name': 'Online Regular Time',
                'station_class': 'online',
                'time_period': 'regular_time',
                'base_rate_per_second': Decimal('0.010'),
                'multiplier': Decimal('1.0'),
            },
            {
                'name': 'Online Off Peak',
                'station_class': 'online',
                'time_period': 'off_peak',
                'base_rate_per_second': Decimal('0.010'),
                'multiplier': Decimal('0.9'),
            },
            
            # Community Stations
            {
                'name': 'Community All Times',
                'station_class': 'community',
                'time_period': 'prime_time',
                'base_rate_per_second': Decimal('0.005'),
                'multiplier': Decimal('1.0'),
            },
            {
                'name': 'Community All Times',
                'station_class': 'community',
                'time_period': 'regular_time',
                'base_rate_per_second': Decimal('0.005'),
                'multiplier': Decimal('1.0'),
            },
            {
                'name': 'Community All Times',
                'station_class': 'community',
                'time_period': 'off_peak',
                'base_rate_per_second': Decimal('0.005'),
                'multiplier': Decimal('1.0'),
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for rate_data in rate_structures:
            rate_data['territory'] = territory
            rate_data['currency'] = 'GHS'
            rate_data['effective_date'] = timezone.now().date()
            
            # Check if rate structure already exists
            existing = RoyaltyRateStructure.objects.filter(
                station_class=rate_data['station_class'],
                time_period=rate_data['time_period'],
                territory=territory,
                is_active=True
            ).first()
            
            if existing:
                if update_existing:
                    for key, value in rate_data.items():
                        if key not in ['station_class', 'time_period', 'territory']:
                            setattr(existing, key, value)
                    existing.save()
                    updated_count += 1
                    self.stdout.write(f'Updated: {existing}')
                else:
                    self.stdout.write(f'Exists: {existing}')
            else:
                rate_structure = RoyaltyRateStructure.objects.create(**rate_data)
                created_count += 1
                self.stdout.write(f'Created: {rate_structure}')
        
        # Set up default exchange rates
        exchange_rates = [
            {'from_currency': 'GHS', 'to_currency': 'USD', 'rate': Decimal('0.16')},
            {'from_currency': 'GHS', 'to_currency': 'EUR', 'rate': Decimal('0.15')},
            {'from_currency': 'GHS', 'to_currency': 'GBP', 'rate': Decimal('0.13')},
            {'from_currency': 'USD', 'to_currency': 'GHS', 'rate': Decimal('6.25')},
            {'from_currency': 'EUR', 'to_currency': 'GHS', 'rate': Decimal('6.67')},
            {'from_currency': 'GBP', 'to_currency': 'GHS', 'rate': Decimal('7.69')},
        ]
        
        exchange_created = 0
        exchange_updated = 0
        
        for rate_data in exchange_rates:
            rate_data['effective_date'] = timezone.now()
            rate_data['source'] = 'setup_command'
            
            existing_rate = CurrencyExchangeRate.objects.filter(
                from_currency=rate_data['from_currency'],
                to_currency=rate_data['to_currency'],
                is_active=True
            ).first()
            
            if existing_rate:
                if update_existing:
                    existing_rate.rate = rate_data['rate']
                    existing_rate.effective_date = rate_data['effective_date']
                    existing_rate.save()
                    exchange_updated += 1
                    self.stdout.write(f'Updated exchange rate: {existing_rate}')
            else:
                exchange_rate = CurrencyExchangeRate.objects.create(**rate_data)
                exchange_created += 1
                self.stdout.write(f'Created exchange rate: {exchange_rate}')
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary:\n'
                f'Rate structures - Created: {created_count}, Updated: {updated_count}\n'
                f'Exchange rates - Created: {exchange_created}, Updated: {exchange_updated}'
            )
        )
        
        if not update_existing and (created_count == 0 or exchange_created == 0):
            self.stdout.write(
                self.style.WARNING(
                    'Some items already exist. Use --update-existing to update them.'
                )
            )
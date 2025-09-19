"""
Management command for calculating royalties

Usage:
    python manage.py calculate_royalties --cycle-id 1
    python manage.py calculate_royalties --date-range 2024-01-01 2024-01-31
    python manage.py calculate_royalties --play-log-ids 1,2,3,4,5
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal

from royalties.calculator import RoyaltyCalculator, RoyaltyCycleManager
from royalties.models import RoyaltyCycle, RoyaltyCalculationAudit
from music_monitor.models import PlayLog


class Command(BaseCommand):
    help = 'Calculate royalties for play logs, cycles, or date ranges'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cycle-id',
            type=int,
            help='Calculate royalties for specific royalty cycle'
        )
        
        parser.add_argument(
            '--date-range',
            nargs=2,
            metavar=('START_DATE', 'END_DATE'),
            help='Calculate royalties for date range (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--play-log-ids',
            type=str,
            help='Comma-separated list of play log IDs to calculate'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform calculation without saving results'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation even if already calculated'
        )

    def handle(self, *args, **options):
        calculator = RoyaltyCalculator()
        
        if options['cycle_id']:
            self.calculate_cycle_royalties(calculator, options['cycle_id'], options)
        elif options['date_range']:
            self.calculate_date_range_royalties(calculator, options['date_range'], options)
        elif options['play_log_ids']:
            self.calculate_specific_play_logs(calculator, options['play_log_ids'], options)
        else:
            raise CommandError('Must specify --cycle-id, --date-range, or --play-log-ids')

    def calculate_cycle_royalties(self, calculator, cycle_id, options):
        """Calculate royalties for a specific royalty cycle"""
        try:
            cycle = RoyaltyCycle.objects.get(id=cycle_id)
        except RoyaltyCycle.DoesNotExist:
            raise CommandError(f'Royalty cycle {cycle_id} does not exist')
        
        if cycle.status == 'Locked' and not options['force']:
            raise CommandError(f'Cycle {cycle_id} is already locked. Use --force to recalculate')
        
        self.stdout.write(f'Calculating royalties for cycle: {cycle.name}')
        self.stdout.write(f'Period: {cycle.period_start} to {cycle.period_end}')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))
        
        cycle_manager = RoyaltyCycleManager(calculator)
        
        if not options['dry_run']:
            result = cycle_manager.process_royalty_cycle(cycle)
            
            # Create audit record
            RoyaltyCalculationAudit.objects.create(
                calculation_type='cycle',
                royalty_cycle=cycle,
                total_amount=Decimal(result['total_amount']),
                currency=result['currency'],
                distributions_count=result['distributions_created'],
                calculation_metadata=result,
                calculated_by=None  # System calculation
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully processed {result["play_logs_processed"]} play logs, '
                    f'created {result["distributions_created"]} distributions, '
                    f'total amount: {result["total_amount"]} {result["currency"]}'
                )
            )
            
            if result['errors']:
                self.stdout.write(self.style.WARNING(f'Errors encountered: {len(result["errors"])}'))
                for error in result['errors'][:10]:  # Show first 10 errors
                    self.stdout.write(f'  - {error}')
        else:
            # Dry run - just count what would be processed
            play_logs = PlayLog.objects.filter(
                played_at__date__gte=cycle.period_start,
                played_at__date__lte=cycle.period_end,
                track__isnull=False
            )
            self.stdout.write(f'Would process {play_logs.count()} play logs')

    def calculate_date_range_royalties(self, calculator, date_range, options):
        """Calculate royalties for a date range"""
        try:
            start_date = datetime.strptime(date_range[0], '%Y-%m-%d').date()
            end_date = datetime.strptime(date_range[1], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError('Invalid date format. Use YYYY-MM-DD')
        
        self.stdout.write(f'Calculating royalties for date range: {start_date} to {end_date}')
        
        play_logs = PlayLog.objects.filter(
            played_at__date__gte=start_date,
            played_at__date__lte=end_date,
            track__isnull=False
        ).select_related('track', 'station')
        
        if not play_logs.exists():
            self.stdout.write(self.style.WARNING('No play logs found for the specified date range'))
            return
        
        self.stdout.write(f'Found {play_logs.count()} play logs to process')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))
            return
        
        # Calculate royalties
        results = calculator.batch_calculate_royalties(list(play_logs))
        
        total_distributions = 0
        total_amount = Decimal('0')
        errors = []
        
        for result in results:
            if result.errors:
                errors.extend(result.errors)
                continue
            
            distributions = calculator.create_royalty_distributions(result)
            total_distributions += len(distributions)
            total_amount += result.total_gross_amount
        
        # Create audit record
        RoyaltyCalculationAudit.objects.create(
            calculation_type='batch',
            total_amount=total_amount,
            currency='GHS',
            distributions_count=total_distributions,
            calculation_metadata={
                'date_range': [str(start_date), str(end_date)],
                'play_logs_processed': len(results),
                'errors_count': len(errors)
            },
            errors=errors[:100],  # Store first 100 errors
            calculated_by=None
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed {len(results)} play logs, '
                f'created {total_distributions} distributions, '
                f'total amount: {total_amount} GHS'
            )
        )
        
        if errors:
            self.stdout.write(self.style.WARNING(f'Errors encountered: {len(errors)}'))

    def calculate_specific_play_logs(self, calculator, play_log_ids_str, options):
        """Calculate royalties for specific play log IDs"""
        try:
            play_log_ids = [int(id.strip()) for id in play_log_ids_str.split(',')]
        except ValueError:
            raise CommandError('Invalid play log IDs format. Use comma-separated integers')
        
        play_logs = PlayLog.objects.filter(
            id__in=play_log_ids,
            track__isnull=False
        ).select_related('track', 'station')
        
        found_ids = list(play_logs.values_list('id', flat=True))
        missing_ids = set(play_log_ids) - set(found_ids)
        
        if missing_ids:
            self.stdout.write(
                self.style.WARNING(f'Play logs not found: {sorted(missing_ids)}')
            )
        
        if not play_logs.exists():
            self.stdout.write(self.style.WARNING('No valid play logs found'))
            return
        
        self.stdout.write(f'Calculating royalties for {play_logs.count()} play logs')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))
            return
        
        # Calculate royalties
        results = calculator.batch_calculate_royalties(list(play_logs))
        
        total_distributions = 0
        total_amount = Decimal('0')
        
        for i, result in enumerate(results):
            play_log = result.play_log
            
            if result.errors:
                self.stdout.write(
                    self.style.ERROR(f'Play log {play_log.id}: {", ".join(result.errors)}')
                )
                continue
            
            distributions = calculator.create_royalty_distributions(result)
            total_distributions += len(distributions)
            total_amount += result.total_gross_amount
            
            self.stdout.write(
                f'Play log {play_log.id}: {result.total_gross_amount} GHS, '
                f'{len(distributions)} distributions'
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Total: {total_amount} GHS across {total_distributions} distributions'
            )
        )
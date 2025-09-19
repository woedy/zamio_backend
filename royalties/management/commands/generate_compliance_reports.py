"""
Management command for generating compliance reports for regulatory bodies

Usage:
    python manage.py generate_compliance_reports --cycle-id 1 --pro ASCAP
    python manage.py generate_compliance_reports --cycle-id 1 --all-pros
    python manage.py generate_compliance_reports --date-range 2024-01-01 2024-03-31 --pro BMI
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime

from royalties.pro_integration import ComplianceReporter, PROReportGenerator
from royalties.models import RoyaltyCycle, PartnerPRO, UsageAttribution


class Command(BaseCommand):
    help = 'Generate compliance reports for regulatory bodies (ASCAP, BMI, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cycle-id',
            type=int,
            help='Generate reports for specific royalty cycle'
        )
        
        parser.add_argument(
            '--date-range',
            nargs=2,
            metavar=('START_DATE', 'END_DATE'),
            help='Generate reports for date range (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--pro',
            type=str,
            help='Generate report for specific PRO (ASCAP, BMI, GHAMRO, etc.)'
        )
        
        parser.add_argument(
            '--all-pros',
            action='store_true',
            help='Generate reports for all active PROs'
        )
        
        parser.add_argument(
            '--format',
            type=str,
            choices=['CSV', 'CWR', 'DDEX-DSR', 'JSON'],
            default='CSV',
            help='Report format (default: CSV)'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Custom output directory for reports'
        )

    def handle(self, *args, **options):
        reporter = ComplianceReporter()
        
        # Determine reporting period
        if options['cycle_id']:
            try:
                cycle = RoyaltyCycle.objects.get(id=options['cycle_id'])
                period_start = cycle.period_start
                period_end = cycle.period_end
                period_name = cycle.name
            except RoyaltyCycle.DoesNotExist:
                raise CommandError(f'Royalty cycle {options["cycle_id"]} does not exist')
        elif options['date_range']:
            try:
                period_start = datetime.strptime(options['date_range'][0], '%Y-%m-%d').date()
                period_end = datetime.strptime(options['date_range'][1], '%Y-%m-%d').date()
                period_name = f"{period_start}_to_{period_end}"
                cycle = None
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')
        else:
            raise CommandError('Must specify --cycle-id or --date-range')
        
        self.stdout.write(f'Generating compliance reports for period: {period_start} to {period_end}')
        
        # Determine which PROs to process
        if options['pro']:
            pros_to_process = [options['pro'].upper()]
        elif options['all_pros']:
            pros_to_process = list(PartnerPRO.objects.filter(is_active=True).values_list('pro_code', flat=True))
        else:
            raise CommandError('Must specify --pro or --all-pros')
        
        self.stdout.write(f'Processing PROs: {", ".join(pros_to_process)}')
        
        # Generate reports
        reports_generated = []
        errors = []
        
        for pro_code in pros_to_process:
            try:
                report_path = self.generate_pro_report(
                    reporter, pro_code, period_start, period_end, period_name, 
                    options['format'], cycle, options.get('output_dir')
                )
                
                if report_path:
                    reports_generated.append((pro_code, report_path))
                    self.stdout.write(
                        self.style.SUCCESS(f'Generated {pro_code} report: {report_path}')
                    )
                else:
                    errors.append(f'{pro_code}: No data found for reporting period')
                    self.stdout.write(
                        self.style.WARNING(f'No data found for {pro_code} in reporting period')
                    )
                    
            except Exception as e:
                error_msg = f'{pro_code}: {str(e)}'
                errors.append(error_msg)
                self.stdout.write(
                    self.style.ERROR(f'Error generating {pro_code} report: {str(e)}')
                )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary:\n'
                f'Reports generated: {len(reports_generated)}\n'
                f'Errors: {len(errors)}'
            )
        )
        
        if reports_generated:
            self.stdout.write('\nGenerated reports:')
            for pro_code, path in reports_generated:
                self.stdout.write(f'  {pro_code}: {path}')
        
        if errors:
            self.stdout.write('\nErrors:')
            for error in errors:
                self.stdout.write(f'  {error}')

    def generate_pro_report(self, reporter, pro_code, period_start, period_end, period_name, format_type, cycle=None, output_dir=None):
        """Generate compliance report for specific PRO"""
        
        # Get partner PRO
        try:
            partner_pro = PartnerPRO.objects.get(pro_code=pro_code, is_active=True)
        except PartnerPRO.DoesNotExist:
            raise ValueError(f'Partner PRO {pro_code} not found or inactive')
        
        # Get usage attributions for this PRO in the period
        attributions = UsageAttribution.objects.filter(
            origin_partner=partner_pro,
            played_at__date__gte=period_start,
            played_at__date__lte=period_end
        ).select_related('play_log', 'external_recording', 'external_work', 'play_log__station')
        
        if not attributions.exists():
            return None
        
        self.stdout.write(f'Found {attributions.count()} usage attributions for {pro_code}')
        
        # Prepare usage data
        usage_data = []
        total_amount = 0
        
        for attr in attributions:
            play_log = attr.play_log
            recording = attr.external_recording
            work = attr.external_work
            
            # Calculate amounts (simplified - in production this would use the royalty calculator)
            gross_amount = float(play_log.royalty_amount) if play_log and play_log.royalty_amount else 0
            admin_fee = gross_amount * 0.15  # 15% admin fee
            net_amount = gross_amount - admin_fee
            
            total_amount += net_amount
            
            usage_data.append({
                'station_id': play_log.station.id if play_log and play_log.station else None,
                'station_name': play_log.station.name if play_log and play_log.station else None,
                'played_at_utc': play_log.played_at.isoformat() if play_log and play_log.played_at else None,
                'isrc': recording.isrc if recording else None,
                'iswc': work.iswc if work else None,
                'work_title': work.title if work else None,
                'recording_title': recording.title if recording else None,
                'artist_name': self._extract_artist_name(recording, work),
                'duration_seconds': attr.duration_seconds,
                'confidence_score': str(attr.confidence_score),
                'detection_source': attr.match_method,
                'pro_affiliation': pro_code,
                'gross_amount': str(gross_amount),
                'admin_fee_amount': str(admin_fee),
                'net_amount': str(net_amount)
            })
        
        # Create report data structure
        from royalties.pro_integration import PROReportData
        from decimal import Decimal
        
        report_data = PROReportData(
            partner_pro=partner_pro,
            royalty_cycle=cycle,
            usage_data=usage_data,
            total_amount=Decimal(str(total_amount)),
            currency='GHS',
            report_period_start=period_start,
            report_period_end=period_end,
            metadata={
                'compliance_report': True,
                'generated_at': timezone.now().isoformat(),
                'period_name': period_name,
                'format': format_type,
                'usage_count': len(usage_data)
            }
        )
        
        # Generate report using appropriate format
        generator = PROReportGenerator()
        
        # Override output directory if specified
        if output_dir:
            generator.export_dir = output_dir
        
        if format_type == 'CSV':
            return generator.generate_csv_report(report_data)
        elif format_type == 'CWR':
            return generator.generate_cwr_report(report_data)
        elif format_type == 'DDEX-DSR':
            return generator.generate_ddex_dsr_report(report_data)
        elif format_type == 'JSON':
            return generator.generate_json_report(report_data)
        else:
            raise ValueError(f'Unsupported format: {format_type}')

    def _extract_artist_name(self, recording, work):
        """Extract artist name from recording or work metadata"""
        if recording and recording.recording_metadata:
            artist = recording.recording_metadata.get('artist_name')
            if artist:
                return artist
        
        if work and work.work_metadata:
            artist = work.work_metadata.get('artist_name')
            if artist:
                return artist
        
        return None
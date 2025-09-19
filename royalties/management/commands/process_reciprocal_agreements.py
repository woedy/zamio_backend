"""
Management command for processing reciprocal agreements

Usage:
    python manage.py process_reciprocal_agreements --cycle-id 1
    python manage.py process_reciprocal_agreements --partner-pro ASCAP --cycle-id 1
    python manage.py process_reciprocal_agreements --generate-reports-only
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from decimal import Decimal

from royalties.pro_integration import ReciprocalAgreementProcessor, ComplianceReporter
from royalties.models import RoyaltyCycle, PartnerPRO, ReciprocalAgreement


class Command(BaseCommand):
    help = 'Process reciprocal agreements and generate PRO reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cycle-id',
            type=int,
            help='Process specific royalty cycle'
        )
        
        parser.add_argument(
            '--partner-pro',
            type=str,
            help='Process specific partner PRO (e.g., ASCAP, BMI)'
        )
        
        parser.add_argument(
            '--generate-reports-only',
            action='store_true',
            help='Only generate reports without creating new remittances'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform calculation without saving results'
        )
        
        parser.add_argument(
            '--format',
            type=str,
            choices=['CSV', 'CWR', 'DDEX-DSR', 'JSON'],
            help='Override report format for generation'
        )

    def handle(self, *args, **options):
        processor = ReciprocalAgreementProcessor()
        
        if options['cycle_id']:
            self.process_cycle(processor, options['cycle_id'], options)
        elif options['generate_reports_only']:
            self.generate_reports_only(processor, options)
        else:
            raise CommandError('Must specify --cycle-id or --generate-reports-only')

    def process_cycle(self, processor, cycle_id, options):
        """Process reciprocal agreements for a specific cycle"""
        try:
            cycle = RoyaltyCycle.objects.get(id=cycle_id)
        except RoyaltyCycle.DoesNotExist:
            raise CommandError(f'Royalty cycle {cycle_id} does not exist')
        
        if cycle.status != 'Locked':
            raise CommandError(f'Cycle {cycle_id} must be locked before processing reciprocal agreements')
        
        self.stdout.write(f'Processing reciprocal agreements for cycle: {cycle.name}')
        self.stdout.write(f'Period: {cycle.period_start} to {cycle.period_end}')
        
        if options['partner_pro']:
            self.process_specific_partner(processor, cycle, options['partner_pro'], options)
        else:
            self.process_all_partners(processor, cycle, options)

    def process_specific_partner(self, processor, cycle, pro_code, options):
        """Process reciprocal agreement for specific partner"""
        try:
            partner = PartnerPRO.objects.get(pro_code=pro_code.upper(), is_active=True)
        except PartnerPRO.DoesNotExist:
            raise CommandError(f'Partner PRO {pro_code} not found or inactive')
        
        # Check for active agreement
        agreement = ReciprocalAgreement.objects.filter(
            partner=partner,
            status='Active',
            effective_date__lte=cycle.period_end
        ).first()
        
        if not agreement:
            raise CommandError(f'No active reciprocal agreement found for {pro_code}')
        
        self.stdout.write(f'Processing agreement with {partner.display_name} ({pro_code})')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))
            
            # Calculate payment without saving
            payment = processor._calculate_partner_payment(agreement, cycle)
            if payment:
                self.stdout.write(
                    f'Would create remittance: {payment.net_payable} {payment.currency} '
                    f'({payment.usage_count} usages, {payment.works_count} works)'
                )
            else:
                self.stdout.write('No usage found for this partner in the cycle period')
            return
        
        # Process single partner
        payments = [processor._calculate_partner_payment(agreement, cycle)]
        payments = [p for p in payments if p and p.net_payable > 0]
        
        if not payments:
            self.stdout.write(self.style.WARNING(f'No usage found for {pro_code} in cycle period'))
            return
        
        # Create remittance and generate report
        payment = payments[0]
        
        from royalties.models import PartnerRemittance, PartnerReportExport
        
        remittance = PartnerRemittance.objects.create(
            partner=payment.partner_pro,
            royalty_cycle=cycle,
            currency=payment.currency,
            gross_amount=payment.gross_amount,
            admin_fee_amount=payment.admin_fee,
            net_payable=payment.net_payable,
            status='Pending',
            notes=f"Reciprocal agreement payment - {payment.usage_count} usages, {payment.works_count} works"
        )
        
        # Generate report
        report_data = processor._prepare_report_data(payment, cycle)
        
        # Override format if specified
        if options['format']:
            report_data.partner_pro.reporting_standard = options['format']
        
        report_path = processor._generate_partner_report(report_data)
        
        if report_path:
            export_record = PartnerReportExport.objects.create(
                partner=payment.partner_pro,
                royalty_cycle=cycle,
                format=report_data.partner_pro.reporting_standard,
                file=report_path,
                checksum=processor._calculate_file_checksum(report_path)
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully processed {pro_code}:\n'
                    f'  Remittance: {payment.net_payable} {payment.currency}\n'
                    f'  Report: {report_path}\n'
                    f'  Usages: {payment.usage_count}\n'
                    f'  Works: {payment.works_count}'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'Failed to generate report for {pro_code}')
            )

    def process_all_partners(self, processor, cycle, options):
        """Process reciprocal agreements for all active partners"""
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))
            
            # Get all active agreements
            agreements = ReciprocalAgreement.objects.filter(
                status='Active',
                effective_date__lte=cycle.period_end
            ).select_related('partner')
            
            self.stdout.write(f'Found {agreements.count()} active reciprocal agreements')
            
            total_payable = Decimal('0')
            for agreement in agreements:
                payment = processor._calculate_partner_payment(agreement, cycle)
                if payment and payment.net_payable > 0:
                    self.stdout.write(
                        f'  {agreement.partner.pro_code}: {payment.net_payable} {payment.currency} '
                        f'({payment.usage_count} usages)'
                    )
                    total_payable += payment.net_payable
                else:
                    self.stdout.write(f'  {agreement.partner.pro_code}: No usage found')
            
            self.stdout.write(f'Total payable: {total_payable} GHS')
            return
        
        # Process all partners
        result = processor.process_reciprocal_cycle(cycle)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed reciprocal cycle:\n'
                f'  Agreements processed: {result["agreements_processed"]}\n'
                f'  Remittances created: {result["remittances_created"]}\n'
                f'  Reports generated: {result["reports_generated"]}\n'
                f'  Total payable: {result["total_payable"]} {result["currency"]}\n'
                f'  Audit ID: {result["audit_id"]}'
            )
        )

    def generate_reports_only(self, processor, options):
        """Generate reports for existing remittances without creating new ones"""
        from royalties.models import PartnerRemittance
        
        # Get pending remittances
        remittances = PartnerRemittance.objects.filter(
            status='Pending'
        ).select_related('partner', 'royalty_cycle')
        
        if not remittances.exists():
            self.stdout.write(self.style.WARNING('No pending remittances found'))
            return
        
        self.stdout.write(f'Found {remittances.count()} pending remittances')
        
        reports_generated = 0
        
        for remittance in remittances:
            try:
                # Create mock payment object for report generation
                from royalties.pro_integration import ReciprocalPayment
                
                agreement = ReciprocalAgreement.objects.filter(
                    partner=remittance.partner,
                    status='Active'
                ).first()
                
                if not agreement:
                    self.stdout.write(
                        self.style.WARNING(
                            f'No active agreement found for {remittance.partner.pro_code}'
                        )
                    )
                    continue
                
                payment = ReciprocalPayment(
                    partner_pro=remittance.partner,
                    agreement=agreement,
                    gross_amount=remittance.gross_amount,
                    admin_fee=remittance.admin_fee_amount,
                    net_payable=remittance.net_payable,
                    currency=remittance.currency,
                    usage_count=0,  # Would need to be calculated
                    works_count=0,  # Would need to be calculated
                    calculation_metadata={}
                )
                
                report_data = processor._prepare_report_data(payment, remittance.royalty_cycle)
                
                # Override format if specified
                if options['format']:
                    report_data.partner_pro.reporting_standard = options['format']
                
                report_path = processor._generate_partner_report(report_data)
                
                if report_path:
                    from royalties.models import PartnerReportExport
                    
                    PartnerReportExport.objects.create(
                        partner=remittance.partner,
                        royalty_cycle=remittance.royalty_cycle,
                        format=report_data.partner_pro.reporting_standard,
                        file=report_path,
                        checksum=processor._calculate_file_checksum(report_path)
                    )
                    
                    reports_generated += 1
                    self.stdout.write(f'Generated report for {remittance.partner.pro_code}: {report_path}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error generating report for {remittance.partner.pro_code}: {str(e)}'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Generated {reports_generated} reports')
        )
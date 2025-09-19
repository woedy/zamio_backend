"""
PRO Integration and Reciprocal Agreements Module

This module handles:
- Automated reporting to partner PROs in standard formats
- Reciprocal royalty calculation and distribution system
- Compliance reporting for ASCAP, BMI, and international standards
- Audit trails for all PRO-related transactions and reporting
"""

import csv
import json
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import hashlib
import os

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from .models import (
    PartnerPRO,
    ReciprocalAgreement,
    RoyaltyCycle,
    RoyaltyLineItem,
    PartnerRemittance,
    PartnerReportExport,
    UsageAttribution,
    ExternalWork,
    ExternalRecording,
    RoyaltyCalculationAudit
)
from music_monitor.models import PlayLog, AudioDetection

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Supported PRO report formats"""
    CSV = "CSV"
    CWR = "CWR"  # Common Works Registration
    DDEX_DSR = "DDEX-DSR"  # Digital Data Exchange - Digital Sales Report
    XML_CUSTOM = "XML-Custom"
    JSON_CUSTOM = "JSON-Custom"


class PROStandard(Enum):
    """PRO standards and their requirements"""
    ASCAP = "ASCAP"
    BMI = "BMI"
    GHAMRO = "GHAMRO"
    PRS = "PRS"
    SACEM = "SACEM"
    GEMA = "GEMA"
    JASRAC = "JASRAC"
    SOCAN = "SOCAN"
    APRA = "APRA"


@dataclass
class PROReportData:
    """Data structure for PRO reporting"""
    partner_pro: PartnerPRO
    royalty_cycle: RoyaltyCycle
    usage_data: List[Dict[str, Any]]
    total_amount: Decimal
    currency: str
    report_period_start: date
    report_period_end: date
    metadata: Dict[str, Any]


@dataclass
class ReciprocalPayment:
    """Reciprocal payment calculation result"""
    partner_pro: PartnerPRO
    agreement: ReciprocalAgreement
    gross_amount: Decimal
    admin_fee: Decimal
    net_payable: Decimal
    currency: str
    usage_count: int
    works_count: int
    calculation_metadata: Dict[str, Any]


class PROReportGenerator:
    """Generate reports in various PRO-compliant formats"""
    
    def __init__(self):
        self.export_dir = getattr(settings, 'PRO_EXPORT_DIR', 
                                 os.path.join(settings.BASE_DIR, 'exports', 'pro_reports'))
        os.makedirs(self.export_dir, exist_ok=True)
    
    def generate_csv_report(self, report_data: PROReportData) -> str:
        """Generate CSV format report (most common)"""
        filename = f"{report_data.partner_pro.pro_code}_{report_data.royalty_cycle.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(self.export_dir, filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'report_period_start',
                'report_period_end',
                'station_id',
                'station_name',
                'played_at_utc',
                'isrc',
                'iswc',
                'work_title',
                'recording_title',
                'artist_name',
                'duration_seconds',
                'confidence_score',
                'detection_source',
                'pro_affiliation',
                'gross_amount',
                'admin_fee_amount',
                'net_amount',
                'currency',
                'territory',
                'usage_type'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for usage in report_data.usage_data:
                writer.writerow({
                    'report_period_start': report_data.report_period_start.isoformat(),
                    'report_period_end': report_data.report_period_end.isoformat(),
                    'station_id': usage.get('station_id'),
                    'station_name': usage.get('station_name'),
                    'played_at_utc': usage.get('played_at_utc'),
                    'isrc': usage.get('isrc'),
                    'iswc': usage.get('iswc'),
                    'work_title': usage.get('work_title'),
                    'recording_title': usage.get('recording_title'),
                    'artist_name': usage.get('artist_name'),
                    'duration_seconds': usage.get('duration_seconds'),
                    'confidence_score': usage.get('confidence_score'),
                    'detection_source': usage.get('detection_source'),
                    'pro_affiliation': usage.get('pro_affiliation'),
                    'gross_amount': usage.get('gross_amount'),
                    'admin_fee_amount': usage.get('admin_fee_amount'),
                    'net_amount': usage.get('net_amount'),
                    'currency': report_data.currency,
                    'territory': 'GH',
                    'usage_type': 'broadcast'
                })
        
        return filepath
    
    def generate_cwr_report(self, report_data: PROReportData) -> str:
        """Generate CWR (Common Works Registration) format report"""
        filename = f"{report_data.partner_pro.pro_code}_CWR_{report_data.royalty_cycle.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cwr"
        filepath = os.path.join(self.export_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as cwrfile:
            # CWR Header
            cwrfile.write(f"HDR01GHAMRO{datetime.now().strftime('%Y%m%d%H%M%S')}01.00CWR\n")
            
            # Group Header
            cwrfile.write(f"GRH01{report_data.partner_pro.pro_code}0001\n")
            
            # Transaction sequence number
            seq_num = 1
            
            for usage in report_data.usage_data:
                # Work Registration Transaction
                if usage.get('iswc'):
                    cwrfile.write(f"WRK{seq_num:08d}00000000{usage.get('work_title', '')[:60]:<60}\n")
                    seq_num += 1
                
                # Performance Data
                cwrfile.write(
                    f"PER{seq_num:08d}"
                    f"{usage.get('played_at_utc', '')[:8]}"
                    f"{usage.get('station_id', '')[:14]:<14}"
                    f"{usage.get('recording_title', '')[:60]:<60}"
                    f"{usage.get('duration_seconds', 0):06d}"
                    f"{int(float(usage.get('gross_amount', 0)) * 100):012d}\n"
                )
                seq_num += 1
            
            # Group Trailer
            cwrfile.write(f"GRT01{seq_num-1:08d}0001\n")
            
            # Transmission Trailer
            cwrfile.write(f"TRL01{seq_num:08d}0001\n")
        
        return filepath
    
    def generate_ddex_dsr_report(self, report_data: PROReportData) -> str:
        """Generate DDEX DSR (Digital Sales Report) XML format"""
        filename = f"{report_data.partner_pro.pro_code}_DDEX_{report_data.royalty_cycle.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        filepath = os.path.join(self.export_dir, filename)
        
        # Create XML structure
        root = ET.Element("DigitalSalesReport")
        root.set("xmlns", "http://ddex.net/xml/dsr/20120404")
        root.set("MessageSchemaVersionId", "dsr/20120404")
        
        # Message Header
        header = ET.SubElement(root, "MessageHeader")
        ET.SubElement(header, "MessageThreadId").text = f"GHAMRO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ET.SubElement(header, "MessageId").text = f"DSR_{report_data.royalty_cycle.name}"
        ET.SubElement(header, "MessageCreatedDateTime").text = datetime.now().isoformat()
        
        # Message Sender
        sender = ET.SubElement(header, "MessageSender")
        ET.SubElement(sender, "PartyId").text = "GHAMRO"
        ET.SubElement(sender, "PartyName").text = "Ghana Music Rights Organization"
        
        # Message Recipient
        recipient = ET.SubElement(header, "MessageRecipient")
        ET.SubElement(recipient, "PartyId").text = report_data.partner_pro.pro_code
        ET.SubElement(recipient, "PartyName").text = report_data.partner_pro.display_name
        
        # Report Details
        report_details = ET.SubElement(root, "ReportDetails")
        ET.SubElement(report_details, "ReportId").text = f"RPT_{report_data.royalty_cycle.name}"
        ET.SubElement(report_details, "ReportType").text = "UsageReport"
        ET.SubElement(report_details, "ReportPeriodStartDate").text = report_data.report_period_start.isoformat()
        ET.SubElement(report_details, "ReportPeriodEndDate").text = report_data.report_period_end.isoformat()
        
        # Usage Data
        for usage in report_data.usage_data:
            usage_elem = ET.SubElement(root, "UsageRecord")
            ET.SubElement(usage_elem, "ISRC").text = usage.get('isrc', '')
            ET.SubElement(usage_elem, "RecordingTitle").text = usage.get('recording_title', '')
            ET.SubElement(usage_elem, "ArtistName").text = usage.get('artist_name', '')
            ET.SubElement(usage_elem, "UsageDateTime").text = usage.get('played_at_utc', '')
            ET.SubElement(usage_elem, "Duration").text = str(usage.get('duration_seconds', 0))
            ET.SubElement(usage_elem, "Territory").text = "GH"
            ET.SubElement(usage_elem, "UsageType").text = "Broadcast"
            
            # Royalty Information
            royalty_elem = ET.SubElement(usage_elem, "RoyaltyInformation")
            ET.SubElement(royalty_elem, "GrossAmount").text = str(usage.get('gross_amount', 0))
            ET.SubElement(royalty_elem, "NetAmount").text = str(usage.get('net_amount', 0))
            ET.SubElement(royalty_elem, "Currency").text = report_data.currency
        
        # Write XML to file
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        
        return filepath
    
    def generate_json_report(self, report_data: PROReportData) -> str:
        """Generate JSON format report for modern APIs"""
        filename = f"{report_data.partner_pro.pro_code}_JSON_{report_data.royalty_cycle.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.export_dir, filename)
        
        report_json = {
            "report_metadata": {
                "report_id": f"RPT_{report_data.royalty_cycle.name}",
                "partner_pro": report_data.partner_pro.pro_code,
                "partner_name": report_data.partner_pro.display_name,
                "reporting_organization": "GHAMRO",
                "report_period": {
                    "start_date": report_data.report_period_start.isoformat(),
                    "end_date": report_data.report_period_end.isoformat()
                },
                "generated_at": datetime.now().isoformat(),
                "currency": report_data.currency,
                "territory": "GH",
                "total_amount": str(report_data.total_amount),
                "usage_count": len(report_data.usage_data)
            },
            "usage_data": report_data.usage_data,
            "summary": {
                "total_gross_amount": str(sum(Decimal(str(u.get('gross_amount', 0))) for u in report_data.usage_data)),
                "total_net_amount": str(sum(Decimal(str(u.get('net_amount', 0))) for u in report_data.usage_data)),
                "unique_works": len(set(u.get('iswc') for u in report_data.usage_data if u.get('iswc'))),
                "unique_recordings": len(set(u.get('isrc') for u in report_data.usage_data if u.get('isrc')))
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(report_json, jsonfile, indent=2, ensure_ascii=False)
        
        return filepath


class ReciprocalAgreementProcessor:
    """Process reciprocal agreements and calculate payments"""
    
    def __init__(self):
        self.report_generator = PROReportGenerator()
    
    def calculate_reciprocal_payments(self, royalty_cycle: RoyaltyCycle) -> List[ReciprocalPayment]:
        """Calculate reciprocal payments for all active agreements"""
        payments = []
        
        # Get all active reciprocal agreements
        agreements = ReciprocalAgreement.objects.filter(
            status='Active',
            effective_date__lte=royalty_cycle.period_end
        ).select_related('partner')
        
        for agreement in agreements:
            payment = self._calculate_partner_payment(agreement, royalty_cycle)
            if payment and payment.net_payable > 0:
                payments.append(payment)
        
        return payments
    
    def _calculate_partner_payment(self, agreement: ReciprocalAgreement, royalty_cycle: RoyaltyCycle) -> Optional[ReciprocalPayment]:
        """Calculate payment for a specific partner agreement"""
        try:
            # Get usage attributions for this partner within the cycle period
            attributions = UsageAttribution.objects.filter(
                origin_partner=agreement.partner,
                territory=agreement.territory,
                played_at__date__gte=royalty_cycle.period_start,
                played_at__date__lte=royalty_cycle.period_end
            ).select_related('play_log', 'external_recording', 'external_work')
            
            if not attributions.exists():
                return None
            
            # Calculate totals
            total_usage_count = attributions.count()
            total_duration = sum(attr.duration_seconds or 0 for attr in attributions)
            
            # Calculate gross amount based on play logs
            gross_amount = Decimal('0')
            for attribution in attributions:
                if attribution.play_log and attribution.play_log.royalty_amount:
                    gross_amount += Decimal(str(attribution.play_log.royalty_amount))
            
            # Apply admin fee
            admin_fee_percent = agreement.admin_fee_percent or agreement.partner.default_admin_fee_percent
            admin_fee = gross_amount * (admin_fee_percent / Decimal('100'))
            net_payable = gross_amount - admin_fee
            
            # Count unique works
            unique_works = attributions.values('external_work').distinct().count()
            
            calculation_metadata = {
                'agreement_id': agreement.id,
                'cycle_id': royalty_cycle.id,
                'admin_fee_percent': str(admin_fee_percent),
                'total_duration_seconds': total_duration,
                'calculation_date': timezone.now().isoformat(),
                'unique_works_count': unique_works,
                'attribution_method': 'play_log_royalty'
            }
            
            return ReciprocalPayment(
                partner_pro=agreement.partner,
                agreement=agreement,
                gross_amount=gross_amount,
                admin_fee=admin_fee,
                net_payable=net_payable,
                currency='GHS',  # Base currency
                usage_count=total_usage_count,
                works_count=unique_works,
                calculation_metadata=calculation_metadata
            )
            
        except Exception as e:
            logger.error(f"Error calculating payment for agreement {agreement.id}: {str(e)}")
            return None
    
    @transaction.atomic
    def process_reciprocal_cycle(self, royalty_cycle: RoyaltyCycle) -> Dict[str, Any]:
        """Process complete reciprocal cycle with payments and reporting"""
        logger.info(f"Processing reciprocal agreements for cycle: {royalty_cycle.name}")
        
        # Calculate all reciprocal payments
        payments = self.calculate_reciprocal_payments(royalty_cycle)
        
        # Create remittance records
        remittances_created = []
        reports_generated = []
        total_payable = Decimal('0')
        
        for payment in payments:
            # Create remittance record
            remittance = PartnerRemittance.objects.create(
                partner=payment.partner_pro,
                royalty_cycle=royalty_cycle,
                currency=payment.currency,
                gross_amount=payment.gross_amount,
                admin_fee_amount=payment.admin_fee,
                net_payable=payment.net_payable,
                status='Pending',
                notes=f"Reciprocal agreement payment - {payment.usage_count} usages, {payment.works_count} works"
            )
            remittances_created.append(remittance)
            total_payable += payment.net_payable
            
            # Generate report for partner
            try:
                report_data = self._prepare_report_data(payment, royalty_cycle)
                report_path = self._generate_partner_report(report_data)
                
                if report_path:
                    # Create export record
                    export_record = PartnerReportExport.objects.create(
                        partner=payment.partner_pro,
                        royalty_cycle=royalty_cycle,
                        format=payment.partner_pro.reporting_standard,
                        file=report_path,
                        checksum=self._calculate_file_checksum(report_path)
                    )
                    reports_generated.append(export_record)
                    
            except Exception as e:
                logger.error(f"Error generating report for partner {payment.partner_pro.pro_code}: {str(e)}")
        
        # Create audit record
        audit_record = RoyaltyCalculationAudit.objects.create(
            calculation_type='reciprocal',
            royalty_cycle=royalty_cycle,
            total_amount=total_payable,
            currency='GHS',
            distributions_count=len(remittances_created),
            calculation_metadata={
                'agreements_processed': len(payments),
                'remittances_created': len(remittances_created),
                'reports_generated': len(reports_generated),
                'processing_date': timezone.now().isoformat()
            }
        )
        
        return {
            'cycle_id': royalty_cycle.id,
            'agreements_processed': len(payments),
            'remittances_created': len(remittances_created),
            'reports_generated': len(reports_generated),
            'total_payable': str(total_payable),
            'currency': 'GHS',
            'audit_id': audit_record.calculation_id,
            'processed_at': timezone.now().isoformat()
        }
    
    def _prepare_report_data(self, payment: ReciprocalPayment, royalty_cycle: RoyaltyCycle) -> PROReportData:
        """Prepare report data for partner"""
        # Get detailed usage data
        attributions = UsageAttribution.objects.filter(
            origin_partner=payment.partner_pro,
            territory=payment.agreement.territory,
            played_at__date__gte=royalty_cycle.period_start,
            played_at__date__lte=royalty_cycle.period_end
        ).select_related('play_log', 'external_recording', 'external_work', 'play_log__station')
        
        usage_data = []
        for attr in attributions:
            play_log = attr.play_log
            recording = attr.external_recording
            work = attr.external_work
            
            usage_data.append({
                'station_id': play_log.station.id if play_log and play_log.station else None,
                'station_name': play_log.station.name if play_log and play_log.station else None,
                'played_at_utc': play_log.played_at.isoformat() if play_log and play_log.played_at else None,
                'isrc': recording.isrc if recording else None,
                'iswc': work.iswc if work else None,
                'work_title': work.title if work else None,
                'recording_title': recording.title if recording else None,
                'artist_name': None,  # Would need to be extracted from metadata
                'duration_seconds': attr.duration_seconds,
                'confidence_score': str(attr.confidence_score),
                'detection_source': attr.match_method,
                'pro_affiliation': payment.partner_pro.pro_code,
                'gross_amount': str(play_log.royalty_amount) if play_log and play_log.royalty_amount else '0',
                'admin_fee_amount': str(payment.admin_fee / payment.usage_count) if payment.usage_count > 0 else '0',
                'net_amount': str((payment.net_payable / payment.usage_count)) if payment.usage_count > 0 else '0'
            })
        
        return PROReportData(
            partner_pro=payment.partner_pro,
            royalty_cycle=royalty_cycle,
            usage_data=usage_data,
            total_amount=payment.net_payable,
            currency=payment.currency,
            report_period_start=royalty_cycle.period_start,
            report_period_end=royalty_cycle.period_end,
            metadata=payment.calculation_metadata
        )
    
    def _generate_partner_report(self, report_data: PROReportData) -> Optional[str]:
        """Generate report in partner's preferred format"""
        format_type = report_data.partner_pro.reporting_standard
        
        try:
            if format_type == "CSV":
                return self.report_generator.generate_csv_report(report_data)
            elif format_type == "CWR":
                return self.report_generator.generate_cwr_report(report_data)
            elif format_type == "DDEX-DSR":
                return self.report_generator.generate_ddex_dsr_report(report_data)
            else:
                # Default to JSON for custom formats
                return self.report_generator.generate_json_report(report_data)
                
        except Exception as e:
            logger.error(f"Error generating {format_type} report: {str(e)}")
            return None
    
    def _calculate_file_checksum(self, filepath: str) -> str:
        """Calculate SHA-256 checksum for file integrity"""
        hash_sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


class ComplianceReporter:
    """Generate compliance reports for regulatory bodies"""
    
    def __init__(self):
        self.processor = ReciprocalAgreementProcessor()
    
    def generate_ascap_compliance_report(self, royalty_cycle: RoyaltyCycle) -> str:
        """Generate ASCAP-specific compliance report"""
        try:
            ascap_partner = PartnerPRO.objects.get(pro_code='ASCAP', is_active=True)
        except PartnerPRO.DoesNotExist:
            raise ValueError("ASCAP partner not configured")
        
        # Get ASCAP-specific data
        attributions = UsageAttribution.objects.filter(
            origin_partner=ascap_partner,
            played_at__date__gte=royalty_cycle.period_start,
            played_at__date__lte=royalty_cycle.period_end
        )
        
        # Generate ASCAP-compliant report
        # This would follow ASCAP's specific reporting requirements
        return self._generate_standard_compliance_report(ascap_partner, royalty_cycle, attributions)
    
    def generate_bmi_compliance_report(self, royalty_cycle: RoyaltyCycle) -> str:
        """Generate BMI-specific compliance report"""
        try:
            bmi_partner = PartnerPRO.objects.get(pro_code='BMI', is_active=True)
        except PartnerPRO.DoesNotExist:
            raise ValueError("BMI partner not configured")
        
        # Get BMI-specific data
        attributions = UsageAttribution.objects.filter(
            origin_partner=bmi_partner,
            played_at__date__gte=royalty_cycle.period_start,
            played_at__date__lte=royalty_cycle.period_end
        )
        
        return self._generate_standard_compliance_report(bmi_partner, royalty_cycle, attributions)
    
    def _generate_standard_compliance_report(self, partner: PartnerPRO, cycle: RoyaltyCycle, attributions) -> str:
        """Generate standard compliance report format"""
        report_data = PROReportData(
            partner_pro=partner,
            royalty_cycle=cycle,
            usage_data=[],  # Would be populated with attribution data
            total_amount=Decimal('0'),
            currency='GHS',
            report_period_start=cycle.period_start,
            report_period_end=cycle.period_end,
            metadata={'compliance_report': True}
        )
        
        # Use appropriate format based on partner preference
        generator = PROReportGenerator()
        return generator.generate_csv_report(report_data)
import csv
import hashlib
import os
from datetime import datetime

from django.conf import settings
from django.db import transaction, models
from django.utils.timezone import now
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal

from music_monitor.models import PlayLog
from .models import (
    PartnerPRO,
    ReciprocalAgreement,
    ExternalRecording,
    ExternalWork,
    UsageAttribution,
    RoyaltyCycle,
    RoyaltyLineItem,
    PartnerRemittance,
    PartnerReportExport,
)
from .serializers import (
    PartnerPROSerializer,
    ReciprocalAgreementSerializer,
    RoyaltyCycleSerializer,
    RoyaltyLineItemSerializer,
    PartnerRemittanceSerializer,
    ImportRequestSerializer,
    UploadRepertoireSerializer,
)


def _export_dir():
    base = getattr(settings, "PARTNER_EXPORT_DIR", None) or os.path.join(settings.BASE_DIR, "exports")
    os.makedirs(base, exist_ok=True)
    return base


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_partner(request):
    serializer = PartnerPROSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Ensure required PublisherProfile.user is set
    display_name = serializer.validated_data.get("display_name")
    company_name = serializer.validated_data.get("company_name") or display_name

    partner = PartnerPRO.objects.create(
        user=request.user,  # bind to the admin creating the partner
        company_name=company_name,
        display_name=display_name,
        country_code=serializer.validated_data.get("country_code"),
        contact_email=serializer.validated_data.get("contact_email"),
        reporting_standard=serializer.validated_data.get("reporting_standard", "CSV-Custom"),
        default_admin_fee_percent=serializer.validated_data.get("default_admin_fee_percent", 15.00),
        metadata=serializer.validated_data.get("metadata", {}),
        active=serializer.validated_data.get("active", True),
    )

    return Response(PartnerPROSerializer(partner).data, status=status.HTTP_201_CREATED)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_partner(request, partner_id: int):
    try:
        partner = PartnerPRO.objects.get(id=partner_id)
    except PartnerPRO.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(PartnerPROSerializer(partner).data)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_partners(request):
    qs = PartnerPRO.objects.all().order_by("display_name", "company_name")
    return Response(PartnerPROSerializer(qs, many=True).data)


@api_view(["POST"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_agreement(request, partner_id: int):
    try:
        partner = PartnerPRO.objects.get(id=partner_id)
    except PartnerPRO.DoesNotExist:
        return Response({"detail": "Partner not found"}, status=status.HTTP_404_NOT_FOUND)
    payload = request.data.copy()
    payload["partner"] = partner.id
    serializer = ReciprocalAgreementSerializer(data=payload)
    if serializer.is_valid():
        agreement = serializer.save()
        return Response(ReciprocalAgreementSerializer(agreement).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_agreements(request, partner_id: int):
    try:
        partner = PartnerPRO.objects.get(id=partner_id)
    except PartnerPRO.DoesNotExist:
        return Response({"detail": "Partner not found"}, status=status.HTTP_404_NOT_FOUND)
    qs = partner.agreements.all().order_by("-effective_date")
    return Response(ReciprocalAgreementSerializer(qs, many=True).data)


@api_view(["POST"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ingest_repertoire(request, partner_id: int):
    try:
        partner = PartnerPRO.objects.get(id=partner_id)
    except PartnerPRO.DoesNotExist:
        return Response({"detail": "Partner not found"}, status=status.HTTP_404_NOT_FOUND)

    ser = ImportRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    csv_path = ser.validated_data["csv_path"]
    dry_run = ser.validated_data["dry_run"]

    created = 0
    updated = 0
    skipped = 0
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                isrc = (row.get("isrc") or "").strip()
                title = (row.get("title") or "").strip()
                work_title = (row.get("work_title") or "").strip() or None
                duration = row.get("duration_seconds")
                duration = int(duration) if (duration and str(duration).isdigit()) else None

                if not isrc and not title:
                    skipped += 1
                    continue
                if dry_run:
                    continue
                work = None
                if work_title:
                    work, _ = ExternalWork.objects.get_or_create(
                        origin_partner=partner,
                        title=work_title,
                        defaults={"iswc": None},
                    )
                obj, created_flag = ExternalRecording.objects.update_or_create(
                    origin_partner=partner,
                    isrc=isrc or None,
                    defaults={
                        "title": title or (work_title or "Unknown"),
                        "work": work,
                        "duration": duration,
                    },
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1
    except FileNotFoundError:
        return Response({"detail": f"CSV not found: {csv_path}"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"created": created, "updated": updated, "skipped": skipped, "dry_run": dry_run})


@api_view(["POST"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ingest_repertoire_upload(request, partner_id: int):
    try:
        partner = PartnerPRO.objects.get(id=partner_id)
    except PartnerPRO.DoesNotExist:
        return Response({"detail": "Partner not found"}, status=status.HTTP_404_NOT_FOUND)

    ser = UploadRepertoireSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    upload = request.FILES.get("file")
    dry_run = ser.validated_data.get("dry_run", False)

    created = 0
    updated = 0
    skipped = 0

    try:
        import io, csv
        content = upload.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            isrc = (row.get("isrc") or "").strip()
            title = (row.get("title") or "").strip()
            work_title = (row.get("work_title") or "").strip() or None
            duration = row.get("duration_seconds")
            duration = int(duration) if (duration and str(duration).isdigit()) else None

            if not isrc and not title:
                skipped += 1
                continue
            if dry_run:
                continue
            work = None
            if work_title:
                work, _ = ExternalWork.objects.get_or_create(
                    origin_partner=partner,
                    title=work_title,
                    defaults={"iswc": None},
                )
            obj, created_flag = ExternalRecording.objects.update_or_create(
                origin_partner=partner,
                isrc=isrc or None,
                defaults={
                    "title": title or (work_title or "Unknown"),
                    "work": work,
                    "duration": duration,
                },
            )
            if created_flag:
                created += 1
            else:
                updated += 1
    except Exception as e:
        return Response({"detail": f"Failed to parse CSV: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"created": created, "updated": updated, "skipped": skipped, "dry_run": dry_run})


@api_view(["POST"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_cycle(request):
    serializer = RoyaltyCycleSerializer(data=request.data)
    if serializer.is_valid():
        cycle = serializer.save()
        return Response(RoyaltyCycleSerializer(cycle).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_cycles(request):
    qs = RoyaltyCycle.objects.all().order_by("-period_start")
    return Response(RoyaltyCycleSerializer(qs, many=True).data)


@api_view(["POST"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic
def close_cycle(request, cycle_id: int):
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
    except RoyaltyCycle.DoesNotExist:
        return Response({"detail": "Cycle not found"}, status=status.HTTP_404_NOT_FOUND)

    # Aggregate UsageAttribution within period and territory
    atts = UsageAttribution.objects.select_related("play_log", "external_recording", "origin_partner").filter(
        territory=cycle.territory,
        played_at__date__gte=cycle.period_start,
        played_at__date__lte=cycle.period_end,
    )

    aggregates = {}
    for a in atts.iterator():
        key = (a.origin_partner_id, a.external_recording_id or 0)
        if key not in aggregates:
            aggregates[key] = {
                "partner_id": a.origin_partner_id,
                "external_recording_id": a.external_recording_id,
                "usage_count": 0,
                "total_duration_seconds": 0,
                "gross_amount": 0,
            }
        row = aggregates[key]
        row["usage_count"] += 1
        if a.duration_seconds:
            row["total_duration_seconds"] += a.duration_seconds
        # Use PlayLog.royalty_amount if available as gross component; else 0
        if a.play_log and a.play_log.royalty_amount:
            try:
                row["gross_amount"] += float(a.play_log.royalty_amount)
            except Exception:
                pass

    # Create line items
    created = 0
    for (partner_id, rec_id), row in aggregates.items():
        admin_percent = float(cycle.admin_fee_percent_default)
        gross = row["gross_amount"]
        admin_fee = round(gross * (admin_percent / 100.0), 2)
        net = round(gross - admin_fee, 2)

        RoyaltyLineItem.objects.create(
            royalty_cycle=cycle,
            partner_id=partner_id,
            external_recording_id=rec_id or None,
            usage_count=row["usage_count"],
            total_duration_seconds=row["total_duration_seconds"],
            gross_amount=gross,
            admin_fee_amount=admin_fee,
            net_amount=net,
            calculation_notes=f"Admin fee {admin_percent}%",
        )
        created += 1

    cycle.status = "Locked"
    cycle.save(update_fields=["status"])
    return Response({"line_items_created": created, "status": cycle.status})


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_cycle_line_items(request, cycle_id: int):
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
    except RoyaltyCycle.DoesNotExist:
        return Response({"detail": "Cycle not found"}, status=status.HTTP_404_NOT_FOUND)
    items = cycle.line_items.select_related("partner", "external_recording").all()
    data = RoyaltyLineItemSerializer(items, many=True).data
    return Response(data)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_cycle_exports(request, cycle_id: int):
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
    except RoyaltyCycle.DoesNotExist:
        return Response({"detail": "Cycle not found"}, status=status.HTTP_404_NOT_FOUND)
    qs = cycle.report_exports.select_related("partner").all().order_by("-generated_at")
    data = [
        {
            "id": e.id,
            "partner": e.partner_id,
            "format": e.format,
            "file": e.file,
            "checksum": e.checksum,
            "generated_at": e.generated_at,
        }
        for e in qs
    ]
    return Response(data)


@api_view(["POST"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def export_partner_csv(request, cycle_id: int, partner_id: int):
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
        partner = PartnerPRO.objects.get(id=partner_id)
    except (RoyaltyCycle.DoesNotExist, PartnerPRO.DoesNotExist):
        return Response({"detail": "Cycle or Partner not found"}, status=status.HTTP_404_NOT_FOUND)

    items = RoyaltyLineItem.objects.filter(royalty_cycle=cycle, partner=partner).select_related("external_recording")
    export_dir = _export_dir()
    folder = os.path.join(export_dir, f"partner_{partner.id}", cycle.name)
    os.makedirs(folder, exist_ok=True)
    out_path = os.path.join(folder, f"usage_{partner.id}_{cycle.id}.csv")

    checksum = hashlib.sha256()
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "station_id",
                "played_at_utc",
                "isrc",
                "recording_title",
                "duration_seconds",
                "confidence",
                "match_method",
                "attribution_source",
                "gross_amount",
                "admin_fee_amount",
                "net_amount",
                "currency",
                "cycle_name",
            ],
        )
        writer.writeheader()

        # Walk attributions per line item to reconstruct rows (simplified)
        for item in items:
            # For simplicity, summarize at line-item level as one row
            isrc = item.external_recording.isrc if item.external_recording else None
            title = item.external_recording.title if item.external_recording else None
            row = {
                "station_id": None,
                "played_at_utc": None,
                "isrc": isrc,
                "recording_title": title,
                "duration_seconds": item.total_duration_seconds,
                "confidence": None,
                "match_method": "metadata",
                "attribution_source": "Partner",
                "gross_amount": item.gross_amount,
                "admin_fee_amount": item.admin_fee_amount,
                "net_amount": item.net_amount,
                "currency": "GHS",
                "cycle_name": cycle.name,
            }
            writer.writerow(row)
            checksum.update(str(row).encode("utf-8"))

    pre = PartnerReportExport.objects.create(
        partner=partner,
        royalty_cycle=cycle,
        format="CSV",
        file=out_path,
        checksum=checksum.hexdigest(),
    )
    return Response({"file": out_path, "checksum": pre.checksum})


@api_view(["POST"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_remittance(request, cycle_id: int, partner_id: int):
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
        partner = PartnerPRO.objects.get(id=partner_id)
    except (RoyaltyCycle.DoesNotExist, PartnerPRO.DoesNotExist):
        return Response({"detail": "Cycle or Partner not found"}, status=status.HTTP_404_NOT_FOUND)

    items = RoyaltyLineItem.objects.filter(royalty_cycle=cycle, partner=partner)
    gross = sum([float(i.gross_amount) for i in items])
    admin_fee = sum([float(i.admin_fee_amount) for i in items])
    net = sum([float(i.net_amount) for i in items])

    remit = PartnerRemittance.objects.create(
        partner=partner,
        royalty_cycle=cycle,
        currency="GHS",
        gross_amount=gross,
        admin_fee_amount=admin_fee,
        net_payable=net,
        status="Pending",
    )
    return Response(PartnerRemittanceSerializer(remit).data, status=status.HTTP_201_CREATED)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_remittance(request, remittance_id: int):
    try:
        remit = PartnerRemittance.objects.get(id=remittance_id)
    except PartnerRemittance.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(PartnerRemittanceSerializer(remit).data)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_cycle_remittances(request, cycle_id: int):
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
    except RoyaltyCycle.DoesNotExist:
        return Response({"detail": "Cycle not found"}, status=status.HTTP_404_NOT_FOUND)
    qs = cycle.remittances.select_related("partner").all().order_by("-created_at")
    return Response(PartnerRemittanceSerializer(qs, many=True).data)


@api_view(["GET"]) 
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_unmatched_usage(request):
    # PlayLogs with no UsageAttribution (recent 500)
    without = PlayLog.objects.exclude(usage_attributions__isnull=False).order_by("-created_at")[:500]
    data = [
        {
            "id": p.id,
            "track_id": p.track_id,
            "station_id": p.station_id,
            "played_at": p.played_at,
            "duration": p.duration.total_seconds() if p.duration else None,
        }
        for p in without
    ]
    return Response({"count": len(data), "items": data})


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def calculate_play_log_royalties(request):
    """Calculate royalties for specific play logs"""
    from .calculator import RoyaltyCalculator
    from .serializers import RoyaltyCalculationResultSerializer
    
    play_log_ids = request.data.get('play_log_ids', [])
    if not play_log_ids:
        return Response({"detail": "play_log_ids required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        play_logs = PlayLog.objects.filter(
            id__in=play_log_ids,
            track__isnull=False
        ).select_related('track', 'station')
        
        if not play_logs.exists():
            return Response({"detail": "No valid play logs found"}, status=status.HTTP_404_NOT_FOUND)
        
        calculator = RoyaltyCalculator()
        results = calculator.batch_calculate_royalties(list(play_logs))
        
        # Create distribution records if not dry run
        dry_run = request.data.get('dry_run', False)
        if not dry_run:
            for result in results:
                if not result.errors:
                    calculator.create_royalty_distributions(result)
        
        # Prepare response data
        response_data = {
            'results': [
                {
                    'play_log_id': result.play_log.id,
                    'total_gross_amount': str(result.total_gross_amount),
                    'currency': result.currency,
                    'distributions_count': len(result.distributions),
                    'distributions': [
                        {
                            'recipient_id': dist.recipient_id,
                            'recipient_type': dist.recipient_type,
                            'gross_amount': str(dist.gross_amount),
                            'net_amount': str(dist.net_amount),
                            'percentage_split': str(dist.percentage_split),
                            'pro_share': str(dist.pro_share),
                        }
                        for dist in result.distributions
                    ],
                    'errors': result.errors,
                    'calculation_metadata': result.calculation_metadata
                }
                for result in results
            ],
            'summary': {
                'total_play_logs': len(results),
                'successful_calculations': len([r for r in results if not r.errors]),
                'total_amount': str(sum(r.total_gross_amount for r in results if not r.errors)),
                'currency': 'GHS',
                'dry_run': dry_run
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({"detail": f"Calculation error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_royalty_rates(request):
    """Get current royalty rate structures"""
    from .models import RoyaltyRateStructure
    
    territory = request.GET.get('territory', 'GH')
    
    rates = RoyaltyRateStructure.objects.filter(
        territory=territory,
        is_active=True,
        effective_date__lte=timezone.now().date()
    ).order_by('station_class', 'time_period')
    
    data = [
        {
            'id': rate.id,
            'name': rate.name,
            'station_class': rate.station_class,
            'station_class_display': rate.get_station_class_display(),
            'time_period': rate.time_period,
            'time_period_display': rate.get_time_period_display(),
            'base_rate_per_second': str(rate.base_rate_per_second),
            'multiplier': str(rate.multiplier),
            'effective_date': rate.effective_date,
            'currency': rate.currency,
        }
        for rate in rates
    ]
    
    return Response({'rates': data, 'territory': territory})


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_royalty_rate(request, rate_id):
    """Update a royalty rate structure"""
    from .models import RoyaltyRateStructure
    
    try:
        rate = RoyaltyRateStructure.objects.get(id=rate_id)
    except RoyaltyRateStructure.DoesNotExist:
        return Response({"detail": "Rate structure not found"}, status=status.HTTP_404_NOT_FOUND)
    
    # Update allowed fields
    allowed_fields = ['base_rate_per_second', 'multiplier', 'notes']
    updated_fields = []
    
    for field in allowed_fields:
        if field in request.data:
            setattr(rate, field, request.data[field])
            updated_fields.append(field)
    
    if updated_fields:
        rate.save(update_fields=updated_fields + ['updated_at'])
        
        return Response({
            'id': rate.id,
            'updated_fields': updated_fields,
            'base_rate_per_second': str(rate.base_rate_per_second),
            'multiplier': str(rate.multiplier),
            'notes': rate.notes,
        })
    else:
        return Response({"detail": "No valid fields to update"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_exchange_rates(request):
    """Get current exchange rates"""
    from .models import CurrencyExchangeRate
    
    rates = CurrencyExchangeRate.objects.filter(
        is_active=True,
        effective_date__lte=timezone.now()
    ).order_by('from_currency', 'to_currency', '-effective_date')
    
    # Get latest rate for each currency pair
    latest_rates = {}
    for rate in rates:
        pair_key = f"{rate.from_currency}_{rate.to_currency}"
        if pair_key not in latest_rates:
            latest_rates[pair_key] = rate
    
    data = [
        {
            'id': rate.id,
            'from_currency': rate.from_currency,
            'to_currency': rate.to_currency,
            'rate': str(rate.rate),
            'effective_date': rate.effective_date,
            'source': rate.source,
        }
        for rate in latest_rates.values()
    ]
    
    return Response({'exchange_rates': data})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_calculation_audit(request):
    """Get royalty calculation audit trail"""
    from .models import RoyaltyCalculationAudit
    
    calculation_type = request.GET.get('type')
    limit = int(request.GET.get('limit', 50))
    
    queryset = RoyaltyCalculationAudit.objects.all()
    
    if calculation_type:
        queryset = queryset.filter(calculation_type=calculation_type)
    
    audits = queryset.order_by('-calculated_at')[:limit]
    
    data = [
        {
            'id': audit.id,
            'calculation_id': str(audit.calculation_id),
            'calculation_type': audit.calculation_type,
            'total_amount': str(audit.total_amount),
            'currency': audit.currency,
            'distributions_count': audit.distributions_count,
            'calculated_at': audit.calculated_at,
            'calculated_by': audit.calculated_by.email if audit.calculated_by else 'System',
            'errors_count': len(audit.errors) if audit.errors else 0,
            'has_errors': bool(audit.errors),
        }
        for audit in audits
    ]
    
    return Response({
        'audits': data,
        'total_count': queryset.count(),
        'limit': limit
    })


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def process_reciprocal_cycle(request, cycle_id):
    """Process reciprocal agreements for a royalty cycle"""
    from .pro_integration import ReciprocalAgreementProcessor
    
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
    except RoyaltyCycle.DoesNotExist:
        return Response({"detail": "Cycle not found"}, status=status.HTTP_404_NOT_FOUND)
    
    if cycle.status != 'Locked':
        return Response(
            {"detail": "Cycle must be locked before processing reciprocal agreements"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        processor = ReciprocalAgreementProcessor()
        result = processor.process_reciprocal_cycle(cycle)
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"detail": f"Error processing reciprocal cycle: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generate_pro_report(request):
    """Generate PRO compliance report"""
    from .pro_integration import PROReportGenerator, PROReportData
    from decimal import Decimal
    
    # Validate request data
    partner_id = request.data.get('partner_id')
    cycle_id = request.data.get('cycle_id')
    report_format = request.data.get('format', 'CSV')
    
    if not partner_id:
        return Response({"detail": "partner_id required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        partner = PartnerPRO.objects.get(id=partner_id, is_active=True)
    except PartnerPRO.DoesNotExist:
        return Response({"detail": "Partner PRO not found"}, status=status.HTTP_404_NOT_FOUND)
    
    # Get cycle or use date range
    if cycle_id:
        try:
            cycle = RoyaltyCycle.objects.get(id=cycle_id)
            period_start = cycle.period_start
            period_end = cycle.period_end
        except RoyaltyCycle.DoesNotExist:
            return Response({"detail": "Cycle not found"}, status=status.HTTP_404_NOT_FOUND)
    else:
        # Use date range from request
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        cycle = None
        
        if not period_start or not period_end:
            return Response(
                {"detail": "Either cycle_id or period_start/period_end required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    try:
        # Get usage attributions for this partner
        attributions = UsageAttribution.objects.filter(
            origin_partner=partner,
            played_at__date__gte=period_start,
            played_at__date__lte=period_end
        ).select_related('play_log', 'external_recording', 'external_work', 'play_log__station')
        
        if not attributions.exists():
            return Response(
                {"detail": "No usage data found for the specified period"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Prepare usage data
        usage_data = []
        total_amount = Decimal('0')
        
        for attr in attributions:
            play_log = attr.play_log
            recording = attr.external_recording
            work = attr.external_work
            
            gross_amount = Decimal(str(play_log.royalty_amount)) if play_log and play_log.royalty_amount else Decimal('0')
            admin_fee = gross_amount * Decimal('0.15')  # 15% admin fee
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
                'duration_seconds': attr.duration_seconds,
                'confidence_score': str(attr.confidence_score),
                'detection_source': attr.match_method,
                'pro_affiliation': partner.pro_code,
                'gross_amount': str(gross_amount),
                'admin_fee_amount': str(admin_fee),
                'net_amount': str(net_amount)
            })
        
        # Create report data
        report_data = PROReportData(
            partner_pro=partner,
            royalty_cycle=cycle,
            usage_data=usage_data,
            total_amount=total_amount,
            currency='GHS',
            report_period_start=period_start,
            report_period_end=period_end,
            metadata={
                'generated_by': request.user.email,
                'generated_at': timezone.now().isoformat(),
                'format': report_format
            }
        )
        
        # Generate report
        generator = PROReportGenerator()
        
        if report_format == 'CSV':
            report_path = generator.generate_csv_report(report_data)
        elif report_format == 'CWR':
            report_path = generator.generate_cwr_report(report_data)
        elif report_format == 'DDEX-DSR':
            report_path = generator.generate_ddex_dsr_report(report_data)
        elif report_format == 'JSON':
            report_path = generator.generate_json_report(report_data)
        else:
            return Response(
                {"detail": f"Unsupported format: {report_format}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create export record
        export_record = PartnerReportExport.objects.create(
            partner=partner,
            royalty_cycle=cycle,
            format=report_format,
            file=report_path,
            checksum=hashlib.sha256(open(report_path, 'rb').read()).hexdigest()
        )
        
        return Response({
            'export_id': export_record.id,
            'partner': partner.pro_code,
            'format': report_format,
            'file_path': report_path,
            'usage_count': len(usage_data),
            'total_amount': str(total_amount),
            'currency': 'GHS',
            'generated_at': export_record.generated_at.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {"detail": f"Error generating report: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_reciprocal_payments_summary(request, cycle_id):
    """Get summary of reciprocal payments for a cycle"""
    try:
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
    except RoyaltyCycle.DoesNotExist:
        return Response({"detail": "Cycle not found"}, status=status.HTTP_404_NOT_FOUND)
    
    # Get remittances for this cycle
    remittances = PartnerRemittance.objects.filter(
        royalty_cycle=cycle
    ).select_related('partner')
    
    # Get usage attributions summary
    attributions_summary = UsageAttribution.objects.filter(
        played_at__date__gte=cycle.period_start,
        played_at__date__lte=cycle.period_end
    ).values('origin_partner__pro_code', 'origin_partner__display_name').annotate(
        usage_count=models.Count('id'),
        total_duration=models.Sum('duration_seconds')
    )
    
    # Prepare response data
    payments_data = []
    total_payable = Decimal('0')
    
    for remittance in remittances:
        # Find corresponding attribution summary
        attr_summary = next(
            (a for a in attributions_summary if a['origin_partner__pro_code'] == remittance.partner.pro_code),
            {'usage_count': 0, 'total_duration': 0}
        )
        
        payments_data.append({
            'partner_pro': remittance.partner.pro_code,
            'partner_name': remittance.partner.display_name,
            'gross_amount': str(remittance.gross_amount),
            'admin_fee_amount': str(remittance.admin_fee_amount),
            'net_payable': str(remittance.net_payable),
            'currency': remittance.currency,
            'status': remittance.status,
            'usage_count': attr_summary['usage_count'],
            'total_duration_seconds': attr_summary['total_duration'] or 0,
            'created_at': remittance.created_at.isoformat()
        })
        
        total_payable += remittance.net_payable
    
    return Response({
        'cycle': {
            'id': cycle.id,
            'name': cycle.name,
            'period_start': cycle.period_start,
            'period_end': cycle.period_end,
            'status': cycle.status
        },
        'payments': payments_data,
        'summary': {
            'total_partners': len(payments_data),
            'total_payable': str(total_payable),
            'currency': 'GHS',
            'total_usages': sum(p['usage_count'] for p in payments_data)
        }
    })

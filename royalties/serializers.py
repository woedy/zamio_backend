from rest_framework import serializers

from .models import (
    PartnerPRO,
    ReciprocalAgreement,
    RoyaltyCycle,
    RoyaltyLineItem,
    PartnerRemittance,
    RoyaltyRateStructure,
    CurrencyExchangeRate,
    RoyaltyCalculationAudit,
)


class PartnerPROSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerPRO
        fields = [
            "id",
            "display_name",
            "company_name",
            "country_code",
            "contact_email",
            "reporting_standard",
            "default_admin_fee_percent",
            "active",
            "metadata",
        ]


class ReciprocalAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReciprocalAgreement
        fields = [
            "id",
            "partner",
            "territory",
            "effective_date",
            "expiry_date",
            "admin_fee_percent",
            "status",
            "reporting_frequency",
            "notes",
        ]


class RoyaltyCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoyaltyCycle
        fields = [
            "id",
            "name",
            "territory",
            "period_start",
            "period_end",
            "status",
            "admin_fee_percent_default",
            "created_at",
        ]


class RoyaltyLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoyaltyLineItem
        fields = [
            "id",
            "royalty_cycle",
            "partner",
            "external_work",
            "external_recording",
            "usage_count",
            "total_duration_seconds",
            "gross_amount",
            "admin_fee_amount",
            "net_amount",
            "calculation_notes",
        ]


class PartnerRemittanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerRemittance
        fields = [
            "id",
            "partner",
            "royalty_cycle",
            "currency",
            "gross_amount",
            "admin_fee_amount",
            "net_payable",
            "payment_reference",
            "statement_file",
            "status",
            "sent_at",
            "settled_at",
            "notes",
            "created_at",
        ]


class ImportRequestSerializer(serializers.Serializer):
    csv_path = serializers.CharField()
    dry_run = serializers.BooleanField(required=False, default=False)


class UploadRepertoireSerializer(serializers.Serializer):
    file = serializers.FileField()
    dry_run = serializers.BooleanField(required=False, default=False)


class RoyaltyRateStructureSerializer(serializers.ModelSerializer):
    station_class_display = serializers.CharField(source='get_station_class_display', read_only=True)
    time_period_display = serializers.CharField(source='get_time_period_display', read_only=True)
    
    class Meta:
        model = RoyaltyRateStructure
        fields = [
            'id', 'name', 'station_class', 'station_class_display',
            'time_period', 'time_period_display', 'base_rate_per_second',
            'multiplier', 'effective_date', 'expiry_date', 'currency',
            'territory', 'notes', 'is_active', 'created_at', 'updated_at'
        ]


class CurrencyExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyExchangeRate
        fields = [
            'id', 'from_currency', 'to_currency', 'rate',
            'effective_date', 'source', 'is_active', 'created_at'
        ]


class RoyaltyCalculationAuditSerializer(serializers.ModelSerializer):
    calculated_by_email = serializers.CharField(source='calculated_by.email', read_only=True)
    
    class Meta:
        model = RoyaltyCalculationAudit
        fields = [
            'id', 'calculation_id', 'calculation_type', 'total_amount',
            'currency', 'distributions_count', 'calculation_metadata',
            'rate_structure_used', 'errors', 'calculated_by_email',
            'calculated_at'
        ]

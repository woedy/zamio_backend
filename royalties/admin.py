from django.contrib import admin

from .models import (
    PartnerPRO,
    ReciprocalAgreement,
    ExternalWork,
    ExternalRecording,
    UsageAttribution,
    RoyaltyCycle,
    RoyaltyLineItem,
    PartnerRemittance,
    PartnerReportExport,
)


@admin.register(PartnerPRO)
class PartnerPROAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "company_name", "country_code", "active", "reporting_standard")
    search_fields = ("display_name", "company_name", "country_code")
    list_filter = ("active", "reporting_standard")


@admin.register(ReciprocalAgreement)
class ReciprocalAgreementAdmin(admin.ModelAdmin):
    list_display = ("id", "partner", "territory", "status", "effective_date", "expiry_date")
    list_filter = ("status", "territory")


@admin.register(ExternalWork)
class ExternalWorkAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "iswc", "origin_partner")
    search_fields = ("title", "iswc")


@admin.register(ExternalRecording)
class ExternalRecordingAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "isrc", "origin_partner", "work")
    search_fields = ("title", "isrc")


@admin.register(UsageAttribution)
class UsageAttributionAdmin(admin.ModelAdmin):
    list_display = ("id", "play_log", "origin_partner", "match_method", "confidence_score", "territory", "played_at")
    list_filter = ("match_method", "territory")


@admin.register(RoyaltyCycle)
class RoyaltyCycleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "territory", "period_start", "period_end", "status")
    list_filter = ("status", "territory")


@admin.register(RoyaltyLineItem)
class RoyaltyLineItemAdmin(admin.ModelAdmin):
    list_display = ("id", "royalty_cycle", "partner", "usage_count", "gross_amount", "admin_fee_amount", "net_amount")
    list_filter = ("royalty_cycle", "partner")


@admin.register(PartnerRemittance)
class PartnerRemittanceAdmin(admin.ModelAdmin):
    list_display = ("id", "partner", "royalty_cycle", "currency", "net_payable", "status", "sent_at", "settled_at")
    list_filter = ("status", "partner")


@admin.register(PartnerReportExport)
class PartnerReportExportAdmin(admin.ModelAdmin):
    list_display = ("id", "partner", "royalty_cycle", "format", "file", "generated_at")
    list_filter = ("format", "partner")

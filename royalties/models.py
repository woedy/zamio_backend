import uuid
from django.db import models
from django.utils import timezone
from decimal import Decimal

from publishers.models import PublisherProfile
from music_monitor.models import PlayLog


class PartnerPRO(PublisherProfile):
    REPORTING_STANDARDS = (
        ("CWR", "CWR"),
        ("DDEX-DSR", "DDEX-DSR"),
        ("CSV-Custom", "CSV-Custom"),
    )
    
    PRO_TYPES = (
        ("local", "Local PRO"),
        ("international", "International PRO"),
        ("reciprocal", "Reciprocal Partner"),
    )

    display_name = models.CharField(max_length=255, blank=True, null=True)
    pro_code = models.CharField(max_length=20, unique=True, help_text="Unique PRO identifier (e.g., ASCAP, BMI, GHAMRO)")
    pro_type = models.CharField(max_length=20, choices=PRO_TYPES, default="international")
    country_code = models.CharField(max_length=3, blank=True, null=True)
    territory = models.CharField(max_length=100, blank=True, null=True, help_text="Territory or region covered")
    contact_email = models.EmailField(blank=True, null=True)
    reporting_standard = models.CharField(max_length=20, choices=REPORTING_STANDARDS, default="CSV-Custom")
    default_admin_fee_percent = models.DecimalField(max_digits=6, decimal_places=2, default=15.00)
    
    # API integration settings
    api_endpoint = models.URLField(blank=True, null=True, help_text="API endpoint for direct integration")
    api_key = models.CharField(max_length=255, blank=True, null=True, help_text="API key for integration")
    api_settings = models.JSONField(default=dict, blank=True, help_text="Additional API configuration")
    
    # Enhanced metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Status and activity
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(blank=True, null=True)
    sync_status = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = "Partner PRO"
        verbose_name_plural = "Partner PROs"

    def __str__(self):
        return self.display_name or self.company_name or f"PartnerPRO {self.pk}"


class ReciprocalAgreement(models.Model):
    STATUS = (
        ("Draft", "Draft"),
        ("Active", "Active"),
        ("Suspended", "Suspended"),
        ("Terminated", "Terminated"),
    )
    FREQ = (
        ("Quarterly", "Quarterly"),
        ("SemiAnnual", "SemiAnnual"),
        ("Annual", "Annual"),
        ("Custom", "Custom"),
    )

    partner = models.ForeignKey(PartnerPRO, on_delete=models.CASCADE, related_name="agreements")
    territory = models.CharField(max_length=10, default="GH")
    effective_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(blank=True, null=True)
    admin_fee_percent = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS, default="Draft")
    reporting_frequency = models.CharField(max_length=20, choices=FREQ, default="Quarterly")
    notes = models.TextField(blank=True, null=True)
    

    def __str__(self):
        return f"{self.partner} - {self.territory} ({self.status})"


class ExternalWork(models.Model):
    origin_partner = models.ForeignKey(PartnerPRO, on_delete=models.CASCADE, related_name="external_works")
    iswc = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    title = models.CharField(max_length=500)
    alt_titles = models.JSONField(default=list, blank=True)
    work_metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.title


class ExternalRecording(models.Model):
    origin_partner = models.ForeignKey(PartnerPRO, on_delete=models.CASCADE, related_name="external_recordings")
    work = models.ForeignKey(ExternalWork, on_delete=models.SET_NULL, blank=True, null=True, related_name="recordings")
    isrc = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    title = models.CharField(max_length=500)
    duration = models.PositiveIntegerField(blank=True, null=True, help_text="Duration in seconds")
    recording_metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.title} ({self.isrc or 'no-ISRC'})"


class UsageAttribution(models.Model):
    MATCH_METHODS = (
        ("fingerprint", "fingerprint"),
        ("metadata", "metadata"),
    )

    play_log = models.ForeignKey(PlayLog, on_delete=models.CASCADE, related_name="usage_attributions")
    external_work = models.ForeignKey(ExternalWork, on_delete=models.SET_NULL, blank=True, null=True)
    external_recording = models.ForeignKey(ExternalRecording, on_delete=models.SET_NULL, blank=True, null=True)
    origin_partner = models.ForeignKey(PartnerPRO, on_delete=models.CASCADE)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    match_method = models.CharField(max_length=20, choices=MATCH_METHODS, default="metadata")
    territory = models.CharField(max_length=10, default="GH")
    station_id = models.IntegerField(blank=True, null=True)
    played_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["territory", "played_at"]),
        ]

    def __str__(self):
        return f"Attribution {self.id} → {self.origin_partner}"
class RoyaltyCycle(models.Model):
    STATUS = (
        ("Open", "Open"),
        ("Locked", "Locked"),
        ("Invoiced", "Invoiced"),
        ("Remitted", "Remitted"),
    )

    name = models.CharField(max_length=100)
    territory = models.CharField(max_length=10, default="GH")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default="Open")
    admin_fee_percent_default = models.DecimalField(max_digits=6, decimal_places=2, default=15.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.territory}) [{self.status}]"


class RoyaltyLineItem(models.Model):
    royalty_cycle = models.ForeignKey(RoyaltyCycle, on_delete=models.CASCADE, related_name="line_items")
    partner = models.ForeignKey(PartnerPRO, on_delete=models.SET_NULL, blank=True, null=True)

    external_work = models.ForeignKey(ExternalWork, on_delete=models.SET_NULL, blank=True, null=True)
    external_recording = models.ForeignKey(ExternalRecording, on_delete=models.SET_NULL, blank=True, null=True)

    usage_count = models.PositiveIntegerField(default=0)
    total_duration_seconds = models.PositiveIntegerField(default=0)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    admin_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    calculation_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        ref = self.external_recording or self.external_work or self.partner
        return f"LineItem {self.id} for {ref}"


class PartnerRemittance(models.Model):
    STATUS = (
        ("Pending", "Pending"),
        ("Sent", "Sent"),
        ("Settled", "Settled"),
        ("Failed", "Failed"),
    )

    partner = models.ForeignKey(PartnerPRO, on_delete=models.CASCADE, related_name="remittances")
    royalty_cycle = models.ForeignKey(RoyaltyCycle, on_delete=models.CASCADE, related_name="remittances")
    currency = models.CharField(max_length=10, default="GHS")
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    admin_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_reference = models.CharField(max_length=255, blank=True, null=True)
    statement_file = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS, default="Pending")
    sent_at = models.DateTimeField(blank=True, null=True)
    settled_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Remittance {self.id} -> {self.partner} [{self.status}]"


class PartnerReportExport(models.Model):
    FORMAT = (
        ("CSV", "CSV"),
        ("CWR", "CWR"),
        ("DDEX-DSR", "DDEX-DSR"),
    )

    partner = models.ForeignKey(PartnerPRO, on_delete=models.CASCADE, related_name="report_exports")
    royalty_cycle = models.ForeignKey(RoyaltyCycle, on_delete=models.CASCADE, related_name="report_exports")
    format = models.CharField(max_length=20, choices=FORMAT, default="CSV")
    file = models.CharField(max_length=500)
    generated_at = models.DateTimeField(auto_now_add=True)
    checksum = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return f"Export {self.id} {self.format} for {self.partner}"


class RoyaltyRateStructure(models.Model):
    """Configurable royalty rate structures for different station classes and time periods"""
    STATION_CLASSES = [
        ('class_a', 'Class A - Major Metropolitan'),
        ('class_b', 'Class B - Regional'),
        ('class_c', 'Class C - Local/Community'),
        ('online', 'Online Only'),
        ('community', 'Community/Non-Profit'),
    ]
    
    TIME_PERIODS = [
        ('prime_time', 'Prime Time (6-10 AM, 4-8 PM)'),
        ('regular_time', 'Regular Time (10 AM-4 PM, 8 PM-12 AM)'),
        ('off_peak', 'Off Peak (12-6 AM)'),
    ]
    
    name = models.CharField(max_length=100, help_text="Rate structure name")
    station_class = models.CharField(max_length=20, choices=STATION_CLASSES)
    time_period = models.CharField(max_length=20, choices=TIME_PERIODS)
    
    # Rate configuration
    base_rate_per_second = models.DecimalField(max_digits=10, decimal_places=6, help_text="Base rate per second in GHS")
    multiplier = models.DecimalField(max_digits=5, decimal_places=3, default=1.0, help_text="Time period multiplier")
    
    # Validity period
    effective_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Metadata
    currency = models.CharField(max_length=3, default='GHS')
    territory = models.CharField(max_length=10, default='GH')
    notes = models.TextField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('station_class', 'time_period', 'effective_date', 'territory')
        indexes = [
            models.Index(fields=['station_class', 'time_period', 'effective_date']),
            models.Index(fields=['is_active', 'territory']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.get_station_class_display()} ({self.get_time_period_display()})"
    
    def is_valid_for_date(self, check_date):
        """Check if rate structure is valid for given date"""
        if check_date < self.effective_date:
            return False
        if self.expiry_date and check_date > self.expiry_date:
            return False
        return self.is_active


class CurrencyExchangeRate(models.Model):
    """Currency exchange rates for international payments"""
    from_currency = models.CharField(max_length=3, help_text="Source currency code (ISO 4217)")
    to_currency = models.CharField(max_length=3, help_text="Target currency code (ISO 4217)")
    rate = models.DecimalField(max_digits=15, decimal_places=8, help_text="Exchange rate")
    
    effective_date = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=50, default='manual', help_text="Rate source (manual, api, etc.)")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('from_currency', 'to_currency', 'effective_date')
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'effective_date']),
            models.Index(fields=['is_active', 'effective_date']),
        ]
    
    def __str__(self):
        return f"{self.from_currency}/{self.to_currency}: {self.rate} ({self.effective_date.date()})"
    
    @classmethod
    def get_rate(cls, from_currency, to_currency, date=None):
        """Get exchange rate for currency pair on specific date"""
        if from_currency == to_currency:
            return Decimal('1.0')
        
        if date is None:
            date = timezone.now()
        
        rate = cls.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            effective_date__lte=date,
            is_active=True
        ).order_by('-effective_date').first()
        
        if rate:
            return rate.rate
        
        # Try inverse rate
        inverse_rate = cls.objects.filter(
            from_currency=to_currency,
            to_currency=from_currency,
            effective_date__lte=date,
            is_active=True
        ).order_by('-effective_date').first()
        
        if inverse_rate and inverse_rate.rate != 0:
            return Decimal('1') / inverse_rate.rate
        
        return Decimal('1.0')  # Fallback


class RoyaltyCalculationAudit(models.Model):
    """Audit trail for royalty calculations"""
    CALCULATION_TYPES = [
        ('individual', 'Individual Play Log'),
        ('batch', 'Batch Processing'),
        ('cycle', 'Royalty Cycle'),
        ('recalculation', 'Recalculation'),
    ]
    
    calculation_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPES)
    
    # Source references
    play_log = models.ForeignKey('music_monitor.PlayLog', on_delete=models.CASCADE, null=True, blank=True)
    royalty_cycle = models.ForeignKey(RoyaltyCycle, on_delete=models.CASCADE, null=True, blank=True)
    
    # Calculation details
    total_amount = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(max_length=3, default='GHS')
    distributions_count = models.IntegerField(default=0)
    
    # Metadata
    calculation_metadata = models.JSONField(default=dict, blank=True)
    rate_structure_used = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    
    # Audit information
    calculated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['calculation_type', 'calculated_at']),
            models.Index(fields=['play_log', 'calculated_at']),
            models.Index(fields=['royalty_cycle', 'calculated_at']),
        ]
    
    def __str__(self):
        return f"Calculation {self.calculation_id} - {self.calculation_type} ({self.total_amount} {self.currency})"

# management/commands/populate_admin_dashboard.py

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate, ExtractWeekDay, TruncMonth

from music_monitor.models import PlayLog
from artists.models import Artist, Track, Station
from music_monitor.models import PlatformAvailability

CACHE_KEY = "admin_dashboard_data"
CACHE_TIMEOUT = 15 * 60  # 15 minutes

class Command(BaseCommand):
    help = "Precompute metrics for admin dashboard and store in cache"

    def handle(self, *args, **kwargs):
        now = timezone.now()
        one_month_ago = now - timedelta(days=30)

        logs = PlayLog.objects.filter(active=True)
        logs_month = logs.filter(played_at__gte=one_month_ago)

        # Platform Stats
        platform_stats = {
            "totalStations": Station.objects.count(),
            "totalArtists": Artist.objects.count(),
            "totalSongs": Track.objects.count(),
            "totalPlays": logs.count(),
            "totalRoyalties": float(logs.aggregate(sum=Sum('royalty_amount'))['sum'] or 0),
            "pendingPayments": float(logs.filter(flagged=True).aggregate(sum=Sum('royalty_amount'))['sum'] or 0),
            "monthlyGrowthPercent": round(((logs_month.count() / (logs.count() or 1)) * 100), 2)
        }

        # Station Performance
        sp = logs.values('station__name').annotate(
            plays=Count('id'),
            revenue=Sum('royalty_amount')
        ).order_by('-revenue')[:5]
        station_performance = [
            {"station": r['station__name'], "plays": r['plays'], "revenue": float(r['revenue'] or 0)}
            for r in sp
        ]

        # Top Earners
        ta = Artist.objects.annotate(
            earnings=Sum('track__track_playlog__royalty_amount', filter=Q(track__track_playlog__active=True)),
            plays=Count('track__track_playlog', filter=Q(track__track_playlog__active=True))
        ).order_by('-earnings')[:5]
        top_earners = [
            {
                "name": artist.stage_name,
                "plays": artist.plays,
                "totalEarnings": float(artist.earnings or 0)
            } for artist in ta
        ]

        # Distribution Metrics by platform
        dist = PlatformAvailability.objects.filter(track__track_playlog__active=True)
        pd = dist.values('platform').annotate(
            tracks=Count('track', distinct=True),
            revenue=Sum('track__track_playlog__royalty_amount')
        )
        distribution_metrics = [
            {
                "platform": r['platform'],
                "tracks": r['tracks'],
                "revenue": float(r['revenue'] or 0)
            } for r in pd
        ]

        # Revenue Over Time (last 30 days per day)
        rev_trend = logs_month.annotate(day=TruncDate('played_at')).values('day').annotate(
            revenue=Sum('royalty_amount'),
            plays=Count('id')
        ).order_by('day')
        revenue_data = [
            {"date": r['day'].isoformat(), "revenue": float(r['revenue']), "plays": r['plays']}
            for r in rev_trend
        ]

        # Genre breakdown (by play count)
        gd = Track.objects.filter(
            track_playlog__active=True
        ).values('genre__name').annotate(
            plays=Count('track_playlog')
        )
        genre_data = [
            {"name": x['genre__name'] or "Unknown", "value": x['plays']}
            for x in gd
        ]

        # Daily Activity Trends (last week)
        week_logs = logs.filter(played_at__gte=now - timedelta(days=7))
        da = week_logs.annotate(day=ExtractWeekDay('played_at')).values('day').annotate(
            plays=Count('id'),
            disputes=Count('id', filter=Q(flagged=True))
        )
        weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        daily_activity_data = [
            {
                "day": weekdays[r['day'] % 7],
                "plays": r['plays'],
                "disputes": r['disputes']
            } for r in da
        ]

        # Compose data
        data = {
            "timestamp": now.isoformat(),
            "platformStats": platform_stats,
            "stationPerformance": station_performance,
            "topEarners": top_earners,
            "distributionMetrics": distribution_metrics,
            "revenueData": revenue_data,
            "genreData": genre_data,
            "dailyActivityData": daily_activity_data
        }

        cache.set(CACHE_KEY, data, CACHE_TIMEOUT)
        self.stdout.write(self.style.SUCCESS("🌟 Admin dashboard data populated to cache."))

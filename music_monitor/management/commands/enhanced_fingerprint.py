"""
Management command for enhanced fingerprinting operations
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from artists.models import Track
from music_monitor.services.enhanced_fingerprinting import (
    EnhancedFingerprintService,
    batch_fingerprint_all_tracks,
    get_system_fingerprint_stats
)
import json


class Command(BaseCommand):
    help = 'Enhanced fingerprinting operations for tracks'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['single', 'batch', 'all', 'stats', 'reprocess'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--track-id',
            type=int,
            help='Track ID for single track fingerprinting'
        )
        
        parser.add_argument(
            '--track-ids',
            nargs='+',
            type=int,
            help='List of track IDs for batch fingerprinting'
        )
        
        parser.add_argument(
            '--config',
            choices=['fast', 'balanced', 'high_quality'],
            default='balanced',
            help='Fingerprinting configuration to use'
        )
        
        parser.add_argument(
            '--workers',
            type=int,
            default=4,
            help='Number of parallel workers for batch processing'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reprocessing of existing fingerprints'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of tracks to process (for testing)'
        )
        
        parser.add_argument(
            '--filter-unprocessed',
            action='store_true',
            help='Only process tracks without current version fingerprints'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        try:
            if action == 'single':
                self.handle_single_track(options)
            elif action == 'batch':
                self.handle_batch_tracks(options)
            elif action == 'all':
                self.handle_all_tracks(options)
            elif action == 'stats':
                self.handle_stats(options)
            elif action == 'reprocess':
                self.handle_reprocess(options)
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')

    def handle_single_track(self, options):
        """Handle single track fingerprinting"""
        track_id = options.get('track_id')
        if not track_id:
            raise CommandError('--track-id is required for single track action')
        
        config = options.get('config', 'balanced')
        force = options.get('force', False)
        
        self.stdout.write(f'Fingerprinting track {track_id} with {config} config...')
        
        try:
            track = Track.objects.get(id=track_id)
            service = EnhancedFingerprintService(config)
            success = service.fingerprint_track(track, force_reprocess=force)
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully fingerprinted track {track_id}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed to fingerprint track {track_id}')
                )
        except Track.DoesNotExist:
            raise CommandError(f'Track {track_id} not found')

    def handle_batch_tracks(self, options):
        """Handle batch track fingerprinting"""
        track_ids = options.get('track_ids')
        if not track_ids:
            raise CommandError('--track-ids is required for batch action')
        
        config = options.get('config', 'balanced')
        workers = options.get('workers', 4)
        force = options.get('force', False)
        
        self.stdout.write(f'Batch fingerprinting {len(track_ids)} tracks with {config} config...')
        
        service = EnhancedFingerprintService(config)
        results = service.batch_fingerprint_tracks(track_ids, workers, force)
        
        self.display_batch_results(results)

    def handle_all_tracks(self, options):
        """Handle fingerprinting all tracks"""
        config = options.get('config', 'balanced')
        workers = options.get('workers', 4)
        force = options.get('force', False)
        limit = options.get('limit')
        filter_unprocessed = options.get('filter_unprocessed', False)
        
        # Build query
        query = Track.objects.filter(active=True, is_archived=False)
        
        if filter_unprocessed:
            # Only tracks without current version fingerprints
            current_version = EnhancedFingerprintService.CURRENT_VERSION
            query = query.exclude(
                fingerprint_track__metadata__version=current_version
            )
        
        if limit:
            query = query[:limit]
        
        track_ids = list(query.values_list('id', flat=True))
        
        if not track_ids:
            self.stdout.write(self.style.WARNING('No tracks found to process'))
            return
        
        self.stdout.write(f'Fingerprinting {len(track_ids)} tracks with {config} config...')
        
        service = EnhancedFingerprintService(config)
        results = service.batch_fingerprint_tracks(track_ids, workers, force)
        
        self.display_batch_results(results)

    def handle_stats(self, options):
        """Handle displaying fingerprint statistics"""
        self.stdout.write('Fingerprint Statistics:')
        self.stdout.write('=' * 50)
        
        stats = get_system_fingerprint_stats()
        
        if 'error' in stats:
            self.stdout.write(self.style.ERROR(f'Error getting stats: {stats["error"]}'))
            return
        
        self.stdout.write(f'Total Fingerprints: {stats.get("total_fingerprints", 0):,}')
        self.stdout.write(f'Current Version ({stats.get("current_version", "N/A")}): {stats.get("current_version_fingerprints", 0):,}')
        self.stdout.write(f'Coverage: {stats.get("coverage_percentage", 0)}%')
        self.stdout.write(f'Algorithm: {stats.get("algorithm", "N/A")}')
        self.stdout.write(f'Config: {stats.get("config_name", "N/A")}')
        
        if 'version_distribution' in stats:
            self.stdout.write('\nVersion Distribution:')
            for version_info in stats['version_distribution']:
                version = version_info.get('metadata__version', 'Unknown')
                count = version_info.get('count', 0)
                self.stdout.write(f'  {version}: {count:,}')

    def handle_reprocess(self, options):
        """Handle reprocessing tracks with old fingerprint versions"""
        config = options.get('config', 'balanced')
        workers = options.get('workers', 4)
        limit = options.get('limit')
        
        current_version = EnhancedFingerprintService.CURRENT_VERSION
        
        # Find tracks with old fingerprint versions
        query = Track.objects.filter(
            active=True,
            is_archived=False,
            fingerprint_track__isnull=False
        ).exclude(
            fingerprint_track__metadata__version=current_version
        ).distinct()
        
        if limit:
            query = query[:limit]
        
        track_ids = list(query.values_list('id', flat=True))
        
        if not track_ids:
            self.stdout.write(self.style.WARNING('No tracks found for reprocessing'))
            return
        
        self.stdout.write(f'Reprocessing {len(track_ids)} tracks with outdated fingerprints...')
        
        service = EnhancedFingerprintService(config)
        results = service.batch_fingerprint_tracks(track_ids, workers, force_reprocess=True)
        
        self.display_batch_results(results)

    def display_batch_results(self, results):
        """Display batch processing results"""
        self.stdout.write('\nBatch Processing Results:')
        self.stdout.write('=' * 30)
        
        total = results.get('total_tracks', 0)
        successful = results.get('successful', 0)
        failed = results.get('failed', 0)
        processing_time = results.get('processing_time_seconds', 0)
        
        self.stdout.write(f'Total Tracks: {total}')
        self.stdout.write(f'Successful: {successful}')
        self.stdout.write(f'Failed: {failed}')
        self.stdout.write(f'Processing Time: {processing_time:.2f}s')
        
        if 'performance_metrics' in results:
            metrics = results['performance_metrics']
            self.stdout.write(f'Success Rate: {metrics.get("success_rate", 0)}%')
            self.stdout.write(f'Tracks/Second: {metrics.get("tracks_per_second", 0):.2f}')
            self.stdout.write(f'Avg Time/Track: {metrics.get("average_time_per_track", 0):.2f}s')
        
        if results.get('failed_tracks'):
            self.stdout.write(f'\nFailed Track IDs: {results["failed_tracks"]}')
        
        if successful > 0:
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully processed {successful}/{total} tracks'))
        else:
            self.stdout.write(self.style.ERROR('\nNo tracks were successfully processed'))
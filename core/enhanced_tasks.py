"""
Enhanced Celery tasks for ZamIO platform with optimized performance,
monitoring, and retry mechanisms.
"""

import logging
from typing import Dict, List, Any, Optional
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from core.background_processing import (
    EnhancedTask, monitored_task, BatchProcessor, TaskScheduler,
    PerformanceOptimizer, with_progress_tracking, with_retry_logic
)
from core.caching_service import CacheInvalidator

logger = logging.getLogger(__name__)


# Audio Processing Tasks
@shared_task(base=EnhancedTask, bind=True, queue='critical')
@with_progress_tracking
@with_retry_logic(max_retries=2, countdown=30)
def enhanced_audio_detection_task(self, audio_data_b64: str, station_id: int, 
                                session_id: str, audio_timestamp: str) -> Dict[str, Any]:
    """
    Enhanced audio detection with hybrid local/ACRCloud processing
    """
    try:
        from music_monitor.services.hybrid_detection import HybridDetectionService
        from stations.models import Station
        from artists.models import Fingerprint
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Initializing detection'})
        
        # Get station and fingerprints
        station = Station.objects.get(id=station_id)
        local_fingerprints = list(
            Fingerprint.objects.select_related('track').values_list(
                'track_id', 'hash', 'offset'
            )
        )
        
        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': 'Processing audio'})
        
        # Initialize hybrid detection service
        hybrid_service = HybridDetectionService()
        
        # Perform detection
        match_result, detection_source, processing_metadata = hybrid_service.identify_with_fallback(
            audio_data_b64, local_fingerprints, session_id, station_id
        )
        
        self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'Saving results'})
        
        # Create detection record
        from music_monitor.models import AudioDetection
        
        detection_data = {
            'session_id': session_id,
            'station': station,
            'detection_source': detection_source,
            'confidence_score': match_result.get('confidence', 0) / 100.0 if match_result else 0,
            'processing_status': 'completed',
            'audio_timestamp': audio_timestamp,
            'processing_time_ms': processing_metadata.get('total_processing_time_ms', 0),
            'external_metadata': processing_metadata
        }
        
        if match_result and detection_source == 'local':
            from artists.models import Track
            track = Track.objects.get(id=match_result['song_id'])
            detection_data.update({
                'track': track,
                'detected_title': track.title,
                'detected_artist': track.artist.stage_name,
                'pro_affiliation': 'ghamro',
            })
        elif match_result and detection_source == 'acrcloud':
            detection_data.update({
                'detected_title': match_result.get('title'),
                'detected_artist': match_result.get('artist'),
                'isrc': match_result.get('isrc'),
                'pro_affiliation': match_result.get('pro_affiliation', 'unknown'),
                'acrcloud_response': match_result.get('external_metadata', {}),
            })
        
        detection = AudioDetection.objects.create(**detection_data)
        
        # Invalidate relevant caches
        CacheInvalidator.invalidate_on_playlog_create(
            station_id, 
            match_result.get('song_id') if match_result else None,
            None  # We don't have artist_id directly
        )
        
        self.update_state(state='PROGRESS', meta={'progress': 100, 'status': 'Detection completed'})
        
        return {
            'success': True,
            'detection_id': str(detection.detection_id),
            'detection_source': detection_source,
            'match_found': bool(match_result),
            'confidence': match_result.get('confidence', 0) if match_result else 0,
            'processing_time_ms': processing_metadata.get('total_processing_time_ms', 0)
        }
        
    except Exception as e:
        logger.error(f"Audio detection task failed: {e}")
        raise


@shared_task(base=EnhancedTask, bind=True, queue='high')
@with_progress_tracking
def batch_fingerprint_tracks_task(self, track_ids: List[int], config_name: str = 'balanced') -> Dict[str, Any]:
    """
    Batch fingerprinting task with progress tracking and optimization
    """
    try:
        from music_monitor.services.enhanced_fingerprinting import EnhancedFingerprintService
        from artists.models import Track
        
        # Initialize service
        service = EnhancedFingerprintService(config_name)
        
        # Get optimal batch size based on system load
        optimal_batch_size = PerformanceOptimizer.get_optimal_batch_size('fingerprinting')
        
        # Process in batches
        batch_processor = BatchProcessor(batch_size=optimal_batch_size, max_workers=2)
        
        def process_batch(batch_track_ids):
            """Process a batch of tracks"""
            batch_results = {'successful': 0, 'failed': 0, 'errors': []}
            
            for track_id in batch_track_ids:
                try:
                    track = Track.objects.get(id=track_id)
                    success = service.fingerprint_track(track)
                    
                    if success:
                        track.fingerprinted = True
                        track.save(update_fields=['fingerprinted'])
                        batch_results['successful'] += 1
                        
                        # Invalidate track cache
                        CacheInvalidator.invalidate_on_track_update(track_id, track.artist_id)
                    else:
                        batch_results['failed'] += 1
                        batch_results['errors'].append(f"Track {track_id}: Fingerprinting failed")
                        
                except Track.DoesNotExist:
                    batch_results['failed'] += 1
                    batch_results['errors'].append(f"Track {track_id}: Not found")
                except Exception as e:
                    batch_results['failed'] += 1
                    batch_results['errors'].append(f"Track {track_id}: {str(e)}")
            
            return batch_results
        
        # Process all batches
        results = batch_processor.process_in_batches(
            track_ids, 
            process_batch, 
            task_id=self.request.id
        )
        
        return {
            'success': True,
            'total_tracks': len(track_ids),
            'successful': results['successful'],
            'failed': results['failed'],
            'errors': results['errors'][:10],  # Limit errors in response
            'success_rate': results['success_rate']
        }
        
    except Exception as e:
        logger.error(f"Batch fingerprinting task failed: {e}")
        raise


# Royalty Calculation Tasks
@shared_task(base=EnhancedTask, bind=True, queue='normal')
@with_progress_tracking
def calculate_royalty_distributions_task(self, play_log_ids: List[int]) -> Dict[str, Any]:
    """
    Calculate royalty distributions for play logs with enhanced processing
    """
    try:
        from music_monitor.models import PlayLog, RoyaltyDistribution
        from royalties.services.royalty_calculator import EnhancedRoyaltyCalculator
        
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Initializing calculator'})
        
        # Initialize calculator
        calculator = EnhancedRoyaltyCalculator()
        
        # Get play logs
        play_logs = PlayLog.objects.filter(
            id__in=play_log_ids,
            claimed=False
        ).select_related('track', 'station', 'track__artist')
        
        if not play_logs.exists():
            return {
                'success': True,
                'message': 'No unclaimed play logs found',
                'processed': 0
            }
        
        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': f'Processing {play_logs.count()} play logs'})
        
        total_distributions = 0
        total_amount = 0
        errors = []
        
        # Process each play log
        for idx, play_log in enumerate(play_logs):
            try:
                with transaction.atomic():
                    # Calculate distributions
                    distributions = calculator.calculate_royalties(play_log)
                    
                    # Create distribution records
                    for distribution in distributions:
                        RoyaltyDistribution.objects.create(**distribution)
                        total_amount += distribution['net_amount']
                    
                    total_distributions += len(distributions)
                    
                    # Mark play log as claimed
                    play_log.claimed = True
                    play_log.save(update_fields=['claimed'])
                
                # Update progress
                progress = 30 + int((idx + 1) / play_logs.count() * 60)
                self.update_state(
                    state='PROGRESS', 
                    meta={
                        'progress': progress, 
                        'status': f'Processed {idx + 1}/{play_logs.count()} play logs'
                    }
                )
                
            except Exception as e:
                errors.append(f"Play log {play_log.id}: {str(e)}")
                logger.error(f"Failed to calculate royalties for play log {play_log.id}: {e}")
        
        # Invalidate royalty caches
        for play_log in play_logs:
            if play_log.track and play_log.track.artist:
                CacheInvalidator.invalidate_on_royalty_calculation(play_log.track.artist.user_id)
        
        self.update_state(state='PROGRESS', meta={'progress': 100, 'status': 'Royalty calculations completed'})
        
        return {
            'success': True,
            'processed': play_logs.count(),
            'total_distributions': total_distributions,
            'total_amount': float(total_amount),
            'errors': errors[:10]  # Limit errors in response
        }
        
    except Exception as e:
        logger.error(f"Royalty calculation task failed: {e}")
        raise


@shared_task(base=EnhancedTask, bind=True, queue='normal')
@with_progress_tracking
def process_royalty_cycle_task(self, cycle_id: int) -> Dict[str, Any]:
    """
    Process a complete royalty cycle with all calculations and distributions
    """
    try:
        from royalties.models import RoyaltyCycle, RoyaltyLineItem
        from royalties.services.cycle_processor import RoyaltyCycleProcessor
        
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Loading royalty cycle'})
        
        # Get royalty cycle
        cycle = RoyaltyCycle.objects.get(id=cycle_id)
        
        if cycle.status != 'Open':
            return {
                'success': False,
                'error': f'Cycle {cycle_id} is not open for processing'
            }
        
        # Initialize processor
        processor = RoyaltyCycleProcessor(cycle)
        
        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': 'Processing usage data'})
        
        # Process the cycle
        results = processor.process_cycle(
            progress_callback=lambda p, msg: self.update_state(
                state='PROGRESS', 
                meta={'progress': 30 + int(p * 0.6), 'status': msg}
            )
        )
        
        self.update_state(state='PROGRESS', meta={'progress': 95, 'status': 'Finalizing cycle'})
        
        # Update cycle status
        cycle.status = 'Locked'
        cycle.save(update_fields=['status'])
        
        # Invalidate cycle cache
        from core.caching_service import RoyaltyCacheService
        RoyaltyCacheService.delete('royalty', f'cycle:{cycle_id}')
        
        self.update_state(state='PROGRESS', meta={'progress': 100, 'status': 'Cycle processing completed'})
        
        return {
            'success': True,
            'cycle_id': cycle_id,
            'total_line_items': results.get('total_line_items', 0),
            'total_gross_amount': float(results.get('total_gross_amount', 0)),
            'total_net_amount': float(results.get('total_net_amount', 0)),
            'processing_time_seconds': results.get('processing_time_seconds', 0)
        }
        
    except Exception as e:
        logger.error(f"Royalty cycle processing task failed: {e}")
        raise


# Analytics and Reporting Tasks
@shared_task(base=EnhancedTask, bind=True, queue='analytics')
@with_progress_tracking
def generate_analytics_report_task(self, report_type: str, entity_id: int, 
                                 date_range: Dict[str, str], **kwargs) -> Dict[str, Any]:
    """
    Generate analytics reports with caching and optimization
    """
    try:
        from analytics.services.report_generator import AnalyticsReportGenerator
        from core.caching_service import AnalyticsCacheService
        
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Initializing report generator'})
        
        # Check cache first
        cache_key = f"{report_type}:{entity_id}:{date_range['start']}:{date_range['end']}"
        cached_report = AnalyticsCacheService.get('analytics', f'report:{cache_key}')
        
        if cached_report:
            return {
                'success': True,
                'cached': True,
                'report_data': cached_report
            }
        
        # Generate report
        generator = AnalyticsReportGenerator()
        
        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': 'Collecting data'})
        
        report_data = generator.generate_report(
            report_type, 
            entity_id, 
            date_range,
            progress_callback=lambda p, msg: self.update_state(
                state='PROGRESS', 
                meta={'progress': 30 + int(p * 0.6), 'status': msg}
            ),
            **kwargs
        )
        
        self.update_state(state='PROGRESS', meta={'progress': 95, 'status': 'Caching report'})
        
        # Cache the report
        AnalyticsCacheService.set('analytics', f'report:{cache_key}', report_data, 'long')
        
        self.update_state(state='PROGRESS', meta={'progress': 100, 'status': 'Report generated'})
        
        return {
            'success': True,
            'cached': False,
            'report_data': report_data,
            'generation_time_seconds': report_data.get('generation_time_seconds', 0)
        }
        
    except Exception as e:
        logger.error(f"Analytics report generation task failed: {e}")
        raise


# Maintenance and Cleanup Tasks
@shared_task(base=EnhancedTask, bind=True, queue='low')
@with_progress_tracking
def cleanup_old_data_task(self, days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Clean up old data to maintain database performance
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Starting cleanup'})
        
        cleanup_results = {}
        
        # Clean up old audit logs
        from accounts.models import AuditLog
        old_logs_count = AuditLog.objects.filter(timestamp__lt=cutoff_date).count()
        
        if old_logs_count > 0:
            self.update_state(state='PROGRESS', meta={'progress': 30, 'status': f'Cleaning {old_logs_count} audit logs'})
            deleted_logs = AuditLog.objects.filter(timestamp__lt=cutoff_date).delete()[0]
            cleanup_results['audit_logs_deleted'] = deleted_logs
        
        # Clean up old fingerprint versions
        from artists.models import Fingerprint
        self.update_state(state='PROGRESS', meta={'progress': 50, 'status': 'Cleaning old fingerprints'})
        
        # Keep only the latest 2 versions
        from django.db.models import Count
        version_stats = Fingerprint.objects.values('version').annotate(
            count=Count('id')
        ).order_by('-version')
        
        if len(version_stats) > 2:
            versions_to_keep = [v['version'] for v in version_stats[:2]]
            old_fingerprints = Fingerprint.objects.exclude(version__in=versions_to_keep)
            deleted_fingerprints = old_fingerprints.delete()[0]
            cleanup_results['fingerprints_deleted'] = deleted_fingerprints
        
        # Clean up processed audio detections older than cutoff
        from music_monitor.models import AudioDetection
        self.update_state(state='PROGRESS', meta={'progress': 70, 'status': 'Archiving old detections'})
        
        old_detections = AudioDetection.objects.filter(
            detected_at__lt=cutoff_date,
            processing_status='completed'
        )
        
        # Instead of deleting, we could archive to a separate table
        # For now, we'll just count them
        cleanup_results['detections_to_archive'] = old_detections.count()
        
        # Update cache statistics
        self.update_state(state='PROGRESS', meta={'progress': 90, 'status': 'Updating statistics'})
        
        from core.database_optimization import DatabaseMaintenance
        DatabaseMaintenance.update_table_statistics()
        
        self.update_state(state='PROGRESS', meta={'progress': 100, 'status': 'Cleanup completed'})
        
        return {
            'success': True,
            'cutoff_date': cutoff_date.isoformat(),
            'cleanup_results': cleanup_results
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        raise


@shared_task(base=EnhancedTask, bind=True, queue='low')
def warm_cache_task(self, cache_types: List[str] = None) -> Dict[str, Any]:
    """
    Warm cache with frequently accessed data
    """
    try:
        from core.caching_service import CacheWarmer
        
        cache_types = cache_types or ['users', 'analytics', 'tracks']
        results = {}
        
        if 'users' in cache_types:
            CacheWarmer.warm_user_caches()
            results['users'] = 'completed'
        
        if 'analytics' in cache_types:
            CacheWarmer.warm_analytics_caches()
            results['analytics'] = 'completed'
        
        if 'tracks' in cache_types:
            CacheWarmer.warm_track_caches()
            results['tracks'] = 'completed'
        
        return {
            'success': True,
            'cache_types_warmed': cache_types,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Cache warming task failed: {e}")
        raise


# Task orchestration functions
def schedule_audio_processing_pipeline(audio_data_b64: str, station_id: int, 
                                     session_id: str, audio_timestamp: str) -> str:
    """
    Schedule the complete audio processing pipeline
    """
    # Schedule audio detection
    detection_task_id = TaskScheduler.schedule_task(
        enhanced_audio_detection_task,
        'audio_detection',
        args=(audio_data_b64, station_id, session_id, audio_timestamp),
        priority='critical'
    )
    
    logger.info(f"Scheduled audio processing pipeline with detection task {detection_task_id}")
    return detection_task_id


def schedule_batch_fingerprinting(track_ids: List[int], config_name: str = 'balanced') -> List[str]:
    """
    Schedule batch fingerprinting with optimal batching
    """
    return TaskScheduler.schedule_batch_task(
        batch_fingerprint_tracks_task,
        track_ids,
        'fingerprinting',
        processor_kwargs={'config_name': config_name}
    )


def schedule_royalty_processing(play_log_ids: List[int]) -> str:
    """
    Schedule royalty calculation and distribution
    """
    return TaskScheduler.schedule_task(
        calculate_royalty_distributions_task,
        'royalty_calculation',
        args=(play_log_ids,),
        priority='normal'
    )
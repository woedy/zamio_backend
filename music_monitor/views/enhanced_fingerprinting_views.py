"""
Enhanced Fingerprinting API Views
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from celery.result import AsyncResult

from artists.models import Track
from music_monitor.services.enhanced_fingerprinting import (
    EnhancedFingerprintService,
    get_system_fingerprint_stats
)
from music_monitor.tasks import (
    enhanced_fingerprint_track,
    batch_enhanced_fingerprint,
    auto_fingerprint_new_tracks
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fingerprint_track(request):
    """
    Fingerprint a single track with enhanced processing
    
    POST /api/music-monitor/fingerprint/track/
    {
        "track_id": 123,
        "config": "balanced",  // optional: fast, balanced, high_quality
        "force_reprocess": false,  // optional
        "async": true  // optional: process asynchronously
    }
    """
    try:
        track_id = request.data.get('track_id')
        if not track_id:
            return Response(
                {'error': 'track_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate track exists and user has access
        track = get_object_or_404(Track, id=track_id)
        
        # Check permissions (artist owns track or admin)
        if not (track.artist.user == request.user or request.user.is_staff):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        config_name = request.data.get('config', 'balanced')
        force_reprocess = request.data.get('force_reprocess', False)
        async_processing = request.data.get('async', True)
        
        if async_processing:
            # Process asynchronously
            task = enhanced_fingerprint_track.delay(
                track_id, config_name, force_reprocess
            )
            
            return Response({
                'success': True,
                'message': 'Fingerprinting started',
                'task_id': task.id,
                'track_id': track_id,
                'async': True
            })
        else:
            # Process synchronously
            service = EnhancedFingerprintService(config_name)
            success = service.fingerprint_track(track, force_reprocess)
            
            if success:
                track.fingerprinted = True
                track.save(update_fields=['fingerprinted'])
                
                return Response({
                    'success': True,
                    'message': f'Successfully fingerprinted track: {track.title}',
                    'track_id': track_id,
                    'async': False
                })
            else:
                return Response(
                    {'error': 'Fingerprinting failed'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_fingerprint_tracks(request):
    """
    Batch fingerprint multiple tracks
    
    POST /api/music-monitor/fingerprint/batch/
    {
        "track_ids": [1, 2, 3],
        "config": "balanced",  // optional
        "force_reprocess": false,  // optional
        "max_workers": 4,  // optional
        "async": true  // optional
    }
    """
    try:
        track_ids = request.data.get('track_ids', [])
        if not track_ids:
            return Response(
                {'error': 'track_ids is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate tracks exist and user has access
        if not request.user.is_staff:
            # Non-admin users can only fingerprint their own tracks
            user_tracks = Track.objects.filter(
                id__in=track_ids,
                artist__user=request.user
            ).values_list('id', flat=True)
            
            if len(user_tracks) != len(track_ids):
                return Response(
                    {'error': 'Permission denied for some tracks'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        config_name = request.data.get('config', 'balanced')
        force_reprocess = request.data.get('force_reprocess', False)
        max_workers = request.data.get('max_workers', 4)
        async_processing = request.data.get('async', True)
        
        if async_processing:
            # Process asynchronously
            task = batch_enhanced_fingerprint.delay(
                track_ids, config_name, force_reprocess, max_workers
            )
            
            return Response({
                'success': True,
                'message': 'Batch fingerprinting started',
                'task_id': task.id,
                'track_count': len(track_ids),
                'async': True
            })
        else:
            # Process synchronously (not recommended for large batches)
            service = EnhancedFingerprintService(config_name)
            results = service.batch_fingerprint_tracks(
                track_ids, max_workers, force_reprocess
            )
            
            # Update fingerprinted status for successful tracks
            if results['successful'] > 0:
                successful_track_ids = [
                    tid for tid in track_ids 
                    if tid not in results.get('failed_tracks', [])
                ]
                Track.objects.filter(id__in=successful_track_ids).update(fingerprinted=True)
            
            return Response({
                'success': True,
                'results': results,
                'async': False
            })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fingerprint_task_status(request, task_id):
    """
    Get status of a fingerprinting task
    
    GET /api/music-monitor/fingerprint/task/{task_id}/
    """
    try:
        task_result = AsyncResult(task_id)
        
        response_data = {
            'task_id': task_id,
            'status': task_result.status,
            'ready': task_result.ready()
        }
        
        if task_result.ready():
            if task_result.successful():
                response_data['result'] = task_result.result
            else:
                response_data['error'] = str(task_result.result)
        else:
            response_data['info'] = task_result.info
        
        return Response(response_data)
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fingerprint_statistics(request):
    """
    Get fingerprint statistics
    
    GET /api/music-monitor/fingerprint/stats/
    """
    try:
        stats = get_system_fingerprint_stats()
        
        # Add user-specific stats if not admin
        if not request.user.is_staff:
            from django.db.models import Count
            from artists.models import Fingerprint
            
            user_stats = Fingerprint.objects.filter(
                track__artist__user=request.user
            ).aggregate(
                total=Count('id'),
                current_version=Count('id', filter=Q(metadata__version=EnhancedFingerprintService.CURRENT_VERSION))
            )
            
            stats['user_fingerprints'] = user_stats['total']
            stats['user_current_version'] = user_stats['current_version']
        
        return Response(stats)
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auto_fingerprint_new(request):
    """
    Trigger automatic fingerprinting of new tracks
    
    POST /api/music-monitor/fingerprint/auto/
    {
        "config": "balanced"  // optional
    }
    """
    try:
        # Only admin users can trigger auto-fingerprinting
        if not request.user.is_staff:
            return Response(
                {'error': 'Admin access required'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        config_name = request.data.get('config', 'balanced')
        
        # Start auto-fingerprinting task
        task = auto_fingerprint_new_tracks.delay(config_name)
        
        return Response({
            'success': True,
            'message': 'Auto-fingerprinting started',
            'task_id': task.id
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def track_fingerprint_status(request, track_id):
    """
    Get fingerprint status for a specific track
    
    GET /api/music-monitor/fingerprint/track/{track_id}/status/
    """
    try:
        track = get_object_or_404(Track, id=track_id)
        
        # Check permissions
        if not (track.artist.user == request.user or request.user.is_staff):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        from artists.models import Fingerprint
        from django.db.models import Count, Max
        
        # Get fingerprint information
        fingerprint_stats = Fingerprint.objects.filter(track=track).aggregate(
            total_fingerprints=Count('id'),
            latest_version=Max('version')
        )
        
        current_version = EnhancedFingerprintService.CURRENT_VERSION
        has_current_version = Fingerprint.objects.filter(
            track=track,
            metadata__version=current_version
        ).exists()
        
        # Get latest fingerprint metadata
        latest_fingerprint = Fingerprint.objects.filter(track=track).order_by('-date_created').first()
        
        response_data = {
            'track_id': track_id,
            'track_title': track.title,
            'fingerprinted': track.fingerprinted,
            'total_fingerprints': fingerprint_stats['total_fingerprints'] or 0,
            'latest_version': fingerprint_stats['latest_version'],
            'current_version': current_version,
            'has_current_version': has_current_version,
            'needs_update': not has_current_version and fingerprint_stats['total_fingerprints'] > 0
        }
        
        if latest_fingerprint and latest_fingerprint.metadata:
            response_data['latest_metadata'] = {
                'quality_score': latest_fingerprint.metadata.get('quality_score'),
                'processing_time_ms': latest_fingerprint.metadata.get('processing_time_ms'),
                'hash_count': latest_fingerprint.metadata.get('hash_count'),
                'created_at': latest_fingerprint.metadata.get('created_at')
            }
        
        return Response(response_data)
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
"""
ACRCloud Integration API Views
"""

import base64
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone

from music_monitor.services.acrcloud_client import ACRCloudClient, PROMapper, HybridDetectionService
from music_monitor.services.isrc_lookup_service import ISRCLookupService
from music_monitor.tasks import (
    acrcloud_identify_audio, 
    hybrid_audio_detection,
    update_isrc_metadata
)
from artists.models import Fingerprint

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_acrcloud_identification(request):
    """
    Test ACRCloud identification with uploaded audio
    """
    try:
        # Get audio file from request
        audio_file = request.FILES.get('audio_file')
        if not audio_file:
            return Response({
                'error': 'No audio file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Read audio data
        audio_data = audio_file.read()
        
        # Initialize ACRCloud client
        client = ACRCloudClient()
        
        # Identify audio
        result = client.identify_audio(audio_data)
        
        if result:
            # Map to PROs if ISRC available
            pro_affiliations = []
            if result.isrc:
                pro_mapper = PROMapper()
                affiliations = pro_mapper.map_isrc_to_pro(result.isrc)
                pro_affiliations = [
                    {
                        'pro_code': aff.pro_code,
                        'pro_name': aff.pro_name,
                        'territory': aff.territory,
                        'publisher': aff.publisher,
                        'share_percentage': aff.share_percentage
                    }
                    for aff in affiliations
                ]
            
            return Response({
                'success': True,
                'result': {
                    'title': result.title,
                    'artist': result.artist,
                    'album': result.album,
                    'isrc': result.isrc,
                    'iswc': result.iswc,
                    'confidence': result.confidence,
                    'duration_ms': result.duration_ms,
                    'acrid': result.acrid,
                    'label': result.label,
                    'release_date': result.release_date,
                    'pro_affiliations': pro_affiliations
                }
            })
        else:
            return Response({
                'success': False,
                'message': 'No match found'
            })
            
    except Exception as e:
        logger.error(f"ACRCloud identification test error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_hybrid_detection(request):
    """
    Test hybrid detection (local + ACRCloud fallback)
    """
    try:
        # Get audio file from request
        audio_file = request.FILES.get('audio_file')
        if not audio_file:
            return Response({
                'error': 'No audio file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Read audio data
        audio_data = audio_file.read()
        
        # Get local fingerprints
        local_fingerprints = list(
            Fingerprint.objects.select_related('track').values_list(
                'track_id', 'hash', 'offset'
            )
        )
        
        # Initialize hybrid detection service
        hybrid_service = HybridDetectionService()
        
        # Perform detection
        match_result, detection_source, processing_metadata = hybrid_service.identify_with_fallback(
            audio_data, local_fingerprints, session_id='test_session'
        )
        
        return Response({
            'success': True,
            'detection_source': detection_source,
            'match_result': match_result,
            'processing_metadata': processing_metadata
        })
        
    except Exception as e:
        logger.error(f"Hybrid detection test error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lookup_isrc(request, isrc):
    """
    Lookup metadata for a specific ISRC
    """
    try:
        service = ISRCLookupService()
        result = service.lookup_isrc(isrc)
        
        if result:
            return Response({
                'success': True,
                'result': {
                    'isrc': result.isrc,
                    'title': result.title,
                    'artist': result.artist,
                    'album': result.album,
                    'label': result.label,
                    'release_date': result.release_date,
                    'duration_ms': result.duration_ms,
                    'genre': result.genre,
                    'confidence': result.confidence,
                    'pro_affiliations': result.pro_affiliations,
                    'publishers': result.publishers,
                    'writers': result.writers,
                    'external_ids': result.external_ids,
                    'lookup_source': result.lookup_source,
                    'last_updated': result.last_updated
                }
            })
        else:
            return Response({
                'success': False,
                'message': f'No metadata found for ISRC: {isrc}'
            })
            
    except Exception as e:
        logger.error(f"ISRC lookup error for {isrc}: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_lookup_isrcs(request):
    """
    Batch lookup multiple ISRCs
    """
    try:
        isrcs = request.data.get('isrcs', [])
        if not isrcs or not isinstance(isrcs, list):
            return Response({
                'error': 'Please provide a list of ISRCs'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        service = ISRCLookupService()
        results = service.batch_lookup_isrcs(isrcs)
        
        # Format results
        formatted_results = {}
        for isrc, result in results.items():
            if result:
                formatted_results[isrc] = {
                    'success': True,
                    'title': result.title,
                    'artist': result.artist,
                    'album': result.album,
                    'confidence': result.confidence,
                    'pro_affiliations': len(result.pro_affiliations)
                }
            else:
                formatted_results[isrc] = {
                    'success': False,
                    'message': 'No metadata found'
                }
        
        return Response({
            'success': True,
            'results': formatted_results,
            'total_processed': len(isrcs),
            'successful_lookups': sum(1 for r in results.values() if r is not None)
        })
        
    except Exception as e:
        logger.error(f"Batch ISRC lookup error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pro_mappings(request):
    """
    Get all available PRO mappings
    """
    try:
        mapper = PROMapper()
        
        return Response({
            'success': True,
            'pro_mappings': mapper.PRO_MAPPINGS,
            'territory_mappings': mapper.TERRITORY_PRO_MAP,
            'total_pros': len(mapper.PRO_MAPPINGS)
        })
        
    except Exception as e:
        logger.error(f"PRO mappings error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_detection_statistics(request):
    """
    Get detection service statistics
    """
    try:
        hybrid_service = HybridDetectionService()
        isrc_service = ISRCLookupService()
        
        stats = {
            'hybrid_detection': hybrid_service.get_detection_statistics(),
            'isrc_lookup': isrc_service.get_lookup_statistics(),
            'configuration': {
                'acrcloud_configured': bool(
                    getattr(settings, 'ACRCLOUD_ACCESS_KEY', '') and
                    getattr(settings, 'ACRCLOUD_ACCESS_SECRET', '')
                ),
                'audio_detection_config': getattr(settings, 'AUDIO_DETECTION_CONFIG', {}),
                'pro_integration_config': getattr(settings, 'PRO_INTEGRATION_CONFIG', {})
            }
        }
        
        return Response({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Detection statistics error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_isrc_update(request, isrc):
    """
    Trigger background update of ISRC metadata
    """
    try:
        # Trigger async task
        task = update_isrc_metadata.delay(isrc)
        
        return Response({
            'success': True,
            'message': f'ISRC update task triggered for {isrc}',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"ISRC update trigger error for {isrc}: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_hybrid_detection_task(request):
    """
    Trigger background hybrid detection task
    """
    try:
        # Get parameters
        audio_file = request.FILES.get('audio_file')
        station_id = request.data.get('station_id')
        
        if not audio_file or not station_id:
            return Response({
                'error': 'audio_file and station_id are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Encode audio data
        audio_data = audio_file.read()
        audio_data_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Generate session ID
        session_id = f"api_test_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        audio_timestamp = timezone.now().isoformat()
        
        # Trigger async task
        task = hybrid_audio_detection.delay(
            audio_data_b64, session_id, int(station_id), audio_timestamp
        )
        
        return Response({
            'success': True,
            'message': 'Hybrid detection task triggered',
            'task_id': task.id,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Hybrid detection task trigger error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_isrc_update(request, isrc):
    """
    Trigger background update of ISRC metadata
    """
    try:
        # Trigger async task
        task = update_isrc_metadata.delay(isrc)
        
        return Response({
            'success': True,
            'task_id': task.id,
            'isrc': isrc,
            'message': f'ISRC update task started for {isrc}'
        })
        
    except Exception as e:
        logger.error(f"Failed to trigger ISRC update for {isrc}: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_hybrid_detection_task(request):
    """
    Trigger hybrid detection task for uploaded audio
    """
    try:
        # Get audio file and parameters
        audio_file = request.FILES.get('audio_file')
        station_id = request.data.get('station_id')
        session_id = request.data.get('session_id', 'manual_test')
        
        if not audio_file:
            return Response({
                'error': 'No audio file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not station_id:
            return Response({
                'error': 'Station ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Read audio data
        audio_data = audio_file.read()
        
        # Trigger async task
        task = hybrid_audio_detection.delay(
            audio_data, 
            int(station_id), 
            session_id,
            timezone.now().isoformat()
        )
        
        return Response({
            'success': True,
            'task_id': task.id,
            'session_id': session_id,
            'station_id': station_id,
            'message': 'Hybrid detection task started'
        })
        
    except Exception as e:
        logger.error(f"Failed to trigger hybrid detection task: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
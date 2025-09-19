import io
import subprocess
from typing import List, Tuple, Dict, Any

from celery import shared_task
from django.utils import timezone
from django.db import transaction

import librosa

from artists.models import Track, Fingerprint
from stations.models import Station, StationStreamLink
from music_monitor.models import MatchCache, AudioDetection
from music_monitor.utils.match_engine import simple_match, simple_match_mp3
from music_monitor.services.enhanced_fingerprinting import EnhancedFingerprintService


def _capture_stream_wav_bytes(stream_url: str, duration_seconds: int = 20, sample_rate: int = 44100, channels: int = 1) -> bytes:
    """Capture a short chunk from stream as WAV bytes using ffmpeg."""
    cmd = [
        'ffmpeg', '-y',
        '-i', stream_url,
        '-f', 'wav',
        '-ar', str(sample_rate),
        '-ac', str(channels),
        '-t', str(duration_seconds),
        '-'
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    audio_data, _ = proc.communicate()
    if proc.returncode != 0:
        return b''
    return audio_data


def _load_samples(wav_bytes: bytes, sr: int = 44100):
    if not wav_bytes:
        return None, None
    try:
        samples, loaded_sr = librosa.load(io.BytesIO(wav_bytes), sr=sr, mono=True)
        return samples, loaded_sr
    except Exception:
        return None, None


def _get_all_fingerprints() -> List[Tuple[int, str, int]]:
    # (track_id, hash, offset)
    return list(Fingerprint.objects.select_related('track').values_list('track_id', 'hash', 'offset'))


@shared_task(name='music_monitor.scan_single_station_stream')
def scan_single_station_stream(station_id: int, stream_url: str, duration_seconds: int = 20) -> dict:
    """Capture a small window from a station stream and try to match it."""
    try:
        wav_bytes = _capture_stream_wav_bytes(stream_url, duration_seconds=duration_seconds)
        samples, sr = _load_samples(wav_bytes, sr=44100)
        if samples is None or len(samples) == 0:
            return {"ok": False, "reason": "no_audio"}

        fps = _get_all_fingerprints()
        if not fps:
            return {"ok": False, "reason": "no_fingerprints"}

        # For short clips, using simple_match_mp3 is reasonable
        result = simple_match_mp3(samples, sr, fps, min_match_threshold=5)
        if result.get('match'):
            track = Track.objects.get(id=result['song_id'])
            station = Station.objects.get(id=station_id)
            confidence_score = float(result.get('confidence', 0))
            MatchCache.objects.create(
                track=track,
                station=station,
                station_program=None,
                matched_at=timezone.now(),
                avg_confidence_score=confidence_score,
                processed=False
            )
            return {"ok": True, "match": True, "track_id": track.id, "confidence": confidence_score}

        return {"ok": True, "match": False}

    except Exception as e:
        return {"ok": False, "error": str(e)}


@shared_task(name='music_monitor.scan_station_streams')
def scan_station_streams() -> dict:
    """Scan all active station stream links once. Intended to be triggered by Celery Beat."""
    total = 0
    scheduled = 0
    for link in StationStreamLink.objects.select_related('station').filter(active=True, is_archived=False):
        station = link.station
        if not station or station.is_archived:
            continue
        total += 1
        # Fan out tasks per link to avoid blocking
        scan_single_station_stream.delay(station.id, link.link)
        scheduled += 1
    return {"ok": True, "total_links": total, "scheduled": scheduled}



# Enhanced Fingerprinting Tasks

@shared_task(name='music_monitor.enhanced_fingerprint_track')
def enhanced_fingerprint_track(track_id: int, config_name: str = 'balanced', 
                             force_reprocess: bool = False) -> Dict[str, Any]:
    """
    Enhanced fingerprinting task for a single track
    
    Args:
        track_id: ID of track to fingerprint
        config_name: Configuration to use ('fast', 'balanced', 'high_quality')
        force_reprocess: Whether to reprocess existing fingerprints
        
    Returns:
        Dictionary with processing results
    """
    try:
        track = Track.objects.get(id=track_id)
        service = EnhancedFingerprintService(config_name)
        
        success = service.fingerprint_track(track, force_reprocess)
        
        if success:
            # Update track fingerprinted status
            track.fingerprinted = True
            track.save(update_fields=['fingerprinted'])
            
            return {
                'success': True,
                'track_id': track_id,
                'message': f'Successfully fingerprinted track {track.title}'
            }
        else:
            return {
                'success': False,
                'track_id': track_id,
                'error': 'Fingerprinting failed'
            }
            
    except Track.DoesNotExist:
        return {
            'success': False,
            'track_id': track_id,
            'error': 'Track not found'
        }
    except Exception as e:
        return {
            'success': False,
            'track_id': track_id,
            'error': str(e)
        }


@shared_task(name='music_monitor.batch_enhanced_fingerprint')
def batch_enhanced_fingerprint(track_ids: List[int], config_name: str = 'balanced',
                             force_reprocess: bool = False, max_workers: int = 2) -> Dict[str, Any]:
    """
    Batch enhanced fingerprinting task
    
    Args:
        track_ids: List of track IDs to process
        config_name: Configuration to use
        force_reprocess: Whether to reprocess existing fingerprints
        max_workers: Maximum number of parallel workers
        
    Returns:
        Dictionary with batch processing results
    """
    try:
        service = EnhancedFingerprintService(config_name)
        results = service.batch_fingerprint_tracks(track_ids, max_workers, force_reprocess)
        
        # Update fingerprinted status for successful tracks
        if results['successful'] > 0:
            successful_track_ids = [
                tid for tid in track_ids 
                if tid not in results.get('failed_tracks', [])
            ]
            Track.objects.filter(id__in=successful_track_ids).update(fingerprinted=True)
        
        return results
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'total_tracks': len(track_ids),
            'successful': 0,
            'failed': len(track_ids)
        }


@shared_task(name='music_monitor.auto_fingerprint_new_tracks')
def auto_fingerprint_new_tracks(config_name: str = 'balanced') -> Dict[str, Any]:
    """
    Automatically fingerprint newly uploaded tracks that haven't been processed
    
    Args:
        config_name: Configuration to use for fingerprinting
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Find tracks that need fingerprinting
        current_version = EnhancedFingerprintService.CURRENT_VERSION
        
        unprocessed_tracks = Track.objects.filter(
            active=True,
            is_archived=False,
            audio_file__isnull=False
        ).exclude(
            fingerprint_track__metadata__version=current_version
        ).values_list('id', flat=True)[:50]  # Limit to 50 tracks per run
        
        if not unprocessed_tracks:
            return {
                'success': True,
                'message': 'No new tracks to fingerprint',
                'processed': 0
            }
        
        # Process tracks
        service = EnhancedFingerprintService(config_name)
        results = service.batch_fingerprint_tracks(list(unprocessed_tracks), max_workers=2)
        
        # Update fingerprinted status
        if results['successful'] > 0:
            successful_track_ids = [
                tid for tid in unprocessed_tracks 
                if tid not in results.get('failed_tracks', [])
            ]
            Track.objects.filter(id__in=successful_track_ids).update(fingerprinted=True)
        
        return {
            'success': True,
            'processed': results['total_tracks'],
            'successful': results['successful'],
            'failed': results['failed'],
            'processing_time': results['processing_time_seconds']
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='music_monitor.enhanced_audio_detection')
def enhanced_audio_detection(audio_data: bytes, station_id: int, session_id: str,
                           audio_timestamp: str, detection_source: str = 'local') -> Dict[str, Any]:
    """
    Enhanced audio detection task with quality assessment and metadata tracking
    
    Args:
        audio_data: Raw audio data bytes
        station_id: ID of the station
        session_id: Session identifier
        audio_timestamp: Timestamp of the audio capture
        detection_source: Source of detection ('local', 'acrcloud', 'hybrid')
        
    Returns:
        Dictionary with detection results
    """
    try:
        # Load audio samples
        samples, sr = librosa.load(io.BytesIO(audio_data), sr=44100, mono=True)
        
        if len(samples) == 0:
            return {
                'success': False,
                'error': 'No audio samples found'
            }
        
        # Get station
        station = Station.objects.get(id=station_id)
        
        # Create enhanced fingerprint service for detection
        service = EnhancedFingerprintService('fast')  # Use fast config for real-time detection
        
        # Generate fingerprint for the audio segment
        fingerprint_hashes, metadata = service.enhanced_fingerprint(samples, sr)
        
        if not fingerprint_hashes:
            return {
                'success': False,
                'error': 'No fingerprints generated from audio'
            }
        
        # Get all stored fingerprints for matching
        all_fingerprints = list(
            Fingerprint.objects.select_related('track').values_list(
                'track_id', 'hash', 'offset'
            )
        )
        
        if not all_fingerprints:
            return {
                'success': False,
                'error': 'No stored fingerprints for matching'
            }
        
        # Perform matching
        match_result = simple_match_mp3(samples, sr, all_fingerprints, min_match_threshold=5)
        
        # Create AudioDetection record
        detection = AudioDetection.objects.create(
            session_id=session_id,
            station=station,
            detection_source=detection_source,
            confidence_score=match_result.get('confidence', 0) / 100.0,  # Convert to 0-1 scale
            processing_status='completed' if match_result.get('match') else 'completed',
            audio_fingerprint=str(fingerprint_hashes[:10]),  # Store first 10 hashes as sample
            fingerprint_version=service.CURRENT_VERSION,
            audio_timestamp=audio_timestamp,
            duration_seconds=len(samples) / sr,
            processing_time_ms=metadata.processing_time_ms,
            external_metadata={
                'quality_score': metadata.quality_score,
                'hash_count': metadata.hash_count,
                'peak_count': metadata.peak_count,
                'audio_hash': metadata.audio_hash
            }
        )
        
        result = {
            'success': True,
            'detection_id': str(detection.detection_id),
            'match_found': match_result.get('match', False),
            'confidence': match_result.get('confidence', 0),
            'quality_score': metadata.quality_score
        }
        
        if match_result.get('match'):
            # Get matched track
            track = Track.objects.get(id=match_result['song_id'])
            detection.track = track
            detection.detected_title = track.title
            detection.detected_artist = track.artist.stage_name
            detection.save()
            
            # Create MatchCache entry for backward compatibility
            MatchCache.objects.create(
                track=track,
                station=station,
                matched_at=timezone.now(),
                avg_confidence_score=match_result.get('confidence', 0),
                processed=False
            )
            
            result.update({
                'track_id': track.id,
                'track_title': track.title,
                'artist_name': track.artist.stage_name,
                'hashes_matched': match_result.get('hashes_matched', 0)
            })
        
        return result
        
    except Station.DoesNotExist:
        return {
            'success': False,
            'error': f'Station {station_id} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='music_monitor.cleanup_old_fingerprints')
def cleanup_old_fingerprints(keep_versions: int = 2) -> Dict[str, Any]:
    """
    Clean up old fingerprint versions, keeping only the most recent versions
    
    Args:
        keep_versions: Number of recent versions to keep
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        from django.db.models import Count
        
        # Get version statistics
        version_stats = Fingerprint.objects.values('version').annotate(
            count=Count('id')
        ).order_by('-version')
        
        if len(version_stats) <= keep_versions:
            return {
                'success': True,
                'message': f'Only {len(version_stats)} versions found, no cleanup needed',
                'deleted': 0
            }
        
        # Get versions to delete (keep the most recent ones)
        versions_to_keep = [v['version'] for v in version_stats[:keep_versions]]
        versions_to_delete = [v['version'] for v in version_stats[keep_versions:]]
        
        # Delete old versions
        deleted_count = Fingerprint.objects.filter(
            version__in=versions_to_delete
        ).delete()[0]
        
        return {
            'success': True,
            'deleted': deleted_count,
            'versions_kept': versions_to_keep,
            'versions_deleted': versions_to_delete
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
# ACRCloud Integration and PRO Mapping Tasks

@shared_task(name='music_monitor.acrcloud_identify_audio')
def acrcloud_identify_audio(audio_data_b64: str, session_id: str, station_id: int,
                          audio_timestamp: str) -> Dict[str, Any]:
    """
    Identify audio using ACRCloud and map to PROs
    
    Args:
        audio_data_b64: Base64 encoded audio data
        session_id: Session identifier
        station_id: Station ID
        audio_timestamp: Timestamp of audio capture
        
    Returns:
        Dictionary with identification results
    """
    try:
        import base64
        from music_monitor.services.acrcloud_client import ACRCloudClient, PROMapper
        
        # Decode audio data
        audio_data = base64.b64decode(audio_data_b64)
        
        # Get station
        station = Station.objects.get(id=station_id)
        
        # Initialize ACRCloud client
        acrcloud_client = ACRCloudClient()
        pro_mapper = PROMapper()
        
        # Identify audio
        match = acrcloud_client.identify_audio(audio_data)
        
        if not match:
            return {
                'success': False,
                'error': 'No match found in ACRCloud'
            }
        
        # Map to PROs
        pro_affiliations = []
        if match.isrc:
            pro_affiliations = pro_mapper.map_isrc_to_pro(match.isrc)
        
        # Create AudioDetection record
        detection = AudioDetection.objects.create(
            session_id=session_id,
            station=station,
            detection_source='acrcloud',
            confidence_score=match.confidence / 100.0,
            processing_status='completed',
            detected_title=match.title,
            detected_artist=match.artist,
            detected_album=match.album,
            isrc=match.isrc,
            iswc=match.iswc,
            pro_affiliation=pro_affiliations[0].pro_code if pro_affiliations else 'unknown',
            audio_timestamp=audio_timestamp,
            duration_seconds=match.duration_ms / 1000 if match.duration_ms else None,
            acrcloud_response=match.metadata,
            external_metadata={
                'acrid': match.acrid,
                'label': match.label,
                'release_date': match.release_date,
                'pro_affiliations': [
                    {
                        'pro_code': aff.pro_code,
                        'pro_name': aff.pro_name,
                        'territory': aff.territory,
                        'publisher': aff.publisher,
                        'share_percentage': aff.share_percentage
                    }
                    for aff in pro_affiliations
                ]
            }
        )
        
        return {
            'success': True,
            'detection_id': str(detection.detection_id),
            'match': {
                'title': match.title,
                'artist': match.artist,
                'album': match.album,
                'isrc': match.isrc,
                'confidence': match.confidence,
                'pro_affiliations': len(pro_affiliations)
            }
        }
        
    except Station.DoesNotExist:
        return {
            'success': False,
            'error': f'Station {station_id} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='music_monitor.hybrid_audio_detection')
def hybrid_audio_detection(audio_data_b64: str, session_id: str, station_id: int,
                         audio_timestamp: str, confidence_threshold: float = 0.8) -> Dict[str, Any]:
    """
    Hybrid audio detection using local fingerprints first, then ACRCloud fallback
    
    Args:
        audio_data_b64: Base64 encoded audio data
        session_id: Session identifier
        station_id: Station ID
        audio_timestamp: Timestamp of audio capture
        confidence_threshold: Minimum confidence threshold
        
    Returns:
        Dictionary with detection results
    """
    try:
        import base64
        from music_monitor.services.acrcloud_client import HybridDetectionService
        
        # Decode audio data
        audio_data = base64.b64decode(audio_data_b64)
        
        # Get station
        station = Station.objects.get(id=station_id)
        
        # Get local fingerprints
        local_fingerprints = list(
            Fingerprint.objects.select_related('track').values_list(
                'track_id', 'hash', 'offset'
            )
        )
        
        # Initialize hybrid detection service
        hybrid_service = HybridDetectionService(
            local_confidence_threshold=confidence_threshold,
            acrcloud_confidence_threshold=confidence_threshold * 0.9  # Slightly lower for ACRCloud
        )
        
        # Perform hybrid detection
        match_result, detection_source, processing_metadata = hybrid_service.identify_with_fallback(
            audio_data, local_fingerprints, session_id
        )
        
        if not match_result:
            return {
                'success': False,
                'error': 'No match found in local or ACRCloud detection',
                'detection_source': detection_source,
                'processing_metadata': processing_metadata
            }
        
        # Create AudioDetection record
        detection_data = {
            'session_id': session_id,
            'station': station,
            'detection_source': detection_source,
            'confidence_score': match_result.get('confidence', 0) / 100.0,
            'processing_status': 'completed',
            'audio_timestamp': audio_timestamp,
            'processing_time_ms': processing_metadata.get('total_processing_time_ms', 0),
            'external_metadata': processing_metadata
        }
        
        if detection_source == 'local':
            # Local match - get track information
            track = Track.objects.get(id=match_result['song_id'])
            detection_data.update({
                'track': track,
                'detected_title': track.title,
                'detected_artist': track.artist.stage_name,
                'detected_album': track.album.title if track.album else None,
                'pro_affiliation': 'ghamro',  # Default for local tracks
            })
        elif detection_source == 'acrcloud':
            # ACRCloud match
            detection_data.update({
                'detected_title': match_result.get('title'),
                'detected_artist': match_result.get('artist'),
                'detected_album': match_result.get('album'),
                'isrc': match_result.get('isrc'),
                'iswc': match_result.get('iswc'),
                'pro_affiliation': (
                    match_result.get('pro_affiliations', [{}])[0].get('pro_code', 'unknown')
                    if match_result.get('pro_affiliations') else 'unknown'
                ),
                'acrcloud_response': match_result.get('external_metadata', {}),
            })
            
            # Update external_metadata with PRO affiliations
            detection_data['external_metadata'].update({
                'acrid': match_result.get('acrid'),
                'pro_affiliations': match_result.get('pro_affiliations', []),
                'label': match_result.get('label'),
                'release_date': match_result.get('release_date')
            })
        
        detection = AudioDetection.objects.create(**detection_data)
        
        # Create MatchCache for backward compatibility if local match
        if detection_source == 'local' and 'song_id' in match_result:
            MatchCache.objects.create(
                track_id=match_result['song_id'],
                station=station,
                matched_at=timezone.now(),
                avg_confidence_score=match_result.get('confidence', 0),
                processed=False
            )
        
        return {
            'success': True,
            'detection_id': str(detection.detection_id),
            'detection_source': detection_source,
            'match': match_result,
            'confidence': match_result.get('confidence', 0),
            'processing_metadata': processing_metadata
        }
        
    except Station.DoesNotExist:
        return {
            'success': False,
            'error': f'Station {station_id} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='music_monitor.sync_pro_catalog')
def sync_pro_catalog(pro_id: int, batch_size: int = 100) -> Dict[str, Any]:
    """
    Sync catalog from partner PRO
    
    Args:
        pro_id: PartnerPRO ID
        batch_size: Number of records to process per batch
        
    Returns:
        Dictionary with sync results
    """
    try:
        from royalties.models import PartnerPRO, ExternalWork, ExternalRecording
        
        pro = PartnerPRO.objects.get(id=pro_id)
        
        # This would integrate with the PRO's API to fetch their catalog
        # For now, we'll simulate the process
        
        sync_results = {
            'pro_id': pro_id,
            'pro_name': pro.display_name,
            'works_synced': 0,
            'recordings_synced': 0,
            'errors': []
        }
        
        # Update sync status
        pro.last_sync_at = timezone.now()
        pro.sync_status = 'completed'
        pro.save()
        
        return sync_results
        
    except PartnerPRO.DoesNotExist:
        return {
            'success': False,
            'error': f'PartnerPRO {pro_id} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='music_monitor.update_isrc_metadata')
def update_isrc_metadata(isrc: str) -> Dict[str, Any]:
    """
    Update metadata for a specific ISRC using ACRCloud
    
    Args:
        isrc: International Standard Recording Code
        
    Returns:
        Dictionary with update results
    """
    try:
        from music_monitor.services.acrcloud_client import ACRCloudClient, PROMapper
        
        acrcloud_client = ACRCloudClient()
        pro_mapper = PROMapper()
        
        # Get metadata from ACRCloud
        metadata = acrcloud_client.get_track_metadata(isrc)
        
        if not metadata:
            return {
                'success': False,
                'error': f'No metadata found for ISRC {isrc}'
            }
        
        # Map to PROs
        pro_affiliations = pro_mapper.map_isrc_to_pro(isrc)
        
        # Update any existing AudioDetection records with this ISRC
        updated_count = AudioDetection.objects.filter(isrc=isrc).update(
            external_metadata=metadata,
            pro_affiliation=pro_affiliations[0].pro_code if pro_affiliations else 'unknown'
        )
        
        return {
            'success': True,
            'isrc': isrc,
            'updated_detections': updated_count,
            'pro_affiliations': len(pro_affiliations),
            'metadata_keys': list(metadata.keys()) if metadata else []
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='music_monitor.batch_update_pro_mappings')
def batch_update_pro_mappings(detection_ids: List[str] = None, limit: int = 100) -> Dict[str, Any]:
    """
    Batch update PRO mappings for AudioDetection records
    
    Args:
        detection_ids: Specific detection IDs to update (optional)
        limit: Maximum number of records to process
        
    Returns:
        Dictionary with update results
    """
    try:
        from music_monitor.services.acrcloud_client import PROMapper
        
        pro_mapper = PROMapper()
        
        # Get detections to update
        query = AudioDetection.objects.filter(
            detection_source='acrcloud',
            isrc__isnull=False,
            pro_affiliation__in=['unknown', '', None]
        )
        
        if detection_ids:
            query = query.filter(detection_id__in=detection_ids)
        
        detections = query[:limit]
        
        updated_count = 0
        errors = []
        
        for detection in detections:
            try:
                if detection.isrc:
                    pro_affiliations = pro_mapper.map_isrc_to_pro(detection.isrc)
                    
                    if pro_affiliations:
                        detection.pro_affiliation = pro_affiliations[0].pro_code
                        
                        # Update external metadata with PRO info
                        if not detection.external_metadata:
                            detection.external_metadata = {}
                        
                        detection.external_metadata['pro_affiliations'] = [
                            {
                                'pro_code': aff.pro_code,
                                'pro_name': aff.pro_name,
                                'territory': aff.territory,
                                'publisher': aff.publisher,
                                'share_percentage': aff.share_percentage
                            }
                            for aff in pro_affiliations
                        ]
                        
                        detection.save()
                        updated_count += 1
                        
            except Exception as e:
                errors.append(f"Detection {detection.detection_id}: {str(e)}")
        
        return {
            'success': True,
            'processed': len(detections),
            'updated': updated_count,
            'errors': errors
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

        hybrid_service = HybridDetectionService()
        
        # Perform hybrid detection
        match_result, detection_source, processing_metadata = hybrid_service.identify_with_fallback(
            audio_data, local_fingerprints, session_id, station_id
        )
        
        # Create AudioDetection record
        detection = AudioDetection.objects.create(
            session_id=session_id or 'hybrid_task',
            station=station,
            detection_source=detection_source,
            processing_status='completed',
            audio_timestamp=audio_timestamp or timezone.now(),
            external_metadata=processing_metadata
        )
        
        result = {
            'success': True,
            'detection_id': str(detection.detection_id),
            'detection_source': detection_source,
            'match_found': bool(match_result),
            'processing_metadata': processing_metadata
        }
        
        if match_result:
            # Update detection with match information
            if detection_source == 'local':
                # Local match - get track from database
                try:
                    track = Track.objects.get(id=match_result['song_id'])
                    detection.track = track
                    detection.detected_title = track.title
                    detection.detected_artist = track.artist.stage_name
                    detection.confidence_score = match_result.get('confidence', 0) / 100.0
                    
                    result.update({
                        'track_id': track.id,
                        'title': track.title,
                        'artist': track.artist.stage_name,
                        'confidence': match_result.get('confidence', 0)
                    })
                    
                    # Create MatchCache for backward compatibility
                    MatchCache.objects.create(
                        track=track,
                        station=station,
                        matched_at=timezone.now(),
                        avg_confidence_score=match_result.get('confidence', 0),
                        processed=False
                    )
                    
                except Track.DoesNotExist:
                    print(f"Track {match_result['song_id']} not found")
                    
            elif detection_source == 'acrcloud':
                # ACRCloud match - use external metadata
                detection.detected_title = match_result.get('title', '')
                detection.detected_artist = match_result.get('artist', '')
                detection.detected_album = match_result.get('album', '')
                detection.isrc = match_result.get('isrc')
                detection.iswc = match_result.get('iswc')
                detection.confidence_score = match_result.get('confidence', 0) / 100.0
                detection.acrcloud_response = match_result.get('external_metadata', {})
                
                # Set PRO affiliation from first PRO in list
                pro_affiliations = match_result.get('pro_affiliations', [])
                if pro_affiliations:
                    detection.pro_affiliation = pro_affiliations[0].get('pro_code')
                
                result.update({
                    'title': match_result.get('title', ''),
                    'artist': match_result.get('artist', ''),
                    'album': match_result.get('album', ''),
                    'isrc': match_result.get('isrc'),
                    'confidence': match_result.get('confidence', 0),
                    'pro_affiliations': pro_affiliations
                })
            
            detection.save()
        else:
            # No match found
            detection.processing_status = 'completed'
            detection.confidence_score = 0.0
            detection.save()
        
        return result
        
    except Station.DoesNotExist:
        return {
            'success': False,
            'error': f'Station {station_id} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='music_monitor.update_isrc_metadata')
def update_isrc_metadata(isrc: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Background task to update ISRC metadata
    
    Args:
        isrc: ISRC to update
        force_refresh: Whether to force refresh cached data
        
    Returns:
        Dictionary with update results
    """
    try:
        from music_monitor.services.isrc_lookup_service import ISRCLookupService
        
        service = ISRCLookupService()
        result = service.lookup_isrc(isrc, force_refresh)
        
        if result:
            return {
                'success': True,
                'isrc': isrc,
                'title': result.title,
                'artist': result.artist,
                'confidence': result.confidence,
                'pro_affiliations_count': len(result.pro_affiliations),
                'last_updated': result.last_updated
            }
        else:
            return {
                'success': False,
                'isrc': isrc,
                'message': 'No metadata found'
            }
            
    except Exception as e:
        return {
            'success': False,
            'isrc': isrc,
            'error': str(e)
        }


@shared_task(name='music_monitor.batch_update_pro_mappings')
def batch_update_pro_mappings(isrcs: List[str], force_refresh: bool = False) -> Dict[str, Any]:
    """
    Batch update PRO mappings for multiple ISRCs
    
    Args:
        isrcs: List of ISRCs to update
        force_refresh: Whether to force refresh cached data
        
    Returns:
        Dictionary with batch update results
    """
    try:
        from music_monitor.services.isrc_lookup_service import ISRCLookupService
        
        service = ISRCLookupService()
        results = service.batch_lookup_isrcs(isrcs, force_refresh)
        
        successful = sum(1 for result in results.values() if result is not None)
        failed = len(isrcs) - successful
        
        return {
            'success': True,
            'total_isrcs': len(isrcs),
            'successful': successful,
            'failed': failed,
            'results': {
                isrc: {
                    'success': result is not None,
                    'title': result.title if result else None,
                    'artist': result.artist if result else None,
                    'pro_count': len(result.pro_affiliations) if result else 0
                }
                for isrc, result in results.items()
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'total_isrcs': len(isrcs),
            'successful': 0,
            'failed': len(isrcs)
        }
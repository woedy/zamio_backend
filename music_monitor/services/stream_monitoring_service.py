"""
Enhanced Real-time Stream Monitoring Service

This service provides comprehensive stream monitoring capabilities with:
- Configurable capture intervals and retry logic
- Session management for continuous monitoring
- Health monitoring and alerting
- WebSocket integration for real-time updates
"""

import asyncio
import threading
import subprocess
import librosa
import numpy as np
import io
import uuid
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum

from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from artists.models import Fingerprint, Track
from music_monitor.models import MatchCache, AudioDetection
from music_monitor.utils.match_engine import simple_match_mp3
from music_monitor.services.enhanced_fingerprinting import EnhancedFingerprintService
from music_monitor.services.acrcloud_client import HybridDetectionService
from stations.models import Station, StationStreamLink

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Stream monitoring session status"""
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    HEALTH_CHECK_FAILED = "health_check_failed"


class CaptureResult(Enum):
    """Audio capture result status"""
    SUCCESS = "success"
    NO_AUDIO = "no_audio"
    STREAM_UNAVAILABLE = "stream_unavailable"
    TIMEOUT = "timeout"
    PROCESSING_ERROR = "processing_error"


@dataclass
class StreamMonitoringConfig:
    """Configuration for stream monitoring"""
    capture_interval_seconds: int = 30
    capture_duration_seconds: int = 20
    overlap_seconds: int = 5
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 5
    health_check_interval_seconds: int = 300  # 5 minutes
    max_consecutive_failures: int = 5
    audio_sample_rate: int = 44100
    audio_channels: int = 1
    confidence_threshold: float = 0.8
    enable_hybrid_detection: bool = True
    enable_websocket_broadcast: bool = True
    ffmpeg_timeout_seconds: int = 30


@dataclass
class SessionMetrics:
    """Metrics for a monitoring session"""
    session_id: str
    station_id: int
    started_at: datetime
    last_capture_at: Optional[datetime] = None
    total_captures: int = 0
    successful_captures: int = 0
    failed_captures: int = 0
    matches_found: int = 0
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    status: SessionStatus = SessionStatus.STARTING
    
    def success_rate(self) -> float:
        """Calculate capture success rate"""
        if self.total_captures == 0:
            return 0.0
        return (self.successful_captures / self.total_captures) * 100
    
    def match_rate(self) -> float:
        """Calculate match rate"""
        if self.successful_captures == 0:
            return 0.0
        return (self.matches_found / self.successful_captures) * 100


@dataclass
class CaptureAttempt:
    """Information about a capture attempt"""
    timestamp: datetime
    result: CaptureResult
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    audio_quality_score: Optional[float] = None
    match_found: bool = False
    match_confidence: Optional[float] = None
    track_id: Optional[int] = None


class StreamHealthMonitor:
    """Monitor stream health and alert on issues"""
    
    def __init__(self, config: StreamMonitoringConfig):
        self.config = config
        self.health_checks: Dict[str, List[CaptureAttempt]] = {}
        
    def record_capture_attempt(self, session_id: str, attempt: CaptureAttempt):
        """Record a capture attempt for health monitoring"""
        if session_id not in self.health_checks:
            self.health_checks[session_id] = []
        
        # Keep only recent attempts (last hour)
        cutoff_time = timezone.now() - timedelta(hours=1)
        self.health_checks[session_id] = [
            a for a in self.health_checks[session_id] 
            if a.timestamp > cutoff_time
        ]
        
        self.health_checks[session_id].append(attempt)
        
        # Check for health issues
        self._check_session_health(session_id)
    
    def _check_session_health(self, session_id: str):
        """Check session health and trigger alerts if needed"""
        attempts = self.health_checks.get(session_id, [])
        
        if len(attempts) < 5:  # Need at least 5 attempts to assess health
            return
        
        recent_attempts = attempts[-10:]  # Last 10 attempts
        failure_rate = sum(1 for a in recent_attempts if a.result != CaptureResult.SUCCESS) / len(recent_attempts)
        
        if failure_rate > 0.7:  # More than 70% failure rate
            self._trigger_health_alert(session_id, "high_failure_rate", {
                'failure_rate': failure_rate,
                'recent_attempts': len(recent_attempts)
            })
    
    def _trigger_health_alert(self, session_id: str, alert_type: str, details: Dict):
        """Trigger health alert"""
        alert_data = {
            'session_id': session_id,
            'alert_type': alert_type,
            'timestamp': timezone.now().isoformat(),
            'details': details
        }
        
        logger.warning(f"Stream health alert: {alert_type} for session {session_id}", extra=alert_data)
        
        # Store alert in cache for dashboard
        cache_key = f"stream_health_alert:{session_id}:{alert_type}"
        cache.set(cache_key, alert_data, timeout=3600)  # 1 hour
        
        # TODO: Integrate with notification system
        # self._send_notification(alert_data)


class EnhancedStreamMonitor:
    """Enhanced stream monitoring with advanced features"""
    
    def __init__(self, session_id: str, station_id: int, stream_url: str, 
                 config: Optional[StreamMonitoringConfig] = None,
                 websocket_callback: Optional[Callable] = None):
        self.session_id = session_id
        self.station_id = station_id
        self.stream_url = stream_url
        self.config = config or StreamMonitoringConfig()
        self.websocket_callback = websocket_callback
        
        self.metrics = SessionMetrics(
            session_id=session_id,
            station_id=station_id,
            started_at=timezone.now()
        )
        
        self.health_monitor = StreamHealthMonitor(self.config)
        self.fingerprint_service = EnhancedFingerprintService('fast')
        self.hybrid_service = HybridDetectionService() if self.config.enable_hybrid_detection else None
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        
        # Cache for fingerprints to avoid repeated DB queries
        self._fingerprint_cache: Optional[List] = None
        self._fingerprint_cache_time: Optional[datetime] = None
        
    def start(self) -> bool:
        """Start the monitoring session"""
        try:
            if self._is_running:
                logger.warning(f"Session {self.session_id} is already running")
                return False
            
            self.metrics.status = SessionStatus.STARTING
            self._update_session_cache()
            
            # Validate stream URL
            if not self._validate_stream_url():
                self.metrics.status = SessionStatus.ERROR
                self.metrics.last_error = "Stream URL validation failed"
                self._update_session_cache()
                return False
            
            # Start monitoring thread
            self._is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._thread.start()
            
            self.metrics.status = SessionStatus.ACTIVE
            self._update_session_cache()
            
            logger.info(f"Started stream monitoring session {self.session_id} for station {self.station_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start monitoring session {self.session_id}: {e}")
            self.metrics.status = SessionStatus.ERROR
            self.metrics.last_error = str(e)
            self._update_session_cache()
            return False
    
    def stop(self) -> bool:
        """Stop the monitoring session"""
        try:
            if not self._is_running:
                return True
            
            self.metrics.status = SessionStatus.STOPPING
            self._update_session_cache()
            
            self._stop_event.set()
            self._is_running = False
            
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=10)
            
            self.metrics.status = SessionStatus.STOPPED
            self._update_session_cache()
            
            logger.info(f"Stopped stream monitoring session {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping session {self.session_id}: {e}")
            return False
    
    def pause(self):
        """Pause the monitoring session"""
        self.metrics.status = SessionStatus.PAUSED
        self._update_session_cache()
    
    def resume(self):
        """Resume the monitoring session"""
        if self._is_running:
            self.metrics.status = SessionStatus.ACTIVE
            self._update_session_cache()
    
    def get_metrics(self) -> SessionMetrics:
        """Get current session metrics"""
        return self.metrics
    
    def _validate_stream_url(self) -> bool:
        """Validate that the stream URL is accessible"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', self.stream_url,
                '-f', 'null',
                '-t', '2',  # Test for 2 seconds
                '-'
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                timeout=10
            )
            
            _, stderr = process.communicate()
            return process.returncode == 0
            
        except Exception as e:
            logger.error(f"Stream validation failed for {self.stream_url}: {e}")
            return False
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        logger.info(f"Starting monitoring loop for session {self.session_id}")
        
        while self._is_running and not self._stop_event.is_set():
            try:
                if self.metrics.status == SessionStatus.PAUSED:
                    time.sleep(1)
                    continue
                
                # Perform capture and processing
                self._perform_capture_cycle()
                
                # Wait for next capture (considering overlap)
                wait_time = max(1, self.config.capture_interval_seconds - self.config.overlap_seconds)
                if self._stop_event.wait(timeout=wait_time):
                    break
                
            except Exception as e:
                logger.error(f"Error in monitoring loop for session {self.session_id}: {e}")
                self.metrics.consecutive_failures += 1
                self.metrics.last_error = str(e)
                
                if self.metrics.consecutive_failures >= self.config.max_consecutive_failures:
                    self.metrics.status = SessionStatus.ERROR
                    self._update_session_cache()
                    break
                
                # Wait before retrying
                time.sleep(self.config.retry_delay_seconds)
        
        logger.info(f"Monitoring loop ended for session {self.session_id}")
    
    def _perform_capture_cycle(self):
        """Perform a complete capture and processing cycle"""
        start_time = time.time()
        attempt = CaptureAttempt(timestamp=timezone.now(), result=CaptureResult.PROCESSING_ERROR)
        
        try:
            # Capture audio
            audio_data = self._capture_audio_with_retry()
            
            if not audio_data:
                attempt.result = CaptureResult.NO_AUDIO
                self.metrics.failed_captures += 1
                self.metrics.consecutive_failures += 1
            else:
                # Process audio
                match_result = self._process_audio_data(audio_data)
                
                attempt.result = CaptureResult.SUCCESS
                attempt.duration_ms = int((time.time() - start_time) * 1000)
                attempt.audio_quality_score = match_result.get('quality_score', 0.0)
                
                self.metrics.successful_captures += 1
                self.metrics.consecutive_failures = 0
                self.metrics.last_capture_at = timezone.now()
                
                if match_result.get('match_found'):
                    attempt.match_found = True
                    attempt.match_confidence = match_result.get('confidence', 0.0)
                    attempt.track_id = match_result.get('track_id')
                    self.metrics.matches_found += 1
                    
                    # Broadcast match via WebSocket if enabled
                    if self.config.enable_websocket_broadcast and self.websocket_callback:
                        self._broadcast_match_result(match_result)
            
            self.metrics.total_captures += 1
            
        except Exception as e:
            logger.error(f"Capture cycle failed for session {self.session_id}: {e}")
            attempt.result = CaptureResult.PROCESSING_ERROR
            attempt.error_message = str(e)
            self.metrics.failed_captures += 1
            self.metrics.consecutive_failures += 1
            self.metrics.last_error = str(e)
        
        finally:
            # Record attempt for health monitoring
            self.health_monitor.record_capture_attempt(self.session_id, attempt)
            self._update_session_cache()
    
    def _capture_audio_with_retry(self) -> Optional[bytes]:
        """Capture audio with retry logic"""
        for attempt in range(self.config.max_retry_attempts):
            try:
                audio_data = self._capture_stream_audio()
                if audio_data:
                    return audio_data
                    
            except Exception as e:
                logger.warning(f"Audio capture attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.max_retry_attempts - 1:
                    time.sleep(self.config.retry_delay_seconds * (attempt + 1))
        
        return None
    
    def _capture_stream_audio(self) -> Optional[bytes]:
        """Capture audio from stream using ffmpeg"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', self.stream_url,
                '-f', 'wav',
                '-ar', str(self.config.audio_sample_rate),
                '-ac', str(self.config.audio_channels),
                '-t', str(self.config.capture_duration_seconds),
                '-'
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.ffmpeg_timeout_seconds
            )
            
            audio_data, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg failed: {stderr.decode()}")
                return None
            
            if len(audio_data) == 0:
                logger.warning("No audio data captured")
                return None
            
            return audio_data
            
        except subprocess.TimeoutExpired:
            logger.error(f"Audio capture timeout for session {self.session_id}")
            process.kill()
            return None
        except Exception as e:
            logger.error(f"Audio capture error: {e}")
            return None
    
    def _process_audio_data(self, audio_data: bytes) -> Dict[str, Any]:
        """Process captured audio data for music detection"""
        try:
            # Load audio samples
            samples, sr = librosa.load(io.BytesIO(audio_data), sr=self.config.audio_sample_rate, mono=True)
            
            if len(samples) == 0:
                return {'match_found': False, 'error': 'No audio samples'}
            
            # Get fingerprints for matching
            fingerprints = self._get_cached_fingerprints()
            
            if not fingerprints:
                return {'match_found': False, 'error': 'No fingerprints available'}
            
            # Use hybrid detection if enabled
            if self.config.enable_hybrid_detection and self.hybrid_service:
                return self._hybrid_detection(audio_data, samples, sr, fingerprints)
            else:
                return self._local_detection(samples, sr, fingerprints)
                
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return {'match_found': False, 'error': str(e)}
    
    def _local_detection(self, samples: np.ndarray, sr: int, fingerprints: List) -> Dict[str, Any]:
        """Perform local fingerprint detection"""
        try:
            # Use the existing simple_match_mp3 function
            match_result = simple_match_mp3(samples, sr, fingerprints, min_match_threshold=5)
            
            result = {
                'match_found': match_result.get('match', False),
                'confidence': match_result.get('confidence', 0),
                'detection_source': 'local',
                'quality_score': 0.8  # Default quality score for local detection
            }
            
            if match_result.get('match'):
                # Get track information
                try:
                    track = Track.objects.get(id=match_result['song_id'])
                    result.update({
                        'track_id': track.id,
                        'track_title': track.title,
                        'artist_name': track.artist.stage_name,
                        'hashes_matched': match_result.get('hashes_matched', 0)
                    })
                    
                    # Create detection record
                    self._create_detection_record(track, result, samples, sr)
                    
                except Track.DoesNotExist:
                    logger.error(f"Track {match_result['song_id']} not found")
                    result['match_found'] = False
            
            return result
            
        except Exception as e:
            logger.error(f"Local detection error: {e}")
            return {'match_found': False, 'error': str(e)}
    
    def _hybrid_detection(self, audio_data: bytes, samples: np.ndarray, 
                         sr: int, fingerprints: List) -> Dict[str, Any]:
        """Perform hybrid detection (local + ACRCloud)"""
        try:
            # First try local detection
            local_result = self._local_detection(samples, sr, fingerprints)
            
            # If local detection has high confidence, use it
            if (local_result.get('match_found') and 
                local_result.get('confidence', 0) >= self.config.confidence_threshold * 100):
                local_result['detection_source'] = 'local'
                return local_result
            
            # Otherwise, try ACRCloud
            logger.info(f"Local detection confidence too low, trying ACRCloud for session {self.session_id}")
            
            acrcloud_match = self.hybrid_service.acrcloud_client.identify_audio(audio_data)
            
            if acrcloud_match and acrcloud_match.confidence >= self.config.confidence_threshold * 100:
                result = {
                    'match_found': True,
                    'confidence': acrcloud_match.confidence,
                    'detection_source': 'acrcloud',
                    'track_title': acrcloud_match.title,
                    'artist_name': acrcloud_match.artist,
                    'album_name': acrcloud_match.album,
                    'isrc': acrcloud_match.isrc,
                    'quality_score': 0.9  # ACRCloud generally has high quality
                }
                
                # Create detection record for ACRCloud match
                self._create_acrcloud_detection_record(acrcloud_match, result, samples, sr)
                
                return result
            
            # No match found in either system
            return {
                'match_found': False,
                'detection_source': 'hybrid',
                'local_confidence': local_result.get('confidence', 0),
                'acrcloud_confidence': acrcloud_match.confidence if acrcloud_match else 0
            }
            
        except Exception as e:
            logger.error(f"Hybrid detection error: {e}")
            return {'match_found': False, 'error': str(e)}
    
    def _create_detection_record(self, track: Track, result: Dict, samples: np.ndarray, sr: int):
        """Create AudioDetection record for local match"""
        try:
            # Generate fingerprint for the audio segment
            fingerprint_hashes, metadata = self.fingerprint_service.enhanced_fingerprint(samples, sr)
            
            AudioDetection.objects.create(
                session_id=self.session_id,
                station_id=self.station_id,
                track=track,
                detection_source='local',
                confidence_score=result.get('confidence', 0) / 100.0,
                processing_status='completed',
                detected_title=track.title,
                detected_artist=track.artist.stage_name,
                detected_album=track.album.title if track.album else None,
                pro_affiliation='ghamro',  # Default for local tracks
                audio_fingerprint=str(fingerprint_hashes[:10]) if fingerprint_hashes else '',
                fingerprint_version=self.fingerprint_service.CURRENT_VERSION,
                audio_timestamp=timezone.now(),
                duration_seconds=len(samples) / sr,
                processing_time_ms=metadata.processing_time_ms if hasattr(metadata, 'processing_time_ms') else 0,
                external_metadata={
                    'session_id': self.session_id,
                    'capture_config': asdict(self.config),
                    'quality_score': result.get('quality_score', 0.0),
                    'hashes_matched': result.get('hashes_matched', 0)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to create detection record: {e}")
    
    def _create_acrcloud_detection_record(self, acrcloud_match, result: Dict, samples: np.ndarray, sr: int):
        """Create AudioDetection record for ACRCloud match"""
        try:
            # Map ACRCloud result to PRO
            pro_affiliation = 'unknown'
            if acrcloud_match.external_ids:
                # Simple PRO mapping based on territory or other metadata
                # This would be enhanced with the PROMapper service
                pro_affiliation = 'ascap'  # Default for international content
            
            AudioDetection.objects.create(
                session_id=self.session_id,
                station_id=self.station_id,
                detection_source='acrcloud',
                confidence_score=acrcloud_match.confidence / 100.0,
                processing_status='completed',
                detected_title=acrcloud_match.title,
                detected_artist=acrcloud_match.artist,
                detected_album=acrcloud_match.album,
                isrc=acrcloud_match.isrc,
                iswc=acrcloud_match.iswc,
                pro_affiliation=pro_affiliation,
                audio_timestamp=timezone.now(),
                duration_seconds=len(samples) / sr if len(samples) > 0 else acrcloud_match.duration_ms / 1000,
                acrcloud_response=acrcloud_match.metadata,
                external_metadata={
                    'session_id': self.session_id,
                    'acrid': acrcloud_match.acrid,
                    'label': acrcloud_match.label,
                    'release_date': acrcloud_match.release_date,
                    'play_offset_ms': acrcloud_match.play_offset_ms,
                    'external_ids': acrcloud_match.external_ids,
                    'quality_score': result.get('quality_score', 0.0)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to create ACRCloud detection record: {e}")
    
    def _get_cached_fingerprints(self) -> List:
        """Get cached fingerprints or refresh from database"""
        current_time = timezone.now()
        
        # Refresh cache every 5 minutes
        if (not self._fingerprint_cache or 
            not self._fingerprint_cache_time or 
            (current_time - self._fingerprint_cache_time).total_seconds() > 300):
            
            self._fingerprint_cache = list(
                Fingerprint.objects.select_related('track').values_list(
                    'track_id', 'hash', 'offset'
                )
            )
            self._fingerprint_cache_time = current_time
            
            logger.debug(f"Refreshed fingerprint cache: {len(self._fingerprint_cache)} fingerprints")
        
        return self._fingerprint_cache
    
    def _broadcast_match_result(self, match_result: Dict):
        """Broadcast match result via WebSocket"""
        try:
            if self.websocket_callback:
                broadcast_data = {
                    'type': 'audio_match',
                    'session_id': self.session_id,
                    'station_id': self.station_id,
                    'timestamp': timezone.now().isoformat(),
                    'match_data': match_result
                }
                
                self.websocket_callback(broadcast_data)
                
        except Exception as e:
            logger.error(f"WebSocket broadcast failed: {e}")
    
    def _update_session_cache(self):
        """Update session metrics in cache"""
        try:
            cache_key = f"stream_session:{self.session_id}"
            cache_data = {
                'metrics': asdict(self.metrics),
                'config': asdict(self.config),
                'updated_at': timezone.now().isoformat()
            }
            
            cache.set(cache_key, cache_data, timeout=3600)  # 1 hour
            
        except Exception as e:
            logger.error(f"Failed to update session cache: {e}")


class StreamMonitoringManager:
    """Manager for multiple stream monitoring sessions"""
    
    def __init__(self):
        self.active_sessions: Dict[str, EnhancedStreamMonitor] = {}
        self._lock = threading.Lock()
    
    def start_session(self, station_id: int, stream_url: str, 
                     config: Optional[StreamMonitoringConfig] = None,
                     websocket_callback: Optional[Callable] = None) -> str:
        """Start a new monitoring session"""
        session_id = str(uuid.uuid4())
        
        with self._lock:
            monitor = EnhancedStreamMonitor(
                session_id=session_id,
                station_id=station_id,
                stream_url=stream_url,
                config=config,
                websocket_callback=websocket_callback
            )
            
            if monitor.start():
                self.active_sessions[session_id] = monitor
                logger.info(f"Started monitoring session {session_id} for station {station_id}")
                return session_id
            else:
                logger.error(f"Failed to start monitoring session for station {station_id}")
                return None
    
    def stop_session(self, session_id: str) -> bool:
        """Stop a monitoring session"""
        with self._lock:
            monitor = self.active_sessions.get(session_id)
            if monitor:
                success = monitor.stop()
                if success:
                    del self.active_sessions[session_id]
                return success
            return False
    
    def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """Get metrics for a specific session"""
        monitor = self.active_sessions.get(session_id)
        return monitor.get_metrics() if monitor else None
    
    def get_all_sessions(self) -> Dict[str, SessionMetrics]:
        """Get metrics for all active sessions"""
        return {
            session_id: monitor.get_metrics() 
            for session_id, monitor in self.active_sessions.items()
        }
    
    def pause_session(self, session_id: str) -> bool:
        """Pause a monitoring session"""
        monitor = self.active_sessions.get(session_id)
        if monitor:
            monitor.pause()
            return True
        return False
    
    def resume_session(self, session_id: str) -> bool:
        """Resume a monitoring session"""
        monitor = self.active_sessions.get(session_id)
        if monitor:
            monitor.resume()
            return True
        return False
    
    def stop_all_sessions(self):
        """Stop all active monitoring sessions"""
        with self._lock:
            for session_id in list(self.active_sessions.keys()):
                self.stop_session(session_id)


# Global manager instance
stream_monitoring_manager = StreamMonitoringManager()


# Convenience functions
def start_station_monitoring(station_id: int, config: Optional[StreamMonitoringConfig] = None) -> Optional[str]:
    """Start monitoring for a station using its active stream links"""
    try:
        station = Station.objects.get(id=station_id)
        active_link = station.stream_links.filter(active=True, is_archived=False).first()
        
        if not active_link:
            logger.error(f"No active stream link found for station {station_id}")
            return None
        
        return stream_monitoring_manager.start_session(
            station_id=station_id,
            stream_url=active_link.link,
            config=config
        )
        
    except Station.DoesNotExist:
        logger.error(f"Station {station_id} not found")
        return None


def stop_station_monitoring(station_id: int) -> bool:
    """Stop monitoring for a station"""
    # Find session by station_id
    for session_id, monitor in stream_monitoring_manager.active_sessions.items():
        if monitor.station_id == station_id:
            return stream_monitoring_manager.stop_session(session_id)
    return False


def get_station_monitoring_status(station_id: int) -> Optional[SessionMetrics]:
    """Get monitoring status for a station"""
    for session_id, monitor in stream_monitoring_manager.active_sessions.items():
        if monitor.station_id == station_id:
            return monitor.get_metrics()
    return None
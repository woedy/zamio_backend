"""
Enhanced Local Fingerprinting Service
Implements optimized fingerprinting with versioning, metadata tracking, and quality assessment.
"""

import logging
import time
import hashlib
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

import numpy as np
import librosa
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from artists.models import Track, Fingerprint
from artists.utils.fingerprint_tracks import simple_fingerprint, DEFAULT_CONFIG
from music_monitor.models import AudioDetection

logger = logging.getLogger(__name__)


@dataclass
class FingerprintMetadata:
    """Metadata for fingerprint processing"""
    version: str
    algorithm: str
    config: Dict[str, Any]
    processing_time_ms: int
    audio_duration_seconds: float
    sample_rate: int
    peak_count: int
    hash_count: int
    quality_score: float
    confidence_threshold: float
    created_at: str
    audio_hash: str


@dataclass
class FingerprintQuality:
    """Quality assessment metrics for fingerprints"""
    peak_density: float  # peaks per second
    hash_density: float  # hashes per second
    spectral_centroid_mean: float
    spectral_rolloff_mean: float
    zero_crossing_rate: float
    rms_energy: float
    overall_score: float  # 0-1 quality score


class EnhancedFingerprintService:
    """Enhanced fingerprinting service with optimization and quality assessment"""
    
    CURRENT_VERSION = "2.0"
    ALGORITHM_NAME = "enhanced_spectral_peaks"
    
    # Optimized configurations for different use cases
    CONFIGS = {
        'high_quality': {
            **DEFAULT_CONFIG,
            'DEFAULT_WINDOW_SIZE': 4096,
            'DEFAULT_FAN_VALUE': 20,
            'DEFAULT_AMP_MIN_PERCENTILE': 85,
            'PEAK_NEIGHBORHOOD_SIZE': 15,
            'MAX_HASH_TIME_DELTA': 300,
        },
        'balanced': {
            **DEFAULT_CONFIG,
            'DEFAULT_WINDOW_SIZE': 2048,
            'DEFAULT_FAN_VALUE': 15,
            'DEFAULT_AMP_MIN_PERCENTILE': 90,
            'PEAK_NEIGHBORHOOD_SIZE': 10,
            'MAX_HASH_TIME_DELTA': 200,
        },
        'fast': {
            **DEFAULT_CONFIG,
            'DEFAULT_WINDOW_SIZE': 1024,
            'DEFAULT_FAN_VALUE': 10,
            'DEFAULT_AMP_MIN_PERCENTILE': 95,
            'PEAK_NEIGHBORHOOD_SIZE': 8,
            'MAX_HASH_TIME_DELTA': 150,
        }
    }
    
    def __init__(self, config_name: str = 'balanced'):
        """Initialize with specified configuration"""
        self.config = self.CONFIGS.get(config_name, self.CONFIGS['balanced'])
        self.config_name = config_name
        
    def calculate_audio_hash(self, samples: np.ndarray) -> str:
        """Calculate SHA-256 hash of audio samples for deduplication"""
        audio_bytes = samples.tobytes()
        return hashlib.sha256(audio_bytes).hexdigest()
    
    def assess_audio_quality(self, samples: np.ndarray, sr: int) -> FingerprintQuality:
        """Assess audio quality metrics for fingerprint confidence"""
        try:
            # Calculate spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=samples, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=samples, sr=sr)[0]
            zero_crossings = librosa.feature.zero_crossing_rate(samples)[0]
            rms = librosa.feature.rms(y=samples)[0]
            
            # Calculate means
            spectral_centroid_mean = np.mean(spectral_centroids)
            spectral_rolloff_mean = np.mean(spectral_rolloff)
            zero_crossing_rate = np.mean(zero_crossings)
            rms_energy = np.mean(rms)
            
            # Calculate peak and hash densities (will be updated after fingerprinting)
            duration = len(samples) / sr
            
            # Calculate overall quality score (0-1)
            # Higher spectral centroid and rolloff generally indicate better quality
            # Lower zero crossing rate indicates less noise
            # Higher RMS indicates stronger signal
            
            quality_factors = []
            
            # Spectral centroid score (normalized)
            centroid_score = min(1.0, spectral_centroid_mean / 4000.0)
            quality_factors.append(centroid_score * 0.3)
            
            # RMS energy score
            rms_score = min(1.0, rms_energy * 10)
            quality_factors.append(rms_score * 0.3)
            
            # Zero crossing rate score (inverted - lower is better)
            zcr_score = max(0.0, 1.0 - (zero_crossing_rate * 20))
            quality_factors.append(zcr_score * 0.2)
            
            # Spectral rolloff score
            rolloff_score = min(1.0, spectral_rolloff_mean / 8000.0)
            quality_factors.append(rolloff_score * 0.2)
            
            overall_score = sum(quality_factors)
            
            return FingerprintQuality(
                peak_density=0.0,  # Will be updated after peak detection
                hash_density=0.0,  # Will be updated after hash generation
                spectral_centroid_mean=float(spectral_centroid_mean),
                spectral_rolloff_mean=float(spectral_rolloff_mean),
                zero_crossing_rate=float(zero_crossing_rate),
                rms_energy=float(rms_energy),
                overall_score=float(overall_score)
            )
            
        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return FingerprintQuality(
                peak_density=0.0,
                hash_density=0.0,
                spectral_centroid_mean=0.0,
                spectral_rolloff_mean=0.0,
                zero_crossing_rate=0.0,
                rms_energy=0.0,
                overall_score=0.1  # Low quality fallback
            )
    
    def enhanced_fingerprint(self, samples: np.ndarray, sr: int, 
                           track_id: Optional[int] = None) -> Tuple[List[Tuple[int, int]], FingerprintMetadata]:
        """
        Generate enhanced fingerprint with metadata tracking
        
        Returns:
            Tuple of (fingerprint_hashes, metadata)
        """
        start_time = time.time()
        
        try:
            # Calculate audio hash for deduplication
            audio_hash = self.calculate_audio_hash(samples)
            
            # Assess audio quality
            quality = self.assess_audio_quality(samples, sr)
            
            # Generate fingerprint using optimized algorithm
            fingerprint_hashes = simple_fingerprint(samples, sr, self.config)
            
            # Update quality metrics with actual peak/hash counts
            duration = len(samples) / sr
            if duration > 0:
                quality.hash_density = len(fingerprint_hashes) / duration
                # Estimate peak density (approximate)
                quality.peak_density = quality.hash_density * self.config.get('DEFAULT_FAN_VALUE', 15)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Calculate confidence threshold based on quality
            confidence_threshold = self._calculate_confidence_threshold(quality)
            
            # Create metadata
            metadata = FingerprintMetadata(
                version=self.CURRENT_VERSION,
                algorithm=self.ALGORITHM_NAME,
                config=self.config.copy(),
                processing_time_ms=processing_time,
                audio_duration_seconds=duration,
                sample_rate=sr,
                peak_count=int(quality.peak_density * duration),
                hash_count=len(fingerprint_hashes),
                quality_score=quality.overall_score,
                confidence_threshold=confidence_threshold,
                created_at=timezone.now().isoformat(),
                audio_hash=audio_hash
            )
            
            logger.info(f"Enhanced fingerprint generated: {len(fingerprint_hashes)} hashes, "
                       f"quality={quality.overall_score:.3f}, time={processing_time}ms")
            
            return fingerprint_hashes, metadata
            
        except Exception as e:
            logger.error(f"Enhanced fingerprinting failed: {e}")
            # Return empty fingerprint with error metadata
            metadata = FingerprintMetadata(
                version=self.CURRENT_VERSION,
                algorithm=self.ALGORITHM_NAME,
                config=self.config.copy(),
                processing_time_ms=int((time.time() - start_time) * 1000),
                audio_duration_seconds=len(samples) / sr if len(samples) > 0 else 0,
                sample_rate=sr,
                peak_count=0,
                hash_count=0,
                quality_score=0.0,
                confidence_threshold=0.0,
                created_at=timezone.now().isoformat(),
                audio_hash=""
            )
            return [], metadata
    
    def _calculate_confidence_threshold(self, quality: FingerprintQuality) -> float:
        """Calculate dynamic confidence threshold based on audio quality"""
        base_threshold = 0.6
        
        # Adjust threshold based on quality score
        # Higher quality audio can use lower thresholds
        # Lower quality audio needs higher thresholds
        quality_adjustment = (1.0 - quality.overall_score) * 0.3
        
        # Adjust based on hash density
        # More hashes generally mean more reliable matching
        density_adjustment = max(0, (10.0 - quality.hash_density) * 0.02)
        
        threshold = base_threshold + quality_adjustment + density_adjustment
        return min(0.95, max(0.3, threshold))  # Clamp between 0.3 and 0.95
    
    def fingerprint_track(self, track: Track, force_reprocess: bool = False) -> bool:
        """
        Fingerprint a single track with enhanced processing
        
        Args:
            track: Track instance to fingerprint
            force_reprocess: Whether to reprocess even if fingerprints exist
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if already processed with current version
            if not force_reprocess:
                existing_fingerprints = Fingerprint.objects.filter(
                    track=track,
                    metadata__version=self.CURRENT_VERSION
                ).exists()
                
                if existing_fingerprints:
                    logger.info(f"Track {track.id} already has current version fingerprints")
                    return True
            
            # Load audio file
            if not track.audio_file:
                logger.warning(f"Track {track.id} has no audio file")
                return False
            
            try:
                samples, sr = librosa.load(track.audio_file.path, sr=44100, mono=True)
            except Exception as e:
                logger.error(f"Failed to load audio for track {track.id}: {e}")
                return False
            
            if len(samples) == 0:
                logger.warning(f"Track {track.id} has no audio samples")
                return False
            
            # Generate enhanced fingerprint
            fingerprint_hashes, metadata = self.enhanced_fingerprint(samples, sr, track.id)
            
            if not fingerprint_hashes:
                logger.warning(f"No fingerprints generated for track {track.id}")
                return False
            
            # Store fingerprints in database
            with transaction.atomic():
                # Remove old fingerprints if force reprocessing
                if force_reprocess:
                    Fingerprint.objects.filter(track=track).delete()
                
                # Create new fingerprints
                fingerprint_objects = []
                for hash_value, offset in fingerprint_hashes:
                    fingerprint_objects.append(
                        Fingerprint(
                            track=track,
                            hash=str(hash_value),
                            offset=offset,
                            metadata=asdict(metadata)
                        )
                    )
                
                # Batch create for efficiency
                Fingerprint.objects.bulk_create(fingerprint_objects, batch_size=1000)
                
                logger.info(f"Stored {len(fingerprint_objects)} fingerprints for track {track.id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to fingerprint track {track.id}: {e}")
            return False
    
    def batch_fingerprint_tracks(self, track_ids: List[int], max_workers: int = 4, 
                               force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Batch fingerprint multiple tracks with parallel processing
        
        Args:
            track_ids: List of track IDs to process
            max_workers: Maximum number of parallel workers
            force_reprocess: Whether to reprocess existing fingerprints
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        results = {
            'total_tracks': len(track_ids),
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'processing_time_seconds': 0,
            'failed_tracks': [],
            'performance_metrics': {}
        }
        
        try:
            # Get tracks
            tracks = Track.objects.filter(id__in=track_ids).select_related('artist', 'album')
            track_dict = {track.id: track for track in tracks}
            
            # Process tracks in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_track = {
                    executor.submit(self.fingerprint_track, track_dict[track_id], force_reprocess): track_id
                    for track_id in track_ids if track_id in track_dict
                }
                
                # Process completed tasks
                for future in as_completed(future_to_track):
                    track_id = future_to_track[future]
                    try:
                        success = future.result()
                        if success:
                            results['successful'] += 1
                        else:
                            results['failed'] += 1
                            results['failed_tracks'].append(track_id)
                    except Exception as e:
                        logger.error(f"Exception processing track {track_id}: {e}")
                        results['failed'] += 1
                        results['failed_tracks'].append(track_id)
            
            # Calculate performance metrics
            total_time = time.time() - start_time
            results['processing_time_seconds'] = round(total_time, 2)
            
            if results['successful'] > 0:
                results['performance_metrics'] = {
                    'tracks_per_second': round(results['successful'] / total_time, 2),
                    'average_time_per_track': round(total_time / results['successful'], 2),
                    'success_rate': round(results['successful'] / results['total_tracks'] * 100, 1)
                }
            
            logger.info(f"Batch fingerprinting completed: {results['successful']}/{results['total_tracks']} "
                       f"successful in {total_time:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch fingerprinting failed: {e}")
            results['processing_time_seconds'] = time.time() - start_time
            return results
    
    def get_fingerprint_statistics(self) -> Dict[str, Any]:
        """Get statistics about fingerprints in the database"""
        try:
            from django.db.models import Count, Avg
            
            # Get version statistics
            version_stats = Fingerprint.objects.values('metadata__version').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Get quality statistics for current version
            current_version_fingerprints = Fingerprint.objects.filter(
                metadata__version=self.CURRENT_VERSION
            )
            
            total_fingerprints = Fingerprint.objects.count()
            current_version_count = current_version_fingerprints.count()
            
            stats = {
                'total_fingerprints': total_fingerprints,
                'current_version_fingerprints': current_version_count,
                'version_distribution': list(version_stats),
                'current_version': self.CURRENT_VERSION,
                'algorithm': self.ALGORITHM_NAME,
                'config_name': self.config_name
            }
            
            # Calculate average quality metrics for current version
            if current_version_count > 0:
                # This would require aggregating JSON fields, which is complex
                # For now, we'll just provide basic stats
                stats['coverage_percentage'] = round(
                    (current_version_count / total_fingerprints * 100) if total_fingerprints > 0 else 0, 1
                )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get fingerprint statistics: {e}")
            return {'error': str(e)}


# Convenience functions for common operations
def fingerprint_single_track(track_id: int, config_name: str = 'balanced', 
                           force_reprocess: bool = False) -> bool:
    """Fingerprint a single track with specified configuration"""
    try:
        track = Track.objects.get(id=track_id)
        service = EnhancedFingerprintService(config_name)
        return service.fingerprint_track(track, force_reprocess)
    except Track.DoesNotExist:
        logger.error(f"Track {track_id} not found")
        return False


def batch_fingerprint_all_tracks(config_name: str = 'balanced', max_workers: int = 4,
                                force_reprocess: bool = False) -> Dict[str, Any]:
    """Fingerprint all tracks in the database"""
    track_ids = list(Track.objects.values_list('id', flat=True))
    service = EnhancedFingerprintService(config_name)
    return service.batch_fingerprint_tracks(track_ids, max_workers, force_reprocess)


def get_system_fingerprint_stats() -> Dict[str, Any]:
    """Get system-wide fingerprint statistics"""
    service = EnhancedFingerprintService()
    return service.get_fingerprint_statistics()
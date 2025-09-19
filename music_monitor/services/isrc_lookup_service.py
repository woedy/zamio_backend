"""
ISRC Lookup Service
Provides comprehensive ISRC-based track identification and metadata enrichment
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .acrcloud_client import ACRCloudClient, PROMapper, PROAffiliation

logger = logging.getLogger(__name__)


@dataclass
class ISRCLookupResult:
    """ISRC lookup result with comprehensive metadata"""
    isrc: str
    title: str
    artist: str
    album: Optional[str]
    label: Optional[str]
    release_date: Optional[str]
    duration_ms: Optional[int]
    genre: Optional[str]
    
    # PRO and rights information
    pro_affiliations: List[Dict[str, Any]]
    publishers: List[Dict[str, Any]]
    writers: List[Dict[str, Any]]
    
    # External identifiers
    external_ids: Dict[str, Any]
    
    # Metadata
    lookup_source: str
    confidence: float
    last_updated: str
    raw_metadata: Dict[str, Any]


class ISRCLookupService:
    """
    Enhanced ISRC lookup service with multiple data sources and caching
    """
    
    # Cache settings
    CACHE_TTL_SUCCESS = 86400 * 7  # 7 days for successful lookups
    CACHE_TTL_FAILURE = 3600       # 1 hour for failed lookups
    
    # Batch processing settings
    MAX_BATCH_SIZE = 50
    BATCH_TIMEOUT_SECONDS = 60
    
    def __init__(self):
        self.acrcloud_client = ACRCloudClient()
        self.pro_mapper = PROMapper()
    
    def lookup_isrc(self, isrc: str, force_refresh: bool = False) -> Optional[ISRCLookupResult]:
        """
        Lookup comprehensive metadata for an ISRC
        
        Args:
            isrc: International Standard Recording Code
            force_refresh: Whether to bypass cache and force fresh lookup
            
        Returns:
            ISRCLookupResult object or None if not found
        """
        try:
            # Validate ISRC format
            if not self._validate_isrc(isrc):
                logger.warning(f"Invalid ISRC format: {isrc}")
                return None
            
            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_result = self._get_cached_result(isrc)
                if cached_result:
                    logger.debug(f"Returning cached ISRC lookup for {isrc}")
                    return cached_result
            
            # Perform lookup
            result = self._perform_lookup(isrc)
            
            # Cache the result
            if result:
                self._cache_result(isrc, result, success=True)
                logger.info(f"Successfully looked up ISRC {isrc}: {result.title} by {result.artist}")
            else:
                self._cache_result(isrc, None, success=False)
                logger.info(f"No metadata found for ISRC {isrc}")
            
            return result
            
        except Exception as e:
            logger.error(f"ISRC lookup error for {isrc}: {e}")
            return None
    
    def batch_lookup_isrcs(self, isrcs: List[str], force_refresh: bool = False) -> Dict[str, Optional[ISRCLookupResult]]:
        """
        Batch lookup multiple ISRCs efficiently
        
        Args:
            isrcs: List of ISRCs to lookup
            force_refresh: Whether to bypass cache
            
        Returns:
            Dictionary mapping ISRC to lookup result
        """
        results = {}
        
        try:
            # Validate and filter ISRCs
            valid_isrcs = [isrc for isrc in isrcs if self._validate_isrc(isrc)]
            
            if len(valid_isrcs) != len(isrcs):
                logger.warning(f"Filtered {len(isrcs) - len(valid_isrcs)} invalid ISRCs from batch")
            
            # Process in batches
            for i in range(0, len(valid_isrcs), self.MAX_BATCH_SIZE):
                batch = valid_isrcs[i:i + self.MAX_BATCH_SIZE]
                batch_results = self._process_batch(batch, force_refresh)
                results.update(batch_results)
            
            logger.info(f"Batch lookup completed: {len(results)} ISRCs processed")
            return results
            
        except Exception as e:
            logger.error(f"Batch ISRC lookup error: {e}")
            return results
    
    def enrich_detection_with_isrc(self, detection_result: Dict, isrc: str) -> Dict:
        """
        Enrich an existing detection result with ISRC metadata
        
        Args:
            detection_result: Existing detection result dictionary
            isrc: ISRC to lookup and merge
            
        Returns:
            Enhanced detection result
        """
        try:
            isrc_data = self.lookup_isrc(isrc)
            
            if not isrc_data:
                logger.warning(f"No ISRC data found to enrich detection with {isrc}")
                return detection_result
            
            # Merge ISRC data into detection result
            enhanced_result = detection_result.copy()
            
            # Update basic metadata if not present or if ISRC data is more complete
            if not enhanced_result.get('title') or len(isrc_data.title) > len(enhanced_result.get('title', '')):
                enhanced_result['title'] = isrc_data.title
            
            if not enhanced_result.get('artist') or len(isrc_data.artist) > len(enhanced_result.get('artist', '')):
                enhanced_result['artist'] = isrc_data.artist
            
            if not enhanced_result.get('album') and isrc_data.album:
                enhanced_result['album'] = isrc_data.album
            
            if not enhanced_result.get('label') and isrc_data.label:
                enhanced_result['label'] = isrc_data.label
            
            if not enhanced_result.get('release_date') and isrc_data.release_date:
                enhanced_result['release_date'] = isrc_data.release_date
            
            if not enhanced_result.get('duration_ms') and isrc_data.duration_ms:
                enhanced_result['duration_ms'] = isrc_data.duration_ms
            
            # Merge PRO affiliations
            existing_pros = enhanced_result.get('pro_affiliations', [])
            isrc_pros = isrc_data.pro_affiliations
            
            # Combine and deduplicate PRO affiliations
            all_pros = existing_pros + isrc_pros
            unique_pros = self._deduplicate_pro_affiliations(all_pros)
            enhanced_result['pro_affiliations'] = unique_pros
            
            # Add ISRC metadata
            enhanced_result['isrc_metadata'] = {
                'publishers': isrc_data.publishers,
                'writers': isrc_data.writers,
                'external_ids': isrc_data.external_ids,
                'lookup_source': isrc_data.lookup_source,
                'last_updated': isrc_data.last_updated
            }
            
            # Update confidence if ISRC lookup provides additional validation
            if enhanced_result.get('confidence', 0) < 90 and isrc_data.confidence > 0.8:
                enhanced_result['confidence'] = min(95, enhanced_result.get('confidence', 0) + 10)
            
            logger.info(f"Enhanced detection result with ISRC {isrc} metadata")
            return enhanced_result
            
        except Exception as e:
            logger.error(f"Error enriching detection with ISRC {isrc}: {e}")
            return detection_result
    
    def _validate_isrc(self, isrc: str) -> bool:
        """Validate ISRC format (CC-XXX-YY-NNNNN)"""
        if not isrc or len(isrc) != 12:
            return False
        
        # Remove hyphens for validation
        clean_isrc = isrc.replace('-', '').upper()
        
        if len(clean_isrc) != 12:
            return False
        
        # Check format: 2 letters + 3 alphanumeric + 2 digits + 5 digits
        if not (clean_isrc[:2].isalpha() and 
                clean_isrc[2:5].isalnum() and 
                clean_isrc[5:7].isdigit() and 
                clean_isrc[7:12].isdigit()):
            return False
        
        return True
    
    def _get_cached_result(self, isrc: str) -> Optional[ISRCLookupResult]:
        """Get cached ISRC lookup result"""
        cache_key = f"isrc_lookup_{isrc}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            if cached_data.get('success'):
                return ISRCLookupResult(**cached_data['result'])
            else:
                # Cached failure
                return None
        
        return None
    
    def _cache_result(self, isrc: str, result: Optional[ISRCLookupResult], success: bool):
        """Cache ISRC lookup result"""
        cache_key = f"isrc_lookup_{isrc}"
        
        if success and result:
            cache_data = {
                'success': True,
                'result': asdict(result),
                'cached_at': timezone.now().isoformat()
            }
            cache.set(cache_key, cache_data, self.CACHE_TTL_SUCCESS)
        else:
            cache_data = {
                'success': False,
                'cached_at': timezone.now().isoformat()
            }
            cache.set(cache_key, cache_data, self.CACHE_TTL_FAILURE)
    
    def _perform_lookup(self, isrc: str) -> Optional[ISRCLookupResult]:
        """Perform the actual ISRC lookup"""
        try:
            # Get metadata from ACRCloud
            metadata = self.acrcloud_client.get_track_metadata(isrc)
            
            if not metadata:
                return None
            
            # Extract basic information
            title = metadata.get('title', '')
            artist = self._extract_artist_name(metadata)
            album = metadata.get('album', {}).get('name') if isinstance(metadata.get('album'), dict) else metadata.get('album')
            label = metadata.get('label')
            release_date = metadata.get('release_date')
            duration_ms = metadata.get('duration_ms')
            genre = metadata.get('genre')
            
            # Extract PRO affiliations
            pro_affiliations = self.pro_mapper.map_isrc_to_pro(isrc, metadata)
            pro_affiliations_dict = [
                {
                    'pro_code': aff.pro_code,
                    'pro_name': aff.pro_name,
                    'territory': aff.territory,
                    'publisher': aff.publisher,
                    'writer': aff.writer,
                    'composer': aff.composer,
                    'share_percentage': aff.share_percentage,
                    'work_id': aff.work_id
                }
                for aff in pro_affiliations
            ]
            
            # Extract publishers and writers
            publishers = self._extract_publishers(metadata)
            writers = self._extract_writers(metadata)
            
            # Extract external IDs
            external_ids = metadata.get('external_ids', {})
            
            # Calculate confidence based on data completeness
            confidence = self._calculate_confidence(metadata)
            
            return ISRCLookupResult(
                isrc=isrc,
                title=title,
                artist=artist,
                album=album,
                label=label,
                release_date=release_date,
                duration_ms=duration_ms,
                genre=genre,
                pro_affiliations=pro_affiliations_dict,
                publishers=publishers,
                writers=writers,
                external_ids=external_ids,
                lookup_source='acrcloud',
                confidence=confidence,
                last_updated=timezone.now().isoformat(),
                raw_metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"ISRC lookup performance error for {isrc}: {e}")
            return None
    
    def _extract_artist_name(self, metadata: Dict) -> str:
        """Extract artist name from metadata"""
        artists = metadata.get('artists', [])
        if isinstance(artists, list) and artists:
            return ', '.join([artist.get('name', '') for artist in artists if artist.get('name')])
        elif isinstance(artists, str):
            return artists
        
        # Fallback to artist field
        return metadata.get('artist', '')
    
    def _extract_publishers(self, metadata: Dict) -> List[Dict[str, Any]]:
        """Extract publisher information from metadata"""
        publishers = []
        
        publisher_data = metadata.get('publishers', [])
        if not isinstance(publisher_data, list):
            publisher_data = [publisher_data] if publisher_data else []
        
        for pub in publisher_data:
            if isinstance(pub, dict):
                publishers.append({
                    'name': pub.get('name', ''),
                    'share_percentage': pub.get('share', 0),
                    'territory': pub.get('territory', ''),
                    'role': pub.get('role', 'publisher')
                })
            elif isinstance(pub, str):
                publishers.append({
                    'name': pub,
                    'share_percentage': 0,
                    'territory': '',
                    'role': 'publisher'
                })
        
        return publishers
    
    def _extract_writers(self, metadata: Dict) -> List[Dict[str, Any]]:
        """Extract writer/composer information from metadata"""
        writers = []
        
        # Check multiple fields for writer information
        writer_fields = ['writers', 'composers', 'songwriters']
        
        for field in writer_fields:
            writer_data = metadata.get(field, [])
            if not isinstance(writer_data, list):
                writer_data = [writer_data] if writer_data else []
            
            for writer in writer_data:
                if isinstance(writer, dict):
                    writers.append({
                        'name': writer.get('name', ''),
                        'role': writer.get('role', field.rstrip('s')),  # Remove 's' from field name
                        'share_percentage': writer.get('share', 0),
                        'pro_affiliation': writer.get('pro', '')
                    })
                elif isinstance(writer, str):
                    writers.append({
                        'name': writer,
                        'role': field.rstrip('s'),
                        'share_percentage': 0,
                        'pro_affiliation': ''
                    })
        
        return writers
    
    def _calculate_confidence(self, metadata: Dict) -> float:
        """Calculate confidence score based on metadata completeness"""
        score = 0.0
        
        # Basic fields (40% of score)
        if metadata.get('title'):
            score += 0.15
        if metadata.get('artists') or metadata.get('artist'):
            score += 0.15
        if metadata.get('album'):
            score += 0.10
        
        # Additional metadata (30% of score)
        if metadata.get('label'):
            score += 0.10
        if metadata.get('release_date'):
            score += 0.10
        if metadata.get('duration_ms'):
            score += 0.10
        
        # Rights information (30% of score)
        if metadata.get('publishers'):
            score += 0.15
        if metadata.get('writers') or metadata.get('composers'):
            score += 0.15
        
        return min(1.0, score)
    
    def _deduplicate_pro_affiliations(self, affiliations: List[Dict]) -> List[Dict]:
        """Remove duplicate PRO affiliations"""
        seen = set()
        unique_affiliations = []
        
        for aff in affiliations:
            key = (aff.get('pro_code'), aff.get('territory'))
            if key not in seen:
                seen.add(key)
                unique_affiliations.append(aff)
        
        return unique_affiliations
    
    def _process_batch(self, isrcs: List[str], force_refresh: bool) -> Dict[str, Optional[ISRCLookupResult]]:
        """Process a batch of ISRCs"""
        results = {}
        
        for isrc in isrcs:
            try:
                result = self.lookup_isrc(isrc, force_refresh)
                results[isrc] = result
                
                # Small delay to avoid overwhelming the API
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing ISRC {isrc} in batch: {e}")
                results[isrc] = None
        
        return results
    
    def get_lookup_statistics(self) -> Dict[str, Any]:
        """Get ISRC lookup service statistics"""
        try:
            # This would typically query cache or database for statistics
            # For now, return basic configuration info
            return {
                'cache_ttl_success_hours': self.CACHE_TTL_SUCCESS / 3600,
                'cache_ttl_failure_hours': self.CACHE_TTL_FAILURE / 3600,
                'max_batch_size': self.MAX_BATCH_SIZE,
                'batch_timeout_seconds': self.BATCH_TIMEOUT_SECONDS,
                'supported_pro_count': len(self.pro_mapper.PRO_MAPPINGS)
            }
        except Exception as e:
            logger.error(f"Failed to get lookup statistics: {e}")
            return {'error': str(e)}


# Convenience functions
def lookup_single_isrc(isrc: str, force_refresh: bool = False) -> Optional[ISRCLookupResult]:
    """Lookup a single ISRC"""
    service = ISRCLookupService()
    return service.lookup_isrc(isrc, force_refresh)


def batch_lookup_isrcs(isrcs: List[str], force_refresh: bool = False) -> Dict[str, Optional[ISRCLookupResult]]:
    """Batch lookup multiple ISRCs"""
    service = ISRCLookupService()
    return service.batch_lookup_isrcs(isrcs, force_refresh)


def enrich_detection_with_isrc_data(detection_result: Dict, isrc: str) -> Dict:
    """Enrich detection result with ISRC data"""
    service = ISRCLookupService()
    return service.enrich_detection_with_isrc(detection_result, isrc)
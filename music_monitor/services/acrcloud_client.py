"""
ACRCloud Integration Client
Enhanced implementation with proper error handling, rate limiting, and PRO mapping
Handles external audio identification and ISRC lookup with comprehensive PRO mapping
"""

import base64
import hashlib
import hmac
import json
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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import librosa
import io

logger = logging.getLogger(__name__)


@dataclass
class ACRCloudMatch:
    """ACRCloud match result"""
    title: str
    artist: str
    album: Optional[str]
    isrc: Optional[str]
    iswc: Optional[str]
    label: Optional[str]
    release_date: Optional[str]
    duration_ms: int
    confidence: float
    play_offset_ms: int
    acrid: str
    external_ids: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class PROAffiliation:
    """PRO affiliation information"""
    pro_code: str
    pro_name: str
    territory: str
    publisher: Optional[str]
    writer: Optional[str]
    composer: Optional[str]
    share_percentage: Optional[float]
    work_id: Optional[str]


class ACRCloudClient:
    """
    Enhanced ACRCloud API client with comprehensive error handling, rate limiting, and caching
    """
    
    # ACRCloud API endpoints
    IDENTIFY_ENDPOINT = "https://identify-{region}.acrcloud.com/v1/identify"
    METADATA_ENDPOINT = "https://eu-api-v2.acrcloud.com/api/external-metadata/tracks"
    LOOKUP_ENDPOINT = "https://eu-api-v2.acrcloud.com/api/external-metadata/tracks/{isrc}"
    
    # Enhanced rate limiting settings
    MAX_REQUESTS_PER_MINUTE = 45  # Slightly below limit for safety
    MAX_REQUESTS_PER_DAY = 1800   # Conservative daily limit
    MAX_CONCURRENT_REQUESTS = 5   # Concurrent request limit
    
    # Cache settings
    CACHE_TTL_SECONDS = 3600      # 1 hour for identification results
    METADATA_CACHE_TTL = 86400    # 24 hours for metadata
    ERROR_CACHE_TTL = 300         # 5 minutes for error responses
    
    # Retry settings
    MAX_RETRY_ATTEMPTS = 3
    RETRY_BACKOFF_FACTOR = 2
    RETRY_STATUSES = [429, 500, 502, 503, 504]
    
    # Thread-safe rate limiting
    _request_lock = threading.Lock()
    _request_times = []
    
    def __init__(self, access_key: str = None, access_secret: str = None, 
                 host: str = None, region: str = "eu-west-1"):
        """
        Initialize ACRCloud client
        
        Args:
            access_key: ACRCloud access key (from settings if not provided)
            access_secret: ACRCloud access secret (from settings if not provided)
            host: ACRCloud host (from settings if not provided)
            region: ACRCloud region for identification
        """
        self.access_key = access_key or getattr(settings, 'ACRCLOUD_ACCESS_KEY', '')
        self.access_secret = access_secret or getattr(settings, 'ACRCLOUD_ACCESS_SECRET', '')
        self.host = host or getattr(settings, 'ACRCLOUD_HOST', '')
        self.region = region
        
        if not all([self.access_key, self.access_secret, self.host]):
            logger.warning("ACRCloud credentials not fully configured")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ZamIO-Platform/1.0'
        })
    
    def _generate_signature(self, method: str, uri: str, access_key: str, 
                          access_secret: str, timestamp: str) -> str:
        """Generate ACRCloud API signature"""
        string_to_sign = f"{method}\n{uri}\n{access_key}\ntext\n{timestamp}"
        signature = base64.b64encode(
            hmac.new(
                access_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')
        return signature
    
    def _check_rate_limit(self) -> Tuple[bool, Optional[float]]:
        """
        Enhanced rate limiting with thread safety and wait time calculation
        
        Returns:
            Tuple of (can_proceed, wait_time_seconds)
        """
        with self._request_lock:
            current_time = time.time()
            
            # Clean old request times (older than 1 minute)
            self._request_times = [t for t in self._request_times if current_time - t < 60]
            
            # Check minute limit
            if len(self._request_times) >= self.MAX_REQUESTS_PER_MINUTE:
                oldest_request = min(self._request_times)
                wait_time = 60 - (current_time - oldest_request)
                logger.warning(f"ACRCloud minute rate limit exceeded, wait {wait_time:.1f}s")
                return False, wait_time
            
            # Check daily limit using cache
            day_key = f"acrcloud_requests_day_{int(current_time // 86400)}"
            day_count = cache.get(day_key, 0)
            
            if day_count >= self.MAX_REQUESTS_PER_DAY:
                # Calculate time until next day
                next_day = ((int(current_time // 86400) + 1) * 86400)
                wait_time = next_day - current_time
                logger.warning(f"ACRCloud daily rate limit exceeded, wait {wait_time/3600:.1f}h")
                return False, wait_time
            
            # Record this request
            self._request_times.append(current_time)
            cache.set(day_key, day_count + 1, 86400)
            
            return True, None
    
    def _make_request(self, method: str, url: str, data: Dict = None, 
                     files: Dict = None, timeout: int = 30, retry_count: int = 0) -> Optional[Dict]:
        """
        Enhanced request method with retry logic and better error handling
        """
        # Check rate limits
        can_proceed, wait_time = self._check_rate_limit()
        if not can_proceed:
            if wait_time and wait_time < 300:  # Only wait up to 5 minutes
                logger.info(f"Rate limited, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                return self._make_request(method, url, data, files, timeout, retry_count)
            else:
                logger.error("Rate limit exceeded, request rejected")
                return None
        
        timestamp = str(int(time.time()))
        uri = url.split('/', 3)[-1] if '/' in url else url
        
        signature = self._generate_signature(
            method, f"/{uri}", self.access_key, self.access_secret, timestamp
        )
        
        auth_data = {
            'access_key': self.access_key,
            'timestamp': timestamp,
            'signature': signature,
            'data_type': 'text'
        }
        
        if data:
            auth_data.update(data)
        
        try:
            # Make the request
            if method.upper() == 'POST':
                if files:
                    response = self.session.post(url, data=auth_data, files=files, timeout=timeout)
                else:
                    response = self.session.post(url, data=auth_data, timeout=timeout)
            else:
                response = self.session.get(url, params=auth_data, timeout=timeout)
            
            # Handle different response codes
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"ACRCloud API response parsing failed: {e}")
                    return None
            
            elif response.status_code in self.RETRY_STATUSES and retry_count < self.MAX_RETRY_ATTEMPTS:
                wait_time = (self.RETRY_BACKOFF_FACTOR ** retry_count)
                logger.warning(f"ACRCloud API returned {response.status_code}, retrying in {wait_time}s (attempt {retry_count + 1})")
                time.sleep(wait_time)
                return self._make_request(method, url, data, files, timeout, retry_count + 1)
            
            else:
                logger.error(f"ACRCloud API request failed with status {response.status_code}: {response.text}")
                return None
            
        except requests.exceptions.Timeout:
            if retry_count < self.MAX_RETRY_ATTEMPTS:
                logger.warning(f"ACRCloud API timeout, retrying (attempt {retry_count + 1})")
                return self._make_request(method, url, data, files, timeout * 1.5, retry_count + 1)
            else:
                logger.error("ACRCloud API timeout after all retries")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if retry_count < self.MAX_RETRY_ATTEMPTS:
                wait_time = (self.RETRY_BACKOFF_FACTOR ** retry_count)
                logger.warning(f"ACRCloud API connection error, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                return self._make_request(method, url, data, files, timeout, retry_count + 1)
            else:
                logger.error(f"ACRCloud API connection failed after all retries: {e}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"ACRCloud API request failed: {e}")
            return None
    
    def identify_audio(self, audio_data: bytes, audio_format: str = 'wav') -> Optional[ACRCloudMatch]:
        """
        Identify audio using ACRCloud
        
        Args:
            audio_data: Raw audio data bytes
            audio_format: Audio format (wav, mp3, etc.)
            
        Returns:
            ACRCloudMatch object if successful, None otherwise
        """
        try:
            # Check cache first
            audio_hash = hashlib.md5(audio_data).hexdigest()
            cache_key = f"acrcloud_identify_{audio_hash}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                logger.debug("Returning cached ACRCloud result")
                return ACRCloudMatch(**cached_result)
            
            # Prepare request
            url = self.IDENTIFY_ENDPOINT.format(region=self.region)
            files = {
                'sample': ('audio_sample', audio_data, f'audio/{audio_format}')
            }
            
            data = {
                'sample_bytes': str(len(audio_data))
            }
            
            logger.info(f"Sending audio identification request to ACRCloud ({len(audio_data)} bytes)")
            
            response = self._make_request('POST', url, data=data, files=files)
            
            if not response:
                return None
            
            # Parse response
            if response.get('status', {}).get('code') != 0:
                error_msg = response.get('status', {}).get('msg', 'Unknown error')
                logger.warning(f"ACRCloud identification failed: {error_msg}")
                return None
            
            metadata = response.get('metadata', {})
            music_list = metadata.get('music', [])
            
            if not music_list:
                logger.info("No music matches found in ACRCloud response")
                return None
            
            # Get the best match (first result is usually best)
            best_match = music_list[0]
            
            # Extract match information
            match = ACRCloudMatch(
                title=best_match.get('title', ''),
                artist=', '.join([artist.get('name', '') for artist in best_match.get('artists', [])]),
                album=best_match.get('album', {}).get('name'),
                isrc=best_match.get('external_ids', {}).get('isrc'),
                iswc=best_match.get('external_ids', {}).get('iswc'),
                label=best_match.get('label'),
                release_date=best_match.get('release_date'),
                duration_ms=best_match.get('duration_ms', 0),
                confidence=best_match.get('score', 0),
                play_offset_ms=best_match.get('play_offset_ms', 0),
                acrid=best_match.get('acrid', ''),
                external_ids=best_match.get('external_ids', {}),
                metadata=best_match
            )
            
            # Cache the result
            cache.set(cache_key, match.__dict__, self.CACHE_TTL_SECONDS)
            
            logger.info(f"ACRCloud identified: {match.title} by {match.artist} (confidence: {match.confidence})")
            
            return match
            
        except Exception as e:
            logger.error(f"ACRCloud identification error: {e}")
            return None
    
    def get_track_metadata(self, isrc: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed track metadata by ISRC
        
        Args:
            isrc: International Standard Recording Code
            
        Returns:
            Dictionary with detailed metadata or None
        """
        try:
            # Check cache first
            cache_key = f"acrcloud_metadata_{isrc}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                logger.debug(f"Returning cached metadata for ISRC {isrc}")
                return cached_result
            
            # Make API request
            url = f"{self.METADATA_ENDPOINT}/{isrc}"
            response = self._make_request('GET', url)
            
            if not response:
                return None
            
            # Cache the result
            cache.set(cache_key, response, self.METADATA_CACHE_TTL)
            
            logger.info(f"Retrieved metadata for ISRC {isrc}")
            return response
            
        except Exception as e:
            logger.error(f"ACRCloud metadata lookup error for ISRC {isrc}: {e}")
            return None


class PROMapper:
    """
    Enhanced PRO mapping system with comprehensive international coverage
    Maps ISRCs and track metadata to Performing Rights Organizations (PROs)
    """
    
    # Comprehensive PRO mapping database
    PRO_MAPPINGS = {
        # North America
        'ASCAP': {
            'code': 'ascap',
            'name': 'American Society of Composers, Authors and Publishers',
            'territory': 'USA',
            'country_codes': ['US', 'USA'],
            'identifiers': ['ascap', 'ASCAP'],
            'api_endpoint': None,
            'reciprocal_rate': 0.15,
            'currency': 'USD'
        },
        'BMI': {
            'code': 'bmi',
            'name': 'Broadcast Music, Inc.',
            'territory': 'USA',
            'country_codes': ['US', 'USA'],
            'identifiers': ['bmi', 'BMI'],
            'api_endpoint': None,
            'reciprocal_rate': 0.15,
            'currency': 'USD'
        },
        'SOCAN': {
            'code': 'socan',
            'name': 'Society of Composers, Authors and Music Publishers of Canada',
            'territory': 'Canada',
            'country_codes': ['CA', 'CAN'],
            'identifiers': ['socan', 'SOCAN'],
            'api_endpoint': None,
            'reciprocal_rate': 0.12,
            'currency': 'CAD'
        },
        
        # Europe
        'PRS': {
            'code': 'prs',
            'name': 'Performing Right Society',
            'territory': 'United Kingdom',
            'country_codes': ['GB', 'UK'],
            'identifiers': ['prs', 'PRS', 'mcps-prs', 'prs for music'],
            'api_endpoint': None,
            'reciprocal_rate': 0.14,
            'currency': 'GBP'
        },
        'SACEM': {
            'code': 'sacem',
            'name': 'Société des auteurs, compositeurs et éditeurs de musique',
            'territory': 'France',
            'country_codes': ['FR', 'FRA'],
            'identifiers': ['sacem', 'SACEM'],
            'api_endpoint': None,
            'reciprocal_rate': 0.13,
            'currency': 'EUR'
        },
        'GEMA': {
            'code': 'gema',
            'name': 'Gesellschaft für musikalische Aufführungs- und mechanische Vervielfältigungsrechte',
            'territory': 'Germany',
            'country_codes': ['DE', 'DEU'],
            'identifiers': ['gema', 'GEMA'],
            'api_endpoint': None,
            'reciprocal_rate': 0.13,
            'currency': 'EUR'
        },
        'SIAE': {
            'code': 'siae',
            'name': 'Società Italiana degli Autori ed Editori',
            'territory': 'Italy',
            'country_codes': ['IT', 'ITA'],
            'identifiers': ['siae', 'SIAE'],
            'api_endpoint': None,
            'reciprocal_rate': 0.13,
            'currency': 'EUR'
        },
        'SGAE': {
            'code': 'sgae',
            'name': 'Sociedad General de Autores y Editores',
            'territory': 'Spain',
            'country_codes': ['ES', 'ESP'],
            'identifiers': ['sgae', 'SGAE'],
            'api_endpoint': None,
            'reciprocal_rate': 0.13,
            'currency': 'EUR'
        },
        
        # Asia-Pacific
        'JASRAC': {
            'code': 'jasrac',
            'name': 'Japanese Society for Rights of Authors, Composers and Publishers',
            'territory': 'Japan',
            'country_codes': ['JP', 'JPN'],
            'identifiers': ['jasrac', 'JASRAC'],
            'api_endpoint': None,
            'reciprocal_rate': 0.16,
            'currency': 'JPY'
        },
        'APRA': {
            'code': 'apra',
            'name': 'Australasian Performing Right Association',
            'territory': 'Australia',
            'country_codes': ['AU', 'AUS'],
            'identifiers': ['apra', 'APRA', 'amcos'],
            'api_endpoint': None,
            'reciprocal_rate': 0.14,
            'currency': 'AUD'
        },
        'KOMCA': {
            'code': 'komca',
            'name': 'Korea Music Copyright Association',
            'territory': 'South Korea',
            'country_codes': ['KR', 'KOR'],
            'identifiers': ['komca', 'KOMCA'],
            'api_endpoint': None,
            'reciprocal_rate': 0.15,
            'currency': 'KRW'
        },
        
        # Africa
        'GHAMRO': {
            'code': 'ghamro',
            'name': 'Ghana Music Rights Organisation',
            'territory': 'Ghana',
            'country_codes': ['GH', 'GHA'],
            'identifiers': ['ghamro', 'GHAMRO', 'ghana'],
            'api_endpoint': None,
            'reciprocal_rate': 0.10,  # Local PRO, lower rate
            'currency': 'GHS'
        },
        'SAMRO': {
            'code': 'samro',
            'name': 'Southern African Music Rights Organisation',
            'territory': 'South Africa',
            'country_codes': ['ZA', 'ZAF'],
            'identifiers': ['samro', 'SAMRO'],
            'api_endpoint': None,
            'reciprocal_rate': 0.12,
            'currency': 'ZAR'
        },
        'COSGA': {
            'code': 'cosga',
            'name': 'Copyright Society of Ghana',
            'territory': 'Ghana',
            'country_codes': ['GH', 'GHA'],
            'identifiers': ['cosga', 'COSGA'],
            'api_endpoint': None,
            'reciprocal_rate': 0.10,
            'currency': 'GHS'
        },
        
        # Latin America
        'UBC': {
            'code': 'ubc',
            'name': 'União Brasileira de Compositores',
            'territory': 'Brazil',
            'country_codes': ['BR', 'BRA'],
            'identifiers': ['ubc', 'UBC'],
            'api_endpoint': None,
            'reciprocal_rate': 0.14,
            'currency': 'BRL'
        },
        'SADAIC': {
            'code': 'sadaic',
            'name': 'Sociedad Argentina de Autores y Compositores de Música',
            'territory': 'Argentina',
            'country_codes': ['AR', 'ARG'],
            'identifiers': ['sadaic', 'SADAIC'],
            'api_endpoint': None,
            'reciprocal_rate': 0.13,
            'currency': 'ARS'
        }
    }
    
    # Territory to PRO mapping for quick lookup
    TERRITORY_PRO_MAP = {}
    
    def __init__(self):
        self.acrcloud_client = ACRCloudClient()
        self._build_territory_map()
    
    def _build_territory_map(self):
        """Build territory to PRO mapping for efficient lookups"""
        for pro_name, pro_info in self.PRO_MAPPINGS.items():
            territory = pro_info['territory'].lower()
            self.TERRITORY_PRO_MAP[territory] = pro_info['code']
            
            # Add country codes
            for country_code in pro_info.get('country_codes', []):
                self.TERRITORY_PRO_MAP[country_code.lower()] = pro_info['code']
    
    def map_isrc_to_pro(self, isrc: str, additional_metadata: Dict = None) -> List[PROAffiliation]:
        """
        Enhanced ISRC to PRO mapping with comprehensive metadata analysis
        
        Args:
            isrc: International Standard Recording Code
            additional_metadata: Additional metadata from ACRCloud response
            
        Returns:
            List of PROAffiliation objects
        """
        try:
            # Check cache first
            cache_key = f"pro_mapping_{isrc}"
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f"Returning cached PRO mapping for ISRC {isrc}")
                return [PROAffiliation(**aff) for aff in cached_result]
            
            affiliations = []
            
            # Get detailed metadata from ACRCloud
            metadata = self.acrcloud_client.get_track_metadata(isrc)
            if additional_metadata:
                metadata = {**(metadata or {}), **additional_metadata}
            
            if not metadata:
                logger.warning(f"No metadata found for ISRC {isrc}")
                # Return default local PRO
                default_affiliation = self._get_default_pro_affiliation()
                return [default_affiliation]
            
            # Extract PRO information from multiple sources
            affiliations.extend(self._extract_pro_from_metadata(metadata))
            affiliations.extend(self._extract_pro_from_territory(metadata))
            affiliations.extend(self._extract_pro_from_publishers(metadata))
            affiliations.extend(self._extract_pro_from_writers(metadata))
            affiliations.extend(self._extract_pro_from_labels(metadata))
            
            # Remove duplicates and validate
            unique_affiliations = self._deduplicate_affiliations(affiliations)
            
            # If no PRO found, default to local PRO
            if not unique_affiliations:
                unique_affiliations = [self._get_default_pro_affiliation()]
            
            # Cache the result
            cache_data = [asdict(aff) for aff in unique_affiliations]
            cache.set(cache_key, cache_data, self.acrcloud_client.METADATA_CACHE_TTL)
            
            logger.info(f"Mapped ISRC {isrc} to {len(unique_affiliations)} PRO affiliations")
            return unique_affiliations
            
        except Exception as e:
            logger.error(f"PRO mapping error for ISRC {isrc}: {e}")
            return [self._get_default_pro_affiliation()]
    
    def _extract_pro_from_metadata(self, metadata: Dict) -> List[PROAffiliation]:
        """Extract PRO information from explicit metadata fields"""
        affiliations = []
        
        # Check for explicit PRO mentions
        pro_info = metadata.get('rights_info', {}) or metadata.get('pro_info', {})
        
        if isinstance(pro_info, dict):
            for pro_name, pro_data in pro_info.items():
                if pro_name.upper() in self.PRO_MAPPINGS:
                    pro_config = self.PRO_MAPPINGS[pro_name.upper()]
                    affiliations.append(PROAffiliation(
                        pro_code=pro_config['code'],
                        pro_name=pro_config['name'],
                        territory=pro_config['territory'],
                        publisher=pro_data.get('publisher'),
                        writer=pro_data.get('writer'),
                        composer=pro_data.get('composer'),
                        share_percentage=pro_data.get('share', 100.0),
                        work_id=pro_data.get('work_id')
                    ))
        
        return affiliations
    
    def _extract_pro_from_territory(self, metadata: Dict) -> List[PROAffiliation]:
        """Extract PRO information from territory/country data"""
        affiliations = []
        
        # Check various territory fields
        territory_fields = ['territory', 'country', 'origin_country', 'release_territory']
        
        for field in territory_fields:
            territory = metadata.get(field)
            if territory:
                pro_affiliation = self._map_territory_to_pro(territory)
                if pro_affiliation:
                    affiliations.append(pro_affiliation)
                    break  # Use first valid territory mapping
        
        return affiliations
    
    def _extract_pro_from_publishers(self, metadata: Dict) -> List[PROAffiliation]:
        """Extract PRO information from publisher data"""
        affiliations = []
        
        publishers = metadata.get('publishers', []) or metadata.get('publisher', [])
        if not isinstance(publishers, list):
            publishers = [publishers] if publishers else []
        
        for publisher in publishers:
            if isinstance(publisher, dict):
                publisher_name = publisher.get('name', '')
                pro_affiliation = self._map_publisher_to_pro(publisher_name, publisher)
                if pro_affiliation:
                    affiliations.append(pro_affiliation)
            elif isinstance(publisher, str):
                pro_affiliation = self._map_publisher_to_pro(publisher, {})
                if pro_affiliation:
                    affiliations.append(pro_affiliation)
        
        return affiliations
    
    def _extract_pro_from_writers(self, metadata: Dict) -> List[PROAffiliation]:
        """Extract PRO information from writer/composer data"""
        affiliations = []
        
        writers = metadata.get('writers', []) or metadata.get('composers', [])
        if not isinstance(writers, list):
            writers = [writers] if writers else []
        
        for writer in writers:
            if isinstance(writer, dict):
                writer_name = writer.get('name', '')
                pro_affiliation = self._map_writer_to_pro(writer_name, writer)
                if pro_affiliation:
                    affiliations.append(pro_affiliation)
        
        return affiliations
    
    def _extract_pro_from_labels(self, metadata: Dict) -> List[PROAffiliation]:
        """Extract PRO information from record label data"""
        affiliations = []
        
        label = metadata.get('label') or metadata.get('record_label')
        if label:
            # Some labels have territory-specific operations
            label_lower = label.lower()
            
            # Map major labels to likely territories
            label_territory_map = {
                'universal': 'USA',
                'sony': 'USA', 
                'warner': 'USA',
                'emi': 'UK',
                'parlophone': 'UK',
                'columbia': 'USA',
                'atlantic': 'USA',
                'def jam': 'USA',
                'interscope': 'USA'
            }
            
            for label_key, territory in label_territory_map.items():
                if label_key in label_lower:
                    pro_affiliation = self._map_territory_to_pro(territory)
                    if pro_affiliation:
                        affiliations.append(pro_affiliation)
                        break
        
        return affiliations
    
    def _map_territory_to_pro(self, territory: str) -> Optional[PROAffiliation]:
        """Map territory to PRO affiliation"""
        territory_lower = territory.lower()
        pro_code = self.TERRITORY_PRO_MAP.get(territory_lower)
        
        if pro_code:
            # Find the PRO config
            for pro_name, pro_config in self.PRO_MAPPINGS.items():
                if pro_config['code'] == pro_code:
                    return PROAffiliation(
                        pro_code=pro_code,
                        pro_name=pro_config['name'],
                        territory=pro_config['territory'],
                        publisher=None,
                        writer=None,
                        composer=None,
                        share_percentage=100.0,
                        work_id=None
                    )
        
        return None
    
    def _map_publisher_to_pro(self, publisher_name: str, publisher_data: Dict) -> Optional[PROAffiliation]:
        """Map publisher to PRO affiliation"""
        publisher_lower = publisher_name.lower()
        
        # Known publisher to PRO mappings
        publisher_pro_map = {
            'universal music': 'ascap',
            'sony music': 'ascap',
            'warner music': 'ascap',
            'emi music': 'prs',
            'bmg rights': 'ascap',
            'kobalt music': 'ascap',
            'downtown music': 'ascap'
        }
        
        for pub_key, pro_code in publisher_pro_map.items():
            if pub_key in publisher_lower:
                pro_config = None
                for pro_name, config in self.PRO_MAPPINGS.items():
                    if config['code'] == pro_code:
                        pro_config = config
                        break
                
                if pro_config:
                    return PROAffiliation(
                        pro_code=pro_code,
                        pro_name=pro_config['name'],
                        territory=pro_config['territory'],
                        publisher=publisher_name,
                        writer=None,
                        composer=None,
                        share_percentage=publisher_data.get('share', 100.0),
                        work_id=publisher_data.get('work_id')
                    )
        
        return None
    
    def _map_writer_to_pro(self, writer_name: str, writer_data: Dict) -> Optional[PROAffiliation]:
        """Map writer to PRO affiliation"""
        # This would typically require a database of writer PRO affiliations
        # For now, we'll use territory information if available
        territory = writer_data.get('territory') or writer_data.get('country')
        if territory:
            return self._map_territory_to_pro(territory)
        
        return None
    
    def _deduplicate_affiliations(self, affiliations: List[PROAffiliation]) -> List[PROAffiliation]:
        """Remove duplicate PRO affiliations and merge share percentages"""
        pro_map = {}
        
        for aff in affiliations:
            key = (aff.pro_code, aff.territory)
            if key in pro_map:
                # Merge share percentages
                existing = pro_map[key]
                if existing.share_percentage and aff.share_percentage:
                    existing.share_percentage = min(100.0, existing.share_percentage + aff.share_percentage)
                # Keep more detailed information
                if not existing.publisher and aff.publisher:
                    existing.publisher = aff.publisher
                if not existing.writer and aff.writer:
                    existing.writer = aff.writer
                if not existing.work_id and aff.work_id:
                    existing.work_id = aff.work_id
            else:
                pro_map[key] = aff
        
        return list(pro_map.values())
    
    def _get_default_pro_affiliation(self) -> PROAffiliation:
        """Get default PRO affiliation (GHAMRO for Ghana)"""
        ghamro_config = self.PRO_MAPPINGS['GHAMRO']
        return PROAffiliation(
            pro_code=ghamro_config['code'],
            pro_name=ghamro_config['name'],
            territory=ghamro_config['territory'],
            publisher=None,
            writer=None,
            composer=None,
            share_percentage=100.0,
            work_id=None
        )


class HybridDetectionService:
    """
    Hybrid detection service that combines local fingerprinting with ACRCloud fallback
    """
    
    def __init__(self, local_confidence_threshold: float = 0.8, 
                 acrcloud_confidence_threshold: float = 0.7,
                 fallback_enabled: bool = True,
                 max_retries: int = 2,
                 processing_timeout: int = 30):
        """
        Initialize hybrid detection service
        
        Args:
            local_confidence_threshold: Minimum confidence for local matches
            acrcloud_confidence_threshold: Minimum confidence for ACRCloud matches
            fallback_enabled: Whether to use ACRCloud fallback
            max_retries: Maximum retry attempts
            processing_timeout: Processing timeout in seconds
        """
        self.local_threshold = local_confidence_threshold
        self.acrcloud_threshold = acrcloud_confidence_threshold
        self.fallback_enabled = fallback_enabled
        self.max_retries = max_retries
        self.processing_timeout = processing_timeout
        
        self.acrcloud_client = ACRCloudClient()
        self.pro_mapper = PROMapper()
        # Import here to avoid circular imports
        from .enhanced_fingerprinting import EnhancedFingerprintService
        self.fingerprint_service = EnhancedFingerprintService('fast')
    
    def identify_with_fallback(self, audio_data: bytes, local_fingerprints: List,
                             session_id: str = None, station_id: int = None) -> Tuple[Optional[Dict], str, Dict]:
        """
        Identify audio using local fingerprints first, then ACRCloud fallback
        
        Args:
            audio_data: Raw audio data bytes
            local_fingerprints: List of local fingerprints for matching
            session_id: Optional session identifier
            station_id: Optional station identifier
            
        Returns:
            Tuple of (match_result, detection_source, processing_metadata)
        """
        start_time = time.time()
        processing_metadata = {
            'local_processing_time_ms': 0,
            'acrcloud_processing_time_ms': 0,
            'total_processing_time_ms': 0,
            'fallback_used': False,
            'retry_count': 0
        }
        
        try:
            # Load audio samples
            samples, sr = librosa.load(io.BytesIO(audio_data), sr=44100, mono=True)
            
            if len(samples) == 0:
                processing_metadata['total_processing_time_ms'] = int((time.time() - start_time) * 1000)
                return None, 'error', processing_metadata
            
            # Try local detection first
            local_start = time.time()
            local_result = self._local_detection(samples, sr, local_fingerprints)
            processing_metadata['local_processing_time_ms'] = int((time.time() - local_start) * 1000)
            
            # Check if local detection is confident enough
            if (local_result and local_result.get('match') and 
                local_result.get('confidence', 0) >= self.local_threshold * 100):
                
                processing_metadata['total_processing_time_ms'] = int((time.time() - start_time) * 1000)
                return local_result, 'local', processing_metadata
            
            # Use ACRCloud fallback if enabled
            if self.fallback_enabled:
                processing_metadata['fallback_used'] = True
                
                acrcloud_start = time.time()
                acrcloud_result = self._acrcloud_detection_with_retry(audio_data, processing_metadata)
                processing_metadata['acrcloud_processing_time_ms'] = int((time.time() - acrcloud_start) * 1000)
                
                if acrcloud_result:
                    processing_metadata['total_processing_time_ms'] = int((time.time() - start_time) * 1000)
                    return acrcloud_result, 'acrcloud', processing_metadata
            
            # No match found
            processing_metadata['total_processing_time_ms'] = int((time.time() - start_time) * 1000)
            return None, 'hybrid', processing_metadata
            
        except Exception as e:
            logger.error(f"Hybrid detection error: {e}")
            processing_metadata['total_processing_time_ms'] = int((time.time() - start_time) * 1000)
            processing_metadata['error'] = str(e)
            return None, 'error', processing_metadata
    
    def _local_detection(self, samples: np.ndarray, sr: int, fingerprints: List) -> Optional[Dict]:
        """Perform local fingerprint detection"""
        try:
            from music_monitor.utils.match_engine import simple_match_mp3
            
            match_result = simple_match_mp3(samples, sr, fingerprints, min_match_threshold=5)
            
            if match_result.get('match'):
                return {
                    'match': True,
                    'song_id': match_result['song_id'],
                    'confidence': match_result.get('confidence', 0),
                    'hashes_matched': match_result.get('hashes_matched', 0),
                    'detection_method': 'local_fingerprint'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Local detection error: {e}")
            return None
    
    def _acrcloud_detection_with_retry(self, audio_data: bytes, processing_metadata: Dict) -> Optional[Dict]:
        """Perform ACRCloud detection with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                processing_metadata['retry_count'] = attempt
                
                acrcloud_match = self.acrcloud_client.identify_audio(audio_data)
                
                if (acrcloud_match and 
                    acrcloud_match.confidence >= self.acrcloud_threshold * 100):
                    
                    # Map to PROs
                    pro_affiliations = []
                    if acrcloud_match.isrc:
                        pro_affiliations = self.pro_mapper.map_isrc_to_pro(
                            acrcloud_match.isrc, 
                            acrcloud_match.metadata
                        )
                    
                    return {
                        'match': True,
                        'title': acrcloud_match.title,
                        'artist': acrcloud_match.artist,
                        'album': acrcloud_match.album,
                        'isrc': acrcloud_match.isrc,
                        'iswc': acrcloud_match.iswc,
                        'confidence': acrcloud_match.confidence,
                        'acrid': acrcloud_match.acrid,
                        'label': acrcloud_match.label,
                        'release_date': acrcloud_match.release_date,
                        'pro_affiliations': [asdict(aff) for aff in pro_affiliations],
                        'external_metadata': acrcloud_match.metadata,
                        'detection_method': 'acrcloud'
                    }
                
                # If confidence too low, don't retry
                if acrcloud_match:
                    logger.info(f"ACRCloud confidence {acrcloud_match.confidence} below threshold {self.acrcloud_threshold * 100}")
                    break
                
            except Exception as e:
                logger.warning(f"ACRCloud detection attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries:
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
                else:
                    processing_metadata['final_error'] = str(e)
        
        return None
    
    def batch_identify(self, audio_segments: List[Tuple[bytes, str]], 
                      local_fingerprints: List) -> List[Dict[str, Any]]:
        """
        Batch identify multiple audio segments
        
        Args:
            audio_segments: List of (audio_data, segment_id) tuples
            local_fingerprints: Local fingerprints for matching
            
        Returns:
            List of detection results
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all detection tasks
            future_to_segment = {
                executor.submit(
                    self.identify_with_fallback, 
                    audio_data, 
                    local_fingerprints, 
                    segment_id
                ): segment_id
                for audio_data, segment_id in audio_segments
            }
            
            # Collect results
            for future in as_completed(future_to_segment):
                segment_id = future_to_segment[future]
                try:
                    match_result, detection_source, processing_metadata = future.result()
                    results.append({
                        'segment_id': segment_id,
                        'match_result': match_result,
                        'detection_source': detection_source,
                        'processing_metadata': processing_metadata
                    })
                except Exception as e:
                    logger.error(f"Batch detection failed for segment {segment_id}: {e}")
                    results.append({
                        'segment_id': segment_id,
                        'match_result': None,
                        'detection_source': 'error',
                        'processing_metadata': {'error': str(e)}
                    })
        
        return results
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """Get detection performance statistics"""
        try:
            # This would typically query detection logs/database
            # For now, return basic configuration info
            return {
                'local_threshold': self.local_threshold,
                'acrcloud_threshold': self.acrcloud_threshold,
                'fallback_enabled': self.fallback_enabled,
                'max_retries': self.max_retries,
                'processing_timeout': self.processing_timeout,
                'pro_mappings_count': len(self.pro_mapper.PRO_MAPPINGS),
                'supported_territories': list(self.pro_mapper.TERRITORY_PRO_MAP.keys())
            }
        except Exception as e:
            logger.error(f"Failed to get detection statistics: {e}")
            return {'error': str(e)}
            # Some labels have territory-specific operations
            label_lower = label.lower()
            
            # Map major labels to likely territories
            label_territory_map = {
                'universal': 'USA',
                'sony': 'USA', 
                'warner': 'USA',
                'emi': 'UK',
                'parlophone': 'UK',
                'columbia': 'USA',
                'atlantic': 'USA',
                'def jam': 'USA',
                'interscope': 'USA'
            }
            
            for label_key, territory in label_territory_map.items():
                if label_key in label_lower:
                    pro_affiliation = self._map_territory_to_pro(territory)
                    if pro_affiliation:
                        affiliations.append(pro_affiliation)
                        break
        
        return affiliations
    
    def _deduplicate_affiliations(self, affiliations: List[PROAffiliation]) -> List[PROAffiliation]:
        """Remove duplicate PRO affiliations and merge share percentages"""
        pro_map = {}
        
        for aff in affiliations:
            key = (aff.pro_code, aff.territory)
            if key in pro_map:
                # Merge share percentages
                existing = pro_map[key]
                if existing.share_percentage and aff.share_percentage:
                    existing.share_percentage = min(100.0, existing.share_percentage + aff.share_percentage)
                # Keep more detailed information
                if not existing.publisher and aff.publisher:
                    existing.publisher = aff.publisher
                if not existing.writer and aff.writer:
                    existing.writer = aff.writer
                if not existing.work_id and aff.work_id:
                    existing.work_id = aff.work_id
            else:
                pro_map[key] = aff
        
        return list(pro_map.values())
    
    def _get_default_pro_affiliation(self) -> PROAffiliation:
        """Get default PRO affiliation (GHAMRO for Ghana)"""
        ghamro_config = self.PRO_MAPPINGS.get('GHAMRO', {})
        return PROAffiliation(
            pro_code=ghamro_config.get('code', 'ghamro'),
            pro_name=ghamro_config.get('name', 'Ghana Music Rights Organisation'),
            territory=ghamro_config.get('territory', 'Ghana'),
            publisher=None,
            writer=None,
            composer=None,
            share_percentage=100.0,
            work_id=None
        )
    
    def _map_territory_to_pro(self, territory: str) -> Optional[PROAffiliation]:
        """Map territory to PRO affiliation"""
        if not territory:
            return None
        
        territory_lower = territory.lower()
        pro_code = self.TERRITORY_PRO_MAP.get(territory_lower)
        
        if not pro_code:
            return None
        
        # Find PRO config by code
        for pro_name, pro_config in self.PRO_MAPPINGS.items():
            if pro_config['code'] == pro_code:
                return PROAffiliation(
                    pro_code=pro_code,
                    pro_name=pro_config['name'],
                    territory=pro_config['territory'],
                    publisher=None,
                    writer=None,
                    composer=None,
                    share_percentage=100.0,
                    work_id=None
                )
        
        return None
    
    def _map_publisher_to_pro(self, publisher_name: str, publisher_data: Dict) -> Optional[PROAffiliation]:
        """Map publisher to PRO affiliation"""
        if not publisher_name:
            return None
        
        publisher_lower = publisher_name.lower()
        
        # Check for explicit PRO mentions in publisher name
        for pro_name, pro_config in self.PRO_MAPPINGS.items():
            for identifier in pro_config.get('identifiers', []):
                if identifier.lower() in publisher_lower:
                    return PROAffiliation(
                        pro_code=pro_config['code'],
                        pro_name=pro_config['name'],
                        territory=pro_config['territory'],
                        publisher=publisher_name,
                        writer=None,
                        composer=None,
                        share_percentage=publisher_data.get('share', 100.0),
                        work_id=publisher_data.get('work_id')
                    )
        
        return None
    
    def _map_writer_to_pro(self, writer_name: str, writer_data: Dict) -> Optional[PROAffiliation]:
        """Map writer to PRO affiliation"""
        if not writer_name:
            return None
        
        # Check if writer data contains explicit PRO information
        pro_affiliation = writer_data.get('pro_affiliation') or writer_data.get('pro')
        
        if pro_affiliation:
            pro_lower = pro_affiliation.lower()
            for pro_name, pro_config in self.PRO_MAPPINGS.items():
                for identifier in pro_config.get('identifiers', []):
                    if identifier.lower() == pro_lower:
                        return PROAffiliation(
                            pro_code=pro_config['code'],
                            pro_name=pro_config['name'],
                            territory=pro_config['territory'],
                            publisher=None,
                            writer=writer_name,
                            composer=writer_name if writer_data.get('role') == 'composer' else None,
                            share_percentage=writer_data.get('share', 100.0),
                            work_id=writer_data.get('work_id')
                        )
        
        return None


class HybridDetectionService:
    """
    Hybrid detection service that combines local fingerprinting with ACRCloud fallback
    """
    
    def __init__(self, local_confidence_threshold: float = 0.8, 
                 acrcloud_confidence_threshold: float = 0.7):
        """
        Initialize hybrid detection service
        
        Args:
            local_confidence_threshold: Minimum confidence for local matches
            acrcloud_confidence_threshold: Minimum confidence for ACRCloud matches
        """
        self.local_confidence_threshold = local_confidence_threshold
        self.acrcloud_confidence_threshold = acrcloud_confidence_threshold
        self.acrcloud_client = ACRCloudClient()
        self.pro_mapper = PROMapper()
        
        # Import here to avoid circular imports
        from music_monitor.services.enhanced_fingerprinting import EnhancedFingerprintService
        self.fingerprint_service = EnhancedFingerprintService('fast')
    
    def identify_with_fallback(self, audio_data: bytes, local_fingerprints: List[Tuple[int, str, int]], 
                             session_id: str = None) -> Tuple[Optional[Dict], str, Dict]:
        """
        Identify audio using local fingerprints first, then ACRCloud fallback
        
        Args:
            audio_data: Raw audio data bytes
            local_fingerprints: List of (track_id, hash, offset) tuples
            session_id: Optional session identifier for tracking
            
        Returns:
            Tuple of (match_result, detection_source, processing_metadata)
        """
        import librosa
        import io
        from music_monitor.utils.match_engine import simple_match_mp3
        
        processing_metadata = {
            'session_id': session_id,
            'local_fingerprints_count': len(local_fingerprints),
            'processing_steps': [],
            'total_processing_time_ms': 0
        }
        
        start_time = time.time()
        
        try:
            # Load audio samples
            samples, sr = librosa.load(io.BytesIO(audio_data), sr=44100, mono=True)
            
            if len(samples) == 0:
                processing_metadata['error'] = 'No audio samples found'
                return None, 'error', processing_metadata
            
            processing_metadata['audio_duration_seconds'] = len(samples) / sr
            processing_metadata['processing_steps'].append('audio_loaded')
            
            # Step 1: Try local fingerprinting first
            logger.info(f"Attempting local fingerprint matching with {len(local_fingerprints)} fingerprints")
            
            local_start = time.time()
            local_match = simple_match_mp3(
                samples, sr, local_fingerprints, 
                min_match_threshold=5
            )
            local_time = (time.time() - local_start) * 1000
            
            processing_metadata['local_processing_time_ms'] = local_time
            processing_metadata['processing_steps'].append('local_matching_attempted')
            
            # Check if local match meets confidence threshold
            if (local_match.get('match') and 
                local_match.get('confidence', 0) >= self.local_confidence_threshold * 100):
                
                processing_metadata['total_processing_time_ms'] = (time.time() - start_time) * 1000
                processing_metadata['processing_steps'].append('local_match_successful')
                
                logger.info(f"Local match found: track {local_match['song_id']} "
                           f"with confidence {local_match['confidence']}%")
                
                return local_match, 'local', processing_metadata
            
            # Step 2: Fallback to ACRCloud if local matching failed or low confidence
            logger.info("Local matching failed or low confidence, falling back to ACRCloud")
            processing_metadata['processing_steps'].append('acrcloud_fallback_initiated')
            
            acrcloud_start = time.time()
            acrcloud_match = self.acrcloud_client.identify_audio(audio_data)
            acrcloud_time = (time.time() - acrcloud_start) * 1000
            
            processing_metadata['acrcloud_processing_time_ms'] = acrcloud_time
            processing_metadata['processing_steps'].append('acrcloud_matching_attempted')
            
            if not acrcloud_match:
                processing_metadata['total_processing_time_ms'] = (time.time() - start_time) * 1000
                processing_metadata['processing_steps'].append('no_match_found')
                
                logger.info("No match found in ACRCloud")
                return None, 'acrcloud', processing_metadata
            
            # Check ACRCloud confidence threshold
            if acrcloud_match.confidence < self.acrcloud_confidence_threshold * 100:
                processing_metadata['total_processing_time_ms'] = (time.time() - start_time) * 1000
                processing_metadata['processing_steps'].append('acrcloud_low_confidence')
                
                logger.info(f"ACRCloud match confidence too low: {acrcloud_match.confidence}%")
                return None, 'acrcloud', processing_metadata
            
            # Step 3: Map ACRCloud result to PRO affiliations
            pro_affiliations = []
            if acrcloud_match.isrc:
                try:
                    affiliations = self.pro_mapper.map_isrc_to_pro(
                        acrcloud_match.isrc, acrcloud_match.metadata
                    )
                    pro_affiliations = [
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
                        for aff in affiliations
                    ]
                    processing_metadata['processing_steps'].append('pro_mapping_completed')
                except Exception as e:
                    logger.warning(f"PRO mapping failed: {e}")
                    processing_metadata['pro_mapping_error'] = str(e)
            
            # Format ACRCloud result
            acrcloud_result = {
                'title': acrcloud_match.title,
                'artist': acrcloud_match.artist,
                'album': acrcloud_match.album,
                'isrc': acrcloud_match.isrc,
                'iswc': acrcloud_match.iswc,
                'confidence': acrcloud_match.confidence,
                'duration_ms': acrcloud_match.duration_ms,
                'acrid': acrcloud_match.acrid,
                'label': acrcloud_match.label,
                'release_date': acrcloud_match.release_date,
                'pro_affiliations': pro_affiliations,
                'external_metadata': acrcloud_match.metadata
            }
            
            processing_metadata['total_processing_time_ms'] = (time.time() - start_time) * 1000
            processing_metadata['processing_steps'].append('acrcloud_match_successful')
            
            logger.info(f"ACRCloud match found: {acrcloud_match.title} by {acrcloud_match.artist} "
                       f"with confidence {acrcloud_match.confidence}%")
            
            return acrcloud_result, 'acrcloud', processing_metadata
            
        except Exception as e:
            processing_metadata['total_processing_time_ms'] = (time.time() - start_time) * 1000
            processing_metadata['error'] = str(e)
            processing_metadata['processing_steps'].append('error_occurred')
            
            logger.error(f"Hybrid detection error: {e}")
            return None, 'error', processing_metadata
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """Get detection service statistics"""
        try:
            from django.db.models import Count, Avg
            from music_monitor.models import AudioDetection
            
            # Get detection statistics by source
            detection_stats = AudioDetection.objects.values('detection_source').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence_score')
            )
            
            # Get recent detection performance
            recent_detections = AudioDetection.objects.filter(
                detected_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            return {
                'detection_sources': list(detection_stats),
                'recent_detections_7_days': recent_detections,
                'local_confidence_threshold': self.local_confidence_threshold,
                'acrcloud_confidence_threshold': self.acrcloud_confidence_threshold,
                'acrcloud_configured': bool(
                    self.acrcloud_client.access_key and 
                    self.acrcloud_client.access_secret
                )
            }
            
        except Exception as e:
            logger.error(f"Failed to get detection statistics: {e}")
            return {'error': str(e)}
        
        if default_pro.upper() in self.PRO_MAPPINGS:
            pro_config = self.PRO_MAPPINGS[default_pro.upper()]
            return PROAffiliation(
                pro_code=pro_config['code'],
                pro_name=pro_config['name'],
                territory=pro_config['territory'],
                publisher=None,
                writer=None,
                composer=None,
                share_percentage=100.0,
                work_id=None
            )
        
        # Fallback to GHAMRO
        pro_config = self.PRO_MAPPINGS['GHAMRO']
        return PROAffiliation(
            pro_code=pro_config['code'],
            pro_name=pro_config['name'],
            territory=pro_config['territory'],
            publisher=None,
            writer=None,
            composer=None,
            share_percentage=100.0,
            work_id=None
        )
    
    def _map_territory_to_pro(self, territory: str) -> Optional[PROAffiliation]:
        """Map territory/country to default PRO"""
        territory_mappings = {
            'US': 'ASCAP',  # Default to ASCAP for US (could also be BMI)
            'USA': 'ASCAP',
            'United States': 'ASCAP',
            'UK': 'PRS',
            'United Kingdom': 'PRS',
            'GB': 'PRS',
            'France': 'SACEM',
            'FR': 'SACEM',
            'Germany': 'GEMA',
            'DE': 'GEMA',
            'Japan': 'JASRAC',
            'JP': 'JASRAC',
            'Canada': 'SOCAN',
            'CA': 'SOCAN',
            'Australia': 'APRA',
            'AU': 'APRA',
            'Ghana': 'GHAMRO',
            'GH': 'GHAMRO'
        }
        
        pro_name = territory_mappings.get(territory)
        if pro_name and pro_name in self.PRO_MAPPINGS:
            pro_info = self.PRO_MAPPINGS[pro_name]
            return PROAffiliation(
                pro_code=pro_info['code'],
                pro_name=pro_info['name'],
                territory=pro_info['territory'],
                publisher=None,
                writer=None,
                composer=None,
                share_percentage=100.0,
                work_id=None
            )
        
        return None
    
    def _map_publisher_to_pro(self, publisher_name: str, publisher_info: Dict) -> Optional[PROAffiliation]:
        """Map publisher to PRO based on name patterns"""
        publisher_lower = publisher_name.lower()
        
        # Check for PRO identifiers in publisher name
        for pro_name, pro_info in self.PRO_MAPPINGS.items():
            for identifier in pro_info['identifiers']:
                if identifier.lower() in publisher_lower:
                    return PROAffiliation(
                        pro_code=pro_info['code'],
                        pro_name=pro_info['name'],
                        territory=pro_info['territory'],
                        publisher=publisher_name,
                        writer=None,
                        composer=None,
                        share_percentage=publisher_info.get('share_percentage', 100.0),
                        work_id=publisher_info.get('work_id')
                    )
        
        return None
    
    def _map_writer_to_pro(self, writer_name: str, writer_info: Dict) -> Optional[PROAffiliation]:
        """Map writer to PRO based on affiliation information"""
        # This would typically require a database of writer-PRO affiliations
        # For now, we'll return None and rely on territory mapping
        return None
    
    def get_pro_info(self, pro_code: str) -> Optional[Dict[str, Any]]:
        """Get PRO information by code"""
        for pro_name, pro_info in self.PRO_MAPPINGS.items():
            if pro_info['code'] == pro_code:
                return pro_info
        return None
    
    def get_all_pros(self) -> Dict[str, Dict[str, Any]]:
        """Get all PRO mappings"""
        return self.PRO_MAPPINGS.copy()


class HybridDetectionService:
    """
    Enhanced hybrid detection service with intelligent fallback logic and comprehensive error handling
    """
    
    def __init__(self):
        self.acrcloud_client = ACRCloudClient()
        self.pro_mapper = PROMapper()
        self.config = getattr(settings, 'AUDIO_DETECTION_CONFIG', {})
        
        # Detection thresholds from settings
        self.local_threshold = self.config.get('LOCAL_CONFIDENCE_THRESHOLD', 0.8)
        self.acrcloud_threshold = self.config.get('ACRCLOUD_CONFIDENCE_THRESHOLD', 0.7)
        self.fallback_enabled = self.config.get('HYBRID_FALLBACK_ENABLED', True)
        self.max_retries = self.config.get('MAX_RETRY_ATTEMPTS', 3)
        self.processing_timeout = self.config.get('PROCESSING_TIMEOUT_SECONDS', 30)
    
    def identify_with_fallback(self, audio_data: bytes, local_fingerprints: List[Tuple],
                             session_id: str = None, station_id: int = None) -> Tuple[Optional[Dict], str, Dict]:
        """
        Enhanced audio identification with intelligent fallback logic
        
        Args:
            audio_data: Raw audio data bytes
            local_fingerprints: List of (track_id, hash, offset) tuples
            session_id: Optional session ID for tracking
            station_id: Optional station ID for context
            
        Returns:
            Tuple of (match_result, detection_source, processing_metadata)
        """
        processing_start = time.time()
        processing_metadata = {
            'session_id': session_id,
            'station_id': station_id,
            'processing_start': processing_start,
            'local_attempted': False,
            'acrcloud_attempted': False,
            'errors': [],
            'performance_metrics': {}
        }
        
        try:
            # Validate input
            if not audio_data or len(audio_data) == 0:
                processing_metadata['errors'].append('Empty audio data')
                return None, 'error', processing_metadata
            
            # Step 1: Try local fingerprinting first
            local_result, local_metadata = self._try_local_detection(
                audio_data, local_fingerprints, processing_metadata
            )
            
            if local_result and local_result.get('match'):
                confidence = local_result.get('confidence', 0)
                if confidence >= self.local_threshold * 100:
                    logger.info(f"Local match found with confidence {confidence}% (session: {session_id})")
                    processing_metadata['final_source'] = 'local'
                    processing_metadata['processing_time'] = time.time() - processing_start
                    return local_result, 'local', processing_metadata
                else:
                    logger.info(f"Local match confidence {confidence}% below threshold {self.local_threshold * 100}%")
            
            # Step 2: Fallback to ACRCloud if enabled and local failed
            if self.fallback_enabled:
                acrcloud_result, acrcloud_metadata = self._try_acrcloud_detection(
                    audio_data, processing_metadata
                )
                
                if acrcloud_result and acrcloud_result.get('match'):
                    confidence = acrcloud_result.get('confidence', 0)
                    if confidence >= self.acrcloud_threshold * 100:
                        logger.info(f"ACRCloud match found with confidence {confidence}% (session: {session_id})")
                        processing_metadata['final_source'] = 'acrcloud'
                        processing_metadata['processing_time'] = time.time() - processing_start
                        return acrcloud_result, 'acrcloud', processing_metadata
                    else:
                        logger.info(f"ACRCloud match confidence {confidence}% below threshold {self.acrcloud_threshold * 100}%")
            
            # No matches found
            logger.info(f"No matches found in hybrid detection (session: {session_id})")
            processing_metadata['final_source'] = 'none'
            processing_metadata['processing_time'] = time.time() - processing_start
            return None, 'none', processing_metadata
            
        except Exception as e:
            logger.error(f"Hybrid detection error (session: {session_id}): {e}")
            processing_metadata['errors'].append(f"Hybrid detection error: {str(e)}")
            processing_metadata['processing_time'] = time.time() - processing_start
            return None, 'error', processing_metadata
    
    def _try_local_detection(self, audio_data: bytes, local_fingerprints: List[Tuple], 
                           metadata: Dict) -> Tuple[Optional[Dict], Dict]:
        """Try local fingerprint detection"""
        local_start = time.time()
        metadata['local_attempted'] = True
        
        try:
            if not local_fingerprints:
                logger.debug("No local fingerprints available for matching")
                metadata['local_skip_reason'] = 'no_fingerprints'
                return None, {'processing_time': time.time() - local_start}
            
            # Load audio samples
            from music_monitor.utils.match_engine import simple_match_mp3
            import librosa
            import io
            
            samples, sr = librosa.load(io.BytesIO(audio_data), sr=44100, mono=True)
            
            if len(samples) == 0:
                logger.warning("No audio samples loaded for local detection")
                metadata['local_skip_reason'] = 'no_samples'
                return None, {'processing_time': time.time() - local_start}
            
            # Perform local matching
            local_result = simple_match_mp3(
                samples, sr, local_fingerprints, 
                min_match_threshold=5
            )
            
            local_processing_time = time.time() - local_start
            metadata['performance_metrics']['local_processing_time'] = local_processing_time
            
            if local_result.get('match'):
                # Enhance result with additional metadata
                local_result['detection_source'] = 'local'
                local_result['processing_time_ms'] = int(local_processing_time * 1000)
                local_result['audio_duration_seconds'] = len(samples) / sr
                
                logger.debug(f"Local detection completed in {local_processing_time:.3f}s")
                return local_result, {'processing_time': local_processing_time}
            else:
                logger.debug(f"Local detection found no matches in {local_processing_time:.3f}s")
                return local_result, {'processing_time': local_processing_time}
                
        except Exception as e:
            logger.error(f"Local detection error: {e}")
            metadata['errors'].append(f"Local detection error: {str(e)}")
            return None, {'processing_time': time.time() - local_start, 'error': str(e)}
    
    def _try_acrcloud_detection(self, audio_data: bytes, metadata: Dict) -> Tuple[Optional[Dict], Dict]:
        """Try ACRCloud external detection"""
        acrcloud_start = time.time()
        metadata['acrcloud_attempted'] = True
        
        try:
            # Identify with ACRCloud
            acrcloud_match = self.acrcloud_client.identify_audio(audio_data)
            
            if not acrcloud_match:
                logger.debug("ACRCloud returned no match")
                acrcloud_processing_time = time.time() - acrcloud_start
                metadata['performance_metrics']['acrcloud_processing_time'] = acrcloud_processing_time
                return None, {'processing_time': acrcloud_processing_time}
            
            # Map to PRO affiliations
            pro_affiliations = []
            if acrcloud_match.isrc:
                try:
                    pro_affiliations = self.pro_mapper.map_isrc_to_pro(
                        acrcloud_match.isrc, 
                        acrcloud_match.metadata
                    )
                except Exception as e:
                    logger.warning(f"PRO mapping failed for ISRC {acrcloud_match.isrc}: {e}")
                    metadata['errors'].append(f"PRO mapping error: {str(e)}")
            
            # Build comprehensive result
            result = {
                'match': True,
                'title': acrcloud_match.title,
                'artist': acrcloud_match.artist,
                'album': acrcloud_match.album,
                'isrc': acrcloud_match.isrc,
                'iswc': acrcloud_match.iswc,
                'confidence': acrcloud_match.confidence,
                'duration_ms': acrcloud_match.duration_ms,
                'play_offset_ms': acrcloud_match.play_offset_ms,
                'acrid': acrcloud_match.acrid,
                'detection_source': 'acrcloud',
                'label': acrcloud_match.label,
                'release_date': acrcloud_match.release_date,
                'external_ids': acrcloud_match.external_ids,
                'pro_affiliations': [
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
                ],
                'external_metadata': acrcloud_match.metadata
            }
            
            acrcloud_processing_time = time.time() - acrcloud_start
            result['processing_time_ms'] = int(acrcloud_processing_time * 1000)
            metadata['performance_metrics']['acrcloud_processing_time'] = acrcloud_processing_time
            
            logger.debug(f"ACRCloud detection completed in {acrcloud_processing_time:.3f}s")
            return result, {'processing_time': acrcloud_processing_time}
            
        except Exception as e:
            logger.error(f"ACRCloud detection error: {e}")
            metadata['errors'].append(f"ACRCloud detection error: {str(e)}")
            return None, {'processing_time': time.time() - acrcloud_start, 'error': str(e)}
    
    def batch_identify(self, audio_segments: List[Tuple[bytes, str]], local_fingerprints: List[Tuple],
                      max_workers: int = 3) -> List[Dict]:
        """
        Batch process multiple audio segments with parallel processing
        
        Args:
            audio_segments: List of (audio_data, segment_id) tuples
            local_fingerprints: Local fingerprint database
            max_workers: Maximum concurrent workers
            
        Returns:
            List of detection results
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=min(max_workers, len(audio_segments))) as executor:
            # Submit all tasks
            future_to_segment = {
                executor.submit(
                    self.identify_with_fallback, 
                    audio_data, 
                    local_fingerprints, 
                    segment_id
                ): segment_id
                for audio_data, segment_id in audio_segments
            }
            
            # Collect results
            for future in as_completed(future_to_segment):
                segment_id = future_to_segment[future]
                try:
                    match_result, source, metadata = future.result()
                    results.append({
                        'segment_id': segment_id,
                        'match_result': match_result,
                        'detection_source': source,
                        'processing_metadata': metadata
                    })
                except Exception as e:
                    logger.error(f"Batch processing error for segment {segment_id}: {e}")
                    results.append({
                        'segment_id': segment_id,
                        'match_result': None,
                        'detection_source': 'error',
                        'processing_metadata': {'error': str(e)}
                    })
        
        return results
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """Get detection performance statistics"""
        try:
            # This would typically query detection logs/database
            # For now, return basic configuration info
            return {
                'local_threshold': self.local_threshold,
                'acrcloud_threshold': self.acrcloud_threshold,
                'fallback_enabled': self.fallback_enabled,
                'max_retries': self.max_retries,
                'processing_timeout': self.processing_timeout,
                'pro_mappings_count': len(self.pro_mapper.PRO_MAPPINGS),
                'supported_territories': list(self.pro_mapper.TERRITORY_PRO_MAP.keys())
            }
        except Exception as e:
            logger.error(f"Failed to get detection statistics: {e}")
            return {'error': str(e)}
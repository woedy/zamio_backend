# Hybrid Audio Detection Pipeline

## Overview

The Hybrid Audio Detection Pipeline is a comprehensive system that combines local fingerprinting with external ACRCloud identification to provide robust music detection capabilities for the ZamIO platform. This system implements the requirements from task 3 of the platform UI improvements specification.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hybrid Detection Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Enhanced Local  │  │ ACRCloud        │  │ Real-time       │ │
│  │ Fingerprinting  │  │ Integration     │  │ Stream Monitor  │ │
│  │                 │  │                 │  │                 │ │
│  │ • Optimized     │  │ • External ID   │  │ • Continuous    │ │
│  │   Algorithm     │  │ • ISRC Lookup   │  │   Monitoring    │ │
│  │ • Quality       │  │ • PRO Mapping   │  │ • Health Check  │ │
│  │   Assessment    │  │ • Rate Limiting │  │ • WebSocket     │ │
│  │ • Versioning    │  │ • Retry Logic   │  │   Broadcasting  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           │                     │                     │         │
│           └─────────────────────┼─────────────────────┘         │
│                                 │                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              Hybrid Detection Service                       │ │
│  │  • Local fingerprint matching (primary)                    │ │
│  │  • ACRCloud fallback (secondary)                           │ │
│  │  • Confidence-based routing                                │ │
│  │  • PRO affiliation mapping                                 │ │
│  │  • Comprehensive error handling                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Enhanced Local Fingerprinting (`enhanced_fingerprinting.py`)

**Features:**
- Optimized fingerprinting algorithm with configurable performance profiles
- Quality assessment and confidence scoring
- Fingerprint versioning and metadata tracking
- Batch processing capabilities
- Performance metrics and statistics

**Configurations:**
- `fast`: Quick processing for real-time detection
- `balanced`: Good balance of speed and accuracy (default)
- `high_quality`: Maximum accuracy for archival processing

**Key Classes:**
- `EnhancedFingerprintService`: Main service class
- `FingerprintMetadata`: Metadata tracking for fingerprints
- `FingerprintQuality`: Quality assessment metrics

### 2. ACRCloud Integration (`acrcloud_client.py`)

**Features:**
- Comprehensive ACRCloud API client with rate limiting
- ISRC lookup and metadata enrichment
- PRO mapping for international content
- Retry logic and error handling
- Caching for performance optimization

**Key Classes:**
- `ACRCloudClient`: Main API client
- `PROMapper`: Maps tracks to Performing Rights Organizations
- `HybridDetectionService`: Combines local and external detection
- `ACRCloudMatch`: Structured match results
- `PROAffiliation`: PRO membership information

**Supported PROs:**
- GHAMRO (Ghana)
- ASCAP, BMI (USA)
- PRS (UK)
- SACEM (France)
- GEMA (Germany)
- JASRAC (Japan)
- APRA (Australia)
- And many more...

### 3. ISRC Lookup Service (`isrc_lookup_service.py`)

**Features:**
- Comprehensive ISRC-based metadata lookup
- Batch processing capabilities
- Caching for performance
- Detection result enrichment
- Publisher and writer information extraction

**Key Classes:**
- `ISRCLookupService`: Main lookup service
- `ISRCLookupResult`: Structured lookup results

### 4. Real-time Stream Monitoring (`stream_monitoring_service.py`)

**Features:**
- Continuous audio stream monitoring
- Configurable capture intervals and retry logic
- Session management and health monitoring
- WebSocket integration for real-time updates
- Comprehensive error handling and alerting

**Key Classes:**
- `EnhancedStreamMonitor`: Main monitoring service
- `StreamMonitoringManager`: Manages multiple sessions
- `StreamHealthMonitor`: Health monitoring and alerting
- `SessionMetrics`: Performance tracking

## Database Models

### AudioDetection
Enhanced model supporting both local and external detection:

```python
class AudioDetection(models.Model):
    # Core identification
    detection_id = UUIDField(unique=True)
    session_id = UUIDField()
    station = ForeignKey(Station)
    
    # Detection metadata
    detection_source = CharField(choices=['local', 'acrcloud', 'hybrid'])
    confidence_score = DecimalField(max_digits=5, decimal_places=4)
    processing_status = CharField()
    
    # External identification
    isrc = CharField(max_length=12)
    pro_affiliation = CharField()
    
    # Fingerprint data
    audio_fingerprint = TextField()
    fingerprint_version = CharField()
    
    # Processing metadata
    processing_time_ms = IntegerField()
    retry_count = IntegerField()
    acrcloud_response = JSONField()
    external_metadata = JSONField()
```

### RoyaltyDistribution
Enhanced model for complex royalty splitting:

```python
class RoyaltyDistribution(models.Model):
    # Source information
    play_log = ForeignKey(PlayLog)
    audio_detection = ForeignKey(AudioDetection)
    
    # Recipient information
    recipient = ForeignKey(User)
    recipient_type = CharField(choices=['artist', 'publisher', 'pro'])
    
    # PRO and external routing
    pro_share = DecimalField()
    external_pro = ForeignKey(PartnerPRO)
    reciprocal_agreement = ForeignKey(ReciprocalAgreement)
```

## API Endpoints

### Enhanced Fingerprinting
- `POST /api/music-monitor/fingerprint/track/` - Fingerprint single track
- `POST /api/music-monitor/fingerprint/batch/` - Batch fingerprint tracks
- `GET /api/music-monitor/fingerprint/stats/` - Get fingerprint statistics
- `GET /api/music-monitor/fingerprint/task/{task_id}/` - Get task status

### ACRCloud Integration
- `POST /api/music-monitor/acrcloud/test-identification/` - Test ACRCloud ID
- `POST /api/music-monitor/acrcloud/test-hybrid/` - Test hybrid detection
- `GET /api/music-monitor/acrcloud/isrc/{isrc}/` - Lookup ISRC metadata
- `POST /api/music-monitor/acrcloud/batch-isrc/` - Batch ISRC lookup
- `GET /api/music-monitor/acrcloud/pro-mappings/` - Get PRO mappings

## Celery Tasks

### Enhanced Fingerprinting Tasks
- `enhanced_fingerprint_track` - Process single track
- `batch_enhanced_fingerprint` - Process multiple tracks
- `auto_fingerprint_new_tracks` - Auto-process new uploads
- `cleanup_old_fingerprints` - Maintenance task

### Hybrid Detection Tasks
- `hybrid_audio_detection` - Perform hybrid detection
- `acrcloud_identify_audio` - ACRCloud identification
- `update_isrc_metadata` - Update ISRC metadata
- `batch_update_pro_mappings` - Update PRO mappings

## Configuration

### Django Settings
```python
# ACRCloud Configuration
ACRCLOUD_ACCESS_KEY = 'your_access_key'
ACRCLOUD_ACCESS_SECRET = 'your_access_secret'
ACRCLOUD_HOST = 'identify-eu-west-1.acrcloud.com'

# Audio Detection Configuration
AUDIO_DETECTION_CONFIG = {
    'local_confidence_threshold': 0.8,
    'acrcloud_confidence_threshold': 0.7,
    'enable_hybrid_fallback': True,
    'max_retry_attempts': 3,
    'processing_timeout': 30
}

# PRO Integration Configuration
PRO_INTEGRATION_CONFIG = {
    'default_pro': 'ghamro',
    'reciprocal_rate_ascap': 0.15,
    'reciprocal_rate_bmi': 0.15,
    'enable_international_routing': True
}
```

### Stream Monitoring Configuration
```python
config = StreamMonitoringConfig(
    capture_interval_seconds=30,
    capture_duration_seconds=20,
    overlap_seconds=5,
    max_retry_attempts=3,
    confidence_threshold=0.8,
    enable_hybrid_detection=True,
    enable_websocket_broadcast=True
)
```

## Usage Examples

### 1. Enhanced Fingerprinting
```python
from music_monitor.services.enhanced_fingerprinting import EnhancedFingerprintService

# Initialize service
service = EnhancedFingerprintService('balanced')

# Fingerprint a track
track = Track.objects.get(id=123)
success = service.fingerprint_track(track)

# Batch fingerprint tracks
track_ids = [1, 2, 3, 4, 5]
results = service.batch_fingerprint_tracks(track_ids, max_workers=4)
```

### 2. Hybrid Detection
```python
from music_monitor.services.acrcloud_client import HybridDetectionService

# Initialize service
hybrid_service = HybridDetectionService()

# Perform detection
audio_data = b'...'  # Raw audio bytes
local_fingerprints = get_local_fingerprints()

match_result, detection_source, metadata = hybrid_service.identify_with_fallback(
    audio_data, local_fingerprints, session_id='test_session'
)
```

### 3. Stream Monitoring
```python
from music_monitor.services.stream_monitoring_service import start_station_monitoring

# Start monitoring a station
session_id = start_station_monitoring(
    station_id=123,
    config=StreamMonitoringConfig(enable_hybrid_detection=True)
)

# Get monitoring status
status = get_station_monitoring_status(station_id=123)
```

### 4. ISRC Lookup
```python
from music_monitor.services.isrc_lookup_service import ISRCLookupService

# Initialize service
isrc_service = ISRCLookupService()

# Lookup single ISRC
result = isrc_service.lookup_isrc('USRC17607839')

# Batch lookup
isrcs = ['USRC17607839', 'GBUM71505078']
results = isrc_service.batch_lookup_isrcs(isrcs)
```

## Performance Considerations

### Caching Strategy
- **Fingerprints**: Cached in memory for 5 minutes during active monitoring
- **ACRCloud Results**: Cached for 1 hour (successful) / 5 minutes (failed)
- **ISRC Metadata**: Cached for 7 days (successful) / 1 hour (failed)
- **PRO Mappings**: Cached for 24 hours

### Rate Limiting
- **ACRCloud API**: 45 requests/minute, 1800 requests/day
- **Concurrent Requests**: Maximum 5 simultaneous requests
- **Retry Logic**: Exponential backoff with maximum 3 attempts

### Batch Processing
- **Fingerprinting**: Up to 4 parallel workers
- **ISRC Lookup**: Maximum 50 ISRCs per batch
- **Detection**: Queue-based processing with Celery

## Monitoring and Alerting

### Health Checks
- Stream connectivity validation
- Capture success rate monitoring
- Processing time tracking
- Error rate alerting

### Metrics
- Detection accuracy rates
- Processing performance
- Cache hit rates
- API usage statistics

### Logging
- Structured logging with correlation IDs
- Performance metrics logging
- Error tracking and alerting
- Audit trails for all operations

## Testing

Run the comprehensive test suite:
```bash
cd zamio_backend
python music_monitor/test_hybrid_detection.py
```

The test suite validates:
- Enhanced fingerprinting functionality
- ACRCloud client configuration
- PRO mapping accuracy
- Hybrid detection service
- ISRC lookup capabilities
- Component integration

## Deployment Considerations

### Dependencies
- librosa (audio processing)
- numpy (numerical operations)
- requests (HTTP client)
- celery (background tasks)
- redis (caching and queues)

### Environment Variables
```bash
ACRCLOUD_ACCESS_KEY=your_key
ACRCLOUD_ACCESS_SECRET=your_secret
ACRCLOUD_HOST=identify-eu-west-1.acrcloud.com
```

### Celery Configuration
Ensure Celery workers are configured to handle audio processing tasks:
```bash
celery -A core worker -l info --concurrency=4
celery -A core beat -l info
```

## Troubleshooting

### Common Issues

1. **ACRCloud Authentication Errors**
   - Verify credentials in settings
   - Check rate limits and quotas
   - Validate network connectivity

2. **Fingerprinting Performance**
   - Adjust configuration profiles
   - Monitor memory usage
   - Check audio file formats

3. **Stream Monitoring Issues**
   - Validate stream URLs
   - Check ffmpeg installation
   - Monitor network stability

4. **PRO Mapping Accuracy**
   - Verify ISRC format
   - Check metadata completeness
   - Update PRO mappings

### Debug Mode
Enable debug logging:
```python
import logging
logging.getLogger('music_monitor').setLevel(logging.DEBUG)
```

## Future Enhancements

1. **Machine Learning Integration**
   - Audio similarity matching
   - Confidence score optimization
   - Automated PRO mapping

2. **Additional Data Sources**
   - MusicBrainz integration
   - Spotify metadata
   - Local music databases

3. **Advanced Analytics**
   - Detection accuracy tracking
   - Performance optimization
   - Predictive maintenance

4. **Real-time Improvements**
   - WebSocket streaming
   - Edge computing support
   - Mobile app integration

## Requirements Fulfilled

This implementation fulfills the following requirements from the specification:

- **7.1, 7.2**: Real-time stream monitoring with improved reliability
- **7.3**: Enhanced local fingerprinting with performance optimization
- **7.4, 7.5**: ACRCloud integration with ISRC lookup and PRO mapping
- **11.1, 11.2**: Hybrid detection system with fallback logic
- **11.3**: Comprehensive PRO mapping for international content

The system provides a robust, scalable, and maintainable solution for audio detection that meets the professional standards required for partnerships with major PROs like ASCAP and BMI.
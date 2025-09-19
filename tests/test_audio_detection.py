"""
Unit and integration tests for audio detection and fingerprinting functionality.
"""

import pytest
from django.test import TestCase
from unittest.mock import patch, Mock, MagicMock
from decimal import Decimal
import json
import uuid
from io import BytesIO

from music_monitor.models import PlayLog, AudioDetection, FingerprintData
from music_monitor.services.fingerprinting import FingerprintService, HybridFingerprintMatcher
from music_monitor.services.acrcloud_client import ACRCloudClient
from music_monitor.services.stream_monitor import StreamMonitorService
from music_monitor.tasks import process_audio_detection, batch_fingerprint_tracks
from tests.factories import (
    TrackFactory, StationProfileFactory, AudioDetectionFactory,
    PlayLogFactory, FingerprintDataFactory
)


@pytest.mark.detection
class FingerprintServiceTestCase(TestCase):
    """Test cases for fingerprinting service."""
    
    def setUp(self):
        self.service = FingerprintService()
        self.track = TrackFactory()
        self.mock_audio_data = b'mock_audio_data'
    
    @patch('music_monitor.services.fingerprinting.librosa.load')
    @patch('music_monitor.services.fingerprinting.librosa.feature.chroma_stft')
    def test_generate_fingerprint_success(self, mock_chroma, mock_load):
        """Test successful fingerprint generation."""
        # Mock librosa functions
        mock_load.return_value = ([0.1, 0.2, 0.3], 22050)  # audio, sr
        mock_chroma.return_value = [[0.1, 0.2], [0.3, 0.4]]
        
        fingerprint = self.service.generate_fingerprint(self.mock_audio_data)
        
        self.assertIsNotNone(fingerprint)
        self.assertIsInstance(fingerprint, str)
        mock_load.assert_called_once()
        mock_chroma.assert_called_once()
    
    @patch('music_monitor.services.fingerprinting.librosa.load')
    def test_generate_fingerprint_invalid_audio(self, mock_load):
        """Test fingerprint generation with invalid audio data."""
        mock_load.side_effect = Exception("Invalid audio format")
        
        with self.assertRaises(Exception):
            self.service.generate_fingerprint(self.mock_audio_data)
    
    def test_compare_fingerprints_exact_match(self):
        """Test fingerprint comparison with exact match."""
        fingerprint1 = "abc123def456"
        fingerprint2 = "abc123def456"
        
        similarity = self.service.compare_fingerprints(fingerprint1, fingerprint2)
        
        self.assertEqual(similarity, 1.0)
    
    def test_compare_fingerprints_no_match(self):
        """Test fingerprint comparison with no match."""
        fingerprint1 = "abc123def456"
        fingerprint2 = "xyz789uvw012"
        
        similarity = self.service.compare_fingerprints(fingerprint1, fingerprint2)
        
        self.assertEqual(similarity, 0.0)
    
    def test_compare_fingerprints_partial_match(self):
        """Test fingerprint comparison with partial match."""
        fingerprint1 = "abc123def456"
        fingerprint2 = "abc123xyz789"  # 50% match
        
        similarity = self.service.compare_fingerprints(fingerprint1, fingerprint2)
        
        self.assertGreater(similarity, 0.0)
        self.assertLess(similarity, 1.0)
    
    @patch('music_monitor.services.fingerprinting.FingerprintData.objects.filter')
    def test_match_against_database_success(self, mock_filter):
        """Test successful database fingerprint matching."""
        # Mock database fingerprint
        mock_fingerprint = Mock()
        mock_fingerprint.track = self.track
        mock_fingerprint.fingerprint_hash = "abc123def456"
        mock_fingerprint.confidence_threshold = 0.8
        
        mock_filter.return_value = [mock_fingerprint]
        
        # Mock comparison to return high similarity
        with patch.object(self.service, 'compare_fingerprints', return_value=0.9):
            match = self.service.match_against_database("abc123def456")
        
        self.assertIsNotNone(match)
        self.assertEqual(match['track'], self.track)
        self.assertEqual(match['confidence'], 0.9)
    
    @patch('music_monitor.services.fingerprinting.FingerprintData.objects.filter')
    def test_match_against_database_no_match(self, mock_filter):
        """Test database fingerprint matching with no match."""
        mock_filter.return_value = []
        
        match = self.service.match_against_database("unknown_fingerprint")
        
        self.assertIsNone(match)
    
    def test_store_fingerprint_success(self):
        """Test successful fingerprint storage."""
        fingerprint_hash = "abc123def456"
        metadata = {
            'algorithm': 'chromaprint',
            'sample_rate': 22050,
            'duration': 180.0
        }
        
        fingerprint_data = self.service.store_fingerprint(
            self.track, fingerprint_hash, metadata
        )
        
        self.assertIsNotNone(fingerprint_data)
        self.assertEqual(fingerprint_data.track, self.track)
        self.assertEqual(fingerprint_data.fingerprint_hash, fingerprint_hash)
        self.assertEqual(fingerprint_data.metadata, metadata)


@pytest.mark.detection
class ACRCloudClientTestCase(TestCase):
    """Test cases for ACRCloud integration."""
    
    def setUp(self):
        self.client = ACRCloudClient()
        self.mock_audio_data = b'mock_audio_data'
    
    @patch('music_monitor.services.acrcloud_client.requests.post')
    def test_identify_audio_success(self, mock_post):
        """Test successful audio identification via ACRCloud."""
        # Mock successful ACRCloud response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': {'msg': 'Success', 'code': 0},
            'metadata': {
                'music': [{
                    'title': 'Test Song',
                    'artists': [{'name': 'Test Artist'}],
                    'external_ids': {'isrc': 'TESTISRC123'},
                    'duration_ms': 180000,
                    'score': 95
                }]
            }
        }
        mock_post.return_value = mock_response
        
        result = self.client.identify_audio(self.mock_audio_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], 'Test Song')
        self.assertEqual(result['isrc'], 'TESTISRC123')
        self.assertEqual(result['confidence'], 0.95)
    
    @patch('music_monitor.services.acrcloud_client.requests.post')
    def test_identify_audio_no_match(self, mock_post):
        """Test audio identification with no match."""
        # Mock no match response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': {'msg': 'No result', 'code': 1001}
        }
        mock_post.return_value = mock_response
        
        result = self.client.identify_audio(self.mock_audio_data)
        
        self.assertIsNone(result)
    
    @patch('music_monitor.services.acrcloud_client.requests.post')
    def test_identify_audio_api_error(self, mock_post):
        """Test audio identification with API error."""
        # Mock API error
        mock_post.side_effect = Exception("API connection failed")
        
        with self.assertRaises(Exception):
            self.client.identify_audio(self.mock_audio_data)
    
    def test_prepare_audio_data(self):
        """Test audio data preparation for ACRCloud."""
        prepared_data = self.client._prepare_audio_data(self.mock_audio_data)
        
        self.assertIsInstance(prepared_data, dict)
        self.assertIn('sample', prepared_data)
        self.assertIn('sample_bytes', prepared_data)


@pytest.mark.detection
class HybridFingerprintMatcherTestCase(TestCase):
    """Test cases for hybrid fingerprint matching."""
    
    def setUp(self):
        self.matcher = HybridFingerprintMatcher()
        self.track = TrackFactory()
        self.station = StationProfileFactory()
        self.mock_audio_data = b'mock_audio_data'
    
    @patch('music_monitor.services.fingerprinting.FingerprintService.match_against_database')
    def test_identify_audio_local_match_high_confidence(self, mock_local_match):
        """Test audio identification with high confidence local match."""
        # Mock high confidence local match
        mock_local_match.return_value = {
            'track': self.track,
            'confidence': 0.9,
            'source': 'local'
        }
        
        result = self.matcher.identify_audio(self.mock_audio_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['track'], self.track)
        self.assertEqual(result['confidence'], 0.9)
        self.assertEqual(result['source'], 'local')
    
    @patch('music_monitor.services.fingerprinting.FingerprintService.match_against_database')
    @patch('music_monitor.services.acrcloud_client.ACRCloudClient.identify_audio')
    def test_identify_audio_fallback_to_acrcloud(self, mock_acrcloud, mock_local_match):
        """Test audio identification fallback to ACRCloud."""
        # Mock low confidence local match
        mock_local_match.return_value = {
            'track': None,
            'confidence': 0.3,
            'source': 'local'
        }
        
        # Mock successful ACRCloud match
        mock_acrcloud.return_value = {
            'title': 'External Song',
            'artist': 'External Artist',
            'isrc': 'EXTISRC123',
            'confidence': 0.85,
            'duration_ms': 200000
        }
        
        result = self.matcher.identify_audio(self.mock_audio_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['source'], 'acrcloud')
        self.assertEqual(result['isrc'], 'EXTISRC123')
        self.assertEqual(result['confidence'], 0.85)
    
    @patch('music_monitor.services.fingerprinting.FingerprintService.match_against_database')
    @patch('music_monitor.services.acrcloud_client.ACRCloudClient.identify_audio')
    def test_identify_audio_no_match_anywhere(self, mock_acrcloud, mock_local_match):
        """Test audio identification with no match in local or external."""
        # Mock no local match
        mock_local_match.return_value = None
        
        # Mock no ACRCloud match
        mock_acrcloud.return_value = None
        
        result = self.matcher.identify_audio(self.mock_audio_data)
        
        self.assertIsNone(result)


@pytest.mark.detection
class StreamMonitorServiceTestCase(TestCase):
    """Test cases for stream monitoring service."""
    
    def setUp(self):
        self.service = StreamMonitorService()
        self.station = StationProfileFactory(stream_url='http://test.stream.com/live')
    
    @patch('music_monitor.services.stream_monitor.requests.get')
    def test_capture_audio_stream_success(self, mock_get):
        """Test successful audio stream capture."""
        # Mock stream response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'audio_chunk_1', b'audio_chunk_2']
        mock_get.return_value = mock_response
        
        audio_data = self.service.capture_audio_stream(self.station.stream_url, duration=30)
        
        self.assertIsNotNone(audio_data)
        self.assertIsInstance(audio_data, bytes)
    
    @patch('music_monitor.services.stream_monitor.requests.get')
    def test_capture_audio_stream_connection_error(self, mock_get):
        """Test audio stream capture with connection error."""
        mock_get.side_effect = Exception("Connection failed")
        
        with self.assertRaises(Exception):
            self.service.capture_audio_stream(self.station.stream_url, duration=30)
    
    @patch('music_monitor.services.stream_monitor.StreamMonitorService.capture_audio_stream')
    @patch('music_monitor.services.fingerprinting.HybridFingerprintMatcher.identify_audio')
    def test_monitor_station_success(self, mock_identify, mock_capture):
        """Test successful station monitoring."""
        # Mock audio capture
        mock_capture.return_value = b'captured_audio_data'
        
        # Mock audio identification
        mock_identify.return_value = {
            'track': self.station,  # Mock track object
            'confidence': 0.9,
            'source': 'local',
            'isrc': 'TESTISRC123'
        }
        
        session_id = self.service.monitor_station(self.station)
        
        self.assertIsNotNone(session_id)
        mock_capture.assert_called()
        mock_identify.assert_called()
    
    def test_validate_stream_url_valid(self):
        """Test stream URL validation with valid URL."""
        valid_url = 'http://stream.example.com/live.mp3'
        
        is_valid = self.service.validate_stream_url(valid_url)
        
        self.assertTrue(is_valid)
    
    def test_validate_stream_url_invalid(self):
        """Test stream URL validation with invalid URL."""
        invalid_url = 'not_a_url'
        
        is_valid = self.service.validate_stream_url(invalid_url)
        
        self.assertFalse(is_valid)


@pytest.mark.detection
class AudioDetectionTasksTestCase(TestCase):
    """Test cases for audio detection Celery tasks."""
    
    def setUp(self):
        self.track = TrackFactory()
        self.station = StationProfileFactory()
    
    @patch('music_monitor.tasks.HybridFingerprintMatcher.identify_audio')
    def test_process_audio_detection_task_success(self, mock_identify):
        """Test successful audio detection task processing."""
        # Mock identification result
        mock_identify.return_value = {
            'track': self.track,
            'confidence': 0.9,
            'source': 'local',
            'isrc': self.track.isrc
        }
        
        audio_data = b'test_audio_data'
        session_id = str(uuid.uuid4())
        
        result = process_audio_detection.apply(
            args=[audio_data, self.station.id, session_id]
        )
        
        self.assertTrue(result.successful())
        
        # Verify detection was created
        detection = AudioDetection.objects.filter(session_id=session_id).first()
        self.assertIsNotNone(detection)
        self.assertEqual(detection.track, self.track)
        self.assertEqual(detection.confidence_score, Decimal('0.9'))
    
    @patch('music_monitor.tasks.HybridFingerprintMatcher.identify_audio')
    def test_process_audio_detection_task_no_match(self, mock_identify):
        """Test audio detection task with no match."""
        # Mock no identification result
        mock_identify.return_value = None
        
        audio_data = b'test_audio_data'
        session_id = str(uuid.uuid4())
        
        result = process_audio_detection.apply(
            args=[audio_data, self.station.id, session_id]
        )
        
        self.assertTrue(result.successful())
        
        # Verify no detection was created
        detection = AudioDetection.objects.filter(session_id=session_id).first()
        self.assertIsNone(detection)
    
    @patch('music_monitor.services.fingerprinting.FingerprintService.generate_fingerprint')
    @patch('music_monitor.services.fingerprinting.FingerprintService.store_fingerprint')
    def test_batch_fingerprint_tracks_task(self, mock_store, mock_generate):
        """Test batch fingerprinting task."""
        # Create tracks without fingerprints
        tracks = [TrackFactory() for _ in range(3)]
        track_ids = [track.id for track in tracks]
        
        # Mock fingerprint generation
        mock_generate.return_value = "generated_fingerprint_hash"
        
        result = batch_fingerprint_tracks.apply(args=[track_ids])
        
        self.assertTrue(result.successful())
        
        # Verify fingerprints were generated for all tracks
        self.assertEqual(mock_generate.call_count, 3)
        self.assertEqual(mock_store.call_count, 3)


@pytest.mark.detection
@pytest.mark.integration
class AudioDetectionIntegrationTestCase(TestCase):
    """Integration tests for complete audio detection workflow."""
    
    def setUp(self):
        self.track = TrackFactory()
        self.station = StationProfileFactory()
        
        # Create fingerprint data for the track
        self.fingerprint = FingerprintDataFactory(
            track=self.track,
            fingerprint_hash="test_fingerprint_hash",
            processing_status='completed'
        )
    
    @patch('music_monitor.services.stream_monitor.requests.get')
    @patch('music_monitor.services.fingerprinting.librosa.load')
    @patch('music_monitor.services.fingerprinting.librosa.feature.chroma_stft')
    def test_complete_detection_workflow_local_match(self, mock_chroma, mock_load, mock_stream):
        """Test complete detection workflow with local fingerprint match."""
        # Mock stream capture
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'audio_data']
        mock_stream.return_value = mock_response
        
        # Mock audio processing to return matching fingerprint
        mock_load.return_value = ([0.1, 0.2, 0.3], 22050)
        mock_chroma.return_value = [[0.1, 0.2], [0.3, 0.4]]
        
        # Mock fingerprint service to return exact match
        with patch('music_monitor.services.fingerprinting.FingerprintService.compare_fingerprints') as mock_compare:
            mock_compare.return_value = 0.95  # High similarity
            
            # Start monitoring
            monitor_service = StreamMonitorService()
            session_id = monitor_service.monitor_station(self.station)
            
            # Verify detection was created
            detection = AudioDetection.objects.filter(session_id=session_id).first()
            self.assertIsNotNone(detection)
            self.assertEqual(detection.track, self.track)
            self.assertEqual(detection.detection_source, 'local')
            self.assertGreaterEqual(detection.confidence_score, Decimal('0.8'))
    
    @patch('music_monitor.services.stream_monitor.requests.get')
    @patch('music_monitor.services.acrcloud_client.requests.post')
    def test_complete_detection_workflow_acrcloud_fallback(self, mock_acrcloud_post, mock_stream):
        """Test complete detection workflow with ACRCloud fallback."""
        # Mock stream capture
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'audio_data']
        mock_stream.return_value = mock_response
        
        # Mock ACRCloud response
        mock_acrcloud_response = Mock()
        mock_acrcloud_response.status_code = 200
        mock_acrcloud_response.json.return_value = {
            'status': {'msg': 'Success', 'code': 0},
            'metadata': {
                'music': [{
                    'title': 'External Song',
                    'artists': [{'name': 'External Artist'}],
                    'external_ids': {'isrc': 'EXTISRC123'},
                    'duration_ms': 180000,
                    'score': 85
                }]
            }
        }
        mock_acrcloud_post.return_value = mock_acrcloud_response
        
        # Mock local fingerprint to return no match (force ACRCloud fallback)
        with patch('music_monitor.services.fingerprinting.FingerprintService.match_against_database') as mock_local:
            mock_local.return_value = None
            
            # Start monitoring
            monitor_service = StreamMonitorService()
            session_id = monitor_service.monitor_station(self.station)
            
            # Verify detection was created with ACRCloud data
            detection = AudioDetection.objects.filter(session_id=session_id).first()
            self.assertIsNotNone(detection)
            self.assertEqual(detection.detection_source, 'acrcloud')
            self.assertEqual(detection.isrc, 'EXTISRC123')
            self.assertEqual(detection.confidence_score, Decimal('0.85'))
    
    def test_detection_creates_play_log(self):
        """Test that successful detection creates a play log entry."""
        # Create an audio detection
        detection = AudioDetectionFactory(
            station=self.station,
            track=self.track,
            confidence_score=Decimal('0.9')
        )
        
        # Verify play log was created
        play_log = PlayLog.objects.filter(
            station=self.station,
            track=self.track,
            session_id=detection.session_id
        ).first()
        
        self.assertIsNotNone(play_log)
        self.assertEqual(play_log.confidence_score, detection.confidence_score)
        self.assertEqual(play_log.detection_source, detection.detection_source)
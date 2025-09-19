"""
Performance tests for audio processing and high-load scenarios.
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from unittest.mock import patch, Mock
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import statistics

from music_monitor.services.fingerprinting import FingerprintService
from music_monitor.tasks import process_audio_detection, batch_fingerprint_tracks
from royalties.services.calculator import RoyaltyCalculator
from royalties.tasks import calculate_royalty_cycle
from tests.factories import (
    TrackFactory, StationProfileFactory, PlayLogFactory,
    RoyaltyCycleFactory, ArtistFactory
)


@pytest.mark.performance
@pytest.mark.slow
class FingerprintingPerformanceTestCase(TestCase):
    """Performance tests for audio fingerprinting."""
    
    def setUp(self):
        self.service = FingerprintService()
        self.mock_audio_data = b'mock_audio_data' * 1000  # Larger mock data
    
    @patch('music_monitor.services.fingerprinting.librosa.load')
    @patch('music_monitor.services.fingerprinting.librosa.feature.chroma_stft')
    def test_fingerprint_generation_performance(self, mock_chroma, mock_load):
        """Test fingerprint generation performance."""
        # Mock librosa functions
        mock_load.return_value = ([0.1] * 44100, 22050)  # 2 seconds of audio
        mock_chroma.return_value = [[0.1, 0.2] * 100] * 12  # Realistic chroma size
        
        # Measure time for single fingerprint
        start_time = time.time()
        fingerprint = self.service.generate_fingerprint(self.mock_audio_data)
        single_time = time.time() - start_time
        
        self.assertIsNotNone(fingerprint)
        self.assertLess(single_time, 1.0)  # Should complete within 1 second
        
        # Measure time for batch fingerprinting
        batch_size = 10
        start_time = time.time()
        
        fingerprints = []
        for _ in range(batch_size):
            fingerprint = self.service.generate_fingerprint(self.mock_audio_data)
            fingerprints.append(fingerprint)
        
        batch_time = time.time() - start_time
        avg_time_per_fingerprint = batch_time / batch_size
        
        self.assertEqual(len(fingerprints), batch_size)
        self.assertLess(avg_time_per_fingerprint, 1.0)  # Average should be under 1 second
        
        print(f"Single fingerprint time: {single_time:.3f}s")
        print(f"Batch average time: {avg_time_per_fingerprint:.3f}s")
    
    def test_fingerprint_comparison_performance(self):
        """Test fingerprint comparison performance with large dataset."""
        # Create test fingerprints
        fingerprints = [f"fingerprint_{i:06d}" for i in range(1000)]
        target_fingerprint = "fingerprint_000500"  # Middle of the list
        
        # Measure comparison time
        start_time = time.time()
        
        similarities = []
        for fp in fingerprints:
            similarity = self.service.compare_fingerprints(target_fingerprint, fp)
            similarities.append(similarity)
        
        comparison_time = time.time() - start_time
        avg_comparison_time = comparison_time / len(fingerprints)
        
        self.assertEqual(len(similarities), 1000)
        self.assertLess(avg_comparison_time, 0.001)  # Should be very fast
        
        # Verify exact match was found
        max_similarity = max(similarities)
        self.assertEqual(max_similarity, 1.0)
        
        print(f"1000 comparisons completed in {comparison_time:.3f}s")
        print(f"Average comparison time: {avg_comparison_time:.6f}s")
    
    def test_database_matching_performance(self):
        """Test database fingerprint matching performance."""
        # Create tracks with fingerprints
        tracks = []
        for i in range(100):
            track = TrackFactory()
            # Create fingerprint data
            from music_monitor.models import FingerprintData
            FingerprintData.objects.create(
                track=track,
                fingerprint_hash=f"hash_{i:03d}",
                processing_status='completed'
            )
            tracks.append(track)
        
        # Test matching performance
        test_fingerprint = "hash_050"  # Should match one of the tracks
        
        start_time = time.time()
        match = self.service.match_against_database(test_fingerprint)
        match_time = time.time() - start_time
        
        self.assertIsNotNone(match)
        self.assertLess(match_time, 0.1)  # Should complete within 100ms
        
        print(f"Database match completed in {match_time:.3f}s")


@pytest.mark.performance
@pytest.mark.slow
class RoyaltyCalculationPerformanceTestCase(TestCase):
    """Performance tests for royalty calculations."""
    
    def setUp(self):
        self.calculator = RoyaltyCalculator()
        
        # Create rate structure
        from royalties.models import RoyaltyRateStructure
        self.rate_structure = RoyaltyRateStructure.objects.create(
            name='Performance Test Rate',
            station_class='A',
            time_period='standard',
            base_rate=Decimal('0.05'),
            multiplier=Decimal('1.0'),
            territory='Ghana',
            effective_date='2024-01-01',
            is_active=True
        )
    
    def test_large_scale_royalty_calculation(self):
        """Test royalty calculation performance with large dataset."""
        # Create test data
        artists = [ArtistFactory() for _ in range(10)]
        tracks = []
        for artist in artists:
            for _ in range(10):  # 10 tracks per artist
                tracks.append(TrackFactory(artist=artist))
        
        stations = [StationProfileFactory() for _ in range(5)]
        
        # Create large number of play logs
        play_logs = []
        for track in tracks[:50]:  # Use first 50 tracks
            for station in stations:
                for _ in range(20):  # 20 plays per track per station
                    play_log = PlayLogFactory(track=track, station=station)
                    play_logs.append(play_log)
        
        total_plays = len(play_logs)
        print(f"Testing with {total_plays} play logs")
        
        # Measure calculation time
        start_time = time.time()
        
        total_royalties = Decimal('0')
        distributions_count = 0
        
        for play_log in play_logs:
            distributions = self.calculator.calculate_royalty_distributions(play_log)
            distributions_count += len(distributions)
            
            for dist in distributions:
                total_royalties += dist['amount']
        
        calculation_time = time.time() - start_time
        avg_time_per_play = calculation_time / total_plays
        
        self.assertGreater(total_royalties, Decimal('0'))
        self.assertGreater(distributions_count, 0)
        self.assertLess(avg_time_per_play, 0.01)  # Should be under 10ms per play
        
        print(f"Calculated {total_plays} plays in {calculation_time:.3f}s")
        print(f"Average time per play: {avg_time_per_play:.6f}s")
        print(f"Total royalties: {total_royalties}")
        print(f"Total distributions: {distributions_count}")
    
    def test_concurrent_royalty_calculations(self):
        """Test concurrent royalty calculations."""
        # Create test data
        tracks = [TrackFactory() for _ in range(20)]
        station = StationProfileFactory()
        
        play_logs = [PlayLogFactory(track=track, station=station) for track in tracks]
        
        def calculate_single_royalty(play_log):
            """Calculate royalty for a single play log."""
            start_time = time.time()
            distributions = self.calculator.calculate_royalty_distributions(play_log)
            end_time = time.time()
            return {
                'play_log_id': play_log.id,
                'distributions': len(distributions),
                'time': end_time - start_time
            }
        
        # Test concurrent execution
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(calculate_single_royalty, play_log)
                for play_log in play_logs
            ]
            
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        total_time = time.time() - start_time
        
        self.assertEqual(len(results), len(play_logs))
        
        # Calculate statistics
        calculation_times = [r['time'] for r in results]
        avg_time = statistics.mean(calculation_times)
        max_time = max(calculation_times)
        
        print(f"Concurrent calculation of {len(play_logs)} plays completed in {total_time:.3f}s")
        print(f"Average calculation time: {avg_time:.6f}s")
        print(f"Maximum calculation time: {max_time:.6f}s")
        
        # Concurrent execution should be faster than sequential
        sequential_estimate = sum(calculation_times)
        speedup = sequential_estimate / total_time
        
        print(f"Estimated speedup: {speedup:.2f}x")
        self.assertGreater(speedup, 1.5)  # Should have some speedup
    
    def test_royalty_cycle_calculation_performance(self):
        """Test performance of complete royalty cycle calculation."""
        # Create cycle with substantial data
        cycle = RoyaltyCycleFactory()
        
        # Create artists and tracks
        artists = [ArtistFactory() for _ in range(20)]
        tracks = []
        for artist in artists:
            for _ in range(5):  # 5 tracks per artist
                track = TrackFactory(artist=artist)
                tracks.append(track)
                
                # Create contributor
                from tests.factories import TrackContributorFactory
                TrackContributorFactory(
                    track=track,
                    user=artist.user,
                    percent_split=100.0
                )
        
        # Create stations and play logs
        stations = [StationProfileFactory() for _ in range(10)]
        
        play_logs = []
        for track in tracks:
            for station in stations:
                for _ in range(10):  # 10 plays per track per station
                    play_log = PlayLogFactory(
                        track=track,
                        station=station,
                        played_at=cycle.start_date
                    )
                    play_logs.append(play_log)
        
        total_plays = len(play_logs)
        print(f"Testing cycle calculation with {total_plays} plays")
        
        # Measure cycle calculation time
        start_time = time.time()
        
        total_plays_calculated, total_royalties = self.calculator.calculate_cycle_totals(cycle)
        
        calculation_time = time.time() - start_time
        
        self.assertEqual(total_plays_calculated, total_plays)
        self.assertGreater(total_royalties, Decimal('0'))
        self.assertLess(calculation_time, 30.0)  # Should complete within 30 seconds
        
        print(f"Cycle calculation completed in {calculation_time:.3f}s")
        print(f"Plays per second: {total_plays / calculation_time:.1f}")
        print(f"Total royalties calculated: {total_royalties}")


@pytest.mark.performance
@pytest.mark.slow
class CeleryTaskPerformanceTestCase(TransactionTestCase):
    """Performance tests for Celery tasks."""
    
    def test_batch_fingerprinting_performance(self):
        """Test performance of batch fingerprinting task."""
        # Create tracks without fingerprints
        tracks = [TrackFactory() for _ in range(50)]
        track_ids = [track.id for track in tracks]
        
        # Mock fingerprint generation to be fast
        with patch('music_monitor.services.fingerprinting.FingerprintService.generate_fingerprint') as mock_generate:
            mock_generate.return_value = "mock_fingerprint_hash"
            
            start_time = time.time()
            
            # Execute batch fingerprinting task
            result = batch_fingerprint_tracks.apply(args=[track_ids])
            
            execution_time = time.time() - start_time
            
            self.assertTrue(result.successful())
            self.assertLess(execution_time, 10.0)  # Should complete within 10 seconds
            
            # Verify all tracks were processed
            self.assertEqual(mock_generate.call_count, len(tracks))
            
            print(f"Batch fingerprinting of {len(tracks)} tracks completed in {execution_time:.3f}s")
            print(f"Tracks per second: {len(tracks) / execution_time:.1f}")
    
    def test_audio_detection_task_performance(self):
        """Test performance of audio detection task."""
        station = StationProfileFactory()
        
        # Mock audio detection to be fast
        with patch('music_monitor.tasks.HybridFingerprintMatcher.identify_audio') as mock_identify:
            mock_identify.return_value = {
                'track': TrackFactory(),
                'confidence': 0.9,
                'source': 'local'
            }
            
            # Test multiple concurrent detections
            audio_data = b'test_audio_data'
            session_ids = [f'session_{i}' for i in range(20)]
            
            start_time = time.time()
            
            # Execute tasks concurrently
            results = []
            for session_id in session_ids:
                result = process_audio_detection.apply(
                    args=[audio_data, station.id, session_id]
                )
                results.append(result)
            
            execution_time = time.time() - start_time
            
            # Verify all tasks completed successfully
            for result in results:
                self.assertTrue(result.successful())
            
            self.assertLess(execution_time, 5.0)  # Should complete within 5 seconds
            
            print(f"Processed {len(session_ids)} audio detections in {execution_time:.3f}s")
            print(f"Detections per second: {len(session_ids) / execution_time:.1f}")


@pytest.mark.performance
@pytest.mark.slow
class DatabasePerformanceTestCase(TestCase):
    """Performance tests for database operations."""
    
    def test_large_dataset_queries(self):
        """Test query performance with large datasets."""
        # Create large dataset
        artists = [ArtistFactory() for _ in range(100)]
        tracks = []
        for artist in artists:
            for _ in range(10):  # 10 tracks per artist
                tracks.append(TrackFactory(artist=artist))
        
        stations = [StationProfileFactory() for _ in range(20)]
        
        # Create many play logs
        play_logs = []
        for i, track in enumerate(tracks[:500]):  # Use first 500 tracks
            station = stations[i % len(stations)]
            for _ in range(5):  # 5 plays per track
                play_logs.append(PlayLogFactory(track=track, station=station))
        
        print(f"Created dataset: {len(artists)} artists, {len(tracks)} tracks, {len(play_logs)} plays")
        
        # Test query performance
        queries = [
            ("Artist list query", lambda: list(artists[0].__class__.objects.all())),
            ("Track list query", lambda: list(tracks[0].__class__.objects.all())),
            ("Play log list query", lambda: list(play_logs[0].__class__.objects.all())),
            ("Artist with tracks", lambda: list(
                artists[0].__class__.objects.prefetch_related('track_set').all()
            )),
            ("Tracks with play counts", lambda: list(
                tracks[0].__class__.objects.annotate(
                    play_count=models.Count('playlog')
                ).all()
            )),
        ]
        
        for query_name, query_func in queries:
            start_time = time.time()
            result = query_func()
            query_time = time.time() - start_time
            
            self.assertGreater(len(result), 0)
            self.assertLess(query_time, 1.0)  # Should complete within 1 second
            
            print(f"{query_name}: {query_time:.3f}s ({len(result)} results)")
    
    def test_concurrent_database_access(self):
        """Test database performance under concurrent access."""
        # Create base data
        artists = [ArtistFactory() for _ in range(10)]
        
        def create_tracks_for_artist(artist):
            """Create tracks for an artist (simulating concurrent users)."""
            tracks_created = []
            for i in range(5):
                track = TrackFactory(
                    artist=artist,
                    title=f"Track {i} by {artist.stage_name}"
                )
                tracks_created.append(track)
            return len(tracks_created)
        
        # Test concurrent track creation
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(create_tracks_for_artist, artist)
                for artist in artists
            ]
            
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        execution_time = time.time() - start_time
        total_tracks_created = sum(results)
        
        self.assertEqual(len(results), len(artists))
        self.assertEqual(total_tracks_created, len(artists) * 5)
        self.assertLess(execution_time, 5.0)  # Should complete within 5 seconds
        
        print(f"Concurrent creation of {total_tracks_created} tracks completed in {execution_time:.3f}s")
        print(f"Tracks per second: {total_tracks_created / execution_time:.1f}")


@pytest.mark.performance
class MemoryUsageTestCase(TestCase):
    """Tests for memory usage optimization."""
    
    def test_large_dataset_memory_usage(self):
        """Test memory usage with large datasets."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large dataset
        tracks = []
        for i in range(1000):
            track = TrackFactory(title=f"Track {i}")
            tracks.append(track)
        
        # Create play logs
        station = StationProfileFactory()
        play_logs = []
        for track in tracks[:100]:  # Use first 100 tracks
            for _ in range(10):
                play_log = PlayLogFactory(track=track, station=station)
                play_logs.append(play_log)
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Clean up
        del tracks
        del play_logs
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Peak memory: {peak_memory:.1f} MB")
        print(f"Memory increase: {memory_increase:.1f} MB")
        print(f"Final memory: {final_memory:.1f} MB")
        
        # Memory increase should be reasonable
        self.assertLess(memory_increase, 100)  # Should not use more than 100MB
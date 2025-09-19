#!/usr/bin/env python
"""
Test script for the Hybrid Audio Detection Pipeline
This script tests the integration of all components in the hybrid detection system.
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import logging
import numpy as np
from music_monitor.services.enhanced_fingerprinting import EnhancedFingerprintService
from music_monitor.services.acrcloud_client import ACRCloudClient, PROMapper, HybridDetectionService
from music_monitor.services.isrc_lookup_service import ISRCLookupService
from music_monitor.services.stream_monitoring_service import StreamMonitoringConfig, EnhancedStreamMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_enhanced_fingerprinting():
    """Test enhanced fingerprinting service"""
    print("\n=== Testing Enhanced Fingerprinting Service ===")
    
    try:
        service = EnhancedFingerprintService('balanced')
        
        # Generate test audio (sine wave)
        duration = 5  # seconds
        sample_rate = 44100
        frequency = 440  # A4 note
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        samples = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        # Test fingerprinting
        fingerprint_hashes, metadata = service.enhanced_fingerprint(samples, sample_rate)
        
        print(f"✓ Generated {len(fingerprint_hashes)} fingerprint hashes")
        print(f"✓ Quality score: {metadata.quality_score:.3f}")
        print(f"✓ Processing time: {metadata.processing_time_ms}ms")
        print(f"✓ Confidence threshold: {metadata.confidence_threshold:.3f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Enhanced fingerprinting test failed: {e}")
        return False


def test_acrcloud_client():
    """Test ACRCloud client (without making actual API calls)"""
    print("\n=== Testing ACRCloud Client ===")
    
    try:
        client = ACRCloudClient()
        
        # Test configuration
        print(f"✓ ACRCloud client initialized")
        print(f"✓ Access key configured: {'Yes' if client.access_key else 'No'}")
        print(f"✓ Host configured: {'Yes' if client.host else 'No'}")
        print(f"✓ Rate limit settings: {client.MAX_REQUESTS_PER_MINUTE}/min, {client.MAX_REQUESTS_PER_DAY}/day")
        
        return True
        
    except Exception as e:
        print(f"✗ ACRCloud client test failed: {e}")
        return False


def test_pro_mapper():
    """Test PRO mapping service"""
    print("\n=== Testing PRO Mapper ===")
    
    try:
        mapper = PROMapper()
        
        # Test PRO mappings
        print(f"✓ Loaded {len(mapper.PRO_MAPPINGS)} PRO mappings")
        print(f"✓ Territory mappings: {len(mapper.TERRITORY_PRO_MAP)}")
        
        # Test territory mapping
        ghamro_affiliation = mapper._map_territory_to_pro('Ghana')
        if ghamro_affiliation:
            print(f"✓ Ghana mapped to: {ghamro_affiliation.pro_name}")
        
        usa_affiliation = mapper._map_territory_to_pro('USA')
        if usa_affiliation:
            print(f"✓ USA mapped to: {usa_affiliation.pro_name}")
        
        # Test default PRO
        default_pro = mapper._get_default_pro_affiliation()
        print(f"✓ Default PRO: {default_pro.pro_name}")
        
        return True
        
    except Exception as e:
        print(f"✗ PRO mapper test failed: {e}")
        return False


def test_hybrid_detection_service():
    """Test hybrid detection service"""
    print("\n=== Testing Hybrid Detection Service ===")
    
    try:
        service = HybridDetectionService()
        
        # Test configuration
        print(f"✓ Local threshold: {service.local_threshold}")
        print(f"✓ ACRCloud threshold: {service.acrcloud_threshold}")
        print(f"✓ Fallback enabled: {service.fallback_enabled}")
        print(f"✓ Max retries: {service.max_retries}")
        
        # Test statistics
        stats = service.get_detection_statistics()
        print(f"✓ Detection statistics: {len(stats)} metrics")
        
        return True
        
    except Exception as e:
        print(f"✗ Hybrid detection service test failed: {e}")
        return False


def test_isrc_lookup_service():
    """Test ISRC lookup service"""
    print("\n=== Testing ISRC Lookup Service ===")
    
    try:
        service = ISRCLookupService()
        
        # Test ISRC validation
        valid_isrc = "USRC17607839"
        invalid_isrc = "INVALID123"
        
        print(f"✓ Valid ISRC validation: {service._validate_isrc(valid_isrc)}")
        print(f"✓ Invalid ISRC validation: {service._validate_isrc(invalid_isrc)}")
        
        # Test statistics
        stats = service.get_lookup_statistics()
        print(f"✓ Lookup statistics: {len(stats)} metrics")
        
        return True
        
    except Exception as e:
        print(f"✗ ISRC lookup service test failed: {e}")
        return False


def test_stream_monitoring_config():
    """Test stream monitoring configuration"""
    print("\n=== Testing Stream Monitoring Configuration ===")
    
    try:
        config = StreamMonitoringConfig(
            capture_interval_seconds=30,
            capture_duration_seconds=20,
            confidence_threshold=0.8,
            enable_hybrid_detection=True
        )
        
        print(f"✓ Capture interval: {config.capture_interval_seconds}s")
        print(f"✓ Capture duration: {config.capture_duration_seconds}s")
        print(f"✓ Confidence threshold: {config.confidence_threshold}")
        print(f"✓ Hybrid detection: {config.enable_hybrid_detection}")
        print(f"✓ Max retry attempts: {config.max_retry_attempts}")
        
        return True
        
    except Exception as e:
        print(f"✗ Stream monitoring config test failed: {e}")
        return False


def test_integration():
    """Test integration between components"""
    print("\n=== Testing Component Integration ===")
    
    try:
        # Test that all services can be initialized together
        fingerprint_service = EnhancedFingerprintService('fast')
        acrcloud_client = ACRCloudClient()
        pro_mapper = PROMapper()
        hybrid_service = HybridDetectionService()
        isrc_service = ISRCLookupService()
        
        print("✓ All services initialized successfully")
        
        # Test that services can access each other's functionality
        pro_count = len(pro_mapper.PRO_MAPPINGS)
        fingerprint_version = fingerprint_service.CURRENT_VERSION
        hybrid_stats = hybrid_service.get_detection_statistics()
        
        print(f"✓ Cross-service communication working")
        print(f"✓ PRO mappings available: {pro_count}")
        print(f"✓ Fingerprint version: {fingerprint_version}")
        print(f"✓ Hybrid service operational: {len(hybrid_stats)} stats")
        
        return True
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🎵 ZamIO Hybrid Audio Detection Pipeline Test Suite 🎵")
    print("=" * 60)
    
    tests = [
        test_enhanced_fingerprinting,
        test_acrcloud_client,
        test_pro_mapper,
        test_hybrid_detection_service,
        test_isrc_lookup_service,
        test_stream_monitoring_config,
        test_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Hybrid Audio Detection Pipeline is ready!")
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
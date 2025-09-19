"""
Management command to test ACRCloud integration and PRO mapping
"""

import os
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from music_monitor.services.acrcloud_client import ACRCloudClient, PROMapper, HybridDetectionService
from music_monitor.services.isrc_lookup_service import ISRCLookupService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test ACRCloud integration, PRO mapping, and ISRC lookup functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test-audio',
            type=str,
            help='Path to audio file for testing identification'
        )
        parser.add_argument(
            '--test-isrc',
            type=str,
            help='ISRC code to test lookup functionality'
        )
        parser.add_argument(
            '--test-batch-isrcs',
            nargs='+',
            help='Multiple ISRC codes to test batch lookup'
        )
        parser.add_argument(
            '--test-pro-mapping',
            action='store_true',
            help='Test PRO mapping functionality'
        )
        parser.add_argument(
            '--test-hybrid-detection',
            action='store_true',
            help='Test hybrid detection service'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write(self.style.SUCCESS('Starting ACRCloud Integration Tests'))
        
        # Test configuration
        self._test_configuration()
        
        # Test ACRCloud client
        if options.get('test_audio'):
            self._test_audio_identification(options['test_audio'])
        
        # Test ISRC lookup
        if options.get('test_isrc'):
            self._test_isrc_lookup(options['test_isrc'])
        
        # Test batch ISRC lookup
        if options.get('test_batch_isrcs'):
            self._test_batch_isrc_lookup(options['test_batch_isrcs'])
        
        # Test PRO mapping
        if options.get('test_pro_mapping'):
            self._test_pro_mapping()
        
        # Test hybrid detection
        if options.get('test_hybrid_detection'):
            self._test_hybrid_detection()
        
        self.stdout.write(self.style.SUCCESS('ACRCloud Integration Tests Completed'))
    
    def _test_configuration(self):
        """Test ACRCloud configuration"""
        self.stdout.write('\n=== Testing Configuration ===')
        
        # Check settings
        acrcloud_key = getattr(settings, 'ACRCLOUD_ACCESS_KEY', '')
        acrcloud_secret = getattr(settings, 'ACRCLOUD_ACCESS_SECRET', '')
        acrcloud_host = getattr(settings, 'ACRCLOUD_HOST', '')
        
        if not acrcloud_key:
            self.stdout.write(self.style.WARNING('ACRCLOUD_ACCESS_KEY not configured'))
        else:
            self.stdout.write(self.style.SUCCESS(f'ACRCLOUD_ACCESS_KEY: {acrcloud_key[:8]}...'))
        
        if not acrcloud_secret:
            self.stdout.write(self.style.WARNING('ACRCLOUD_ACCESS_SECRET not configured'))
        else:
            self.stdout.write(self.style.SUCCESS(f'ACRCLOUD_ACCESS_SECRET: {acrcloud_secret[:8]}...'))
        
        if not acrcloud_host:
            self.stdout.write(self.style.WARNING('ACRCLOUD_HOST not configured'))
        else:
            self.stdout.write(self.style.SUCCESS(f'ACRCLOUD_HOST: {acrcloud_host}'))
        
        # Test audio detection config
        audio_config = getattr(settings, 'AUDIO_DETECTION_CONFIG', {})
        self.stdout.write(f'Audio Detection Config: {audio_config}')
        
        # Test PRO integration config
        pro_config = getattr(settings, 'PRO_INTEGRATION_CONFIG', {})
        self.stdout.write(f'PRO Integration Config: {pro_config}')
    
    def _test_audio_identification(self, audio_path):
        """Test audio identification with ACRCloud"""
        self.stdout.write(f'\n=== Testing Audio Identification: {audio_path} ===')
        
        if not os.path.exists(audio_path):
            self.stdout.write(self.style.ERROR(f'Audio file not found: {audio_path}'))
            return
        
        try:
            # Read audio file
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            self.stdout.write(f'Audio file size: {len(audio_data)} bytes')
            
            # Test ACRCloud client
            client = ACRCloudClient()
            result = client.identify_audio(audio_data)
            
            if result:
                self.stdout.write(self.style.SUCCESS('ACRCloud Identification Result:'))
                self.stdout.write(f'  Title: {result.title}')
                self.stdout.write(f'  Artist: {result.artist}')
                self.stdout.write(f'  Album: {result.album}')
                self.stdout.write(f'  ISRC: {result.isrc}')
                self.stdout.write(f'  Confidence: {result.confidence}%')
                self.stdout.write(f'  Duration: {result.duration_ms}ms')
                self.stdout.write(f'  ACR ID: {result.acrid}')
                
                # Test PRO mapping if ISRC available
                if result.isrc:
                    self._test_pro_mapping_for_isrc(result.isrc)
            else:
                self.stdout.write(self.style.WARNING('No identification result from ACRCloud'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Audio identification error: {e}'))
    
    def _test_isrc_lookup(self, isrc):
        """Test ISRC lookup functionality"""
        self.stdout.write(f'\n=== Testing ISRC Lookup: {isrc} ===')
        
        try:
            service = ISRCLookupService()
            result = service.lookup_isrc(isrc)
            
            if result:
                self.stdout.write(self.style.SUCCESS('ISRC Lookup Result:'))
                self.stdout.write(f'  ISRC: {result.isrc}')
                self.stdout.write(f'  Title: {result.title}')
                self.stdout.write(f'  Artist: {result.artist}')
                self.stdout.write(f'  Album: {result.album}')
                self.stdout.write(f'  Label: {result.label}')
                self.stdout.write(f'  Release Date: {result.release_date}')
                self.stdout.write(f'  Duration: {result.duration_ms}ms')
                self.stdout.write(f'  Confidence: {result.confidence:.2f}')
                
                # PRO affiliations
                if result.pro_affiliations:
                    self.stdout.write('  PRO Affiliations:')
                    for aff in result.pro_affiliations:
                        self.stdout.write(f'    - {aff["pro_name"]} ({aff["pro_code"]}) - {aff["territory"]}')
                        if aff.get('share_percentage'):
                            self.stdout.write(f'      Share: {aff["share_percentage"]}%')
                
                # Publishers
                if result.publishers:
                    self.stdout.write('  Publishers:')
                    for pub in result.publishers:
                        self.stdout.write(f'    - {pub["name"]} ({pub["role"]})')
                
                # Writers
                if result.writers:
                    self.stdout.write('  Writers:')
                    for writer in result.writers:
                        self.stdout.write(f'    - {writer["name"]} ({writer["role"]})')
            else:
                self.stdout.write(self.style.WARNING(f'No metadata found for ISRC: {isrc}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ISRC lookup error: {e}'))
    
    def _test_batch_isrc_lookup(self, isrcs):
        """Test batch ISRC lookup functionality"""
        self.stdout.write(f'\n=== Testing Batch ISRC Lookup: {len(isrcs)} ISRCs ===')
        
        try:
            service = ISRCLookupService()
            results = service.batch_lookup_isrcs(isrcs)
            
            self.stdout.write(f'Batch lookup completed: {len(results)} results')
            
            for isrc, result in results.items():
                if result:
                    self.stdout.write(self.style.SUCCESS(f'  {isrc}: {result.title} by {result.artist}'))
                else:
                    self.stdout.write(self.style.WARNING(f'  {isrc}: No result'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Batch ISRC lookup error: {e}'))
    
    def _test_pro_mapping(self):
        """Test PRO mapping functionality"""
        self.stdout.write('\n=== Testing PRO Mapping ===')
        
        try:
            mapper = PROMapper()
            
            # Test territory mappings
            test_territories = ['USA', 'UK', 'Germany', 'France', 'Ghana', 'Japan']
            
            self.stdout.write('Territory to PRO mappings:')
            for territory in test_territories:
                pro_aff = mapper._map_territory_to_pro(territory)
                if pro_aff:
                    self.stdout.write(f'  {territory} -> {pro_aff.pro_name} ({pro_aff.pro_code})')
                else:
                    self.stdout.write(f'  {territory} -> No mapping found')
            
            # Test PRO info
            self.stdout.write(f'\nSupported PROs: {len(mapper.PRO_MAPPINGS)}')
            for pro_name, pro_info in mapper.PRO_MAPPINGS.items():
                self.stdout.write(f'  {pro_name}: {pro_info["territory"]} ({pro_info["code"]})')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'PRO mapping test error: {e}'))
    
    def _test_pro_mapping_for_isrc(self, isrc):
        """Test PRO mapping for a specific ISRC"""
        self.stdout.write(f'\n--- PRO Mapping for ISRC: {isrc} ---')
        
        try:
            mapper = PROMapper()
            affiliations = mapper.map_isrc_to_pro(isrc)
            
            if affiliations:
                self.stdout.write('PRO Affiliations:')
                for aff in affiliations:
                    self.stdout.write(f'  - {aff.pro_name} ({aff.pro_code})')
                    self.stdout.write(f'    Territory: {aff.territory}')
                    if aff.publisher:
                        self.stdout.write(f'    Publisher: {aff.publisher}')
                    if aff.share_percentage:
                        self.stdout.write(f'    Share: {aff.share_percentage}%')
            else:
                self.stdout.write('No PRO affiliations found')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'PRO mapping error for ISRC {isrc}: {e}'))
    
    def _test_hybrid_detection(self):
        """Test hybrid detection service"""
        self.stdout.write('\n=== Testing Hybrid Detection Service ===')
        
        try:
            service = HybridDetectionService()
            stats = service.get_detection_statistics()
            
            self.stdout.write('Hybrid Detection Configuration:')
            for key, value in stats.items():
                self.stdout.write(f'  {key}: {value}')
            
            # Test with empty data (should handle gracefully)
            result, source, metadata = service.identify_with_fallback(
                b'', [], session_id='test_session'
            )
            
            self.stdout.write(f'Empty data test - Source: {source}')
            self.stdout.write(f'Processing metadata: {metadata}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Hybrid detection test error: {e}'))
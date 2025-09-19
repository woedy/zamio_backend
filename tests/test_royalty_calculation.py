"""
Unit and integration tests for royalty calculation functionality.
"""

import pytest
from django.test import TestCase
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, Mock
from freezegun import freeze_time

from royalties.models import (
    RoyaltyCycle, RoyaltyDistribution, RoyaltyLineItem,
    RoyaltyRateStructure, CurrencyExchangeRate, PartnerRemittance
)
from royalties.services.calculator import RoyaltyCalculator
from royalties.services.pro_integration import PROIntegrationService
from royalties.tasks import calculate_royalty_cycle, distribute_royalties
from music_monitor.models import PlayLog
from tests.factories import (
    TrackFactory, ArtistFactory, PublisherProfileFactory,
    StationProfileFactory, PlayLogFactory, RoyaltyCycleFactory,
    RoyaltyDistributionFactory, TrackContributorFactory,
    PublisherArtistRelationshipFactory
)


@pytest.mark.royalty
class RoyaltyCalculatorTestCase(TestCase):
    """Test cases for royalty calculation engine."""
    
    def setUp(self):
        self.calculator = RoyaltyCalculator()
        self.artist = ArtistFactory()
        self.track = TrackFactory(artist=self.artist)
        self.station = StationProfileFactory(station_class='A')
        
        # Create rate structure
        self.rate_structure = RoyaltyRateStructure.objects.create(
            name='Standard Rate',
            station_class='A',
            time_period='peak',
            base_rate=Decimal('0.05'),
            multiplier=Decimal('1.5'),
            territory='Ghana',
            effective_date=date.today(),
            is_active=True
        )
    
    def test_calculate_base_royalty_amount(self):
        """Test basic royalty amount calculation."""
        play_log = PlayLogFactory(
            track=self.track,
            station=self.station,
            duration_seconds=180,  # 3 minutes
            played_at=date.today()
        )
        
        amount = self.calculator.calculate_base_royalty(play_log)
        
        # Base rate (0.05) * duration (180) * multiplier (1.5) = 13.5
        expected_amount = Decimal('0.05') * 180 * Decimal('1.5')
        self.assertEqual(amount, expected_amount)
    
    def test_calculate_royalty_with_time_multiplier(self):
        """Test royalty calculation with time-of-day multiplier."""
        # Create peak time play (12 PM)
        with freeze_time("2024-01-01 12:00:00"):
            play_log = PlayLogFactory(
                track=self.track,
                station=self.station,
                duration_seconds=180
            )
        
        amount = self.calculator.calculate_base_royalty(play_log)
        
        # Should apply peak time multiplier
        self.assertGreater(amount, Decimal('0.05') * 180)
    
    def test_calculate_royalty_with_station_class_multiplier(self):
        """Test royalty calculation with station class multiplier."""
        # Create Class B station (lower rate)
        station_b = StationProfileFactory(station_class='B')
        
        rate_b = RoyaltyRateStructure.objects.create(
            name='Class B Rate',
            station_class='B',
            time_period='standard',
            base_rate=Decimal('0.03'),
            multiplier=Decimal('1.0'),
            territory='Ghana',
            effective_date=date.today(),
            is_active=True
        )
        
        play_log = PlayLogFactory(
            track=self.track,
            station=station_b,
            duration_seconds=180
        )
        
        amount = self.calculator.calculate_base_royalty(play_log)
        
        # Should use lower rate for Class B
        expected_amount = Decimal('0.03') * 180 * Decimal('1.0')
        self.assertEqual(amount, expected_amount)
    
    def test_distribute_royalty_single_contributor(self):
        """Test royalty distribution for single contributor."""
        play_log = PlayLogFactory(track=self.track, station=self.station)
        
        # Create single contributor (100% split)
        contributor = TrackContributorFactory(
            track=self.track,
            user=self.artist.user,
            percent_split=100.0
        )
        
        distributions = self.calculator.calculate_royalty_distributions(play_log)
        
        self.assertEqual(len(distributions), 1)
        self.assertEqual(distributions[0]['recipient'], self.artist.user)
        self.assertEqual(distributions[0]['recipient_type'], 'artist')
        self.assertEqual(distributions[0]['percent_split'], 100.0)
    
    def test_distribute_royalty_multiple_contributors(self):
        """Test royalty distribution for multiple contributors."""
        play_log = PlayLogFactory(track=self.track, station=self.station)
        
        # Create multiple contributors
        artist2 = ArtistFactory()
        contributor1 = TrackContributorFactory(
            track=self.track,
            user=self.artist.user,
            percent_split=60.0,
            role='Artist'
        )
        contributor2 = TrackContributorFactory(
            track=self.track,
            user=artist2.user,
            percent_split=40.0,
            role='Producer'
        )
        
        distributions = self.calculator.calculate_royalty_distributions(play_log)
        
        self.assertEqual(len(distributions), 2)
        
        # Verify splits
        splits = {d['recipient']: d['percent_split'] for d in distributions}
        self.assertEqual(splits[self.artist.user], 60.0)
        self.assertEqual(splits[artist2.user], 40.0)
    
    def test_distribute_royalty_with_publisher(self):
        """Test royalty distribution when artist has publisher."""
        publisher = PublisherProfileFactory()
        
        # Create publisher-artist relationship
        relationship = PublisherArtistRelationshipFactory(
            publisher=publisher,
            artist=self.artist,
            royalty_split_percentage=70.0,  # Publisher gets 70%
            status='active'
        )
        
        # Update artist to not be self-published
        self.artist.self_publish = False
        self.artist.save()
        
        play_log = PlayLogFactory(track=self.track, station=self.station)
        
        contributor = TrackContributorFactory(
            track=self.track,
            user=self.artist.user,
            percent_split=100.0,
            publisher=publisher
        )
        
        distributions = self.calculator.calculate_royalty_distributions(play_log)
        
        # Should route to publisher, not artist
        self.assertEqual(len(distributions), 1)
        self.assertEqual(distributions[0]['recipient'], publisher.user)
        self.assertEqual(distributions[0]['recipient_type'], 'publisher')
    
    def test_calculate_pro_share_local_track(self):
        """Test PRO share calculation for local track."""
        play_log = PlayLogFactory(track=self.track, station=self.station)
        
        pro_share = self.calculator.calculate_pro_share(play_log, 'ghamro')
        
        # Local PRO should get standard percentage
        expected_share = self.calculator.get_base_royalty_amount(play_log) * Decimal('0.10')
        self.assertEqual(pro_share, expected_share)
    
    def test_calculate_pro_share_foreign_track(self):
        """Test PRO share calculation for foreign track."""
        play_log = PlayLogFactory(track=self.track, station=self.station)
        
        # Mock as foreign track
        play_log.pro_affiliation = 'ascap'
        play_log.save()
        
        pro_share = self.calculator.calculate_pro_share(play_log, 'ascap')
        
        # Foreign PRO should get higher percentage
        expected_share = self.calculator.get_base_royalty_amount(play_log) * Decimal('0.15')
        self.assertEqual(pro_share, expected_share)
    
    def test_currency_conversion(self):
        """Test currency conversion in royalty calculations."""
        # Create exchange rate
        exchange_rate = CurrencyExchangeRate.objects.create(
            from_currency='GHS',
            to_currency='USD',
            rate=Decimal('0.08'),  # 1 GHS = 0.08 USD
            effective_date=date.today(),
            source='bank'
        )
        
        ghs_amount = Decimal('100.00')
        usd_amount = self.calculator.convert_currency(ghs_amount, 'GHS', 'USD')
        
        expected_usd = ghs_amount * Decimal('0.08')
        self.assertEqual(usd_amount, expected_usd)
    
    def test_royalty_calculation_validation(self):
        """Test validation of royalty calculation inputs."""
        # Test with invalid play log
        with self.assertRaises(ValueError):
            self.calculator.calculate_royalty_distributions(None)
        
        # Test with track that has no contributors
        track_no_contributors = TrackFactory()
        play_log = PlayLogFactory(track=track_no_contributors, station=self.station)
        
        distributions = self.calculator.calculate_royalty_distributions(play_log)
        self.assertEqual(len(distributions), 0)
    
    def test_contributor_split_validation(self):
        """Test that contributor splits must sum to 100%."""
        play_log = PlayLogFactory(track=self.track, station=self.station)
        
        # Create contributors with splits that don't sum to 100%
        artist2 = ArtistFactory()
        TrackContributorFactory(
            track=self.track,
            user=self.artist.user,
            percent_split=60.0
        )
        TrackContributorFactory(
            track=self.track,
            user=artist2.user,
            percent_split=50.0  # Total = 110%
        )
        
        with self.assertRaises(ValueError):
            self.calculator.validate_contributor_splits(self.track)


@pytest.mark.royalty
class RoyaltyCycleTestCase(TestCase):
    """Test cases for royalty cycle management."""
    
    def setUp(self):
        self.calculator = RoyaltyCalculator()
        self.artist = ArtistFactory()
        self.track = TrackFactory(artist=self.artist)
        self.station = StationProfileFactory()
    
    def test_create_royalty_cycle(self):
        """Test creation of new royalty cycle."""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        
        cycle = RoyaltyCycle.objects.create(
            cycle_name='January 2024',
            start_date=start_date,
            end_date=end_date,
            status='pending'
        )
        
        self.assertEqual(cycle.cycle_name, 'January 2024')
        self.assertEqual(cycle.status, 'pending')
        self.assertEqual(cycle.start_date, start_date)
        self.assertEqual(cycle.end_date, end_date)
    
    def test_calculate_cycle_totals(self):
        """Test calculation of cycle totals."""
        cycle = RoyaltyCycleFactory()
        
        # Create play logs for the cycle period
        play_logs = [
            PlayLogFactory(
                track=self.track,
                station=self.station,
                played_at=cycle.start_date,
                duration_seconds=180
            ) for _ in range(5)
        ]
        
        # Calculate cycle
        total_plays, total_royalties = self.calculator.calculate_cycle_totals(cycle)
        
        self.assertEqual(total_plays, 5)
        self.assertGreater(total_royalties, Decimal('0'))
    
    def test_cycle_status_transitions(self):
        """Test royalty cycle status transitions."""
        cycle = RoyaltyCycleFactory(status='pending')
        
        # Transition to calculating
        cycle.status = 'calculating'
        cycle.save()
        self.assertEqual(cycle.status, 'calculating')
        
        # Transition to completed
        cycle.status = 'completed'
        cycle.save()
        self.assertEqual(cycle.status, 'completed')
    
    def test_overlapping_cycles_validation(self):
        """Test that overlapping cycles are not allowed."""
        # Create first cycle
        cycle1 = RoyaltyCycleFactory(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )
        
        # Try to create overlapping cycle
        with self.assertRaises(Exception):
            RoyaltyCycle.objects.create(
                cycle_name='Overlapping Cycle',
                start_date=date(2024, 1, 15),  # Overlaps with cycle1
                end_date=date(2024, 2, 15),
                status='pending'
            )


@pytest.mark.royalty
class PROIntegrationTestCase(TestCase):
    """Test cases for PRO integration service."""
    
    def setUp(self):
        self.pro_service = PROIntegrationService()
        self.cycle = RoyaltyCycleFactory()
    
    def test_generate_pro_report_ghamro(self):
        """Test generation of GHAMRO report."""
        # Create local play logs
        track = TrackFactory()
        play_logs = [
            PlayLogFactory(
                track=track,
                pro_affiliation='ghamro',
                played_at=self.cycle.start_date
            ) for _ in range(3)
        ]
        
        report = self.pro_service.generate_pro_report(self.cycle, 'ghamro')
        
        self.assertIsNotNone(report)
        self.assertEqual(report['pro'], 'ghamro')
        self.assertEqual(len(report['plays']), 3)
        self.assertIn('total_royalties', report)
    
    def test_generate_pro_report_ascap(self):
        """Test generation of ASCAP reciprocal report."""
        # Create foreign play logs
        track = TrackFactory(isrc='USRC17607839')  # US ISRC
        play_logs = [
            PlayLogFactory(
                track=track,
                pro_affiliation='ascap',
                played_at=self.cycle.start_date
            ) for _ in range(2)
        ]
        
        report = self.pro_service.generate_pro_report(self.cycle, 'ascap')
        
        self.assertIsNotNone(report)
        self.assertEqual(report['pro'], 'ascap')
        self.assertEqual(len(report['plays']), 2)
        self.assertIn('reciprocal_rate', report)
    
    @patch('royalties.services.pro_integration.requests.post')
    def test_submit_pro_report_success(self, mock_post):
        """Test successful PRO report submission."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'accepted', 'report_id': 'RPT123'}
        mock_post.return_value = mock_response
        
        report_data = {
            'pro': 'ghamro',
            'cycle_id': self.cycle.id,
            'plays': [],
            'total_royalties': Decimal('100.00')
        }
        
        result = self.pro_service.submit_pro_report(report_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['report_id'], 'RPT123')
    
    @patch('royalties.services.pro_integration.requests.post')
    def test_submit_pro_report_failure(self, mock_post):
        """Test failed PRO report submission."""
        mock_post.side_effect = Exception("Connection failed")
        
        report_data = {
            'pro': 'ghamro',
            'cycle_id': self.cycle.id,
            'plays': [],
            'total_royalties': Decimal('100.00')
        }
        
        result = self.pro_service.submit_pro_report(report_data)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_calculate_reciprocal_royalties(self):
        """Test calculation of reciprocal royalties for foreign PROs."""
        # Create foreign play logs
        foreign_plays = [
            PlayLogFactory(pro_affiliation='ascap') for _ in range(3)
        ]
        
        reciprocal_amount = self.pro_service.calculate_reciprocal_royalties(
            foreign_plays, 'ascap'
        )
        
        self.assertGreater(reciprocal_amount, Decimal('0'))
        
        # Should be higher rate for foreign PRO
        local_plays = [
            PlayLogFactory(pro_affiliation='ghamro') for _ in range(3)
        ]
        local_amount = self.pro_service.calculate_reciprocal_royalties(
            local_plays, 'ghamro'
        )
        
        self.assertGreater(reciprocal_amount, local_amount)


@pytest.mark.royalty
class RoyaltyTasksTestCase(TestCase):
    """Test cases for royalty calculation Celery tasks."""
    
    def setUp(self):
        self.cycle = RoyaltyCycleFactory(status='pending')
        self.artist = ArtistFactory()
        self.track = TrackFactory(artist=self.artist)
        self.station = StationProfileFactory()
    
    @patch('royalties.tasks.RoyaltyCalculator.calculate_cycle_totals')
    def test_calculate_royalty_cycle_task_success(self, mock_calculate):
        """Test successful royalty cycle calculation task."""
        # Mock calculation results
        mock_calculate.return_value = (100, Decimal('500.00'))
        
        result = calculate_royalty_cycle.apply(args=[self.cycle.id])
        
        self.assertTrue(result.successful())
        
        # Verify cycle was updated
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, 'completed')
        self.assertEqual(self.cycle.total_plays, 100)
        self.assertEqual(self.cycle.total_royalties, Decimal('500.00'))
    
    def test_calculate_royalty_cycle_task_failure(self):
        """Test royalty cycle calculation task failure handling."""
        # Use non-existent cycle ID
        result = calculate_royalty_cycle.apply(args=[99999])
        
        self.assertFalse(result.successful())
    
    @patch('royalties.tasks.send_payment_notification')
    def test_distribute_royalties_task_success(self, mock_notify):
        """Test successful royalty distribution task."""
        # Create royalty distribution
        distribution = RoyaltyDistributionFactory(
            cycle=self.cycle,
            recipient=self.artist.user,
            status='pending'
        )
        
        result = distribute_royalties.apply(args=[self.cycle.id])
        
        self.assertTrue(result.successful())
        
        # Verify distribution was processed
        distribution.refresh_from_db()
        self.assertEqual(distribution.status, 'paid')
        
        # Verify notification was sent
        mock_notify.assert_called()
    
    def test_distribute_royalties_task_insufficient_balance(self):
        """Test royalty distribution with insufficient platform balance."""
        # Create large distribution that exceeds platform balance
        distribution = RoyaltyDistributionFactory(
            cycle=self.cycle,
            recipient=self.artist.user,
            total_amount=Decimal('1000000.00'),  # Very large amount
            status='pending'
        )
        
        result = distribute_royalties.apply(args=[self.cycle.id])
        
        # Task should complete but distribution should remain pending
        self.assertTrue(result.successful())
        
        distribution.refresh_from_db()
        self.assertEqual(distribution.status, 'pending')


@pytest.mark.royalty
@pytest.mark.integration
class RoyaltyWorkflowIntegrationTestCase(TestCase):
    """Integration tests for complete royalty workflow."""
    
    def setUp(self):
        self.artist = ArtistFactory()
        self.track = TrackFactory(artist=self.artist)
        self.station = StationProfileFactory()
        
        # Create contributor
        self.contributor = TrackContributorFactory(
            track=self.track,
            user=self.artist.user,
            percent_split=100.0
        )
        
        # Create rate structure
        self.rate_structure = RoyaltyRateStructure.objects.create(
            name='Test Rate',
            station_class=self.station.station_class,
            time_period='standard',
            base_rate=Decimal('0.05'),
            multiplier=Decimal('1.0'),
            territory='Ghana',
            effective_date=date.today(),
            is_active=True
        )
    
    def test_complete_royalty_workflow(self):
        """Test complete workflow from play detection to royalty payment."""
        # Step 1: Create play logs (simulating detected airplay)
        play_logs = [
            PlayLogFactory(
                track=self.track,
                station=self.station,
                duration_seconds=180,
                played_at=date.today()
            ) for _ in range(5)
        ]
        
        # Step 2: Create royalty cycle
        cycle = RoyaltyCycle.objects.create(
            cycle_name='Test Cycle',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status='pending'
        )
        
        # Step 3: Calculate royalties
        calculator = RoyaltyCalculator()
        total_plays, total_royalties = calculator.calculate_cycle_totals(cycle)
        
        # Update cycle
        cycle.total_plays = total_plays
        cycle.total_royalties = total_royalties
        cycle.status = 'calculating'
        cycle.save()
        
        # Step 4: Create distributions
        for play_log in play_logs:
            distributions = calculator.calculate_royalty_distributions(play_log)
            
            for dist_data in distributions:
                distribution, created = RoyaltyDistribution.objects.get_or_create(
                    cycle=cycle,
                    recipient=dist_data['recipient'],
                    recipient_type=dist_data['recipient_type'],
                    defaults={
                        'total_amount': dist_data['amount'],
                        'currency': 'GHS',
                        'status': 'pending'
                    }
                )
                
                if not created:
                    distribution.total_amount += dist_data['amount']
                    distribution.save()
                
                # Create line item
                RoyaltyLineItem.objects.create(
                    distribution=distribution,
                    play_log=play_log,
                    track=self.track,
                    station=self.station,
                    amount=dist_data['amount'],
                    rate_applied=self.rate_structure.base_rate,
                    contributor_split=dist_data['percent_split']
                )
        
        # Step 5: Verify results
        cycle.status = 'completed'
        cycle.save()
        
        # Verify cycle totals
        self.assertEqual(cycle.total_plays, 5)
        self.assertGreater(cycle.total_royalties, Decimal('0'))
        
        # Verify distributions were created
        distributions = RoyaltyDistribution.objects.filter(cycle=cycle)
        self.assertEqual(distributions.count(), 1)  # One recipient (artist)
        
        artist_distribution = distributions.first()
        self.assertEqual(artist_distribution.recipient, self.artist.user)
        self.assertEqual(artist_distribution.recipient_type, 'artist')
        
        # Verify line items were created
        line_items = RoyaltyLineItem.objects.filter(distribution=artist_distribution)
        self.assertEqual(line_items.count(), 5)  # One per play
        
        # Verify total amounts match
        total_line_items = sum(item.amount for item in line_items)
        self.assertEqual(total_line_items, artist_distribution.total_amount)
    
    def test_royalty_workflow_with_publisher(self):
        """Test royalty workflow when artist has publisher."""
        # Create publisher and relationship
        publisher = PublisherProfileFactory()
        relationship = PublisherArtistRelationshipFactory(
            publisher=publisher,
            artist=self.artist,
            royalty_split_percentage=70.0,
            status='active'
        )
        
        # Update artist and contributor
        self.artist.self_publish = False
        self.artist.save()
        
        self.contributor.publisher = publisher
        self.contributor.save()
        
        # Create play log
        play_log = PlayLogFactory(
            track=self.track,
            station=self.station,
            duration_seconds=180
        )
        
        # Calculate royalties
        calculator = RoyaltyCalculator()
        distributions = calculator.calculate_royalty_distributions(play_log)
        
        # Should route to publisher
        self.assertEqual(len(distributions), 1)
        self.assertEqual(distributions[0]['recipient'], publisher.user)
        self.assertEqual(distributions[0]['recipient_type'], 'publisher')
    
    def test_royalty_workflow_with_foreign_pro(self):
        """Test royalty workflow with foreign PRO content."""
        # Create play log with foreign PRO affiliation
        play_log = PlayLogFactory(
            track=self.track,
            station=self.station,
            pro_affiliation='ascap',  # Foreign PRO
            duration_seconds=180
        )
        
        # Calculate royalties
        calculator = RoyaltyCalculator()
        pro_share = calculator.calculate_pro_share(play_log, 'ascap')
        
        # Foreign PRO should get higher share
        base_amount = calculator.get_base_royalty_amount(play_log)
        expected_foreign_share = base_amount * Decimal('0.15')
        
        self.assertEqual(pro_share, expected_foreign_share)
        
        # Create partner remittance
        remittance = PartnerRemittance.objects.create(
            partner_pro='ascap',
            cycle_start_date=date.today(),
            cycle_end_date=date.today() + timedelta(days=30),
            total_amount=pro_share,
            currency='USD',
            status='pending'
        )
        
        self.assertEqual(remittance.partner_pro, 'ascap')
        self.assertEqual(remittance.total_amount, pro_share)
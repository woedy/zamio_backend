"""
Integration tests for API endpoints and cross-system workflows.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from unittest.mock import patch, Mock
import json
from decimal import Decimal
from datetime import date, timedelta

from accounts.models import User
from artists.models import Artist, Track
from stations.models import StationProfile
from publishers.models import PublisherProfile
from royalties.models import RoyaltyCycle, RoyaltyDistribution
from music_monitor.models import PlayLog, AudioDetection
from tests.factories import (
    ArtistUserFactory, AdminUserFactory, StationUserFactory, PublisherUserFactory,
    ArtistFactory, TrackFactory, StationProfileFactory, PublisherProfileFactory,
    PlayLogFactory, RoyaltyCycleFactory
)


@pytest.mark.api
class AuthenticationAPITestCase(APITestCase):
    """Test cases for authentication API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = ArtistUserFactory(email='test@example.com')
        self.user.set_password('testpass123')
        self.user.save()
    
    def test_register_endpoint(self):
        """Test user registration endpoint."""
        url = '/api/auth/register/'
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'Artist',
            'phone_number': '+233123456789'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        
        # Verify user was created
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.user_type, 'Artist')
    
    def test_login_endpoint(self):
        """Test user login endpoint."""
        url = '/api/auth/login/'
        data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], self.user.email)
    
    def test_token_refresh_endpoint(self):
        """Test JWT token refresh endpoint."""
        # First login to get tokens
        login_url = '/api/auth/login/'
        login_data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        login_response = self.client.post(login_url, login_data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Test token refresh
        refresh_url = '/api/auth/token/refresh/'
        refresh_data = {'refresh': refresh_token}
        
        response = self.client.post(refresh_url, refresh_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_user_profile_endpoint(self):
        """Test authenticated user profile endpoint."""
        self.client.force_authenticate(user=self.user)
        
        url = '/api/auth/user/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertEqual(response.data['user_type'], self.user.user_type)


@pytest.mark.api
class ArtistAPITestCase(APITestCase):
    """Test cases for artist API endpoints."""
    
    def setUp(self):
        self.artist_user = ArtistUserFactory()
        self.artist = ArtistFactory(user=self.artist_user)
        self.admin_user = AdminUserFactory()
        self.client = APIClient()
    
    def test_artist_profile_get(self):
        """Test getting artist profile."""
        self.client.force_authenticate(user=self.artist_user)
        
        url = '/api/artists/profile/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stage_name'], self.artist.stage_name)
        self.assertEqual(response.data['self_publish'], self.artist.self_publish)
    
    def test_artist_profile_update(self):
        """Test updating artist profile."""
        self.client.force_authenticate(user=self.artist_user)
        
        url = '/api/artists/profile/'
        data = {
            'stage_name': 'Updated Stage Name',
            'bio': 'Updated bio',
            'genre': 'Hip Hop'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stage_name'], 'Updated Stage Name')
        
        # Verify database was updated
        self.artist.refresh_from_db()
        self.assertEqual(self.artist.stage_name, 'Updated Stage Name')
    
    def test_artist_tracks_list(self):
        """Test listing artist tracks."""
        self.client.force_authenticate(user=self.artist_user)
        
        # Create tracks for the artist
        tracks = [TrackFactory(artist=self.artist) for _ in range(3)]
        
        url = '/api/artists/tracks/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_track_upload(self):
        """Test track upload endpoint."""
        self.client.force_authenticate(user=self.artist_user)
        
        url = '/api/artists/tracks/'
        data = {
            'title': 'New Track',
            'duration': 180,
            'genre': 'Afrobeats',
            'release_date': date.today().isoformat()
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Track')
        
        # Verify track was created
        track = Track.objects.get(title='New Track')
        self.assertEqual(track.artist, self.artist)
    
    def test_artist_analytics(self):
        """Test artist analytics endpoint."""
        self.client.force_authenticate(user=self.artist_user)
        
        # Create some play logs for analytics
        track = TrackFactory(artist=self.artist)
        play_logs = [PlayLogFactory(track=track) for _ in range(5)]
        
        url = '/api/artists/analytics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_plays', response.data)
        self.assertIn('total_earnings', response.data)
        self.assertEqual(response.data['total_plays'], 5)
    
    def test_artist_unauthorized_access(self):
        """Test that artists cannot access other artists' data."""
        other_artist = ArtistFactory()
        self.client.force_authenticate(user=self.artist_user)
        
        url = f'/api/artists/{other_artist.id}/profile/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@pytest.mark.api
class StationAPITestCase(APITestCase):
    """Test cases for station API endpoints."""
    
    def setUp(self):
        self.station_user = StationUserFactory()
        self.station = StationProfileFactory(user=self.station_user)
        self.admin_user = AdminUserFactory()
        self.client = APIClient()
    
    def test_station_profile_get(self):
        """Test getting station profile."""
        self.client.force_authenticate(user=self.station_user)
        
        url = '/api/stations/profile/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['station_name'], self.station.station_name)
        self.assertEqual(response.data['call_sign'], self.station.call_sign)
    
    def test_station_profile_update(self):
        """Test updating station profile."""
        self.client.force_authenticate(user=self.station_user)
        
        url = '/api/stations/profile/'
        data = {
            'station_name': 'Updated Station Name',
            'location': 'Updated Location',
            'stream_url': 'http://updated.stream.com/live'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['station_name'], 'Updated Station Name')
    
    def test_playlog_submission(self):
        """Test playlog submission endpoint."""
        self.client.force_authenticate(user=self.station_user)
        
        track = TrackFactory()
        url = '/api/stations/playlogs/'
        data = {
            'track_id': track.id,
            'played_at': '2024-01-01T12:00:00Z',
            'duration_seconds': 180
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify playlog was created
        playlog = PlayLog.objects.get(track=track, station=self.station)
        self.assertEqual(playlog.duration_seconds, 180)
    
    def test_match_logs_view(self):
        """Test viewing match logs."""
        self.client.force_authenticate(user=self.station_user)
        
        # Create some detections for the station
        detections = [
            AudioDetection.objects.create(
                station=self.station,
                track=TrackFactory(),
                detection_source='local',
                confidence_score=0.9,
                session_id='test-session'
            ) for _ in range(3)
        ]
        
        url = '/api/stations/match-logs/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_stream_validation(self):
        """Test stream URL validation endpoint."""
        self.client.force_authenticate(user=self.station_user)
        
        url = '/api/stations/validate-stream/'
        data = {'stream_url': 'http://valid.stream.com/live.mp3'}
        
        with patch('stations.services.validate_stream_url') as mock_validate:
            mock_validate.return_value = True
            
            response = self.client.post(url, data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['is_valid'])


@pytest.mark.api
class AdminAPITestCase(APITestCase):
    """Test cases for admin API endpoints."""
    
    def setUp(self):
        self.admin_user = AdminUserFactory()
        self.artist_user = ArtistUserFactory()
        self.station_user = StationUserFactory()
        self.client = APIClient()
    
    def test_admin_users_list(self):
        """Test admin users list endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = '/api/admin/users/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 3)  # At least 3 users
    
    def test_admin_user_detail(self):
        """Test admin user detail endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = f'/api/admin/users/{self.artist_user.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.artist_user.email)
    
    def test_admin_kyc_approval(self):
        """Test KYC approval endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Set user KYC to pending
        self.artist_user.kyc_status = 'pending'
        self.artist_user.save()
        
        url = f'/api/admin/users/{self.artist_user.id}/kyc-approve/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify KYC was approved
        self.artist_user.refresh_from_db()
        self.assertEqual(self.artist_user.kyc_status, 'verified')
    
    def test_admin_royalty_cycles(self):
        """Test admin royalty cycles endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create some royalty cycles
        cycles = [RoyaltyCycleFactory() for _ in range(3)]
        
        url = '/api/admin/royalty-cycles/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_admin_create_royalty_cycle(self):
        """Test creating royalty cycle via admin endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = '/api/admin/royalty-cycles/'
        data = {
            'cycle_name': 'Test Cycle',
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify cycle was created
        cycle = RoyaltyCycle.objects.get(cycle_name='Test Cycle')
        self.assertEqual(cycle.created_by, self.admin_user)
    
    def test_admin_platform_analytics(self):
        """Test admin platform analytics endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = '/api/admin/analytics/platform/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_users', response.data)
        self.assertIn('total_tracks', response.data)
        self.assertIn('total_stations', response.data)
    
    def test_non_admin_access_denied(self):
        """Test that non-admin users cannot access admin endpoints."""
        self.client.force_authenticate(user=self.artist_user)
        
        url = '/api/admin/users/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@pytest.mark.api
class PublisherAPITestCase(APITestCase):
    """Test cases for publisher API endpoints."""
    
    def setUp(self):
        self.publisher_user = PublisherUserFactory()
        self.publisher = PublisherProfileFactory(user=self.publisher_user)
        self.artist = ArtistFactory()
        self.client = APIClient()
    
    def test_publisher_profile_get(self):
        """Test getting publisher profile."""
        self.client.force_authenticate(user=self.publisher_user)
        
        url = '/api/publishers/profile/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['company_name'], self.publisher.company_name)
    
    def test_publisher_artists_list(self):
        """Test listing publisher's artists."""
        self.client.force_authenticate(user=self.publisher_user)
        
        # Create publisher-artist relationship
        from publishers.models import PublisherArtistRelationship
        relationship = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=70.0,
            start_date=date.today(),
            status='active',
            created_by=self.publisher_user
        )
        
        url = '/api/publishers/artists/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['artist']['id'], self.artist.id)
    
    def test_publisher_royalty_distributions(self):
        """Test publisher royalty distributions endpoint."""
        self.client.force_authenticate(user=self.publisher_user)
        
        # Create royalty distribution for publisher
        cycle = RoyaltyCycleFactory()
        distribution = RoyaltyDistribution.objects.create(
            cycle=cycle,
            recipient=self.publisher_user,
            recipient_type='publisher',
            total_amount=Decimal('100.00'),
            currency='GHS',
            status='paid'
        )
        
        url = '/api/publishers/royalties/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            Decimal(response.data['results'][0]['total_amount']),
            Decimal('100.00')
        )


@pytest.mark.api
class RoyaltyAPITestCase(APITestCase):
    """Test cases for royalty API endpoints."""
    
    def setUp(self):
        self.admin_user = AdminUserFactory()
        self.artist_user = ArtistUserFactory()
        self.artist = ArtistFactory(user=self.artist_user)
        self.client = APIClient()
    
    def test_royalty_rates_get(self):
        """Test getting royalty rates."""
        self.client.force_authenticate(user=self.admin_user)
        
        from royalties.models import RoyaltyRateStructure
        rate = RoyaltyRateStructure.objects.create(
            name='Test Rate',
            station_class='A',
            time_period='peak',
            base_rate=Decimal('0.05'),
            multiplier=Decimal('1.5'),
            territory='Ghana',
            effective_date=date.today(),
            is_active=True
        )
        
        url = '/api/royalties/rates/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Rate')
    
    def test_royalty_calculation_preview(self):
        """Test royalty calculation preview endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        track = TrackFactory(artist=self.artist)
        station = StationProfileFactory()
        
        url = '/api/royalties/calculate-preview/'
        data = {
            'track_id': track.id,
            'station_id': station.id,
            'duration_seconds': 180,
            'play_count': 5
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('estimated_royalty', response.data)
        self.assertIn('rate_applied', response.data)
    
    def test_artist_royalty_request(self):
        """Test artist royalty payment request."""
        self.client.force_authenticate(user=self.artist_user)
        
        # Create pending royalty distribution
        cycle = RoyaltyCycleFactory()
        distribution = RoyaltyDistribution.objects.create(
            cycle=cycle,
            recipient=self.artist_user,
            recipient_type='artist',
            total_amount=Decimal('50.00'),
            currency='GHS',
            status='pending'
        )
        
        url = '/api/royalties/request-payment/'
        data = {'distribution_id': distribution.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('request_id', response.data)


@pytest.mark.api
class ErrorHandlingAPITestCase(APITestCase):
    """Test cases for API error handling."""
    
    def setUp(self):
        self.user = ArtistUserFactory()
        self.client = APIClient()
    
    def test_unauthenticated_request(self):
        """Test error handling for unauthenticated requests."""
        url = '/api/artists/profile/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertIn('code', response.data['error'])
        self.assertIn('message', response.data['error'])
    
    def test_not_found_error(self):
        """Test error handling for not found resources."""
        self.client.force_authenticate(user=self.user)
        
        url = '/api/artists/tracks/99999/'  # Non-existent track
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_validation_error(self):
        """Test error handling for validation errors."""
        self.client.force_authenticate(user=self.user)
        
        url = '/api/artists/tracks/'
        data = {
            'title': '',  # Empty title should fail validation
            'duration': -1  # Negative duration should fail
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('details', response.data['error'])
    
    def test_permission_denied_error(self):
        """Test error handling for permission denied."""
        artist_user = ArtistUserFactory()
        admin_user = AdminUserFactory()
        
        self.client.force_authenticate(user=artist_user)
        
        # Artist trying to access admin endpoint
        url = '/api/admin/users/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)
    
    def test_rate_limit_error(self):
        """Test error handling for rate limiting."""
        # Mock rate limiting
        with patch('accounts.middleware.RateLimitMiddleware.process_request') as mock_rate_limit:
            from django.http import HttpResponse
            mock_rate_limit.return_value = HttpResponse(
                json.dumps({'error': {'code': 'RATE_LIMIT_EXCEEDED', 'message': 'Too many requests'}}),
                status=429,
                content_type='application/json'
            )
            
            url = '/api/auth/login/'
            response = self.client.post(url, {})
            
            self.assertEqual(response.status_code, 429)


@pytest.mark.api
@pytest.mark.integration
class CrossSystemWorkflowTestCase(APITestCase):
    """Integration tests for cross-system workflows."""
    
    def setUp(self):
        self.admin_user = AdminUserFactory()
        self.artist_user = ArtistUserFactory()
        self.station_user = StationUserFactory()
        self.artist = ArtistFactory(user=self.artist_user)
        self.station = StationProfileFactory(user=self.station_user)
        self.client = APIClient()
    
    def test_complete_track_to_royalty_workflow(self):
        """Test complete workflow from track upload to royalty calculation."""
        # Step 1: Artist uploads track
        self.client.force_authenticate(user=self.artist_user)
        
        track_data = {
            'title': 'Test Track',
            'duration': 180,
            'genre': 'Afrobeats',
            'release_date': date.today().isoformat()
        }
        
        track_response = self.client.post('/api/artists/tracks/', track_data, format='json')
        self.assertEqual(track_response.status_code, status.HTTP_201_CREATED)
        track_id = track_response.data['id']
        
        # Step 2: Station submits playlog
        self.client.force_authenticate(user=self.station_user)
        
        playlog_data = {
            'track_id': track_id,
            'played_at': '2024-01-01T12:00:00Z',
            'duration_seconds': 180
        }
        
        playlog_response = self.client.post('/api/stations/playlogs/', playlog_data, format='json')
        self.assertEqual(playlog_response.status_code, status.HTTP_201_CREATED)
        
        # Step 3: Admin creates royalty cycle
        self.client.force_authenticate(user=self.admin_user)
        
        cycle_data = {
            'cycle_name': 'Test Cycle',
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        }
        
        cycle_response = self.client.post('/api/admin/royalty-cycles/', cycle_data, format='json')
        self.assertEqual(cycle_response.status_code, status.HTTP_201_CREATED)
        cycle_id = cycle_response.data['id']
        
        # Step 4: Calculate royalties
        calculate_response = self.client.post(f'/api/admin/royalty-cycles/{cycle_id}/calculate/')
        self.assertEqual(calculate_response.status_code, status.HTTP_200_OK)
        
        # Step 5: Verify artist can see their royalties
        self.client.force_authenticate(user=self.artist_user)
        
        royalties_response = self.client.get('/api/artists/royalties/')
        self.assertEqual(royalties_response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(royalties_response.data['results']), 0)
    
    def test_publisher_artist_workflow(self):
        """Test publisher-artist relationship workflow."""
        publisher_user = PublisherUserFactory()
        publisher = PublisherProfileFactory(user=publisher_user)
        
        # Step 1: Publisher creates relationship with artist
        self.client.force_authenticate(user=publisher_user)
        
        relationship_data = {
            'artist_id': self.artist.id,
            'relationship_type': 'exclusive',
            'royalty_split_percentage': 70.0,
            'start_date': date.today().isoformat(),
            'territory': 'Ghana'
        }
        
        relationship_response = self.client.post(
            '/api/publishers/artist-relationships/',
            relationship_data,
            format='json'
        )
        self.assertEqual(relationship_response.status_code, status.HTTP_201_CREATED)
        
        # Step 2: Admin approves relationship
        self.client.force_authenticate(user=self.admin_user)
        
        relationship_id = relationship_response.data['id']
        approve_response = self.client.post(
            f'/api/admin/publisher-relationships/{relationship_id}/approve/'
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        
        # Step 3: Verify artist is no longer self-published
        self.client.force_authenticate(user=self.artist_user)
        
        profile_response = self.client.get('/api/artists/profile/')
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertFalse(profile_response.data['self_publish'])
        
        # Step 4: Verify publisher can see artist in their portfolio
        self.client.force_authenticate(user=publisher_user)
        
        artists_response = self.client.get('/api/publishers/artists/')
        self.assertEqual(artists_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(artists_response.data['results']), 1)
        self.assertEqual(artists_response.data['results'][0]['artist']['id'], self.artist.id)
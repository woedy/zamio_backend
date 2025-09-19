"""
Factory classes for generating test data using factory_boy.
"""

import factory
from factory.django import DjangoModelFactory
from factory import Faker, SubFactory, LazyAttribute
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
import uuid

from accounts.models import User
from artists.models import Artist, Track, TrackContributor
from stations.models import Station, StationProfile
from publishers.models import PublisherProfile, PublisherArtistRelationship
from music_monitor.models import PlayLog, AudioDetection, FingerprintData
from royalties.models import RoyaltyCycle, RoyaltyDistribution, RoyaltyLineItem

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
    
    email = Faker('email')
    first_name = Faker('first_name')
    last_name = Faker('last_name')
    user_type = 'Artist'
    is_active = True
    is_verified = True
    kyc_status = 'verified'
    phone_number = Faker('phone_number')
    date_joined = Faker('date_time_this_year', tzinfo=timezone.utc)


class ArtistUserFactory(UserFactory):
    """Factory for creating Artist users."""
    user_type = 'Artist'


class PublisherUserFactory(UserFactory):
    """Factory for creating Publisher users."""
    user_type = 'Publisher'


class StationUserFactory(UserFactory):
    """Factory for creating Station users."""
    user_type = 'Station'


class AdminUserFactory(UserFactory):
    """Factory for creating Admin users."""
    user_type = 'Admin'
    is_staff = True
    is_superuser = True


class ArtistFactory(DjangoModelFactory):
    """Factory for creating Artist profiles."""
    
    class Meta:
        model = Artist
    
    user = SubFactory(ArtistUserFactory)
    stage_name = Faker('name')
    bio = Faker('text', max_nb_chars=500)
    self_publish = True
    country = 'Ghana'
    city = Faker('city')
    genre = 'Afrobeats'


class PublisherProfileFactory(DjangoModelFactory):
    """Factory for creating Publisher profiles."""
    
    class Meta:
        model = PublisherProfile
    
    user = SubFactory(PublisherUserFactory)
    company_name = Faker('company')
    company_description = Faker('text', max_nb_chars=300)
    registration_number = Faker('bothify', text='REG-####-????')
    territory = 'Ghana'
    publisher_type = 'local'


class StationProfileFactory(DjangoModelFactory):
    """Factory for creating Station profiles."""
    
    class Meta:
        model = StationProfile
    
    user = SubFactory(StationUserFactory)
    station_name = Faker('company')
    call_sign = Faker('bothify', text='??##.#')
    frequency = Faker('pyfloat', left_digits=2, right_digits=1, positive=True, min_value=88.0, max_value=108.0)
    location = Faker('city')
    stream_url = Faker('url')
    station_class = 'A'
    license_number = Faker('bothify', text='LIC-####-????')


class TrackFactory(DjangoModelFactory):
    """Factory for creating Track instances."""
    
    class Meta:
        model = Track
    
    title = Faker('sentence', nb_words=3)
    artist = SubFactory(ArtistFactory)
    duration = Faker('pyint', min_value=120, max_value=300)  # 2-5 minutes
    isrc = LazyAttribute(lambda obj: f"GH{Faker('random_int', min=10, max=99).generate()}{Faker('random_int', min=1000000, max=9999999).generate()}")
    genre = 'Afrobeats'
    release_date = Faker('date_this_year')
    audio_file = Faker('file_name', extension='mp3')
    fingerprint_status = 'completed'


class TrackContributorFactory(DjangoModelFactory):
    """Factory for creating Track contributors."""
    
    class Meta:
        model = TrackContributor
    
    track = SubFactory(TrackFactory)
    user = SubFactory(ArtistUserFactory)
    role = 'Artist'
    percent_split = 100.0
    publisher = None


class PublisherArtistRelationshipFactory(DjangoModelFactory):
    """Factory for creating Publisher-Artist relationships."""
    
    class Meta:
        model = PublisherArtistRelationship
    
    publisher = SubFactory(PublisherProfileFactory)
    artist = SubFactory(ArtistFactory)
    relationship_type = 'exclusive'
    royalty_split_percentage = 50.0
    start_date = Faker('date_this_year')
    end_date = None
    territory = 'Ghana'
    status = 'active'
    approved_by_admin = True
    approved_by_artist = True
    created_by = SubFactory(PublisherUserFactory)


class PlayLogFactory(DjangoModelFactory):
    """Factory for creating PlayLog instances."""
    
    class Meta:
        model = PlayLog
    
    session_id = Faker('uuid4')
    station = SubFactory(StationProfileFactory)
    track = SubFactory(TrackFactory)
    played_at = Faker('date_time_this_month', tzinfo=timezone.utc)
    duration_seconds = Faker('pyint', min_value=120, max_value=300)
    confidence_score = Faker('pyfloat', left_digits=1, right_digits=3, positive=True, min_value=0.7, max_value=1.0)
    detection_source = 'local'


class AudioDetectionFactory(DjangoModelFactory):
    """Factory for creating AudioDetection instances."""
    
    class Meta:
        model = AudioDetection
    
    session_id = Faker('uuid4')
    station = SubFactory(StationProfileFactory)
    track = SubFactory(TrackFactory)
    detection_source = 'local'
    confidence_score = Faker('pyfloat', left_digits=1, right_digits=4, positive=True, min_value=0.7, max_value=1.0)
    isrc = LazyAttribute(lambda obj: obj.track.isrc if obj.track else None)
    pro_affiliation = 'ghamro'
    detected_at = Faker('date_time_this_month', tzinfo=timezone.utc)
    audio_fingerprint = Faker('sha256')
    metadata = factory.LazyFunction(lambda: {
        'duration': 30.0,
        'sample_rate': 22050,
        'channels': 2
    })


class FingerprintDataFactory(DjangoModelFactory):
    """Factory for creating FingerprintData instances."""
    
    class Meta:
        model = FingerprintData
    
    track = SubFactory(TrackFactory)
    fingerprint_hash = Faker('sha256')
    fingerprint_version = '1.0'
    processing_status = 'completed'
    confidence_threshold = 0.8
    created_at = Faker('date_time_this_year', tzinfo=timezone.utc)
    metadata = factory.LazyFunction(lambda: {
        'algorithm': 'chromaprint',
        'sample_rate': 22050,
        'duration': 180.0
    })


class RoyaltyCycleFactory(DjangoModelFactory):
    """Factory for creating RoyaltyCycle instances."""
    
    class Meta:
        model = RoyaltyCycle
    
    cycle_name = LazyAttribute(lambda obj: f"Cycle {obj.start_date.strftime('%Y-%m')}")
    start_date = Faker('date_this_year')
    end_date = LazyAttribute(lambda obj: obj.start_date + timedelta(days=30))
    status = 'completed'
    total_plays = Faker('pyint', min_value=1000, max_value=10000)
    total_royalties = Faker('pydecimal', left_digits=6, right_digits=2, positive=True)
    created_by = SubFactory(AdminUserFactory)


class RoyaltyDistributionFactory(DjangoModelFactory):
    """Factory for creating RoyaltyDistribution instances."""
    
    class Meta:
        model = RoyaltyDistribution
    
    cycle = SubFactory(RoyaltyCycleFactory)
    recipient = SubFactory(ArtistUserFactory)
    recipient_type = 'artist'
    total_amount = Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    currency = 'GHS'
    pro_share = Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    calculated_at = Faker('date_time_this_month', tzinfo=timezone.utc)
    status = 'pending'


class RoyaltyLineItemFactory(DjangoModelFactory):
    """Factory for creating RoyaltyLineItem instances."""
    
    class Meta:
        model = RoyaltyLineItem
    
    distribution = SubFactory(RoyaltyDistributionFactory)
    play_log = SubFactory(PlayLogFactory)
    track = SubFactory(TrackFactory)
    station = SubFactory(StationProfileFactory)
    amount = Faker('pydecimal', left_digits=3, right_digits=4, positive=True)
    rate_applied = Faker('pydecimal', left_digits=2, right_digits=4, positive=True)
    contributor_split = 100.0
    calculation_details = factory.LazyFunction(lambda: {
        'base_rate': 0.05,
        'multiplier': 1.0,
        'duration_factor': 1.0
    })
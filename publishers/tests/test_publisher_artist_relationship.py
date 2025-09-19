from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta

from publishers.models import PublisherProfile, PublisherArtistRelationship
from artists.models import Artist

User = get_user_model()


class PublisherArtistRelationshipTestCase(TestCase):
    """Test cases for publisher-artist relationship management"""
    
    def setUp(self):
        # Create artist user
        self.artist_user = User.objects.create_user(
            email='artist@example.com',
            first_name='Test',
            last_name='Artist',
            password='password123',
            user_type='Artist'
        )
        
        # Create publisher user
        self.publisher_user = User.objects.create_user(
            email='publisher@example.com',
            first_name='Test',
            last_name='Publisher',
            password='password123',
            user_type='Publisher'
        )
        
        # Get the artist profile (created by signal)
        self.artist = Artist.objects.get(user=self.artist_user)
        
        # Create publisher profile
        self.publisher = PublisherProfile.objects.create(
            user=self.publisher_user,
            company_name='Test Publishing Company'
        )
    
    def test_artist_initially_self_published(self):
        """Test that artist is initially marked as self-published"""
        self.assertTrue(self.artist.self_publish)
    
    def test_publisher_relationship_removes_self_publish(self):
        """Test that creating active publisher relationship removes self-publish status"""
        # Create active publisher relationship
        relationship = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=50.00,
            start_date=date.today(),
            status='active',
            approved_by_admin=True,
            approved_by_artist=True,
            created_by=self.publisher_user
        )
        
        # Refresh artist from database
        self.artist.refresh_from_db()
        
        # Artist should no longer be self-published
        self.assertFalse(self.artist.self_publish)
    
    def test_pending_relationship_keeps_self_publish(self):
        """Test that pending publisher relationship doesn't affect self-publish status"""
        # Create pending publisher relationship
        relationship = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=50.00,
            start_date=date.today(),
            status='pending',
            created_by=self.publisher_user
        )
        
        # Refresh artist from database
        self.artist.refresh_from_db()
        
        # Artist should still be self-published
        self.assertTrue(self.artist.self_publish)
    
    def test_relationship_termination_restores_self_publish(self):
        """Test that terminating publisher relationship restores self-publish status"""
        # Create active publisher relationship
        relationship = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=50.00,
            start_date=date.today(),
            status='active',
            approved_by_admin=True,
            approved_by_artist=True,
            created_by=self.publisher_user
        )
        
        # Verify artist is not self-published
        self.artist.refresh_from_db()
        self.assertFalse(self.artist.self_publish)
        
        # Terminate the relationship
        relationship.status = 'terminated'
        relationship.save()
        
        # Refresh artist from database
        self.artist.refresh_from_db()
        
        # Artist should be self-published again
        self.assertTrue(self.artist.self_publish)
    
    def test_relationship_deletion_restores_self_publish(self):
        """Test that deleting publisher relationship restores self-publish status"""
        # Create active publisher relationship
        relationship = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=50.00,
            start_date=date.today(),
            status='active',
            approved_by_admin=True,
            approved_by_artist=True,
            created_by=self.publisher_user
        )
        
        # Verify artist is not self-published
        self.artist.refresh_from_db()
        self.assertFalse(self.artist.self_publish)
        
        # Delete the relationship
        relationship.delete()
        
        # Refresh artist from database
        self.artist.refresh_from_db()
        
        # Artist should be self-published again
        self.assertTrue(self.artist.self_publish)
    
    def test_multiple_publishers_one_active(self):
        """Test artist with multiple publishers but only one active"""
        # Create second publisher
        publisher2_user = User.objects.create_user(
            email='publisher2@example.com',
            password='password123',
            user_type='Publisher'
        )
        publisher2 = PublisherProfile.objects.create(
            user=publisher2_user,
            company_name='Second Publishing Company'
        )
        
        # Create one active and one pending relationship
        active_relationship = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=50.00,
            start_date=date.today(),
            status='active',
            created_by=self.publisher_user
        )
        
        pending_relationship = PublisherArtistRelationship.objects.create(
            publisher=publisher2,
            artist=self.artist,
            relationship_type='co_publishing',
            royalty_split_percentage=25.00,
            start_date=date.today(),
            status='pending',
            created_by=publisher2_user
        )
        
        # Refresh artist from database
        self.artist.refresh_from_db()
        
        # Artist should not be self-published (has active relationship)
        self.assertFalse(self.artist.self_publish)
    
    def test_relationship_is_active_method(self):
        """Test the is_active method of PublisherArtistRelationship"""
        # Create relationship that starts today and ends in future
        relationship = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=50.00,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            status='active',
            created_by=self.publisher_user
        )
        
        self.assertTrue(relationship.is_active())
        
        # Test expired relationship
        relationship.end_date = date.today() - timedelta(days=1)
        relationship.save()
        
        self.assertFalse(relationship.is_active())
        
        # Test future relationship
        relationship.start_date = date.today() + timedelta(days=1)
        relationship.end_date = date.today() + timedelta(days=365)
        relationship.save()
        
        self.assertFalse(relationship.is_active())
    
    def test_unique_publisher_artist_territory_constraint(self):
        """Test that publisher-artist-territory combination is unique"""
        # Create first relationship
        relationship1 = PublisherArtistRelationship.objects.create(
            publisher=self.publisher,
            artist=self.artist,
            relationship_type='exclusive',
            royalty_split_percentage=50.00,
            start_date=date.today(),
            territory='Ghana',
            status='active',
            created_by=self.publisher_user
        )
        
        # Try to create duplicate relationship for same territory
        with self.assertRaises(Exception):  # Should raise IntegrityError
            PublisherArtistRelationship.objects.create(
                publisher=self.publisher,
                artist=self.artist,
                relationship_type='co_publishing',
                royalty_split_percentage=25.00,
                start_date=date.today(),
                territory='Ghana',  # Same territory
                status='pending',
                created_by=self.publisher_user
            )
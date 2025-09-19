from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import PublisherArtistRelationship


@receiver(post_save, sender=PublisherArtistRelationship)
def update_artist_self_publish_status(sender, instance, created, **kwargs):
    """
    Update artist's self_publish status when publisher relationship changes
    """
    artist = instance.artist
    
    # Check if artist has any active publisher relationships
    active_relationships = PublisherArtistRelationship.objects.filter(
        artist=artist,
        status='active'
    )
    
    # If artist has active publisher relationships, they are not self-published
    if active_relationships.exists():
        if artist.self_publish:
            artist.self_publish = False
            artist.save(update_fields=['self_publish'])
    else:
        # If no active publisher relationships, artist is self-published
        if not artist.self_publish:
            artist.self_publish = True
            artist.save(update_fields=['self_publish'])


@receiver(post_delete, sender=PublisherArtistRelationship)
def update_artist_self_publish_on_delete(sender, instance, **kwargs):
    """
    Update artist's self_publish status when publisher relationship is deleted
    """
    artist = instance.artist
    
    # Check if artist has any remaining active publisher relationships
    active_relationships = PublisherArtistRelationship.objects.filter(
        artist=artist,
        status='active'
    )
    
    # If no active publisher relationships remain, artist becomes self-published
    if not active_relationships.exists():
        artist.self_publish = True
        artist.save(update_fields=['self_publish'])
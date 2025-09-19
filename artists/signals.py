from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Artist
from accounts.models import UserPermission

User = get_user_model()


@receiver(post_save, sender=User)
def create_artist_profile_and_set_permissions(sender, instance, created, **kwargs):
    """
    Automatically create artist profile and set self-publishing when user registers as Artist
    """
    if created and instance.user_type == 'Artist':
        # Create artist profile
        artist, artist_created = Artist.objects.get_or_create(
            user=instance,
            defaults={
                'self_publish': True,  # Automatically set as self-published
                'stage_name': f"{instance.first_name} {instance.last_name}".strip() or instance.email.split('@')[0],
            }
        )
        
        if artist_created:
            # Set default permissions for self-published artists
            default_permissions = [
                'view_own_profile',
                'edit_own_profile',
                'upload_music',
                'view_own_analytics',
                'view_own_royalties',
                'request_royalty_payment',
                'submit_dispute',
                'view_own_disputes',
                'manage_own_tracks',
                'manage_own_contributors',
            ]
            
            for permission in default_permissions:
                UserPermission.objects.get_or_create(
                    user=instance,
                    permission=permission,
                    defaults={
                        'granted_by': instance,  # Self-granted
                        'is_active': True,
                    }
                )


@receiver(post_save, sender=User)
def create_publisher_permissions(sender, instance, created, **kwargs):
    """
    Set default permissions for publisher users
    """
    if created and instance.user_type == 'Publisher':
        default_permissions = [
            'view_own_profile',
            'edit_own_profile',
            'manage_artists',
            'view_portfolio_analytics',
            'view_publisher_royalties',
            'distribute_royalties',
            'submit_dispute',
            'view_own_disputes',
            'approve_artist_uploads',
            'manage_publishing_agreements',
        ]
        
        for permission in default_permissions:
            UserPermission.objects.get_or_create(
                user=instance,
                permission=permission,
                defaults={
                    'granted_by': instance,  # Self-granted
                    'is_active': True,
                }
            )


@receiver(post_save, sender=User)
def create_station_permissions(sender, instance, created, **kwargs):
    """
    Set default permissions for station users
    """
    if created and instance.user_type == 'Station':
        default_permissions = [
            'view_own_profile',
            'edit_own_profile',
            'submit_playlogs',
            'view_match_logs',
            'upload_audio_captures',
            'view_station_analytics',
            'manage_station_staff',
            'submit_dispute',
            'view_own_disputes',
        ]
        
        for permission in default_permissions:
            UserPermission.objects.get_or_create(
                user=instance,
                permission=permission,
                defaults={
                    'granted_by': instance,  # Self-granted
                    'is_active': True,
                }
            )


@receiver(post_save, sender=User)
def create_admin_permissions(sender, instance, created, **kwargs):
    """
    Set default permissions for admin users
    """
    if created and instance.user_type == 'Admin':
        default_permissions = [
            'view_all_profiles',
            'edit_all_profiles',
            'manage_users',
            'approve_kyc',
            'manage_royalty_cycles',
            'view_platform_analytics',
            'resolve_disputes',
            'manage_permissions',
            'system_administration',
            'financial_oversight',
            'approve_publishers',
            'manage_stations',
        ]
        
        for permission in default_permissions:
            UserPermission.objects.get_or_create(
                user=instance,
                permission=permission,
                defaults={
                    'granted_by': instance,  # Self-granted
                    'is_active': True,
                }
            )
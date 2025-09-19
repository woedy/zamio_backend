from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserPermission

User = get_user_model()


class Command(BaseCommand):
    help = 'Set up default permissions for user types'

    def handle(self, *args, **options):
        # Define default permissions for each user type
        permissions_map = {
            'Artist': [
                'view_own_profile',
                'edit_own_profile',
                'upload_music',
                'view_own_analytics',
                'view_own_royalties',
                'request_royalty_payment',
                'submit_dispute',
                'view_own_disputes',
            ],
            'Publisher': [
                'view_own_profile',
                'edit_own_profile',
                'manage_artists',
                'view_portfolio_analytics',
                'view_publisher_royalties',
                'distribute_royalties',
                'submit_dispute',
                'view_own_disputes',
                'approve_artist_uploads',
            ],
            'Station': [
                'view_own_profile',
                'edit_own_profile',
                'submit_playlogs',
                'view_match_logs',
                'upload_audio_captures',
                'view_station_analytics',
                'manage_station_staff',
                'submit_dispute',
                'view_own_disputes',
            ],
            'Admin': [
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
            ],
            'Fan': [
                'view_own_profile',
                'edit_own_profile',
                'follow_artists',
                'view_public_content',
            ]
        }

        self.stdout.write('Setting up default permissions...')

        # Get all users and assign permissions based on their type
        for user_type, permissions in permissions_map.items():
            users = User.objects.filter(user_type=user_type)
            
            for user in users:
                for permission in permissions:
                    # Check if permission already exists
                    if not UserPermission.objects.filter(
                        user=user, 
                        permission=permission
                    ).exists():
                        UserPermission.objects.create(
                            user=user,
                            permission=permission,
                            granted_by=user,  # Self-granted for default permissions
                        )
                        self.stdout.write(
                            f'Added permission "{permission}" to user {user.email}'
                        )

        # Set self_published flag for artists who registered directly
        artists_without_publisher = User.objects.filter(
            user_type='Artist'
        ).exclude(
            id__in=User.objects.filter(
                user_type='Artist',
                # Add logic to check if they have a publisher relationship
            )
        )

        for artist in artists_without_publisher:
            # This will be enhanced when we implement the artist model extensions
            self.stdout.write(f'Artist {artist.email} marked as self-published')

        self.stdout.write(
            self.style.SUCCESS('Successfully set up default permissions')
        )
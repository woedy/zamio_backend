from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserPermission, AuditLog
from accounts.api.custom_jwt import CustomTokenObtainPairSerializer
from artists.models import Artist

User = get_user_model()


class AuthenticationTestCase(TestCase):
    """Test cases for enhanced authentication system"""
    
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpassword123',
            'user_type': 'Artist'
        }
    
    def test_user_creation_with_enhanced_fields(self):
        """Test that user is created with enhanced authentication fields"""
        user = User.objects.create_user(**self.user_data)
        
        self.assertEqual(user.kyc_status, 'pending')
        self.assertEqual(user.kyc_documents, {})
        self.assertFalse(user.two_factor_enabled)
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertIsNone(user.account_locked_until)
        self.assertIsNotNone(user.last_activity)
    
    def test_artist_auto_self_publish(self):
        """Test that artists are automatically marked as self-published"""
        user = User.objects.create_user(**self.user_data)
        
        # Check if artist profile was created
        self.assertTrue(Artist.objects.filter(user=user).exists())
        
        artist = Artist.objects.get(user=user)
        self.assertTrue(artist.self_publish)
    
    def test_user_permissions_creation(self):
        """Test that default permissions are created for new users"""
        user = User.objects.create_user(**self.user_data)
        
        # Check that permissions were created
        permissions = UserPermission.objects.filter(user=user)
        self.assertTrue(permissions.exists())
        
        # Check for specific artist permissions
        permission_names = list(permissions.values_list('permission', flat=True))
        expected_permissions = [
            'view_own_profile',
            'edit_own_profile',
            'upload_music',
            'view_own_analytics',
            'view_own_royalties',
            'request_royalty_payment',
        ]
        
        for permission in expected_permissions:
            self.assertIn(permission, permission_names)


class JWTAuthenticationTestCase(APITestCase):
    """Test cases for JWT authentication"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            password='testpassword123',
            user_type='Artist'
        )
    
    def test_token_obtain_success(self):
        """Test successful token generation"""
        data = {
            'email': 'test@example.com',
            'password': 'testpassword123'
        }
        
        response = self.client.post('/api/auth/token/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        
        user_data = response.data['user']
        self.assertEqual(user_data['email'], self.user.email)
        self.assertEqual(user_data['user_type'], self.user.user_type)
    
    def test_token_obtain_invalid_credentials(self):
        """Test token generation with invalid credentials"""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post('/api/auth/token/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_failed_login_attempts_tracking(self):
        """Test that failed login attempts are tracked"""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        # Make multiple failed attempts
        for i in range(3):
            response = self.client.post('/api/auth/token/', data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check that failed attempts were recorded
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 3)
    
    def test_account_lockout_after_failed_attempts(self):
        """Test that account gets locked after too many failed attempts"""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        # Make 5 failed attempts to trigger lockout
        for i in range(5):
            response = self.client.post('/api/auth/token/', data)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 5)
        self.assertIsNotNone(self.user.account_locked_until)
        
        # Try with correct password - should still fail due to lockout
        correct_data = {
            'email': 'test@example.com',
            'password': 'testpassword123'
        }
        response = self.client.post('/api/auth/token/', correct_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_successful_login_resets_failed_attempts(self):
        """Test that successful login resets failed attempt counter"""
        # Set some failed attempts
        self.user.failed_login_attempts = 3
        self.user.save()
        
        data = {
            'email': 'test@example.com',
            'password': 'testpassword123'
        }
        
        response = self.client.post('/api/auth/token/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertIsNone(self.user.account_locked_until)


class PermissionTestCase(TestCase):
    """Test cases for permission system"""
    
    def setUp(self):
        self.artist_user = User.objects.create_user(
            email='artist@example.com',
            password='password123',
            user_type='Artist'
        )
        
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='password123',
            user_type='Admin'
        )
    
    def test_user_has_permission(self):
        """Test checking if user has specific permission"""
        # Artist should have upload_music permission
        has_permission = UserPermission.objects.filter(
            user=self.artist_user,
            permission='upload_music',
            is_active=True
        ).exists()
        
        self.assertTrue(has_permission)
    
    def test_admin_has_all_permissions(self):
        """Test that admin users have comprehensive permissions"""
        admin_permissions = UserPermission.objects.filter(
            user=self.admin_user,
            is_active=True
        ).values_list('permission', flat=True)
        
        expected_admin_permissions = [
            'view_all_profiles',
            'manage_users',
            'approve_kyc',
            'system_administration',
        ]
        
        for permission in expected_admin_permissions:
            self.assertIn(permission, admin_permissions)
    
    def test_permission_expiration(self):
        """Test that expired permissions are not considered active"""
        # Create a permission that expires in the past
        expired_permission = UserPermission.objects.create(
            user=self.artist_user,
            permission='test_permission',
            granted_by=self.admin_user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        # Check that expired permission is not considered when checking active permissions
        active_permissions = UserPermission.objects.filter(
            user=self.artist_user,
            permission='test_permission',
            is_active=True,
            expires_at__gt=timezone.now()
        )
        
        self.assertFalse(active_permissions.exists())


class AuditLogTestCase(APITestCase):
    """Test cases for audit logging"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='password123',
            user_type='Artist'
        )
    
    def test_audit_log_creation(self):
        """Test that audit logs are created for API calls"""
        # Make an authenticated request
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = self.client.get('/api/artists/')
        
        # Check that audit log was created
        audit_logs = AuditLog.objects.filter(user=self.user)
        self.assertTrue(audit_logs.exists())
        
        log = audit_logs.first()
        self.assertEqual(log.action, 'GET /api/artists/')
        self.assertEqual(log.status_code, response.status_code)
        self.assertIsNotNone(log.trace_id)
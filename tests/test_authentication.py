"""
Unit tests for authentication and authorization functionality.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, Mock
from freezegun import freeze_time
from datetime import datetime, timedelta

from accounts.models import User, UserPermission
from accounts.api.custom_jwt import CustomJWTAuthentication
from accounts.middleware import RateLimitMiddleware, AuditLoggingMiddleware
from tests.factories import UserFactory, ArtistUserFactory, AdminUserFactory

User = get_user_model()


@pytest.mark.auth
class AuthenticationTestCase(APITestCase):
    """Test cases for user authentication."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = ArtistUserFactory(
            email='test@example.com',
            password='testpass123'
        )
        self.user.set_password('testpass123')
        self.user.save()
    
    def test_user_registration_success(self):
        """Test successful user registration."""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'Artist',
            'phone_number': '+233123456789'
        }
        
        response = self.client.post('/api/auth/register/', data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
        # Verify user was created
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.user_type, 'Artist')
        self.assertFalse(user.is_verified)  # Should require email verification
    
    def test_user_registration_duplicate_email(self):
        """Test registration with duplicate email fails."""
        data = {
            'email': self.user.email,  # Existing email
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'user_type': 'Artist'
        }
        
        response = self.client.post('/api/auth/register/', data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
    
    def test_user_login_success(self):
        """Test successful user login."""
        data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/auth/login/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], self.user.email)
    
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials fails."""
        data = {
            'email': self.user.email,
            'password': 'wrongpassword'
        }
        
        response = self.client.post('/api/auth/login/', data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_login_unverified_account(self):
        """Test login with unverified account."""
        self.user.is_verified = False
        self.user.save()
        
        data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/auth/login/', data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('verify', response.data['detail'].lower())
    
    def test_jwt_token_refresh(self):
        """Test JWT token refresh functionality."""
        refresh = RefreshToken.for_user(self.user)
        
        data = {'refresh': str(refresh)}
        response = self.client.post('/api/auth/token/refresh/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_jwt_token_refresh_invalid(self):
        """Test JWT token refresh with invalid token."""
        data = {'refresh': 'invalid_token'}
        response = self.client.post('/api/auth/token/refresh/', data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    @freeze_time("2024-01-01 12:00:00")
    def test_jwt_token_expiration(self):
        """Test JWT token expiration handling."""
        # Create token that will expire
        refresh = RefreshToken.for_user(self.user)
        access_token = refresh.access_token
        
        # Move time forward beyond token expiration
        with freeze_time("2024-01-01 18:00:00"):  # 6 hours later
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
            response = self.client.get('/api/auth/user/')
            
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout_success(self):
        """Test successful user logout."""
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        data = {'refresh': str(refresh)}
        response = self.client.post('/api/auth/logout/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Token should be blacklisted
        response = self.client.post('/api/auth/token/refresh/', data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.auth
class AuthorizationTestCase(APITestCase):
    """Test cases for user authorization and permissions."""
    
    def setUp(self):
        self.artist_user = ArtistUserFactory()
        self.admin_user = AdminUserFactory()
        self.client = APIClient()
    
    def test_role_based_access_artist_endpoints(self):
        """Test that artists can access artist-specific endpoints."""
        self.client.force_authenticate(user=self.artist_user)
        
        # Artist should access their own profile
        response = self.client.get('/api/artists/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Artist should not access admin endpoints
        response = self.client.get('/api/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_role_based_access_admin_endpoints(self):
        """Test that admins can access admin-specific endpoints."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Admin should access admin endpoints
        response = self.client.get('/api/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin should also access artist endpoints (for management)
        response = self.client.get('/api/artists/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access protected endpoints."""
        # No authentication
        response = self.client.get('/api/artists/profile/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.client.get('/api/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_permission_system(self):
        """Test granular user permission system."""
        # Create custom permission
        permission = UserPermission.objects.create(
            user=self.artist_user,
            permission='can_manage_royalties',
            granted_by=self.admin_user
        )
        
        self.client.force_authenticate(user=self.artist_user)
        
        # Test permission check in view
        with patch('accounts.permissions.user_has_permission') as mock_permission:
            mock_permission.return_value = True
            response = self.client.get('/api/royalties/manage/')
            # Should not be forbidden due to permission
            self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_kyc_status_access_control(self):
        """Test that KYC status affects access to certain endpoints."""
        # User with pending KYC
        self.artist_user.kyc_status = 'pending'
        self.artist_user.save()
        
        self.client.force_authenticate(user=self.artist_user)
        
        # Should not access payment-related endpoints
        response = self.client.get('/api/payments/request/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify KYC and test again
        self.artist_user.kyc_status = 'verified'
        self.artist_user.save()
        
        response = self.client.get('/api/payments/request/')
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@pytest.mark.auth
class MiddlewareTestCase(TestCase):
    """Test cases for authentication middleware."""
    
    def setUp(self):
        self.user = ArtistUserFactory()
        self.factory = APIClient()
    
    def test_rate_limiting_middleware(self):
        """Test rate limiting middleware functionality."""
        middleware = RateLimitMiddleware(Mock())
        
        # Mock request
        request = Mock()
        request.META = {'REMOTE_ADDR': '127.0.0.1'}
        request.path = '/api/auth/login/'
        request.method = 'POST'
        
        # Should allow first few requests
        for i in range(5):
            response = middleware.process_request(request)
            self.assertIsNone(response)  # No rate limit response
        
        # Mock cache to simulate rate limit exceeded
        with patch('django.core.cache.cache.get') as mock_cache:
            mock_cache.return_value = 100  # High request count
            response = middleware.process_request(request)
            self.assertIsNotNone(response)  # Rate limit response
            self.assertEqual(response.status_code, 429)
    
    def test_audit_logging_middleware(self):
        """Test audit logging middleware functionality."""
        middleware = AuditLoggingMiddleware(Mock())
        
        # Mock request and response
        request = Mock()
        request.user = self.user
        request.path = '/api/artists/profile/'
        request.method = 'GET'
        request.META = {'REMOTE_ADDR': '127.0.0.1'}
        
        response = Mock()
        response.status_code = 200
        
        # Should log the request
        with patch('accounts.models.AuditLog.objects.create') as mock_create:
            middleware.process_response(request, response)
            mock_create.assert_called_once()


@pytest.mark.auth
class CustomJWTAuthenticationTestCase(TestCase):
    """Test cases for custom JWT authentication."""
    
    def setUp(self):
        self.user = ArtistUserFactory()
        self.auth = CustomJWTAuthentication()
    
    def test_jwt_authentication_success(self):
        """Test successful JWT authentication."""
        token = RefreshToken.for_user(self.user)
        
        # Mock request with valid token
        request = Mock()
        request.META = {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}
        
        user, validated_token = self.auth.authenticate(request)
        
        self.assertEqual(user, self.user)
        self.assertIsNotNone(validated_token)
    
    def test_jwt_authentication_invalid_token(self):
        """Test JWT authentication with invalid token."""
        request = Mock()
        request.META = {'HTTP_AUTHORIZATION': 'Bearer invalid_token'}
        
        result = self.auth.authenticate(request)
        self.assertIsNone(result)
    
    def test_jwt_authentication_no_token(self):
        """Test JWT authentication with no token."""
        request = Mock()
        request.META = {}
        
        result = self.auth.authenticate(request)
        self.assertIsNone(result)
    
    def test_jwt_authentication_inactive_user(self):
        """Test JWT authentication with inactive user."""
        self.user.is_active = False
        self.user.save()
        
        token = RefreshToken.for_user(self.user)
        
        request = Mock()
        request.META = {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}
        
        with self.assertRaises(Exception):  # Should raise authentication error
            self.auth.authenticate(request)


@pytest.mark.auth
class PasswordSecurityTestCase(TestCase):
    """Test cases for password security features."""
    
    def test_password_validation(self):
        """Test password validation requirements."""
        # Test weak password
        with self.assertRaises(Exception):
            user = User.objects.create_user(
                email='test@example.com',
                password='123',  # Too weak
                user_type='Artist'
            )
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        password = 'testpass123'
        user = UserFactory()
        user.set_password(password)
        user.save()
        
        # Password should be hashed, not stored in plain text
        self.assertNotEqual(user.password, password)
        self.assertTrue(user.check_password(password))
    
    def test_password_reset_token_generation(self):
        """Test password reset token generation and validation."""
        user = UserFactory()
        
        # Generate reset token
        from django.contrib.auth.tokens import default_token_generator
        token = default_token_generator.make_token(user)
        
        # Token should be valid for the user
        self.assertTrue(default_token_generator.check_token(user, token))
        
        # Token should be invalid for different user
        other_user = UserFactory()
        self.assertFalse(default_token_generator.check_token(other_user, token))


@pytest.mark.auth
class TwoFactorAuthenticationTestCase(APITestCase):
    """Test cases for two-factor authentication."""
    
    def setUp(self):
        self.user = ArtistUserFactory()
        self.user.two_factor_enabled = True
        self.user.save()
        self.client = APIClient()
    
    def test_2fa_login_requires_code(self):
        """Test that 2FA enabled users must provide verification code."""
        data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/auth/login/', data)
        
        # Should require 2FA code
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('requires_2fa', response.data)
        self.assertNotIn('access', response.data)  # No access token yet
    
    @patch('accounts.utils.verify_2fa_code')
    def test_2fa_verification_success(self, mock_verify):
        """Test successful 2FA verification."""
        mock_verify.return_value = True
        
        # First login to get 2FA session
        login_data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        login_response = self.client.post('/api/auth/login/', login_data)
        
        # Verify 2FA code
        verify_data = {
            'session_id': login_response.data.get('session_id'),
            'code': '123456'
        }
        verify_response = self.client.post('/api/auth/verify-2fa/', verify_data)
        
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', verify_response.data)
        self.assertIn('refresh', verify_response.data)
    
    @patch('accounts.utils.verify_2fa_code')
    def test_2fa_verification_failure(self, mock_verify):
        """Test failed 2FA verification."""
        mock_verify.return_value = False
        
        # First login to get 2FA session
        login_data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        login_response = self.client.post('/api/auth/login/', login_data)
        
        # Verify with wrong code
        verify_data = {
            'session_id': login_response.data.get('session_id'),
            'code': 'wrong_code'
        }
        verify_response = self.client.post('/api/auth/verify-2fa/', verify_data)
        
        self.assertEqual(verify_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('access', verify_response.data)
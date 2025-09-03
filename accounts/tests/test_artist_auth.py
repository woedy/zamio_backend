from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from artists.models import Artist


User = get_user_model()


class ArtistAuthFlowTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('accounts:register_artist')
        self.verify_url = reverse('accounts:verify_artist_email')
        self.login_url = reverse('accounts:login_artist')
        self.skip_url = reverse('accounts:skip_artist_onboarding_view')
        self.logout_url = reverse('accounts:logout_artist_view')

        self.payload = {
            'email': 'artist@example.com',
            'first_name': 'Ada',
            'last_name': 'Lovelace',
            'stage_name': 'Countess',
            'phone': '+233555000111',
            'country': 'GH',
            'password': 'StrongPass1!',
            'password2': 'StrongPass1!'
        }

    def test_01_artist_registration_success(self):
        resp = self.client.post(self.register_url, self.payload, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data.get('message'), 'Successful')
        data = resp.data.get('data') or {}
        self.assertIn('user_id', data)
        self.assertIn('token', data)

        # DB assertions
        user = User.objects.filter(email=self.payload['email']).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.user_type, 'Artist')
        self.assertTrue(Artist.objects.filter(user=user).exists())

    def test_02_artist_email_verification_success(self):
        # Register first
        self.client.post(self.register_url, self.payload, format='multipart')
        user = User.objects.get(email=self.payload['email'])
        # Use the generated email_token from DB
        verify_payload = {
            'email': user.email,
            'email_token': user.email_token,
        }
        resp = self.client.post(self.verify_url, verify_payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        data = resp.data.get('data') or {}
        self.assertEqual(resp.data.get('message'), 'Successful')
        self.assertIn('artist_id', data)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_active)

    def test_03_artist_login_success(self):
        # Register and verify
        self.client.post(self.register_url, self.payload, format='multipart')
        user = User.objects.get(email=self.payload['email'])
        self.client.post(self.verify_url, {'email': user.email, 'email_token': user.email_token}, format='json')

        # Login
        login_payload = {
            'email': self.payload['email'],
            'password': self.payload['password'],
            'fcm_token': 'test-device-token-123',
        }
        resp = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data.get('message'), 'Successful')
        data = resp.data.get('data') or {}
        self.assertIn('token', data)
        self.assertIn('onboarding_step', data)

    def test_04_skip_and_resume_flow(self):
        # Register and verify
        self.client.post(self.register_url, self.payload, format='multipart')
        user = User.objects.get(email=self.payload['email'])
        self.client.post(self.verify_url, {'email': user.email, 'email_token': user.email_token}, format='json')

        # First login and capture token + artist
        login_payload = {
            'email': self.payload['email'],
            'password': self.payload['password'],
            'fcm_token': 'device-token',
        }
        resp = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        token = resp.data['data']['token']
        artist_id = resp.data['data']['artist_id']
        self.assertEqual(resp.data['data']['onboarding_step'], 'profile')

        # Auth with token for protected endpoints
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # Skip to social-media
        r1 = self.client.post(self.skip_url, { 'artist_id': artist_id, 'step': 'social-media' }, format='json')
        self.assertEqual(r1.status_code, status.HTTP_200_OK, r1.data)
        self.assertEqual(r1.data['data']['next_step'], 'social-media')

        # Logout
        rlogout = self.client.post(self.logout_url, { 'artist_id': artist_id }, format='json')
        self.assertEqual(rlogout.status_code, status.HTTP_200_OK, rlogout.data)

        # Login should resume at social-media
        resp2 = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK, resp2.data)
        self.assertEqual(resp2.data['data']['onboarding_step'], 'social-media')

        # Auth again
        token2 = resp2.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token2}')

        # Skip to payment
        r2 = self.client.post(self.skip_url, { 'artist_id': artist_id, 'step': 'payment' }, format='json')
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.data)
        self.assertEqual(r2.data['data']['next_step'], 'payment')

        # Login again, should point to payment
        resp3 = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        self.assertEqual(resp3.data['data']['onboarding_step'], 'payment')

        # Skip to publisher and verify
        token3 = resp3.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token3}')
        r3 = self.client.post(self.skip_url, { 'artist_id': artist_id, 'step': 'publisher' }, format='json')
        self.assertEqual(r3.status_code, status.HTTP_200_OK, r3.data)
        self.assertEqual(r3.data['data']['next_step'], 'publisher')

        resp4 = self.client.post(self.login_url, login_payload, format='json')
        self.assertEqual(resp4.status_code, status.HTTP_200_OK)
        self.assertEqual(resp4.data['data']['onboarding_step'], 'publisher')

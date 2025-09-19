import uuid
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()


class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            user_id = validated_token['user_id']
            user = User.objects.get(user_id=user_id)
            
            # Update last activity
            user.last_activity = timezone.now()
            user.save(update_fields=['last_activity'])
            
            # Check if account is locked
            if user.account_locked_until and user.account_locked_until > timezone.now():
                raise InvalidToken('Account is temporarily locked')
            
            return user
        except User.DoesNotExist:
            raise InvalidToken('User not found')
        except Exception as e:
            raise InvalidToken(f'Authentication error: {str(e)}')


###############################################################################

from rest_framework import serializers
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView, TokenVerifyView as BaseTokenVerifyView


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Get user first to check account status
        try:
            user = User.objects.get(email=attrs['email'])
            
            # Check if account is locked
            if user.account_locked_until and user.account_locked_until > timezone.now():
                raise serializers.ValidationError('Account is temporarily locked due to multiple failed login attempts')
            
            # Validate credentials
            data = super().validate(attrs)
            
            # Reset failed login attempts on successful login
            if user.failed_login_attempts > 0:
                user.failed_login_attempts = 0
                user.account_locked_until = None
                user.save(update_fields=['failed_login_attempts', 'account_locked_until'])
            
            # Add user info to response
            data['user'] = {
                'user_id': user.user_id,
                'email': user.email,
                'user_type': user.user_type,
                'profile_complete': user.profile_complete,
                'kyc_status': user.kyc_status,
                'two_factor_enabled': user.two_factor_enabled,
            }
            
            return data
            
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials')
        except Exception as e:
            # Handle failed login attempt
            try:
                user = User.objects.get(email=attrs['email'])
                user.failed_login_attempts += 1
                
                # Lock account after 5 failed attempts for 30 minutes
                if user.failed_login_attempts >= 5:
                    user.account_locked_until = timezone.now() + timedelta(minutes=30)
                
                user.save(update_fields=['failed_login_attempts', 'account_locked_until'])
            except User.DoesNotExist:
                pass
            
            raise serializers.ValidationError('Invalid credentials')

    @classmethod
    def get_token(cls, user):
        token = RefreshToken.for_user(user)

        # Customize the access token payload
        token.payload['user_id'] = user.user_id
        token.payload['user_type'] = user.user_type
        token.payload['permissions'] = list(user.user_permissions.filter(
            is_active=True,
            expires_at__isnull=True
        ).values_list('permission', flat=True)) + list(user.user_permissions.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).values_list('permission', flat=True))

        return token

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



class CustomTokenRefreshView(BaseTokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            token = RefreshToken(refresh_token)
            
            # Get user and update permissions in new access token
            user_id = token.payload.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(user_id=user_id)
                    # Create new access token with updated permissions
                    new_token = RefreshToken.for_user(user)
                    access_token = str(new_token.access_token)
                    
                    return Response({
                        'access': access_token,
                        'user': {
                            'user_id': user.user_id,
                            'email': user.email,
                            'user_type': user.user_type,
                            'profile_complete': user.profile_complete,
                            'kyc_status': user.kyc_status,
                        }
                    }, status=status.HTTP_200_OK)
                except User.DoesNotExist:
                    return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Fallback to simple refresh
                access_token = str(token.access_token)
                return Response({'access': access_token}, status=status.HTTP_200_OK)
                
        except TokenError as e:
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenVerifyView(BaseTokenVerifyView):
    def post(self, request, *args, **kwargs):
        try:
            token = request.data.get('token')
            if not token:
                return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Try to decode as access token first
            try:
                from rest_framework_simplejwt.tokens import UntypedToken
                UntypedToken(token)
                return Response({'message': 'Token is valid', 'token_type': 'access'}, status=status.HTTP_200_OK)
            except:
                # Try as refresh token
                token_obj = RefreshToken(token)
                token_obj.verify()
                return Response({'message': 'Token is valid', 'token_type': 'refresh'}, status=status.HTTP_200_OK)
                
        except TokenError as e:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

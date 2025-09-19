from decimal import Decimal
from django.core.mail import send_mail

from django.conf import settings
from django.contrib.auth import get_user_model, authenticate
from django.template.loader import get_template
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response

from accounts.api.serializers import UserRegistrationSerializer
from activities.models import AllActivity


from rest_framework.views import APIView

from accounts.api.serializers import UserRegistrationSerializer
from activities.models import AllActivity
from artists.models import Artist
from bank_account.models import BankAccount
from core.utils import generate_email_token, is_valid_email, is_valid_password
from publishers.models import PublisherProfile


User = get_user_model()



@api_view(['POST', ])
@permission_classes([])
@authentication_classes([])
def register_artist_view(request):

    payload = {}
    data = {}
    errors = {}

    if request.method == 'POST':
        email = request.data.get('email', "").lower()
        first_name = request.data.get('first_name', "")
        last_name = request.data.get('last_name', "")
        stage_name = request.data.get('stage_name', "")
        phone = request.data.get('phone', "")
        photo = request.FILES.get('photo')
        country = request.data.get('country', "")
        password = request.data.get('password', "")
        password2 = request.data.get('password2', "")


        if not email:
            errors['email'] = ['User Email is required.']
        elif not is_valid_email(email):
            errors['email'] = ['Valid email required.']
        elif check_email_exist(email):
            errors['email'] = ['Email already exists in our database.']

        if not first_name:
            errors['first_name'] = ['First Name is required.']

        if not last_name:
            errors['last_name'] = ['last Name is required.']
        if not stage_name:
            errors['stage_name'] = ['Stage Name is required.']

        if not phone:
            errors['phone'] = ['Phone number is required.']

        if not password:
            errors['password'] = ['Password is required.']

        if not password2:
            errors['password2'] = ['Password2 is required.']

        if password != password2:
            errors['password'] = ['Passwords dont match.']

        if not is_valid_password(password):
            errors['password'] = ['Password must be at least 8 characters long\n- Must include at least one uppercase letter,\n- One lowercase letter, one digit,\n- And one special character']

        if errors:
            payload['message'] = "Errors"
            payload['errors'] = errors
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            payload['message'] = "Errors"
            payload['errors'] = serializer.errors
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Populate additional user fields not handled by serializer
        user.user_type = "Artist"
        user.phone = phone
        if country:
            user.country = country
        if photo:
            user.photo = photo
        user.save()

        # Create artist profile and wallet
        artist_profile = Artist.objects.create(
            user=user,
            stage_name=stage_name
        )
        BankAccount.objects.get_or_create(
            user=user,
            defaults={
                'balance': Decimal('0.00'),
                'currency': "Ghc",
            }
        )

        # Prepare response data
        data["user_id"] = user.user_id
        data["email"] = user.email
        data["first_name"] = user.first_name
        data["last_name"] = user.last_name
        data['phone'] = user.phone
        data['country'] = user.country
        data['photo'] = user.photo.url if getattr(user.photo, 'url', None) else None

        # Token for client session (email must still be verified to log in)
        token_obj, _ = Token.objects.get_or_create(user=user)
        data['token'] = token_obj.key

        email_token = generate_email_token()

        user = User.objects.get(email=email)
        user.email_token = email_token
        user.save()

        context = {
            'email_token': email_token,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
#
        txt_ = get_template("registration/emails/verify.txt").render(context)
        html_ = get_template("registration/emails/verify.html").render(context)
#
        subject = 'EMAIL CONFIRMATION CODE'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]



        # # Use Celery chain to execute tasks in sequence
        # email_chain = chain(
        #     send_generic_email.si(subject, txt_, from_email, recipient_list, html_),
        # )
        # # Execute the Celery chain asynchronously
        # email_chain.apply_async()

        send_mail(
            subject,
            txt_,
            from_email,
            recipient_list,
            html_message=html_,
            fail_silently=False,
        )



#
        new_activity = AllActivity.objects.create(
            user=user,
            subject="User Registration",
            body=user.email + " Just created an account."
        )
        new_activity.save()

        payload['message'] = "Successful"
        payload['data'] = data

    return Response(payload)


@api_view(['POST', ])
@permission_classes([])
@authentication_classes([])
def verify_artist_email(request):
    payload = {}
    data = {}
    errors = {}

    email_errors = []
    token_errors = []

    email = request.data.get('email', '').lower()
    email_token = request.data.get('email_token', '')

    if not email:
        email_errors.append('Email is required.')

    qs = User.objects.filter(email=email)
    if not qs.exists():
        email_errors.append('Email does not exist.')

    if email_errors:
        errors['email'] = email_errors

    if not email_token:
        token_errors.append('Token is required.')

    user = None
    if qs.exists():
        user = qs.first()
        if email_token != user.email_token:
            token_errors.append('Invalid Token.')

    if token_errors:
        errors['email_token'] = token_errors

    if email_errors or token_errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)



    try:
        token = Token.objects.get(user=user)
    except Token.DoesNotExist:
        token = Token.objects.create(user=user)

    user.is_active = True
    user.email_verified = True
    user.save()

    artist = Artist.objects.get(user=user)

    data["user_id"] = user.user_id
    data["artist_id"] = artist.artist_id

    data["email"] = user.email
    data["first_name"] = user.first_name
    data["last_name"] = user.last_name
    data["photo"] = user.photo.url
    data["token"] = token.key
    data["country"] = user.country
    data["phone"] = user.phone
    data["next_step"] = artist.onboarding_step

    
    if artist.profile_completed == True:
        data["profile_completed"] = artist.profile_completed
    else:
        data["profile_completed"] = artist.profile_completed


    payload['message'] = "Successful"
    payload['data'] = data

    new_activity = AllActivity.objects.create(
        user=user,
        subject="Verify Email",
        body=user.email + " just verified their email",
    )
    new_activity.save()

    return Response(payload, status=status.HTTP_200_OK)







def check_email_exist(email):

    qs = User.objects.filter(email=email)
    if qs.exists():
        return True
    else:
        return False




class ArtistLogin(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get('email', '').lower()
        password = request.data.get('password', '')
        fcm_token = request.data.get('fcm_token', '')
        payload = {}
        errors = {}

        if not email:
            errors['email'] = ['Email is required.']
        if not password:
            errors['password'] = ['Password is required.']
        if not fcm_token:
            errors['fcm_token'] = ['FCM token is required.']

        if errors:
            return Response({'message': 'Errors', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(email=email, password=password)

        if not user:
            return Response({'message': 'Errors', 'errors': {'email': ['Invalid credentials']}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            artist = Artist.objects.get(user=user)
        except Artist.DoesNotExist:
            return Response({'message': 'Errors', 'errors': {'email': ['User is not an artist']}}, status=status.HTTP_400_BAD_REQUEST)

        if not user.email_verified:
            return Response({'message': 'Errors', 'errors': {'email': ['Please check your email to confirm your account or resend confirmation email.']}}, status=status.HTTP_400_BAD_REQUEST)

        # Token and FCM token
        token, _ = Token.objects.get_or_create(user=user)
        user.fcm_token = fcm_token
        user.save()

        # Do not override stored onboarding_step here.
        # It is updated by completion endpoints or explicit skip actions.
        artist.save()

        data = {
            "user_id": user.user_id,
            "artist_id": artist.artist_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "photo": user.photo.url if getattr(user.photo, 'url', None) else None,
            "country": user.country,
            "phone": user.phone,
            "token": token.key,
            "onboarding_step": artist.onboarding_step,
        }

        AllActivity.objects.create(user=user, subject="Artist Login", body=f"{user.email} just logged in.")

        return Response({'message': 'Successful', 'data': data}, status=status.HTTP_200_OK)


def check_password(email, password):

    try:
        user = User.objects.get(email=email)
        return user.check_password(password)
    except User.DoesNotExist:
        return False




from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status
import json

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_artist_profile_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    bio = request.data.get('bio', "")
    country = request.data.get('country', "")
    region = request.data.get('region', "")
    photo = request.FILES.get('photo')

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Apply changes if provided
    if bio:
        artist.bio = bio
    if country:
        artist.country = country
    if region:
        artist.region = region
    if photo:
        artist.user.photo = photo
    
    artist.user.save()

    # Mark this step as complete
    artist.profile_completed = True

    # Move to next onboarding step
    artist.onboarding_step = artist.get_next_onboarding_step()
    artist.save()

    data["artist_id"] = artist.artist_id
    data["next_step"] = artist.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def skip_artist_onboarding_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    step = request.data.get('step', "")

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']
    if not step:
        errors['step'] = ['Target step is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']
        artist = None

    if artist and step not in dict(Artist.ONBOARDING_STEPS).keys():
        errors['step'] = ['Invalid onboarding step.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Update only the pointer for where to resume onboarding.
    artist.onboarding_step = step
    artist.save()

    data["artist_id"] = artist.artist_id
    data["next_step"] = artist.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_artist_social_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    facebook = request.data.get('facebook', "")
    twitter = request.data.get('twitter', "")
    instagram = request.data.get('instagram', "")
    youtube = request.data.get('youtube', "")

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Apply changes if provided
    if facebook:
        artist.facebook = facebook
    if twitter:
        artist.twitter = twitter
    if instagram:
        artist.instagram = instagram
    if youtube:
        artist.youtube = youtube

    # Mark this step as complete
    artist.social_media_added = True

    # Move to next onboarding step
    artist.onboarding_step = artist.get_next_onboarding_step()
    artist.save()

    data["artist_id"] = artist.artist_id
    data["next_step"] = artist.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_artist_payment_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    momo = request.data.get('momo', "")
    bankAccount = request.data.get('bankAccount', "")

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Apply changes if provided
    if momo:
        artist.momo_account = momo
    if bankAccount:
        artist.bank_account = bankAccount

    # Mark this step as complete
    artist.payment_info_added = True

    # Move to next onboarding step
    artist.onboarding_step = artist.get_next_onboarding_step()
    artist.save()

    data["artist_id"] = artist.artist_id
    data["next_step"] = artist.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_artist_publisher_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    publisher_id = request.data.get('publisher_id', "")
    self_publish_raw = request.data.get('self_publish', "")
    # Coerce common truthy string forms to boolean
    truthy = {True, 'true', 'True', '1', 1, 'on', 'yes', 'Yes'}
    falsy = {False, 'false', 'False', '0', 0, 'off', 'no', 'No', None, ''}
    self_publish = True if self_publish_raw in truthy else False if self_publish_raw in falsy else bool(self_publish_raw)

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Apply changes
    if self_publish is True:
        artist.self_publish = True
        # Clear any previously set publisher if switching to self-publish
        artist.publisher = None
    else:
        artist.self_publish = False
        if publisher_id:
            try:
                publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
                artist.publisher = publisher
            except PublisherProfile.DoesNotExist:
                errors['publisher_id'] = ['Publisher not found.']

        if errors:
            payload['message'] = "Errors"
            payload['errors'] = errors
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            
    # Mark this step as complete
    artist.publisher_added = True

    # Move to next onboarding step
    artist.onboarding_step = artist.get_next_onboarding_step()
    artist.save()

    data["artist_id"] = artist.artist_id
    data["next_step"] = artist.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)








@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def onboard_artist_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fields_to_update = [
        'name', 'stage_name', 'bio', 'profile_image', 'spotify_url',
        'shazam_url', 'instagram', 'twitter', 'website', 'contact_email', 'active'
    ]
    for field in fields_to_update:
        value = request.data.get(field)
        if value is not None:
            setattr(artist, field, value)

    artist.save()


    # Check if fields are not null to complete profile
    if not artist.name or not artist.stage_name or not artist.bio or not artist.profile_image:
        errors['profile'] = ['Please complete your profile.']
    if not artist.spotify_url or not artist.shazam_url:
        errors['links'] = ['Please provide your Spotify and Shazam links.'] 
    if not artist.instagram or not artist.twitter:
        errors['social'] = ['Please provide your Instagram and Twitter links.']
    if not artist.contact_email:
        errors['contact_email'] = ['Contact email is required.']
    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    artist.profile_completed = True
    artist.save()

    
    data["user_id"] = artist.user.user_id
    data["email"] = artist.user.email
    data["artist_id"] = artist.artist_id
    data["name"] = artist.stage_name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def logout_artist_view(request):
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    

    new_activity = AllActivity.objects.create(
        user=artist.user,
        type="Authentication",
        subject="Artist Log out",
        body=artist.user.email + " Just logged out of the account."
    )
    new_activity.save()

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





# Enhanced Artist Onboarding API Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def artist_onboarding_status_view(request, artist_id):
    """Get current onboarding status for an artist"""
    payload = {}
    data = {}
    errors = {}

    try:
        artist = Artist.objects.get(artist_id=artist_id, user=request.user)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found or access denied.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_404_NOT_FOUND)

    # Get user KYC status
    user = artist.user
    
    data = {
        "artist_id": artist.artist_id,
        "onboarding_step": artist.onboarding_step,
        "profile_completed": artist.profile_completed,
        "social_media_added": artist.social_media_added,
        "payment_info_added": artist.payment_info_added,
        "publisher_added": artist.publisher_added,
        "track_uploaded": artist.track_uploaded,
        "kyc_status": user.kyc_status,
        "kyc_documents": user.kyc_documents,
        "self_published": artist.self_published,
        "publisher_relationship_status": artist.publisher_relationship_status,
        "royalty_collection_method": artist.royalty_collection_method,
        "profile_complete_percentage": calculate_profile_completion_percentage(artist),
        "next_recommended_step": get_next_recommended_step(artist),
        "required_fields": get_required_fields_status(artist),
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def update_onboarding_status_view(request):
    """Update specific onboarding step status"""
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    step = request.data.get('step', "")
    completed = request.data.get('completed', False)

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']
    if not step:
        errors['step'] = ['Step is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id, user=request.user)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found or access denied.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Update the specific step status
    step_mapping = {
        'profile': 'profile_completed',
        'social-media': 'social_media_added',
        'payment': 'payment_info_added',
        'publisher': 'publisher_added',
        'track': 'track_uploaded',
    }

    if step in step_mapping:
        setattr(artist, step_mapping[step], completed)
        if completed:
            artist.onboarding_step = artist.get_next_onboarding_step()
        artist.save()

    data = {
        "artist_id": artist.artist_id,
        "step": step,
        "completed": completed,
        "next_step": artist.onboarding_step,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_artist_onboarding_view(request):
    """Mark artist onboarding as complete and set self-published status"""
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id, user=request.user)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found or access denied.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Mark onboarding as complete
    artist.onboarding_step = 'done'
    
    # Ensure self-published status is set correctly
    if not artist.publisher:
        artist.self_published = True
        artist.royalty_collection_method = 'direct'
        artist.publisher_relationship_status = 'independent'
    
    artist.save()

    # Update user profile completion status
    user = artist.user
    user.profile_complete = True
    user.save()

    data = {
        "artist_id": artist.artist_id,
        "onboarding_complete": True,
        "self_published": artist.self_published,
        "royalty_collection_method": artist.royalty_collection_method,
        "publisher_relationship_status": artist.publisher_relationship_status,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def set_self_published_status_view(request):
    """Explicitly set artist self-published status"""
    payload = {}
    data = {}
    errors = {}

    artist_id = request.data.get('artist_id', "")
    self_published = request.data.get('self_published', True)

    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    try:
        artist = Artist.objects.get(artist_id=artist_id, user=request.user)
    except Artist.DoesNotExist:
        errors['artist_id'] = ['Artist not found or access denied.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Update self-published status and related fields
    artist.update_publisher_relationship(
        publisher=None if self_published else artist.publisher,
        relationship_type='independent' if self_published else 'signed'
    )

    data = {
        "artist_id": artist.artist_id,
        "self_published": artist.self_published,
        "royalty_collection_method": artist.royalty_collection_method,
        "publisher_relationship_status": artist.publisher_relationship_status,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def upload_kyc_documents_view(request):
    """Upload KYC documents for verification"""
    from django.utils import timezone
    
    payload = {}
    data = {}
    errors = {}

    user = request.user
    document_type = request.data.get('document_type', '')
    document_file = request.FILES.get('document_file')

    if not document_type:
        errors['document_type'] = ['Document type is required.']
    if not document_file:
        errors['document_file'] = ['Document file is required.']

    valid_document_types = ['id_card', 'passport', 'drivers_license', 'utility_bill', 'bank_statement']
    if document_type not in valid_document_types:
        errors['document_type'] = [f'Invalid document type. Must be one of: {", ".join(valid_document_types)}']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Initialize kyc_documents if not exists
    if not user.kyc_documents:
        user.kyc_documents = {}

    # Store document information
    user.kyc_documents[document_type] = {
        'filename': document_file.name,
        'size': document_file.size,
        'uploaded_at': timezone.now().isoformat(),
        'status': 'uploaded'
    }

    # Update KYC status
    if user.kyc_status == 'pending':
        user.kyc_status = 'incomplete'

    user.save()

    # Here you would typically save the file to storage
    # For now, we'll just track the metadata

    data = {
        "document_type": document_type,
        "status": "uploaded",
        "kyc_status": user.kyc_status,
        "kyc_documents": user.kyc_documents,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


def calculate_profile_completion_percentage(artist):
    """Calculate profile completion percentage"""
    total_fields = 6  # profile, social, payment, publisher, kyc, track
    completed_fields = 0

    if artist.profile_completed:
        completed_fields += 1
    if artist.social_media_added:
        completed_fields += 1
    if artist.payment_info_added:
        completed_fields += 1
    if artist.publisher_added or artist.self_published:
        completed_fields += 1
    if artist.user.kyc_status in ['verified', 'uploaded']:
        completed_fields += 1
    if artist.track_uploaded:
        completed_fields += 1

    return round((completed_fields / total_fields) * 100)


def get_next_recommended_step(artist):
    """Get the next recommended step for the artist"""
    if not artist.profile_completed:
        return 'profile'
    elif artist.user.kyc_status == 'pending':
        return 'kyc'
    elif not artist.social_media_added:
        return 'social-media'
    elif not artist.payment_info_added:
        return 'payment'
    elif not artist.publisher_added and not artist.self_published:
        return 'publisher'
    elif not artist.track_uploaded:
        return 'track'
    return 'done'


def get_required_fields_status(artist):
    """Get status of required fields for profile completion"""
    user = artist.user
    
    return {
        'basic_info': {
            'completed': bool(user.first_name and user.last_name and artist.stage_name),
            'fields': ['first_name', 'last_name', 'stage_name']
        },
        'profile_details': {
            'completed': bool(artist.bio and artist.country and user.photo),
            'fields': ['bio', 'country', 'photo']
        },
        'contact_info': {
            'completed': bool(user.email and user.phone),
            'fields': ['email', 'phone']
        },
        'kyc_verification': {
            'completed': user.kyc_status in ['verified', 'uploaded'],
            'status': user.kyc_status,
            'required_documents': ['id_card', 'utility_bill']
        },
        'payment_info': {
            'completed': bool(artist.momo_account or artist.bank_account),
            'fields': ['momo_account', 'bank_account']
        }
    }
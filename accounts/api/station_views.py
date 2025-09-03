from decimal import Decimal
from django.core.mail import send_mail

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response

from accounts.api.serializers import UserRegistrationSerializer
from activities.models import AllActivity
from django.core.mail import send_mail
from django.contrib.auth import get_user_model, authenticate


from rest_framework.views import APIView

from accounts.api.serializers import UserRegistrationSerializer
from activities.models import AllActivity
from bank_account.models import BankAccount
from stations.models import Station, StationStaff, ROLE_CHOICES
from core.utils import generate_email_token, is_valid_email, is_valid_password


User = get_user_model()



@api_view(['POST', ])
@permission_classes([])
@authentication_classes([])
def register_station_view(request):

    payload = {}
    data = {}
    errors = {}

    if request.method == 'POST':
        email = request.data.get('email', "").lower()
        first_name = request.data.get('first_name', "")
        last_name = request.data.get('last_name', "")
        station_name = request.data.get('station_name', "")
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

        if not station_name:
            errors['station_name'] = ['Staion Name is required.']

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
        if serializer.is_valid():
            user = serializer.save()
            data["user_id"] = user.user_id
            data["email"] = user.email
            data["first_name"] = user.first_name
            data["last_name"] = user.last_name
            data["photo"] = user.photo

            if country:
                data["country"] = user.country


            user.user_type = "Station"
            user.phone = phone

            user.save()

            station_profile = Station.objects.create(
                user=user,
                name=station_name

            )
            station_profile.save()

            account = BankAccount.objects.get_or_create(
                user=user, 
                balance=Decimal('0.00'),
                currency="Ghc"
            )


            data['phone'] = user.phone
            data['country'] = user.country
            data['photo'] = user.photo.url

        token = Token.objects.get(user=user).key
        data['token'] = token

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
def verify_station_email(request):
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

    station = Station.objects.get(user=user)

    data["user_id"] = user.user_id
    data["station_id"] = station.station_id

    data["email"] = user.email
    data["first_name"] = user.first_name
    data["last_name"] = user.last_name
    data["photo"] = user.photo.url
    data["token"] = token.key
    data["country"] = user.country
    data["phone"] = user.phone
    data["next_step"] = station.onboarding_step

    
    if station.profile_completed == True:
        data["profile_completed"] = station.profile_completed
    else:
        data["profile_completed"] = station.profile_completed


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



class StationLogin(APIView):
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
            station = Station.objects.get(user=user)
        except Station.DoesNotExist:
            return Response({'message': 'Errors', 'errors': {'email': ['User is not an station']}}, status=status.HTTP_400_BAD_REQUEST)

        if not user.email_verified:
            return Response({'message': 'Errors', 'errors': {'email': ['Please check your email to confirm your account or resend confirmation email.']}}, status=status.HTTP_400_BAD_REQUEST)

        # Token and FCM token
        token, _ = Token.objects.get_or_create(user=user)
        user.fcm_token = fcm_token
        user.save()

        # Align stored onboarding_step with computed next step, but never regress.
        try:
            step_order = ['profile', 'staff', 'report', 'payment', 'done']
            computed = station.get_next_onboarding_step()
            cur_idx = step_order.index(station.onboarding_step) if station.onboarding_step in step_order else 0
            cmp_idx = step_order.index(computed) if computed in step_order else 0
            new_step = step_order[max(cur_idx, cmp_idx)]
            if new_step != station.onboarding_step:
                station.onboarding_step = new_step
                station.save()
        except Exception:
            station.save()

        data = {
            "user_id": user.user_id,
            "station_id": station.station_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "photo": user.photo.url if user.photo else None,
            "country": user.country,
            "phone": user.phone,
            "token": token.key,
            "onboarding_step": station.onboarding_step,
        }

        AllActivity.objects.create(user=user, subject="Station Login", body=f"{user.email} just logged in.")

        return Response({'message': 'Successful', 'data': data}, status=status.HTTP_200_OK)



def check_password(email, password):

    try:
        user = User.objects.get(email=email)
        return user.check_password(password)
    except User.DoesNotExist:
        return False





from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_station_profile_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.data.get('station_id', "")
    bio = request.data.get('bio', "")
    country = request.data.get('country', "")
    region = request.data.get('region', "")
    photo = request.data.get('photo', "")

    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Apply changes if provided
    if bio:
        station.bio = bio
    if country:
        station.country = country
    if region:
        station.region = region
    if photo:
        station.photo = photo

    # Mark this step as complete (profile)
    station.profile_completed = True

    # Move to next onboarding step
    station.onboarding_step = station.get_next_onboarding_step()
    station.save()

    data["station_id"] = station.station_id
    data["next_step"] = station.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_add_staff_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.data.get('station_id', "")
    staff_payload = request.data.get('staff', [])

    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Normalize staff payload (allow JSON string or list)
    import json
    if isinstance(staff_payload, str):
        try:
            staff_payload = json.loads(staff_payload)
        except Exception:
            staff_payload = []

    if not isinstance(staff_payload, list):
        staff_payload = []

    # Validate and collect staff entries
    valid_roles = [c[0] for c in ROLE_CHOICES]
    to_create = []
    for item in staff_payload:
        try:
            name = (item.get('name') or '').strip()
            email = (item.get('email') or '').strip() or None
            role = (item.get('role') or '').strip()
        except AttributeError:
            continue
        if not name or role not in valid_roles:
            continue
        to_create.append(StationStaff(station=station, name=name, email=email, role=role))

    if to_create:
        StationStaff.objects.bulk_create(to_create)

    # Mark this step as complete when at least one entry is present; otherwise keep current state
    if to_create:
        station.staff_completed = True

    # Move to next onboarding step
    station.onboarding_step = station.get_next_onboarding_step()
    station.save()

    data["station_id"] = station.station_id
    data["next_step"] = station.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_report_method_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.data.get('station_id', "")
    bio = request.data.get('bio', "")
    country = request.data.get('country', "")
    region = request.data.get('region', "")
    photo = request.data.get('photo', "")

    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Apply changes if provided
    if bio:
        station.bio = bio
    if country:
        station.country = country
    if region:
        station.region = region
    if photo:
        station.photo = photo

    # Mark this step as complete (report method)
    station.report_completed = True

    # Move to next onboarding step
    station.onboarding_step = station.get_next_onboarding_step()
    station.save()

    data["station_id"] = station.station_id
    data["next_step"] = station.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def onboard_station_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.data.get('station_id', "")
    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station'] = ['Station not found.']

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
            setattr(station, field, value)

    station.save()

    # Check if fields are not null to complete profile
    profile_fields = [
        'name', 'photo', 'phone', 'country', 'region',
        'location_name', 'lat', 'lng', 'about'
    ]
    profile_complete = all(getattr(station, field) is not None for field in profile_fields)
    station.profile_completed = profile_complete
    station.save()

    data["station_id"] = station.id
    data["name"] = station.name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complete_station_payment_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.data.get('station_id', "")
    momo = request.data.get('momo', "")
    bankAccount = request.data.get('bankAccount', "")

    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Apply changes if provided
    if momo:
        station.momo_account = momo
    if bankAccount:
        station.bank_account = bankAccount

    # Mark this step as complete
    station.payment_info_added = True

    # Move to next onboarding step
    station.onboarding_step = station.get_next_onboarding_step()
    station.save()

    data["station_id"] = station.station_id
    data["next_step"] = station.onboarding_step

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def logout_station_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.data.get('station_id', "")
    if not station_id:
        errors['station_id'] = ['Station ID is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    

    new_activity = AllActivity.objects.create(
        user=station.user,
        type="Authentication",
        subject="Station Log out",
        body=station.user.email + " Just logged out of the account."
    )
    new_activity.save()

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def skip_station_onboarding_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.data.get('station_id', "")
    step = request.data.get('step', "")

    if not station_id:
        errors['station_id'] = ['Station ID is required.']
    if not step:
        errors['step'] = ['Target step is required.']

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station_id'] = ['Station not found.']
        station = None

    if station and step not in dict(Station.ONBOARDING_STEPS).keys():
        errors['step'] = ['Invalid onboarding step.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    station.onboarding_step = step
    station.save()

    data['station_id'] = station.station_id
    data['next_step'] = station.onboarding_step

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def station_onboarding_status_view(request):
    payload = {}
    data = {}
    errors = {}

    station_id = request.query_params.get('station_id', "")
    if not station_id:
        errors['station_id'] = ['Station ID is required.']
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        payload['message'] = 'Errors'
        payload['errors'] = {'station_id': ['Station not found.']}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    data['station_id'] = station.station_id
    data['onboarding_step'] = station.onboarding_step
    data['profile_completed'] = station.profile_completed
    data['staff_completed'] = station.staff_completed
    data['report_completed'] = station.report_completed
    data['payment_info_added'] = station.payment_info_added

    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


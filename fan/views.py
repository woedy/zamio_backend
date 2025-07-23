
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fan.models import Fan

User = get_user_model()



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_fan(request):
    payload = {}
    data = {}
    errors = {}

    user_id = request.data.get('user_id', "")
    name = request.data.get('name', "")
    stage_name = request.data.get('stage_name', "")
    bio = request.data.get('bio', "")
    profile_image = request.data.get('profile_image', "")
    spotify_url = request.data.get('spotify_url', "")
    shazam_url = request.data.get('shazam_url', "")
    instagram = request.data.get('instagram', "")
    twitter = request.data.get('twitter', "")
    website = request.data.get('website', "")
    contact_email = request.data.get('contact_email', "")

    if not name:
        errors['name'] = ['Fan name is required.']

    try:
        user = User.objects.get(user_id=user_id)
    except:
        errors['user_id'] = ['User ID does not exist.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fan = Fan.objects.create(
        user=user,
        name=name,
        stage_name=stage_name,
        bio=bio,
        profile_image=profile_image,
        spotify_url=spotify_url,
        shazam_url=shazam_url,
        instagram=instagram,
        twitter=twitter,
        website=website,
        contact_email=contact_email,
  
    )

    data["fan_id"] = fan.fan_id
    data["name"] = fan.name
    data["stage_name"] = fan.stage_name

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_fans_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_fans = Fan.objects.filter(is_archived=False)

    if search_query:
        all_fans = all_fans.filter(
            Q(username__icontains=search_query)
        )

    paginator = Paginator(all_fans, page_size)
    try:
        paginated_fans = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_fans = paginator.page(1)
    except EmptyPage:
        paginated_fans = paginator.page(paginator.num_pages)

    from .serializers import AllFansSerializer 
    serializer = AllFansSerializer(paginated_fans, many=True)

    data['fans'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_fans.number,
        'total_pages': paginator.num_pages,
        'next': paginated_fans.next_page_number() if paginated_fans.has_next() else None,
        'previous': paginated_fans.previous_page_number() if paginated_fans.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)






@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_fan_details_view(request):
    payload = {}
    data = {}
    errors = {}

    fan_id = request.query_params.get('fan_id')

    if not fan_id:
        errors['fan_id'] = ["Fan ID is required"]

    try:
        fan = Fan.objects.get(fan_id=fan_id)
    except Fan.DoesNotExist:
        errors['fan_id'] = ['Fan does not exist']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import FanSerializer
    serializer = FanSerializer(fan)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)






@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_fan(request):
    payload = {}
    data = {}
    errors = {}

    fan_id = request.data.get('fan_id', "")
    if not fan_id:
        errors['fan_id'] = ['Fan ID is required.']

    try:
        fan = Fan.objects.get(fan_id=fan_id)
    except Fan.DoesNotExist:
        errors['fan'] = ['Fan not found.']

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
            setattr(fan, field, value)

    fan.save()

    data["fan_id"] = fan.id
    data["name"] = fan.name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_fan(request):
    payload = {}
    errors = {}

    fan_id = request.data.get('fan_id')
    if not fan_id:
        errors['fan_id'] = ['Fan ID is required.']

    try:
        fan = Fan.objects.get(fan_id=fan_id)
    except Fan.DoesNotExist:
        errors['fan'] = ['Fan not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fan.is_archived = True
    fan.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_fan(request):
    payload = {}
    errors = {}

    fan_id = request.data.get('fan_id')
    if not fan_id:
        errors['fan_id'] = ['Fan ID is required.']

    try:
        fan = Fan.objects.get(fan_id=fan_id)
    except Fan.DoesNotExist:
        errors['fan'] = ['Fan not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fan.is_archived = False
    fan.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_fan(request):
    payload = {}
    errors = {}

    fan_id = request.data.get('fan_id')
    if not fan_id:
        errors['fan_id'] = ['Fan ID is required.']

    try:
        fan = Fan.objects.get(id=fan_id)
    except Fan.DoesNotExist:
        errors['fan'] = ['Fan not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fan.delete()
    payload['message'] = "Deleted successfully"
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_fans_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_fans = Fan.objects.filter(is_archived=True)

    if search_query:
        all_fans = all_fans.filter(
            Q(name__icontains=search_query) |
            Q(stage_name__icontains=search_query) |
            Q(bio__icontains=search_query)
        )

    paginator = Paginator(all_fans, page_size)
    try:
        paginated_fans = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_fans = paginator.page(1)
    except EmptyPage:
        paginated_fans = paginator.page(paginator.num_pages)

    from ..serializers import FanSerializer  # Make sure you have this
    serializer = FanSerializer(paginated_fans, many=True)

    data['fans'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_fans.number,
        'total_pages': paginator.num_pages,
        'next': paginated_fans.next_page_number() if paginated_fans.has_next() else None,
        'previous': paginated_fans.previous_page_number() if paginated_fans.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)



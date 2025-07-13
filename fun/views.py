
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fun.models import Fun

User = get_user_model()



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_fun(request):
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
        errors['name'] = ['Fun name is required.']

    try:
        user = User.objects.get(user_id=user_id)
    except:
        errors['user_id'] = ['User ID does not exist.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fun = Fun.objects.create(
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

    data["fun_id"] = fun.fun_id
    data["name"] = fun.name
    data["stage_name"] = fun.stage_name

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_201_CREATED)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_funs_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_funs = Fun.objects.filter(is_archived=False)

    if search_query:
        all_funs = all_funs.filter(
            Q(name__icontains=search_query) |
            Q(stage_name__icontains=search_query) |
            Q(bio__icontains=search_query)
        )

    paginator = Paginator(all_funs, page_size)
    try:
        paginated_funs = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_funs = paginator.page(1)
    except EmptyPage:
        paginated_funs = paginator.page(paginator.num_pages)

    from ..serializers import AllFunsSerializer 
    serializer = AllFunsSerializer(paginated_funs, many=True)

    data['funs'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_funs.number,
        'total_pages': paginator.num_pages,
        'next': paginated_funs.next_page_number() if paginated_funs.has_next() else None,
        'previous': paginated_funs.previous_page_number() if paginated_funs.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)






@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_fun_details_view(request):
    payload = {}
    data = {}
    errors = {}

    fun_id = request.query_params.get('fun_id')

    if not fun_id:
        errors['fun_id'] = ["Fun ID is required"]

    try:
        fun = Fun.objects.get(fun_id=fun_id)
    except Fun.DoesNotExist:
        errors['fun_id'] = ['Fun does not exist']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import FunSerializer
    serializer = FunSerializer(fun)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)






@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_fun(request):
    payload = {}
    data = {}
    errors = {}

    fun_id = request.data.get('fun_id', "")
    if not fun_id:
        errors['fun_id'] = ['Fun ID is required.']

    try:
        fun = Fun.objects.get(fun_id=fun_id)
    except Fun.DoesNotExist:
        errors['fun'] = ['Fun not found.']

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
            setattr(fun, field, value)

    fun.save()

    data["fun_id"] = fun.id
    data["name"] = fun.name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_fun(request):
    payload = {}
    errors = {}

    fun_id = request.data.get('fun_id')
    if not fun_id:
        errors['fun_id'] = ['Fun ID is required.']

    try:
        fun = Fun.objects.get(fun_id=fun_id)
    except Fun.DoesNotExist:
        errors['fun'] = ['Fun not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fun.is_archived = True
    fun.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_fun(request):
    payload = {}
    errors = {}

    fun_id = request.data.get('fun_id')
    if not fun_id:
        errors['fun_id'] = ['Fun ID is required.']

    try:
        fun = Fun.objects.get(fun_id=fun_id)
    except Fun.DoesNotExist:
        errors['fun'] = ['Fun not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fun.is_archived = False
    fun.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_fun(request):
    payload = {}
    errors = {}

    fun_id = request.data.get('fun_id')
    if not fun_id:
        errors['fun_id'] = ['Fun ID is required.']

    try:
        fun = Fun.objects.get(id=fun_id)
    except Fun.DoesNotExist:
        errors['fun'] = ['Fun not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    fun.delete()
    payload['message'] = "Deleted successfully"
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_funs_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_funs = Fun.objects.filter(is_archived=True)

    if search_query:
        all_funs = all_funs.filter(
            Q(name__icontains=search_query) |
            Q(stage_name__icontains=search_query) |
            Q(bio__icontains=search_query)
        )

    paginator = Paginator(all_funs, page_size)
    try:
        paginated_funs = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_funs = paginator.page(1)
    except EmptyPage:
        paginated_funs = paginator.page(paginator.num_pages)

    from ..serializers import FunSerializer  # Make sure you have this
    serializer = FunSerializer(paginated_funs, many=True)

    data['funs'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_funs.number,
        'total_pages': paginator.num_pages,
        'next': paginated_funs.next_page_number() if paginated_funs.has_next() else None,
        'previous': paginated_funs.previous_page_number() if paginated_funs.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)



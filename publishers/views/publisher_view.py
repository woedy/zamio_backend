
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from bank_account.models import BankAccount
from core.utils import get_duration
from music_monitor.models import PlayLog, StreamLog
from publishers.models import PublisherProfile

User = get_user_model()



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def add_publisher(request):
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
        errors['name'] = ['PublisherProfile name is required.']

    try:
        user = User.objects.get(user_id=user_id)
    except:
        errors['user_id'] = ['User ID does not exist.']


    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    publisher = PublisherProfile.objects.create(
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


    data["publisher_id"] = publisher.publisher_id
    data["name"] = publisher.name
    data["stage_name"] = publisher.stage_name

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_201_CREATED)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_publishers_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_publishers = PublisherProfile.objects.filter(is_archived=False)

    if search_query:
        all_publishers = all_publishers.filter(
            Q(stage_name__icontains=search_query) |
            Q(bio__icontains=search_query)
        )

    paginator = Paginator(all_publishers, page_size)
    try:
        paginated_publishers = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_publishers = paginator.page(1)
    except EmptyPage:
        paginated_publishers = paginator.page(paginator.num_pages)

    from ..serializers import AllPublisherProfilesSerializer 
    serializer = AllPublisherProfilesSerializer(paginated_publishers, many=True)

    data['publishers'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_publishers.number,
        'total_pages': paginator.num_pages,
        'next': paginated_publishers.next_page_number() if paginated_publishers.has_next() else None,
        'previous': paginated_publishers.previous_page_number() if paginated_publishers.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)






@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_publisher_details_view(request):
    payload = {}
    data = {}
    errors = {}

    publisher_id = request.query_params.get('publisher_id')

    if not publisher_id:
        errors['publisher_id'] = ["PublisherProfile ID is required"]

    try:
        publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
    except PublisherProfile.DoesNotExist:
        errors['publisher_id'] = ['PublisherProfile does not exist']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    from ..serializers import PublisherProfileSerializer
    serializer = PublisherProfileSerializer(publisher)

    payload['message'] = "Successful"
    payload['data'] = serializer.data
    return Response(payload, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_publisher(request):
    payload = {}
    data = {}
    errors = {}

    publisher_id = request.data.get('publisher_id', "")
    if not publisher_id:
        errors['publisher_id'] = ['PublisherProfile ID is required.']

    try:
        publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
    except PublisherProfile.DoesNotExist:
        errors['publisher'] = ['PublisherProfile not found.']

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
            setattr(publisher, field, value)

    publisher.save()

    data["publisher_id"] = publisher.id
    data["name"] = publisher.name

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def archive_publisher(request):
    payload = {}
    errors = {}

    publisher_id = request.data.get('publisher_id')
    if not publisher_id:
        errors['publisher_id'] = ['PublisherProfile ID is required.']

    try:
        publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
    except PublisherProfile.DoesNotExist:
        errors['publisher'] = ['PublisherProfile not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    publisher.is_archived = True
    publisher.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def unarchive_publisher(request):
    payload = {}
    errors = {}

    publisher_id = request.data.get('publisher_id')
    if not publisher_id:
        errors['publisher_id'] = ['PublisherProfile ID is required.']

    try:
        publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
    except PublisherProfile.DoesNotExist:
        errors['publisher'] = ['PublisherProfile not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    publisher.is_archived = False
    publisher.save()

    payload['message'] = "Successful"
    return Response(payload)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def delete_publisher(request):
    payload = {}
    errors = {}

    publisher_id = request.data.get('publisher_id')
    if not publisher_id:
        errors['publisher_id'] = ['PublisherProfile ID is required.']

    try:
        publisher = PublisherProfile.objects.get(id=publisher_id)
    except PublisherProfile.DoesNotExist:
        errors['publisher'] = ['PublisherProfile not found.']

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    publisher.delete()
    payload['message'] = "Deleted successfully"
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_archived_publishers_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_publishers = PublisherProfile.objects.filter(is_archived=True)

    if search_query:
        all_publishers = all_publishers.filter(
            Q(name__icontains=search_query) |
            Q(stage_name__icontains=search_query) |
            Q(bio__icontains=search_query)
        )

    paginator = Paginator(all_publishers, page_size)
    try:
        paginated_publishers = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_publishers = paginator.page(1)
    except EmptyPage:
        paginated_publishers = paginator.page(paginator.num_pages)

    from ..serializers import PublisherProfileSerializer  # Make sure you have this
    serializer = PublisherProfileSerializer(paginated_publishers, many=True)

    data['publishers'] = serializer.data
    data['pagination'] = {
        'page_number': paginated_publishers.number,
        'total_pages': paginator.num_pages,
        'next': paginated_publishers.next_page_number() if paginated_publishers.has_next() else None,
        'previous': paginated_publishers.previous_page_number() if paginated_publishers.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)






from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from django.db.models import Sum, Count, Q, F

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_publisher_profile_view(request):
    payload, data, errors = {}, {}, {}

    publisher_id = request.query_params.get('publisher_id')
    if not publisher_id:
        errors['publisher_id'] = ["PublisherProfile ID is required"]
    else:
        try:
            publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
        except PublisherProfile.DoesNotExist:
            errors['publisher_id'] = ["PublisherProfile does not exist"]

    if errors:
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    tracks = Track.objects.filter(publisher=publisher, is_archived=False)

    # PublisherProfile info
    publisherData = {
        "name": f"{publisher.user.first_name or ''} {publisher.user.last_name or ''}".strip(),
        "stageName": publisher.stage_name,
        "bio": publisher.bio,
        "avatar": publisher.user.photo.url if publisher.user.photo else None,
        "coverImage": None,
        "verified": publisher.verified,
        "followers": publisher.followers.count(),
        "totalPlays": PlayLog.objects.filter(track__in=tracks).count() + StreamLog.objects.filter(track__in=tracks).count(),
        "totalEarnings": float(BankAccount.objects.filter(user=publisher.user).aggregate(Sum('balance'))['balance__sum'] or 0),
        "joinDate": publisher.created_at.date().isoformat(),
        "location": publisher.location_name or f"{publisher.city}, {publisher.country}" if hasattr(publisher, 'country') else "",
        "genres": list(publisher.publisher_genre.filter(is_archived=False).values_list('genre__name', flat=True).distinct()),
        "contact": {
            "email": publisher.contact_email,
            "phone": publisher.user.phone,
            "instagram": publisher.instagram,
            "twitter": publisher.twitter,
            "facebook": None,
        }
    }

    # Songs list
    songs = []
    for t in tracks:
        plays_count = PlayLog.objects.filter(track=t).count() + StreamLog.objects.filter(track=t).count()
        earnings = (PlayLog.objects.filter(track=t).aggregate(Sum('royalty_amount'))['royalty_amount__sum'] or 0) + \
                   (StreamLog.objects.filter(track=t).aggregate(Sum('royalty_amount'))['royalty_amount__sum'] or 0)
        contributors = Contributor.objects.filter(track=t, is_archived=False)
        songs.append({
            "id": t.id,
            "title": t.title,
            "duration": str(t.duration) if t.duration else None,
            "releaseDate": t.release_date.isoformat() if t.release_date else None,
            "totalPlays": plays_count,
            "totalEarnings": float(earnings),
            "status": "Active" if t.active else "Inactive",
            "album": t.album.title if t.album else None,
            "genre": t.genre.name if t.genre else None,
            "contributors": [{"name": c.name, "role": c.role, "percentage": float(c.percent_split)} for c in contributors],
            "recentPlays": [
                {
                    "station": log.station.name,
                    "date": log.played_at.strftime("%Y-%m-%d"),
                    "plays": 1,
                    "earnings": float(log.royalty_amount or 0)
                }
                for log in PlayLog.objects.filter(track=t).order_by('-played_at')[:3]
            ]
        })

    # Royalty history (mix of radio & streaming with status via transaction or claimed flag)
    radio_logs = PlayLog.objects.filter(track__in=tracks).order_by('-played_at')[:10]
    streaming_logs = StreamLog.objects.filter(track__in=tracks).order_by('-played_at')[:10]
    royaltyHistory = []
    for log in radio_logs:
        royaltyHistory.append({
            "date": log.played_at.strftime("%Y-%m-%d"),
            "amount": float(log.royalty_amount or 0),
            "source": "Radio Airplay",
            "status": "Paid" if log.claimed else "Pending"
        })
    for log in streaming_logs:
        royaltyHistory.append({
            "date": log.played_at.strftime("%Y-%m-%d"),
            "amount": float(log.royalty_amount or 0),
            "source": "Streaming",
            "status": "Paid" if log.claimed else "Pending"
        })
    royaltyHistory = sorted(royaltyHistory, key=lambda x: x['date'], reverse=True)[:10]

    # Recent play logs combined
    playlogs_qs = PlayLog.objects.filter(track__in=tracks).order_by('-played_at')[:5]
    playLogs = [
        {
            "id": log.id,
            "song": log.track.title,
            "station": log.station.name,
            "date": log.played_at.strftime("%Y-%m-%d %H:%M"),
            "duration": str(get_duration(log.duration)) if log.duration else None,
            "confidence": float(log.avg_confidence_score or 0),
            "earnings": float(log.royalty_amount or 0)
        } for log in playlogs_qs
    ]

    data.update({
        "publisherData": publisherData,
        "songs": songs,
        "royaltyHistory": royaltyHistory,
        "playLogs": playLogs
    })

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

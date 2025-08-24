from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from publishers.models import PublisherProfile
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.custom_jwt import CustomJWTAuthentication
from artists.models import Artist
from notifications.api.serializers import AllNotificationsSerializer
from notifications.models import Notification

from rest_framework.authentication import TokenAuthentication

from stations.models import Station



@api_view(['POST', ])
@permission_classes([IsAuthenticated, ])
@authentication_classes([CustomJWTAuthentication, ])
def set_notification_to_read(request):
    payload = {}
    data = {}
    errors = {}

    if request.method == 'POST':
        notification_id = request.data.get('notification_id', "")


        if not notification_id:
            errors['notification_id'] = ['Notification ID is required.']



        try:
            notification = Notification.objects.get(id=notification_id)
        except:
            errors['notification_id'] = ['Notification does not exist.']


        if errors:
            payload['message'] = "Errors"
            payload['errors'] = errors
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)


        notification.read = True
        notification.save()

        payload['message'] = "Successful"
        payload['data'] = data

    return Response(payload)




@api_view(['GET', ])
@permission_classes([IsAuthenticated, ])
@authentication_classes([CustomJWTAuthentication, ])
def get_all_notifications(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '')
    filter_department = request.query_params.get('filter_department', '')
    page_number = request.query_params.get('page', 1)
    page_size = 10

    all_notification = Notification.objects.all().order_by('-created_at')


    if search_query:
        all_notification = all_notification.filter(
            Q(department__icontains=search_query)
        )

    if filter_department:
        all_notification = all_notification.filter(
            department__icontains=filter_department
        )


    paginator = Paginator(all_notification, page_size)

    try:
        paginated_notification = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_notification = paginator.page(1)
    except EmptyPage:
        paginated_notification = paginator.page(paginator.num_pages)

    all_notifications_serializer = AllNotificationsSerializer(paginated_notification, many=True)


    data['notifications'] = all_notifications_serializer.data
    data['pagination'] = {
        'page_number': paginated_notification.number,
        'total_pages': paginator.num_pages,
        'next': paginated_notification.next_page_number() if paginated_notification.has_next() else None,
        'previous': paginated_notification.previous_page_number() if paginated_notification.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data

    return Response(payload, status=status.HTTP_200_OK)



@api_view(['POST', ])
@permission_classes([IsAuthenticated, ])
@authentication_classes([CustomJWTAuthentication, ])
def delete_notification(request):
    payload = {}
    data = {}
    errors = {}

    if request.method == 'POST':
        notification_id = request.data.get('notification_id', "")

        if not notification_id:
            errors['notification_id'] = ['Notification ID is required.']

        try:
            notification = Notification.objects.get(id=notification_id)
        except:
            errors['notification_id'] = ['Notification does not exist.']

        if errors:
            payload['message'] = "Errors"
            payload['errors'] = errors
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        notification.delete()


        payload['message'] = "Successful"
        payload['data'] = data

    return Response(payload)


from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from datetime import timezone

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_artist_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    artist_id = request.query_params.get('artist_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        artist = Artist.objects.get(artist_id=artist_id)
    except Artist.DoesNotExist:
        errors['artist'] = ['Artist not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=artist.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_publisher_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    publisher_id = request.query_params.get('publisher_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        publisher = PublisherProfile.objects.get(publisher_id=publisher_id)
    except PublisherProfile.DoesNotExist:
        errors['station'] = ['PublisherProfile not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=publisher.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def get_all_station_notifications_view(request):
    payload = {}
    data = {}
    errors = {}

    search_query = request.query_params.get('search', '').strip()
    page_number = int(request.query_params.get('page', 1))
    station_id = request.query_params.get('station_id', '')
    order_by = request.query_params.get('order_by', '')
    page_size = 10

    # Step 1: Validate artist
    try:
        station = Station.objects.get(station_id=station_id)
    except Station.DoesNotExist:
        errors['station'] = ['Station not found.']
        payload['message'] = "Errors"
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    # Step 2: Fetch notifications
    notifications_qs = Notification.objects.filter(
        user=station.user,
        is_archived=False
    )

    # Step 3: Search filter
    if search_query:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    # Step 4: Ordering
    if order_by:
        order_map = {
            "Title": "title",
            "Newest": "-created_at",
            "Oldest": "created_at",
            "Type": "type"
        }
        notifications_qs = notifications_qs.order_by(order_map.get(order_by, "-created_at"))
    else:
        notifications_qs = notifications_qs.order_by("-created_at")

    # Step 5: Paginate
    paginator = Paginator(notifications_qs, page_size)
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    # Step 6: Format data
    from django.utils.timesince import timesince
    formatted_notifications = []
    for notification in page.object_list:
        formatted_notifications.append({
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "timestamp": timesince(notification.created_at) + " ago" if notification.created_at else "Just now"
        })

    data['notifications'] = formatted_notifications
    data['pagination'] = {
        'page_number': page.number,
        'total_pages': paginator.num_pages,
        'next': page.next_page_number() if page.has_next() else None,
        'previous': page.previous_page_number() if page.has_previous() else None,
    }

    payload['message'] = "Successful"
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)

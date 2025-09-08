from django.contrib.auth import get_user_model
from django.db.models import Q
from django.template.loader import get_template
from django.conf import settings
from django.core.mail import send_mail

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from artists.models import Artist, ArtistInvitation
from publishers.models import PublisherProfile

User = get_user_model()


def _get_publisher_for_user(user: User) -> PublisherProfile:
    try:
        return PublisherProfile.objects.get(user=user)
    except PublisherProfile.DoesNotExist:
        return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def search_artists_to_link_view(request):
    payload, data, errors = {}, {}, {}

    q = request.query_params.get('q', '').strip()

    publisher = _get_publisher_for_user(request.user)
    if not publisher:
        errors['publisher'] = ['Publisher profile not found for user.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    qs = Artist.objects.filter(is_archived=False)
    if q:
        qs = qs.filter(
            Q(stage_name__icontains=q) |
            Q(contact_email__icontains=q) |
            Q(user__email__icontains=q)
        )

    results = []
    for a in qs.order_by('stage_name')[:25]:
        linked_publisher = getattr(a, 'publisher', None)
        results.append({
            'artist_id': a.artist_id,
            'stage_name': a.stage_name,
            'contact_email': a.contact_email,
            'user_email': getattr(getattr(a, 'user', None), 'email', None),
            'linked': bool(linked_publisher is not None),
            'linked_to_you': bool(linked_publisher and linked_publisher == publisher),
            'linked_publisher': getattr(linked_publisher, 'company_name', None) if linked_publisher else None,
        })

    data['results'] = results
    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def link_artist_to_publisher_view(request):
    payload, data, errors = {}, {}, {}

    artist_id = request.data.get('artist_id', '').strip()
    if not artist_id:
        errors['artist_id'] = ['Artist ID is required.']

    publisher = _get_publisher_for_user(request.user)
    if not publisher:
        errors['publisher'] = ['Publisher profile not found for user.']

    artist = None
    if artist_id:
        try:
            artist = Artist.objects.get(artist_id=artist_id)
        except Artist.DoesNotExist:
            errors['artist_id'] = ['Artist does not exist.']

    if artist and artist.publisher and artist.publisher != publisher:
        errors['artist'] = ['Artist is already linked to another publisher.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    artist.publisher = publisher
    artist.publisher_added = True
    artist.save()

    data['artist_id'] = artist.artist_id
    data['stage_name'] = artist.stage_name
    data['linked_to'] = publisher.company_name or publisher.user.email
    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def link_multiple_artists_view(request):
    payload, data, errors = {}, {}, {}

    artist_ids = request.data.get('artist_ids') or []
    if not isinstance(artist_ids, list) or not artist_ids:
        errors['artist_ids'] = ['List of artist IDs is required.']

    publisher = _get_publisher_for_user(request.user)
    if not publisher:
        errors['publisher'] = ['Publisher profile not found for user.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    linked, skipped = [], []
    from artists.models import Artist
    for aid in artist_ids:
        try:
            a = Artist.objects.get(artist_id=str(aid))
        except Artist.DoesNotExist:
            skipped.append({'artist_id': aid, 'reason': 'not_found'})
            continue
        if a.publisher and a.publisher != publisher:
            skipped.append({'artist_id': aid, 'reason': 'linked_elsewhere'})
            continue
        a.publisher = publisher
        a.publisher_added = True
        a.save()
        linked.append(a.artist_id)

    data['linked'] = linked
    data['skipped'] = skipped
    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def invite_artist_view(request):
    payload, data, errors = {}, {}, {}

    email = request.data.get('email', '').strip().lower()
    emails = request.data.get('emails')  # optional list
    stage_name = request.data.get('stage_name', '').strip()

    if not email and not emails:
        errors['email'] = ['Email or emails list is required.']

    publisher = _get_publisher_for_user(request.user)
    if not publisher:
        errors['publisher'] = ['Publisher profile not found for user.']

    if errors:
        payload['message'] = 'Errors'
        payload['errors'] = errors
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    sent = []
    created = []
    to_send = []
    if emails and isinstance(emails, list):
        to_send = [str(e).strip().lower() for e in emails if str(e).strip()]
    elif email:
        to_send = [email]

    subject = 'Invitation to join Zamio as an Artist'
    from_email = settings.DEFAULT_FROM_EMAIL
    display_name = publisher.company_name or f"{publisher.user.first_name} {publisher.user.last_name}".strip() or publisher.user.email

    for em in to_send:
        invite = ArtistInvitation.objects.create(
            invited_by=publisher,
            email=em,
            stage_name=stage_name or None,
            status='pending',
        )
        context = {
            'publisher_name': display_name,
            'stage_name': stage_name or '',
            'invite_token': str(invite.token),
        }
        txt_ = get_template('registration/emails/invite_artist.txt').render(context)
        html_ = get_template('registration/emails/invite_artist.html').render(context)
        send_mail(
            subject,
            txt_,
            from_email,
            [em],
            html_message=html_,
            fail_silently=False,
        )
        created.append({'email': em, 'token': str(invite.token)})
        sent.append(em)

    data['invited'] = created
    payload['message'] = 'Successful'
    payload['data'] = data
    return Response(payload, status=status.HTTP_201_CREATED)

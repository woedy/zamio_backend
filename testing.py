from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view

import os
from django.conf import settings
from django.db import transaction

from accounts.api.artist_views import is_valid_email, check_email_exist
from artists.models import Album

class DeleteAlbumView:
    def post(self, request):
        payload = {}
        errors = {}

        album_id = request.data.get('album_id', "")

        if not album_id:
            errors['album_id'] = ['Album ID is required.']
        elif not is_valid_email(album_id):
            errors['album_id'] = ['Invalid album ID']

        try:
            album = Album.objects.get(id=album_id)
        except Album.DoesNotExist:
            errors['album'] = ['Album not found.']
        except Exception as e:
            errors['album'] = [f'Unknown error: {e}']

        if errors:
            payload['message'] = "Errors"
            payload['errors'] = errors
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        @transaction.atomic
        def delete_album():
            try:
                album.delete()
            except Exception as e:
                # Roll back the transaction and log the error
                print(f"Error deleting album: {e}")
                raise

        delete_album()

        data = {'message': 'Deleted successfully'}

        payload['data'] = data
        return Response(payload, status=HTTP_200_OK)
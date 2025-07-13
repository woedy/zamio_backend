


from music_monitor.models import PlayLog


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_play_logs(request, station_id):
    logs = PlayLog.objects.filter(station_id=station_id).order_by('-played_at')[:100]
    data = [{
        'track_title': log.track.title,
        'artist_name': log.track.artist.name,
        'played_at': log.played_at,
        'duration': log.duration.total_seconds() if log.duration else None,
        'source': log.source,
        'royalty_amount': str(log.royalty_amount) if log.royalty_amount else "0.00"
    } for log in logs]
    return Response(data)
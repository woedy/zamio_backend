import threading
import subprocess
import librosa
import numpy as np
import io
import uuid
import time
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from collections import Counter

from artists.models import Fingerprint, Track
from music_monitor.models import MatchCache
from music_monitor.utils.match_engine import simple_match
from stations.models import Station

# Global dictionary to store active monitoring sessions
active_sessions = {}

class StreamMonitor:
    def __init__(self, session_id, stream_url, station_id):
        self.session_id = session_id
        self.stream_url = stream_url
        self.station_id = station_id
        self.is_running = False
        self.matches = []
        self.thread = None
        
    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_stream)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
            
    def _monitor_stream(self):
        """Main monitoring loop"""
        buffer_duration = 30  # seconds
        overlap = 10  # seconds
        
        while self.is_running:
            try:
                # Capture audio chunk
                audio_data = self._capture_audio_chunk(buffer_duration)
                if audio_data:
                    # Process and match
                    self._process_audio_chunk(audio_data)
                    
                # Wait before next capture (considering overlap)
                time.sleep(buffer_duration - overlap)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Wait before retrying
                
    def _capture_audio_chunk(self, duration):
        """Capture audio from stream using ffmpeg"""
        try:
            cmd = [
                'ffmpeg',
                '-i', self.stream_url,
                '-f', 'wav',
                '-ar', '44100',
                '-ac', '1',  # mono
                '-t', str(duration),
                '-'
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            audio_data, error = process.communicate()
            
            if process.returncode == 0:
                return audio_data
            else:
                print(f"FFmpeg error: {error.decode()}")
                return None
                
        except Exception as e:
            print(f"Audio capture error: {e}")
            return None
            
    def _process_audio_chunk(self, audio_data):
        """Process audio chunk and find matches"""
        try:
            # Load audio data
            samples, sr = librosa.load(io.BytesIO(audio_data), sr=44100)
            
            if len(samples) == 0:
                return
                
            # Get all fingerprints from database for matching
            all_fingerprints = self._get_all_fingerprints()
            
            # Perform matching
            match_result = simple_match(samples, sr, all_fingerprints)
            
            if match_result["match"]:
                # Log the match
                self._log_match(match_result)
                
        except Exception as e:
            print(f"Audio processing error: {e}")
            
    def _get_all_fingerprints(self):
        """Get all fingerprints from database"""
        fingerprints = []
        for fp in Fingerprint.objects.select_related('track').all():
            fingerprints.append((fp.track.id, fp.hash, fp.offset))
        return fingerprints
        
    def _log_match(self, match_result):
        """Log match to database and add to recent matches"""
        try:
            track = Track.objects.get(id=match_result["song_id"])
            station = Station.objects.get(id=self.station_id)
            
            # Create match cache entry
            match_cache = MatchCache.objects.create(
                track=track,
                station=station,
                station_program=None,  # You might want to determine this
                matched_at=timezone.now()
            )
            
            # Add to recent matches for frontend
            match_info = {
                'track_title': track.title,
                'artist_name': track.artist.name,
                'album_title': track.album.title if track.album else None,
                'matched_at': match_cache.matched_at.isoformat(),
                'confidence': min(100, (match_result["hashes_matched"] / 20) * 100),  # Simple confidence calc
                'hashes_matched': match_result["hashes_matched"]
            }
            
            # Keep only last 50 matches
            self.matches.append(match_info)
            if len(self.matches) > 50:
                self.matches = self.matches[-50:]
                
            print(f"Match found: {track.title} by {track.artist.name}")
            
        except Exception as e:
            print(f"Error logging match: {e}")




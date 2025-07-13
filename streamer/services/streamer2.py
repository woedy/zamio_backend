# streamer/services/streamer.py
import ffmpeg
import tempfile
from streamer.tasks import match_audio_clip

def capture_and_match_loop(url, station_name, station_id):
    while True:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            temp_path = temp_audio.name

        try:
            ffmpeg.input(url, t=10).output(
                temp_path, format='wav', acodec='pcm_s16le', ac=1, ar='44100'
            ).overwrite_output().run(quiet=True)

            match_audio_clip.delay(temp_path, station_id)

        except Exception as e:
            print(f"Stream error for {station_name}: {e}")

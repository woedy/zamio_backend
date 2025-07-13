""" from django.core.management.base import BaseCommand
from streamer.services.streamer import record_segment
import time

STREAM_URL = "https://mmg.streamguys1.com/JoyFM-mp3?key=63d8990dfe4438ae984fd70d2d2b4bd31c842c474987bd810ac0e8e0fd62e8cf2015661105cced63ccfdca89a8422ab1"  # e.g. Citi FM
STATION_NAME = "CitiFM"

class Command(BaseCommand):
    help = "Continuously records and slices a radio stream"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS(f"Starting stream capture for {STATION_NAME}"))
        
        try:
            while True:
                out_file = record_segment(STREAM_URL, STATION_NAME)
                print(f"[✓] Saved: {out_file}")
                time.sleep(1)  # 1 sec buffer before next segment
        except KeyboardInterrupt:
            print("Stream capture stopped.")
 """



from django.core.management.base import BaseCommand
import ffmpeg
import os
from datetime import datetime

STREAM_URL = "https://mmg.streamguys1.com/JoyFM-mp3?key=63d8990dfe4438ae984fd70d2d2b4bd31c842c474987bd810ac0e8e0fd62e8cf2015661105cced63ccfdca89a8422ab1"
STATION_NAME = "JoyFM"
SEGMENT_DURATION = 20  # seconds
OUTPUT_DIR = f"recordings/{STATION_NAME}"  # customize folder path

class Command(BaseCommand):
    help = "Continuously records a radio stream into timestamped 10s audio chunks"

    def handle(self, *args, **kwargs):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self.stdout.write(self.style.SUCCESS(f"🎙️ Starting periodic stream capture for {STATION_NAME}"))

        try:
            while True:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                out_filename = f"{STATION_NAME}_{timestamp}.wav"
                out_path = os.path.join(OUTPUT_DIR, out_filename)

                try:
                    (
                        ffmpeg
                        .input(STREAM_URL, t=SEGMENT_DURATION)
                        .output(out_path, format='wav', acodec='pcm_s16le', ar='44100', ac=1)
                        .overwrite_output()
                        .run(quiet=True)
                    )

                    print(f"[✓] Saved chunk: {out_path}")

                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"⚠️ Error capturing chunk: {e}"))

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("⏹️ Stream capture stopped by user."))

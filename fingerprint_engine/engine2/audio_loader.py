from pydub import AudioSegment
import numpy as np

def load_audio(filepath):
    audio = AudioSegment.from_file(filepath).set_channels(1).set_frame_rate(44100)
    samples = np.array(audio.get_array_of_samples())
    return samples

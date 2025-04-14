import numpy as np

def load_audio(filename):
    audio = AudioSegment.from_file(filename).set_channels(1).set_frame_rate(44100)
    samples = np.array(audio.get_array_of_samples())
    return samples


def get_spectrogram(samples, window_size=4096, hop_size=2048):
    spectrogram = []
    for i in range(0, len(samples) - window_size, hop_size):
        window = samples[i:i+window_size] * np.hanning(window_size)
        spectrum = np.abs(np.fft.fft(window))[:window_size//2]
        spectrogram.append(spectrum)
    return np.array(spectrogram)



def get_peaks(spectrogram, threshold=10):
    peaks = []
    for t, spectrum in enumerate(spectrogram):
        for f in range(1, len(spectrum) - 1):
            if spectrum[f] > threshold and spectrum[f] > spectrum[f - 1] and spectrum[f] > spectrum[f + 1]:
                peaks.append((t, f))
    return peaks



import hashlib

def generate_hashes(peaks, fan_value=5):
    hashes = []
    for i in range(len(peaks)):
        for j in range(1, fan_value):
            if i + j < len(peaks):
                t1, f1 = peaks[i]
                t2, f2 = peaks[i + j]
                t_delta = t2 - t1
                if 0 < t_delta <= 200:
                    h = hashlib.sha1(f"{f1}|{f2}|{t_delta}".encode()).hexdigest()[0:20]
                    hashes.append((h, t1))
    return hashes

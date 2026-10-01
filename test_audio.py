import sounddevice as sd
import numpy as np

print("Testing microphone... Speak something for 3 seconds.")
duration = 3  # seconds
fs = 16000
audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
sd.wait()
print("Recording finished! If you reached this line, sounddevice works fine.")
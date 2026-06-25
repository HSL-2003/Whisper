import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure ffmpeg is in path
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

from transcriber import WhisperXTranscriber
from downloader import TEMP_DIR

# Create a dummy WAV file
import numpy as np
import struct

def make_dummy_wav(path, duration=3):
    sample_rate = 16000
    num_samples = sample_rate * duration
    samples = [0] * num_samples
    data_size = num_samples * 2
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))
        f.write(struct.pack("<H", 2))
        f.write(struct.pack("<H", 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        for s in samples:
            f.write(struct.pack("<h", s))

wav_path = str(TEMP_DIR / "dummy_test.wav")
make_dummy_wav(wav_path)

print("Initializing transcriber...")
hf_token = os.getenv("HF_TOKEN")
print(f"HF Token length: {len(hf_token) if hf_token else 0}")

t = WhisperXTranscriber(
    model_name="tiny",
    device="cpu",
    compute_type="float32",
    hf_token=hf_token
)

def progress(p, m):
    print(f"[{p}%] {m}")

try:
    res = t.transcribe(wav_path, progress_callback=progress, enable_diarization=True)
    print("TRANSCRIPTION SUCCESS:")
    import pprint
    pprint.pprint(res)
except Exception as e:
    print("EXCEPTION OCCURRED:")
    import traceback
    traceback.print_exc()
finally:
    if os.path.exists(wav_path):
        os.remove(wav_path)

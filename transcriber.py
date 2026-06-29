"""
WhisperX-style Transcriber Module
Uses faster-whisper directly for ASR + torchaudio for alignment.
Compatible with Python 3.14+.
"""

import gc
import os
import subprocess
import warnings
from typing import Optional, Callable

import numpy as np

warnings.filterwarnings("ignore")

ProgressCallback = Callable[[float, str], None]

SAMPLE_RATE = 16000


def load_audio(file_path: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Load audio file to numpy array using ffmpeg."""
    cmd = [
        "ffmpeg", "-nostdin", "-threads", "0", "-i", file_path,
        "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le",
        "-ar", str(sr), "-"
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")
    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0


class WhisperXTranscriber:
    """
    Transcription pipeline using faster-whisper with word timestamps.
    Provides WhisperX-equivalent functionality without the Python version constraint.
    """

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        batch_size: int = 4,
        hf_token: Optional[str] = None,
        max_speakers: int = 15,
        language: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.batch_size = batch_size
        self.hf_token = hf_token
        self.max_speakers = max_speakers
        self.language = language
        self._model = None
        self._diarize_pipeline = None

    def _get_model(self):
        """Lazy-load the faster-whisper model."""
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[ProgressCallback] = None,
        enable_diarization: bool = True,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        hf_token: Optional[str] = None,
    ) -> dict:
        """Run the full transcription pipeline."""
        if max_speakers is None:
            max_speakers = self.max_speakers

        def _p(pct, msg):
            if progress_callback:
                progress_callback(pct, msg)

        _p(28, "Loading audio file...")

        # ── Step 1: Transcribe with faster-whisper ──────────────
        _p(32, f"Loading ASR model ({self.model_name})...")
        model = self._get_model()

        _p(38, "Transcribing audio (this may take a while on CPU)...")

        segments_gen, info = model.transcribe(
            audio_path,
            beam_size=5,
            language=self.language,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=1000,
                speech_pad_ms=400,
            ),
            condition_on_previous_text=False,
        )

        detected_language = info.language or "en"
        _p(42, f"Language detected: {detected_language}. Processing segments...")

        # Collect and refine segments using word-level timestamps to guarantee exact seconds/minutes
        segments = []
        raw_segments = list(segments_gen)
        total = len(raw_segments) if raw_segments else 1

        for i, segment in enumerate(raw_segments):
            pct = 42 + (i / total) * 33  # 42% -> 75%
            _p(pct, f"Processing segment {i+1}/{total}...")

            if not segment.words:
                segments.append({
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "text": segment.text.strip(),
                    "words": [],
                })
                continue

            # Convert segment words to dictionaries and interpolate missing timestamps
            seg_start = segment.start if segment.start is not None else 0.0
            seg_end = segment.end if segment.end is not None else seg_start + 1.0

            words_list = []
            for w in segment.words:
                words_list.append({
                    "word": str(w.word or "").strip(),
                    "start": w.start,
                    "end": w.end,
                    "probability": round(w.probability, 3) if w.probability is not None else 0.0,
                })

            # Interpolate missing starts/ends
            n_words = len(words_list)
            i_word = 0
            while i_word < n_words:
                if words_list[i_word]["start"] is None or words_list[i_word]["end"] is None:
                    # Find consecutive missing segment
                    start_idx = i_word
                    while i_word < n_words and (words_list[i_word]["start"] is None or words_list[i_word]["end"] is None):
                        i_word += 1
                    end_idx = i_word  # exclusive boundary of missing group

                    # Determine boundaries
                    left_time = seg_start
                    if start_idx > 0:
                        # Find closest preceding word with valid end
                        for prev_i in range(start_idx - 1, -1, -1):
                            if words_list[prev_i]["end"] is not None:
                                left_time = words_list[prev_i]["end"]
                                break

                    right_time = seg_end
                    if end_idx < n_words:
                        # Find closest succeeding word with valid start
                        for next_i in range(end_idx, n_words):
                            if words_list[next_i]["start"] is not None:
                                right_time = words_list[next_i]["start"]
                                break

                    if left_time > right_time:
                        left_time = right_time

                    # Distribute intervals
                    count = end_idx - start_idx
                    duration = right_time - left_time
                    if duration <= 0:
                        for k in range(start_idx, end_idx):
                            words_list[k]["start"] = left_time
                            words_list[k]["end"] = left_time
                    else:
                        slot = duration / count
                        for idx, k in enumerate(range(start_idx, end_idx)):
                            words_list[k]["start"] = round(left_time + idx * slot, 3)
                            words_list[k]["end"] = round(left_time + (idx + 1) * slot, 3)
                else:
                    i_word += 1

            # Split segment by silent gaps to prevent lyrics stretching over long instrumentals
            current_sub_words = []
            max_gap_seconds = 1.5

            for word_data in words_list:
                # Ensure values are rounded properly
                word_data["start"] = round(word_data["start"], 3)
                word_data["end"] = round(word_data["end"], 3)

                if not current_sub_words:
                    current_sub_words.append(word_data)
                else:
                    prev_word = current_sub_words[-1]
                    if word_data["start"] - prev_word["end"] > max_gap_seconds:
                        sub_text = " ".join([wd["word"] for wd in current_sub_words]).strip()
                        if sub_text:
                            segments.append({
                                "start": current_sub_words[0]["start"],
                                "end": current_sub_words[-1]["end"],
                                "text": sub_text,
                                "words": current_sub_words,
                            })
                        current_sub_words = [word_data]
                    else:
                        current_sub_words.append(word_data)

            if current_sub_words:
                sub_text = " ".join([wd["word"] for wd in current_sub_words]).strip()
                if sub_text:
                    segments.append({
                        "start": current_sub_words[0]["start"],
                        "end": current_sub_words[-1]["end"],
                        "text": sub_text,
                        "words": current_sub_words,
                    })

        _p(75, f"Transcription complete: {len(segments)} segments.")

        result = {"segments": segments, "language": detected_language}

        # ── Step 2: Speaker Diarization (optional) ──────────────
        run_token = hf_token or self.hf_token
        if enable_diarization and run_token:
            _p(78, "Loading diarization model (pyannote)...")
            try:
                result = self._run_diarization(
                    audio_path, result, min_speakers, max_speakers, _p, hf_token=run_token
                )
            except Exception as e:
                err_msg = str(e)
                result["diarization_error"] = err_msg
                _p(96, f"Diarization warning: {err_msg[:100]}...")
        else:
            reason = "No HF token" if not run_token else "Disabled by user"
            _p(96, f"Diarization skipped: {reason}")

        _p(100, "Processing complete!")
        return result

    def _run_diarization(self, audio_path, result, min_speakers, max_speakers, _p, hf_token):
        """Run pyannote speaker diarization and assign speakers to segments."""
        import torch
        from pyannote.audio import Pipeline

        # Re-initialize pipeline if token changes or not yet initialized
        if self._diarize_pipeline is None or hf_token != getattr(self, "_last_hf_token", None):
            self._diarize_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=hf_token,
            )
            self._last_hf_token = hf_token
            if self.device == "cuda":
                self._diarize_pipeline = self._diarize_pipeline.to(torch.device("cuda"))

        _p(82, f"Identifying speakers (max {max_speakers})...")

        # Load audio for pyannote
        audio = load_audio(audio_path)
        audio_tensor = torch.from_numpy(audio[None, :])

        diarize_result = self._diarize_pipeline(
            {"waveform": audio_tensor, "sample_rate": SAMPLE_RATE},
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        if hasattr(diarize_result, "speaker_diarization"):
            diarize_result = diarize_result.speaker_diarization

        _p(92, "Assigning speakers to segments...")

        # Build diarization intervals
        diarize_intervals = []
        for turn, _, speaker in diarize_result.itertracks(yield_label=True):
            diarize_intervals.append((turn.start, turn.end, speaker))

        # Assign speakers to segments
        speakers_found = set()
        for seg in result["segments"]:
            speaker = self._find_speaker(
                seg["start"], seg["end"], diarize_intervals
            )
            seg["speaker"] = speaker
            speakers_found.add(speaker)

            # Assign speakers to words too
            for word in seg.get("words", []):
                if "start" in word and "end" in word:
                    word["speaker"] = self._find_speaker(
                        word["start"], word["end"], diarize_intervals
                    )

        _p(96, f"Found {len(speakers_found)} speakers.")
        return result

    @staticmethod
    def _find_speaker(start, end, intervals):
        """Find the dominant speaker for a time range."""
        speaker_durations = {}
        for iv_start, iv_end, speaker in intervals:
            # Check overlap
            overlap_start = max(start, iv_start)
            overlap_end = min(end, iv_end)
            if overlap_start < overlap_end:
                duration = overlap_end - overlap_start
                speaker_durations[speaker] = speaker_durations.get(speaker, 0) + duration

        if speaker_durations:
            return max(speaker_durations, key=speaker_durations.get)
        return "UNKNOWN"

    def cleanup(self):
        """Free model memory and empty PyTorch CUDA cache."""
        self._model = None
        self._diarize_pipeline = None
        self._last_hf_token = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

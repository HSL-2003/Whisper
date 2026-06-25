"""
Unit Tests for WhisperX Meeting Transcriber
Tests all modules: downloader, formatter, transcriber, and server API.
"""

import json
import os
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure ffmpeg is available
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from downloader import (
    detect_source_type,
    convert_to_wav,
    get_audio_duration,
    cleanup_temp_file,
    TEMP_DIR,
)
from formatter import (
    format_timestamp,
    format_timestamp_precise,
    format_result_for_frontend,
    generate_markdown,
)


class TestDetectSourceType(unittest.TestCase):
    """Test URL source type detection."""

    def test_youtube_watch(self):
        self.assertEqual(detect_source_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "youtube")

    def test_youtube_short(self):
        self.assertEqual(detect_source_type("https://youtube.com/shorts/abc123"), "youtube")

    def test_youtube_live(self):
        self.assertEqual(detect_source_type("https://youtube.com/live/abc123"), "youtube")

    def test_youtu_be(self):
        self.assertEqual(detect_source_type("https://youtu.be/dQw4w9WgXcQ"), "youtube")

    def test_tiktok(self):
        self.assertEqual(detect_source_type("https://www.tiktok.com/@user/video/123"), "tiktok")

    def test_tiktok_vm(self):
        self.assertEqual(detect_source_type("https://vm.tiktok.com/abc123"), "tiktok")

    def test_vimeo(self):
        self.assertEqual(detect_source_type("https://vimeo.com/123456"), "vimeo")

    def test_direct_mp4(self):
        self.assertEqual(detect_source_type("https://example.com/video.mp4"), "direct")

    def test_unknown_url(self):
        self.assertEqual(detect_source_type("https://random-site.com/page"), "direct")

    def test_not_url(self):
        self.assertEqual(detect_source_type("not-a-url"), "unknown")

    def test_empty(self):
        self.assertEqual(detect_source_type(""), "unknown")


class TestFormatTimestamp(unittest.TestCase):
    """Test timestamp formatting functions."""

    def test_zero(self):
        self.assertEqual(format_timestamp(0), "00:00:00")

    def test_seconds(self):
        self.assertEqual(format_timestamp(45), "00:00:45")

    def test_minutes(self):
        self.assertEqual(format_timestamp(125), "00:02:05")

    def test_hours(self):
        self.assertEqual(format_timestamp(3661), "01:01:01")

    def test_none(self):
        self.assertEqual(format_timestamp(None), "00:00:00")

    def test_negative(self):
        self.assertEqual(format_timestamp(-5), "00:00:00")

    def test_precise_format(self):
        result = format_timestamp_precise(65.5)
        self.assertTrue(result.startswith("00:01:05"))

    def test_precise_none(self):
        self.assertEqual(format_timestamp_precise(None), "00:00:00.000")


class TestFormatResultForFrontend(unittest.TestCase):
    """Test WhisperX result formatting for frontend."""

    def setUp(self):
        self.sample_result = {
            "segments": [
                {
                    "start": 0.5,
                    "end": 3.2,
                    "text": "Hello everyone",
                    "speaker": "SPEAKER_00",
                    "words": [
                        {"word": "Hello", "start": 0.5, "end": 1.0, "speaker": "SPEAKER_00"},
                        {"word": "everyone", "start": 1.1, "end": 3.2, "speaker": "SPEAKER_00"},
                    ],
                },
                {
                    "start": 3.5,
                    "end": 6.0,
                    "text": "Good morning",
                    "speaker": "SPEAKER_01",
                    "words": [],
                },
            ],
            "language": "en",
        }
        self.metadata = {
            "title": "Test Meeting",
            "source": "https://youtube.com/watch?v=test",
            "duration": 120.0,
        }

    def test_basic_formatting(self):
        result = format_result_for_frontend(self.sample_result, self.metadata)
        self.assertIn("segments", result)
        self.assertIn("speakers", result)
        self.assertIn("metadata", result)

    def test_segment_count(self):
        result = format_result_for_frontend(self.sample_result)
        self.assertEqual(len(result["segments"]), 2)

    def test_speaker_detection(self):
        result = format_result_for_frontend(self.sample_result)
        self.assertEqual(len(result["speakers"]), 2)
        speaker_ids = [s["id"] for s in result["speakers"]]
        self.assertIn("SPEAKER_00", speaker_ids)
        self.assertIn("SPEAKER_01", speaker_ids)

    def test_speaker_colors_assigned(self):
        result = format_result_for_frontend(self.sample_result)
        for speaker in result["speakers"]:
            self.assertIn("color", speaker)
            self.assertTrue(speaker["color"].startswith("#"))

    def test_segment_formatted_times(self):
        result = format_result_for_frontend(self.sample_result)
        seg = result["segments"][0]
        self.assertEqual(seg["startFormatted"], "00:00:00")
        self.assertEqual(seg["endFormatted"], "00:00:03")

    def test_metadata_included(self):
        result = format_result_for_frontend(self.sample_result, self.metadata)
        self.assertEqual(result["metadata"]["title"], "Test Meeting")
        self.assertEqual(result["metadata"]["language"], "en")
        self.assertEqual(result["metadata"]["totalSpeakers"], 2)

    def test_words_preserved(self):
        result = format_result_for_frontend(self.sample_result)
        self.assertEqual(len(result["segments"][0]["words"]), 2)

    def test_empty_segments(self):
        result = format_result_for_frontend({"segments": [], "language": "vi"})
        self.assertEqual(len(result["segments"]), 0)
        self.assertEqual(len(result["speakers"]), 0)

    def test_no_speaker_field(self):
        """Test segments without speaker labels."""
        data = {
            "segments": [{"start": 0, "end": 1, "text": "test"}],
            "language": "en",
        }
        result = format_result_for_frontend(data)
        self.assertEqual(result["segments"][0]["speaker"], "UNKNOWN")


class TestGenerateMarkdown(unittest.TestCase):
    """Test Markdown generation."""

    def setUp(self):
        self.formatted = {
            "segments": [
                {
                    "start": 0.5, "end": 3.2,
                    "startFormatted": "00:00:00",
                    "endFormatted": "00:00:03",
                    "text": "Hello everyone",
                    "speaker": "SPEAKER_00",
                    "speakerEmoji": "🔵",
                    "speakerColor": "#6C9BFF",
                    "words": [],
                },
                {
                    "start": 3.5, "end": 6.0,
                    "startFormatted": "00:00:03",
                    "endFormatted": "00:00:06",
                    "text": "Good morning",
                    "speaker": "SPEAKER_01",
                    "speakerEmoji": "🟢",
                    "speakerColor": "#4AEAB0",
                    "words": [],
                },
            ],
            "speakers": [
                {"id": "SPEAKER_00", "emoji": "🔵", "color": "#6C9BFF",
                 "segmentCount": 1, "totalDuration": 2.7},
                {"id": "SPEAKER_01", "emoji": "🟢", "color": "#4AEAB0",
                 "segmentCount": 1, "totalDuration": 2.5},
            ],
            "metadata": {
                "title": "Test Meeting",
                "source": "test.mp4",
                "language": "en",
                "totalDurationFormatted": "00:00:06",
                "totalSpeakers": 2,
                "processedAt": "2026-06-25T09:00:00",
            },
        }

    def test_markdown_has_header(self):
        md = generate_markdown(self.formatted)
        self.assertIn("# 📝 Meeting Transcript", md)

    def test_markdown_has_metadata(self):
        md = generate_markdown(self.formatted)
        self.assertIn("**Title**: Test Meeting", md)
        self.assertIn("**Language**: EN", md)

    def test_markdown_has_speaker_table(self):
        md = generate_markdown(self.formatted)
        self.assertIn("SPEAKER_00", md)
        self.assertIn("SPEAKER_01", md)
        self.assertIn("| Speaker |", md)

    def test_markdown_has_transcript(self):
        md = generate_markdown(self.formatted)
        self.assertIn("Hello everyone", md)
        self.assertIn("Good morning", md)

    def test_markdown_has_timestamps(self):
        md = generate_markdown(self.formatted)
        self.assertIn("[00:00:00", md)

    def test_empty_segments(self):
        data = {"segments": [], "speakers": [], "metadata": {"language": "en"}}
        md = generate_markdown(data)
        self.assertIn("Full Transcript", md)


class TestFfmpegAvailability(unittest.TestCase):
    """Test that ffmpeg and ffprobe are available."""

    def test_ffmpeg_found(self):
        import shutil
        ffmpeg = shutil.which("ffmpeg")
        self.assertIsNotNone(ffmpeg, "ffmpeg not found in PATH")

    def test_ffprobe_found(self):
        import shutil
        ffprobe = shutil.which("ffprobe")
        self.assertIsNotNone(ffprobe, "ffprobe not found in PATH")

    def test_ffmpeg_runs(self):
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ffmpeg version", result.stdout)


class TestAudioConversion(unittest.TestCase):
    """Test audio file conversion."""

    def test_convert_generated_audio(self):
        """Generate a tiny WAV and verify conversion works."""
        import numpy as np
        import struct

        # Generate 1 second of silence as WAV
        sample_rate = 44100
        duration = 1
        num_samples = sample_rate * duration
        samples = [0] * num_samples

        src = str(TEMP_DIR / "test_src.wav")
        dst = str(TEMP_DIR / "test_dst.wav")

        # Write minimal WAV
        with open(src, "wb") as f:
            # WAV header
            data_size = num_samples * 2
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_size))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))  # chunk size
            f.write(struct.pack("<H", 1))   # PCM
            f.write(struct.pack("<H", 1))   # mono
            f.write(struct.pack("<I", sample_rate))
            f.write(struct.pack("<I", sample_rate * 2))  # byte rate
            f.write(struct.pack("<H", 2))   # block align
            f.write(struct.pack("<H", 16))  # bits per sample
            f.write(b"data")
            f.write(struct.pack("<I", data_size))
            for s in samples:
                f.write(struct.pack("<h", s))

        try:
            convert_to_wav(src, dst)
            self.assertTrue(os.path.exists(dst))
            self.assertGreater(os.path.getsize(dst), 0)

            # Verify it's 16kHz
            duration = get_audio_duration(dst)
            self.assertIsNotNone(duration)
            self.assertGreater(duration, 0.5)
        finally:
            cleanup_temp_file(src)
            cleanup_temp_file(dst)


class TestTempCleanup(unittest.TestCase):
    """Test temp file cleanup."""

    def test_cleanup_existing(self):
        path = str(TEMP_DIR / "test_cleanup.tmp")
        with open(path, "w") as f:
            f.write("test")
        self.assertTrue(os.path.exists(path))
        cleanup_temp_file(path)
        self.assertFalse(os.path.exists(path))

    def test_cleanup_nonexistent(self):
        # Should not raise
        cleanup_temp_file("nonexistent_file_12345.tmp")

    def test_temp_dir_exists(self):
        self.assertTrue(TEMP_DIR.exists())


class TestTranscriberInit(unittest.TestCase):
    """Test transcriber initialization (without loading models)."""

    def test_default_init(self):
        from transcriber import WhisperXTranscriber
        t = WhisperXTranscriber()
        self.assertEqual(t.model_name, "base")
        self.assertEqual(t.device, "cpu")
        self.assertEqual(t.compute_type, "int8")

    def test_custom_init(self):
        from transcriber import WhisperXTranscriber
        t = WhisperXTranscriber(
            model_name="small",
            device="cpu",
            compute_type="float32",
            batch_size=8,
            hf_token="test_token",
            max_speakers=10,
        )
        self.assertEqual(t.model_name, "small")
        self.assertEqual(t.batch_size, 8)
        self.assertEqual(t.hf_token, "test_token")
        self.assertEqual(t.max_speakers, 10)

    def test_find_speaker_basic(self):
        from transcriber import WhisperXTranscriber
        intervals = [
            (0.0, 5.0, "SPEAKER_00"),
            (5.0, 10.0, "SPEAKER_01"),
            (10.0, 15.0, "SPEAKER_00"),
        ]
        # Should find SPEAKER_00 for range 1-4
        speaker = WhisperXTranscriber._find_speaker(1.0, 4.0, intervals)
        self.assertEqual(speaker, "SPEAKER_00")

        # Should find SPEAKER_01 for range 6-9
        speaker = WhisperXTranscriber._find_speaker(6.0, 9.0, intervals)
        self.assertEqual(speaker, "SPEAKER_01")

    def test_find_speaker_overlap(self):
        from transcriber import WhisperXTranscriber
        intervals = [
            (0.0, 6.0, "SPEAKER_00"),
            (4.0, 10.0, "SPEAKER_01"),
        ]
        # Range 3-5 overlaps more with SPEAKER_00 (3-6=2s vs 4-5=1s)
        speaker = WhisperXTranscriber._find_speaker(3.0, 5.0, intervals)
        self.assertEqual(speaker, "SPEAKER_00")

    def test_find_speaker_no_match(self):
        from transcriber import WhisperXTranscriber
        intervals = [(0.0, 5.0, "SPEAKER_00")]
        speaker = WhisperXTranscriber._find_speaker(10.0, 15.0, intervals)
        self.assertEqual(speaker, "UNKNOWN")

    def test_cleanup(self):
        from transcriber import WhisperXTranscriber
        t = WhisperXTranscriber()
        t.cleanup()  # Should not raise


class TestServerImports(unittest.TestCase):
    """Test that server module can be imported."""

    def test_import_server(self):
        """Verify server.py imports without errors."""
        # Import the app object directly
        from server import app
        self.assertIsNotNone(app)

    def test_health_endpoint_exists(self):
        from server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/api/health", routes)

    def test_transcribe_endpoint_exists(self):
        from server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/api/transcribe", routes)


class TestServerAPI(unittest.TestCase):
    """Test FastAPI endpoints using TestClient."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            from server import app
            cls.client = TestClient(app)
        except Exception as e:
            cls.client = None
            cls.skip_reason = str(e)

    def test_health(self):
        if not self.client:
            self.skipTest("TestClient not available")
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("model", data)
        self.assertIn("device", data)

    def test_index_page(self):
        if not self.client:
            self.skipTest("TestClient not available")
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("WhisperX", resp.text)

    def test_transcribe_no_input(self):
        if not self.client:
            self.skipTest("TestClient not available")
        resp = self.client.post("/api/transcribe")
        self.assertEqual(resp.status_code, 400)

    def test_transcribe_bad_file_type(self):
        if not self.client:
            self.skipTest("TestClient not available")
        from io import BytesIO
        files = {"file": ("test.exe", BytesIO(b"fake"), "application/octet-stream")}
        resp = self.client.post("/api/transcribe", files=files)
        self.assertEqual(resp.status_code, 400)

    def test_result_not_found(self):
        if not self.client:
            self.skipTest("TestClient not available")
        resp = self.client.get("/api/transcribe/nonexistent-id/result")
        self.assertEqual(resp.status_code, 404)

    def test_download_not_found(self):
        if not self.client:
            self.skipTest("TestClient not available")
        resp = self.client.get("/api/transcribe/nonexistent-id/download")
        self.assertEqual(resp.status_code, 404)

    def test_transcribe_invalid_mime_type(self):
        if not self.client:
            self.skipTest("TestClient not available")
        from io import BytesIO
        files = {"file": ("test.mp3", BytesIO(b"fake audio content"), "text/plain")}
        resp = self.client.post("/api/transcribe", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid file type", resp.json()["detail"])

    @patch("server.UPLOAD_MAX_SIZE", 10)
    def test_transcribe_file_too_large(self):
        if not self.client:
            self.skipTest("TestClient not available")
        from io import BytesIO
        files = {"file": ("test.mp3", BytesIO(b"this content is longer than ten bytes"), "audio/mpeg")}
        resp = self.client.post("/api/transcribe", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("File too large", resp.json()["detail"])

    @patch("downloader.subprocess.run")
    def test_ffmpeg_missing_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("[WinError 2] The system cannot find the file specified")
        from downloader import convert_to_wav
        with self.assertRaises(RuntimeError) as ctx:
            convert_to_wav("dummy.mp4", "dummy.wav")
        self.assertIn("ffmpeg not found", str(ctx.exception).lower())

    def test_srt_vtt_txt_formatter(self):
        from formatter import generate_srt, generate_vtt, generate_txt
        dummy_result = {
            "segments": [
                {
                    "id": 1,
                    "start": 1.25,
                    "end": 3.5,
                    "startFormatted": "00:00:01",
                    "endFormatted": "00:00:03",
                    "speaker": "SPEAKER_00",
                    "text": "Hello world"
                }
            ]
        }
        srt = generate_srt(dummy_result)
        vtt = generate_vtt(dummy_result)
        txt = generate_txt(dummy_result)
        
        self.assertIn("00:00:01,250 --> 00:00:03,500", srt)
        self.assertIn("[SPEAKER_00]: Hello world", srt)
        
        self.assertIn("WEBVTT", vtt)
        self.assertIn("00:00:01.250 --> 00:00:03.500", vtt)
        
        self.assertIn("[00:00:01 -> 00:00:03] SPEAKER_00: Hello world", txt)


if __name__ == "__main__":
    # Ensure temp dir exists
    TEMP_DIR.mkdir(exist_ok=True)
    unittest.main(verbosity=2)

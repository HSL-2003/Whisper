"""
Media Downloader Module
Downloads audio from YouTube, TikTok, Vimeo, and direct URLs using yt-dlp.
Converts media files to WAV 16kHz mono format required by WhisperX.
"""

import os
import sys
import uuid
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# Supported URL patterns
URL_PATTERNS = {
    "youtube": re.compile(
        r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)"
    ),
    "tiktok": re.compile(
        r"(https?://)?(www\.|vm\.)?tiktok\.com/"
    ),
    "vimeo": re.compile(
        r"(https?://)?(www\.)?vimeo\.com/"
    ),
    "google_drive": re.compile(
        r"(https?://)?(drive\.google\.com/)"
    ),
    "zoom": re.compile(
        r"(https?://)?([a-z0-9\-]+\.)?zoom\.us/"
    ),
}


def detect_source_type(url: str) -> str:
    """Detect the source platform from URL."""
    for platform, pattern in URL_PATTERNS.items():
        if pattern.search(url):
            return platform
    # If it looks like a URL but doesn't match known patterns
    if url.startswith(("http://", "https://")):
        return "direct"
    return "unknown"


def download_audio_from_url(url: str, progress_callback=None, cookies_path: Optional[str] = None) -> Tuple[str, dict]:
    """
    Download audio from a URL using yt-dlp.
    
    Args:
        url: The URL to download from
        progress_callback: Optional callback(percent, status_text)
        cookies_path: Optional path to cookies.txt file
    
    Returns:
        Tuple of (wav_file_path, metadata_dict)
    """
    job_id = str(uuid.uuid4())[:8]
    output_path = TEMP_DIR / f"{job_id}"
    wav_path = str(TEMP_DIR / f"{job_id}.wav")

    source_type = detect_source_type(url)
    
    if progress_callback:
        progress_callback(5, f"Detected source: {source_type}")

    # Base yt-dlp command without cookies
    # Keep safe flags like force-ipv4 and no-cache to avoid triggering DRM protection errors.
    base_cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "-f", "ba/b",
        "--no-cache-dir",
        "--no-check-certificate",
        "--impersonate", "chrome",
        "--extractor-args", "youtube:player_client=ios,android,tv,web_safari",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-4",
        "--output", str(output_path) + ".%(ext)s",
        "--no-warnings",
        url,
    ]

    if progress_callback:
        progress_callback(10, "Downloading audio stream...")

    # Pass current environment containing static-ffmpeg path
    env = os.environ.copy()
    
    success = False
    result = None
    cookie_error = None
    
    # Try 1: Custom cookies file (if uploaded by user)
    if cookies_path and os.path.exists(cookies_path):
        try:
            if progress_callback:
                progress_callback(11, "Attempting download with uploaded cookies...")
            cookie_cmd = base_cmd + ["--cookies", cookies_path]
            result = subprocess.run(
                cookie_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                env=env
            )
            if result.returncode == 0:
                success = True
            else:
                cookie_error = result.stderr
                if progress_callback:
                    progress_callback(13, f"Uploaded cookies failed, trying Chrome browser cookies...")
        except Exception as e:
            cookie_error = str(e)
            if progress_callback:
                progress_callback(13, f"Uploaded cookies error: {str(e)[:40]}")

    # Try 2: Local Chrome browser cookies
    if not success:
        try:
            if progress_callback:
                progress_callback(14, "Attempting download with Chrome browser cookies...")
            cookie_cmd = base_cmd + ["--cookies-from-browser", "chrome"]
            result = subprocess.run(
                cookie_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                env=env
            )
            if result.returncode == 0:
                success = True
        except Exception:
            pass

    # Try 3: Base command (client emulation fallback)
    if not success:
        try:
            if progress_callback:
                progress_callback(16, "Chrome cookies unavailable. Falling back to player_client emulation...")
            result = subprocess.run(
                base_cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                env=env
            )
            if result.returncode == 0:
                success = True
            else:
                err_msg = result.stderr
                if cookie_error:
                    err_msg += f"\n\n[Chi tiết lỗi Cookie upload]:\n{cookie_error}"
                raise RuntimeError(err_msg)
        except FileNotFoundError:
            raise RuntimeError(
                "yt-dlp not found. Install it with: pip install yt-dlp"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Download timed out (>10 minutes)")

    # Find the downloaded raw audio file
    downloaded_file = None
    for file in TEMP_DIR.iterdir():
        if file.stem == job_id and file.suffix != ".wav":
            downloaded_file = str(file)
            break

    if not downloaded_file:
        # Check if it was downloaded directly as wav for some reason
        direct_wav = str(output_path) + ".wav"
        if os.path.exists(direct_wav):
            downloaded_file = direct_wav
        else:
            raise RuntimeError("No audio file was downloaded")

    if progress_callback:
        progress_callback(20, "Converting downloaded stream to WAV 16kHz mono...")

    try:
        convert_to_wav(downloaded_file, wav_path)
    finally:
        # Clean up the raw file if it's different from the target WAV
        if downloaded_file != wav_path:
            cleanup_temp_file(downloaded_file)

    if progress_callback:
        progress_callback(25, "Audio downloaded and converted successfully")

    # Extract metadata
    metadata = extract_metadata(url, cookies_path=cookies_path)

    return wav_path, metadata


def convert_uploaded_file(file_path: str, progress_callback=None) -> Tuple[str, dict]:
    """
    Convert an uploaded video/audio file to WAV 16kHz mono.
    
    Args:
        file_path: Path to the uploaded file
        progress_callback: Optional callback(percent, status_text)
    
    Returns:
        Tuple of (wav_file_path, metadata_dict)
    """
    job_id = str(uuid.uuid4())[:8]
    wav_path = str(TEMP_DIR / f"{job_id}.wav")

    if progress_callback:
        progress_callback(10, "Converting audio format...")

    convert_to_wav(file_path, wav_path)

    if progress_callback:
        progress_callback(25, "Audio conversion complete")

    # Get duration
    duration = get_audio_duration(wav_path)
    metadata = {
        "title": Path(file_path).stem,
        "source": "file_upload",
        "duration": duration,
    }

    return wav_path, metadata


def convert_to_wav(input_path: str, output_path: str):
    """Convert any audio/video file to WAV 16kHz mono using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",  # overwrite
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        "-f", "wav",
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")


def get_audio_duration(wav_path: str) -> Optional[float]:
    """Get audio duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            wav_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def extract_metadata(url: str, cookies_path: Optional[str] = None) -> dict:
    """Extract metadata from URL using yt-dlp."""
    base_cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-download",
        "--no-cache-dir",
        "--no-check-certificate",
        "--impersonate", "chrome",
        "--extractor-args", "youtube:player_client=ios,android,tv,web_safari",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-4",
        "--print", "title",
        "--print", "duration",
        "--print", "uploader",
        "--no-warnings",
        url,
    ]
    
    # Try 1: Custom cookies file (if uploaded by user)
    if cookies_path and os.path.exists(cookies_path):
        try:
            cookie_cmd = base_cmd + ["--cookies", cookies_path]
            result = subprocess.run(
                cookie_cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                return {
                    "title": lines[0] if len(lines) > 0 else "Unknown",
                    "duration": float(lines[1]) if len(lines) > 1 and lines[1].replace(".", "").isdigit() else None,
                    "uploader": lines[2] if len(lines) > 2 else "Unknown",
                    "source": url,
                }
        except Exception:
            pass

    # Try 2: Chrome cookies from browser
    try:
        cookie_cmd = base_cmd + ["--cookies-from-browser", "chrome"]
        result = subprocess.run(
            cookie_cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return {
                "title": lines[0] if len(lines) > 0 else "Unknown",
                "duration": float(lines[1]) if len(lines) > 1 and lines[1].replace(".", "").isdigit() else None,
                "uploader": lines[2] if len(lines) > 2 else "Unknown",
                "source": url,
            }
    except Exception:
        pass
        
    # Try 3: Fallback to without cookies
    try:
        result = subprocess.run(
            base_cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return {
                "title": lines[0] if len(lines) > 0 else "Unknown",
                "duration": float(lines[1]) if len(lines) > 1 and lines[1].replace(".", "").isdigit() else None,
                "uploader": lines[2] if len(lines) > 2 else "Unknown",
                "source": url,
            }
    except Exception:
        pass
    
    return {"title": "Unknown", "source": url, "duration": None}


def cleanup_temp_file(file_path: str):
    """Remove a temporary file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass

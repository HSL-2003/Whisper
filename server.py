"""
WhisperX Meeting Transcription Web Server
FastAPI backend with SSE progress streaming, file upload, and URL processing.
"""

import asyncio
import json
import os
import uuid
import threading
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from downloader import (
    download_audio_from_url,
    convert_uploaded_file,
    cleanup_temp_file,
    detect_source_type,
    TEMP_DIR,
)
from formatter import (
    format_result_for_frontend,
    generate_markdown,
    generate_srt,
    generate_vtt,
    generate_txt,
)
from transcriber import WhisperXTranscriber

# Ensure ffmpeg/ffprobe are on PATH (uses static_ffmpeg bundled binaries)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass  # ffmpeg must be installed system-wide

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
DEVICE = os.getenv("DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "int8")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "4"))
MAX_SPEAKERS = int(os.getenv("MAX_SPEAKERS", "15"))

UPLOAD_MAX_SIZE = 500 * 1024 * 1024  # 500MB

# ─── App Setup ───────────────────────────────────────────────────
app = FastAPI(
    title="WhisperX Meeting Transcriber",
    description="Transcribe meetings with speaker diarization",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# ─── Job Store ───────────────────────────────────────────────────
jobs = {}  # job_id -> job_data


class Job:
    def __init__(self, job_id: str, source: str):
        self.id = job_id
        self.source = source
        self.status = "pending"  # pending, downloading, transcribing, done, error
        self.progress = 0.0
        self.message = "Initializing..."
        self.result = None
        self.error = None
        self.created_at = time.time()
        self.events = []  # list of SSE events to send
        self._lock = threading.Lock()

    def update(self, progress: float, message: str, status: str = None):
        with self._lock:
            self.progress = progress
            self.message = message
            if status:
                self.status = status
            event = {
                "progress": round(progress, 1),
                "message": message,
                "status": self.status,
            }
            self.events.append(event)

    def complete(self, result: dict):
        with self._lock:
            self.status = "done"
            self.progress = 100
            self.message = "Complete!"
            self.result = result
            self.events.append({
                "progress": 100,
                "message": "Complete!",
                "status": "done",
                "result": result,
            })

    def fail(self, error: str):
        with self._lock:
            self.status = "error"
            self.error = error
            self.events.append({
                "progress": self.progress,
                "message": error,
                "status": "error",
                "error": error,
            })

    def get_new_events(self, after_index: int) -> list:
        with self._lock:
            return self.events[after_index:]


# ─── Transcriber Instance ───────────────────────────────────────
transcriber = WhisperXTranscriber(
    model_name=WHISPER_MODEL,
    device=DEVICE,
    compute_type=COMPUTE_TYPE,
    batch_size=BATCH_SIZE,
    hf_token=HF_TOKEN,
    max_speakers=MAX_SPEAKERS,
)

# Concurrency semaphore to prevent parallel heavy model execution causing OOM
pipeline_semaphore = threading.Semaphore(1)


# ─── Routes ─────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main HTML page."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


@app.post("/api/transcribe")
async def start_transcription(
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    max_speakers: Optional[int] = Form(None),
    enable_diarization: bool = Form(True),
    hf_token: Optional[str] = Form(None),
    cookies_file: Optional[UploadFile] = File(None),
):
    """
    Start a transcription job.
    Either provide a URL (YouTube/TikTok/Vimeo) or upload a file (MP4/MOV/MP3/WAV).
    """
    if not url and not file:
        raise HTTPException(status_code=400, detail="Provide either a URL or file")

    job_id = str(uuid.uuid4())
    source = url if url else (file.filename if file else "unknown")
    job = Job(job_id, source)
    jobs[job_id] = job

    # Handle file upload - save to temp
    uploaded_file_path = None
    if file:
        # Validate MIME / Content Type
        content_type = file.content_type or ""
        if not (content_type.startswith("audio/") or content_type.startswith("video/") or content_type == "application/octet-stream"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {content_type}. Only audio/video files are allowed."
            )

        # Validate file extension
        allowed_extensions = {".mp4", ".mov", ".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac"}
        ext = Path(file.filename or "").suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file extension: {ext}. Allowed: {', '.join(allowed_extensions)}"
            )

        uploaded_file_path = str(TEMP_DIR / f"{job_id}_upload{ext}")
        try:
            total_size = 0
            chunk_size = 1024 * 1024  # 1MB
            with open(uploaded_file_path, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > UPLOAD_MAX_SIZE:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File too large (max {UPLOAD_MAX_SIZE // (1024*1024)}MB)"
                        )
                    f.write(chunk)
        except Exception as e:
            cleanup_temp_file(uploaded_file_path)
            raise e

    # Handle cookies file upload if provided
    cookies_file_path = None
    if cookies_file:
        cookies_file_path = str(TEMP_DIR / f"{job_id}_cookies.txt")
        try:
            content = await cookies_file.read()
            with open(cookies_file_path, "wb") as f:
                f.write(content)
        except Exception as e:
            cleanup_temp_file(uploaded_file_path)
            raise HTTPException(status_code=500, detail=f"Failed to save cookies file: {e}")

    # Run transcription in background thread
    speakers_max = max_speakers or MAX_SPEAKERS
    user_hf_token = hf_token or HF_TOKEN

    def run_pipeline():
        wav_path = None
        try:
            job.update(2, "Waiting in queue...", "pending")
            with pipeline_semaphore:
                job.update(5, "Starting pipeline...", "downloading")

                # Step 1: Get audio
                if url:
                    source_type = detect_source_type(url)
                    job.update(8, f"Downloading from {source_type}...")
                    wav_path, metadata = download_audio_from_url(
                        url,
                        progress_callback=lambda p, m: job.update(p, m, "downloading"),
                        cookies_path=cookies_file_path,
                    )
                else:
                    job.update(8, "Processing uploaded file...")
                    wav_path, metadata = convert_uploaded_file(
                        uploaded_file_path,
                        progress_callback=lambda p, m: job.update(p, m, "downloading"),
                    )

                # Step 2: Transcribe
                job.update(28, "Starting WhisperX pipeline...", "transcribing")

                raw_result = transcriber.transcribe(
                    wav_path,
                    progress_callback=lambda p, m: job.update(p, m, "transcribing"),
                    enable_diarization=enable_diarization,
                    max_speakers=speakers_max,
                    hf_token=user_hf_token,
                )

                # Step 3: Format results
                job.update(98, "Formatting results...")
                formatted = format_result_for_frontend(raw_result, metadata)

                # Generate markdown
                md_content = generate_markdown(formatted)
                md_path = str(TEMP_DIR / f"{job_id}_transcript.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                formatted["metadata"]["mdFilePath"] = md_path

                # Generate srt
                srt_content = generate_srt(formatted)
                srt_path = str(TEMP_DIR / f"{job_id}_transcript.srt")
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                formatted["metadata"]["srtFilePath"] = srt_path

                # Generate vtt
                vtt_content = generate_vtt(formatted)
                vtt_path = str(TEMP_DIR / f"{job_id}_transcript.vtt")
                with open(vtt_path, "w", encoding="utf-8") as f:
                    f.write(vtt_content)
                formatted["metadata"]["vttFilePath"] = vtt_path

                # Generate txt
                txt_content = generate_txt(formatted)
                txt_path = str(TEMP_DIR / f"{job_id}_transcript.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(txt_content)
                formatted["metadata"]["txtFilePath"] = txt_path

                # Print dialogue transcript directly to console
                print("\n" + "="*80)
                print(f"[SUCCESS] TRANSCRIPTION COMPLETED FOR JOB: {job_id}")
                print(f"Title: {metadata.get('title', 'Unknown') if metadata else 'Unknown'}")
                print(f"Language: {formatted['metadata']['language'].upper()} | Duration: {formatted['metadata']['totalDurationFormatted']}")
                print("="*80)
                for seg in formatted["segments"]:
                    print(f"[{seg['startFormatted']} -> {seg['endFormatted']}] {seg['speaker']}: {seg['text']}")
                print("="*80 + "\n")

                job.complete(formatted)

        except Exception as e:
            job.fail(f"Error: {str(e)}")
        finally:
            # Cleanup temp files
            if wav_path:
                cleanup_temp_file(wav_path)
            if uploaded_file_path:
                cleanup_temp_file(uploaded_file_path)
            if cookies_file_path:
                cleanup_temp_file(cookies_file_path)
            
            # Check if any other job is active
            active_jobs = [j for j in jobs.values() if j.id != job_id and j.status in ("pending", "downloading", "transcribing")]
            if not active_jobs:
                print("[INFO] No active jobs. Releasing transcriber models to free RAM/VRAM...")
                try:
                    transcriber.cleanup()
                except Exception as e:
                    print(f"[CLEANUP ERROR] Failed to clean up models: {e}")

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    return {"jobId": job_id, "status": "started"}


@app.get("/api/transcribe/{job_id}/stream")
async def stream_progress(job_id: str):
    """SSE endpoint for streaming progress updates."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        job = jobs[job_id]
        event_index = 0

        while True:
            new_events = job.get_new_events(event_index)
            for event in new_events:
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"
                event_index += 1

                if event.get("status") in ("done", "error"):
                    return

            await asyncio.sleep(0.5)

            # Timeout after 30 minutes
            if time.time() - job.created_at > 1800:
                yield f"data: {json.dumps({'status': 'error', 'error': 'Timeout'})}\n\n"
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/transcribe/{job_id}/result")
async def get_result(job_id: str):
    """Get the transcription result."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job.status == "error":
        raise HTTPException(status_code=500, detail=job.error)
    if job.status != "done":
        return {"status": job.status, "progress": job.progress, "message": job.message}

    return job.result


@app.get("/api/transcribe/{job_id}/download")
async def download_markdown(job_id: str):
    """Download the transcript as a Markdown file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job.status != "done" or not job.result:
        raise HTTPException(status_code=400, detail="Transcription not complete")

    md_path = job.result.get("metadata", {}).get("mdFilePath")
    if not md_path or not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Markdown file not found")

    title = job.result.get("metadata", {}).get("title", "transcript")
    # Sanitize filename
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:60]
    filename = f"{safe_title}_transcript.md" if safe_title else "transcript.md"

    return FileResponse(
        path=md_path,
        filename=filename,
        media_type="text/markdown",
    )


@app.get("/api/transcribe/{job_id}/download/srt")
async def download_srt(job_id: str):
    """Download the transcript as an SRT subtitle file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job.status != "done" or not job.result:
        raise HTTPException(status_code=400, detail="Transcription not complete")

    srt_path = job.result.get("metadata", {}).get("srtFilePath")
    if not srt_path or not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail="SRT file not found")

    title = job.result.get("metadata", {}).get("title", "transcript")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:60]
    filename = f"{safe_title}_subtitle.srt" if safe_title else "subtitle.srt"

    return FileResponse(
        path=srt_path,
        filename=filename,
        media_type="text/plain",
    )


@app.get("/api/transcribe/{job_id}/download/vtt")
async def download_vtt(job_id: str):
    """Download the transcript as a WebVTT subtitle file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job.status != "done" or not job.result:
        raise HTTPException(status_code=400, detail="Transcription not complete")

    vtt_path = job.result.get("metadata", {}).get("vttFilePath")
    if not vtt_path or not os.path.exists(vtt_path):
        raise HTTPException(status_code=404, detail="WebVTT file not found")

    title = job.result.get("metadata", {}).get("title", "transcript")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:60]
    filename = f"{safe_title}_subtitle.vtt" if safe_title else "subtitle.vtt"

    return FileResponse(
        path=vtt_path,
        filename=filename,
        media_type="text/vtt",
    )


@app.get("/api/transcribe/{job_id}/download/txt")
async def download_txt(job_id: str):
    """Download the transcript as a plain text file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job.status != "done" or not job.result:
        raise HTTPException(status_code=400, detail="Transcription not complete")

    txt_path = job.result.get("metadata", {}).get("txtFilePath")
    if not txt_path or not os.path.exists(txt_path):
        raise HTTPException(status_code=404, detail="TXT file not found")

    title = job.result.get("metadata", {}).get("title", "transcript")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:60]
    filename = f"{safe_title}_transcript.txt" if safe_title else "transcript.txt"

    return FileResponse(
        path=txt_path,
        filename=filename,
        media_type="text/plain",
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model": WHISPER_MODEL,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "hf_token_set": bool(HF_TOKEN),
    }


# ─── Cleanup old jobs periodically ──────────────────────────────
async def periodic_cleanup():
    """Periodically clean up old temp files and job records."""
    while True:
        try:
            now = time.time()
            cutoff = now - 86400  # 24 hours
            
            jobs_to_delete = []
            for job_id, job in list(jobs.items()):
                if job.created_at < cutoff:
                    jobs_to_delete.append(job_id)
            
            for job_id in jobs_to_delete:
                jobs.pop(job_id, None)
                
            if TEMP_DIR.exists():
                for p in TEMP_DIR.iterdir():
                    if p.is_file():
                        try:
                            mtime = p.stat().st_mtime
                            if mtime < cutoff:
                                p.unlink(missing_ok=True)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")
            
        await asyncio.sleep(3600)  # Every hour


@app.on_event("startup")
async def startup():
    """Cleanup old temp files on startup and start background cleanup."""
    TEMP_DIR.mkdir(exist_ok=True)
    try:
        for p in TEMP_DIR.iterdir():
            if p.is_file() and p.name != ".gitkeep":
                p.unlink(missing_ok=True)
    except Exception:
        pass
        
    asyncio.create_task(periodic_cleanup())
    
    print(f"[*] WhisperX Transcriber Server starting...")
    print(f"    Model: {WHISPER_MODEL} | Device: {DEVICE} | Compute: {COMPUTE_TYPE}")
    print(f"    HF Token: {'Set' if HF_TOKEN else 'Not set'}")
    print(f"    Max speakers: {MAX_SPEAKERS}")
    print(f"    Frontend: {frontend_dir}")


# ─── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)

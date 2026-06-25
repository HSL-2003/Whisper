"""
Result Formatter Module
Converts WhisperX output to structured JSON and Markdown formats.
"""

from datetime import datetime
from typing import Optional


# Speaker color names for display
SPEAKER_COLORS = [
    ("🔵", "#6C9BFF", "Blue"),
    ("🟢", "#4AEAB0", "Green"),
    ("🟣", "#C084FC", "Purple"),
    ("🟠", "#FB923C", "Orange"),
    ("🔴", "#F87171", "Red"),
    ("🟡", "#FACC15", "Yellow"),
    ("🩵", "#67E8F9", "Cyan"),
    ("🩷", "#F9A8D4", "Pink"),
    ("🤎", "#D4A574", "Brown"),
    ("⚪", "#E5E7EB", "Gray"),
    ("💚", "#86EFAC", "Lime"),
    ("💙", "#93C5FD", "Light Blue"),
    ("💜", "#D8B4FE", "Lavender"),
    ("🧡", "#FDBA74", "Peach"),
    ("❤️", "#FCA5A5", "Coral"),
]


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    if seconds is None or seconds < 0:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_timestamp_precise(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.ms format."""
    if seconds is None or seconds < 0:
        return "00:00:00.000"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def format_result_for_frontend(result: dict, metadata: Optional[dict] = None) -> dict:
    """
    Format WhisperX result for the frontend.
    
    Returns a structured dict with segments, speakers, and metadata.
    """
    segments = result.get("segments", [])
    language = result.get("language", "unknown")

    # Collect unique speakers
    speakers = {}
    for seg in segments:
        speaker_id = seg.get("speaker", "UNKNOWN")
        if speaker_id not in speakers:
            idx = len(speakers) % len(SPEAKER_COLORS)
            emoji, color, name = SPEAKER_COLORS[idx]
            speakers[speaker_id] = {
                "id": speaker_id,
                "label": speaker_id,
                "emoji": emoji,
                "color": color,
                "colorName": name,
                "segmentCount": 0,
                "totalDuration": 0.0,
            }
        speakers[speaker_id]["segmentCount"] += 1
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        speakers[speaker_id]["totalDuration"] += (end - start)

    # Format segments
    formatted_segments = []
    for i, seg in enumerate(segments):
        speaker_id = seg.get("speaker", "UNKNOWN")
        speaker_info = speakers.get(speaker_id, {})
        
        formatted_seg = {
            "id": i,
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "startFormatted": format_timestamp(seg.get("start", 0)),
            "endFormatted": format_timestamp(seg.get("end", 0)),
            "text": seg.get("text", "").strip(),
            "speaker": speaker_id,
            "speakerEmoji": speaker_info.get("emoji", "⚪"),
            "speakerColor": speaker_info.get("color", "#E5E7EB"),
            "words": [],
        }

        # Include word-level details if available
        for word in seg.get("words", []):
            formatted_seg["words"].append({
                "word": word.get("word", ""),
                "start": word.get("start"),
                "end": word.get("end"),
                "speaker": word.get("speaker", speaker_id),
            })

        formatted_segments.append(formatted_seg)

    # Calculate total duration
    total_duration = 0
    if formatted_segments:
        total_duration = max(s["end"] for s in formatted_segments)

    # Build response
    response = {
        "segments": formatted_segments,
        "speakers": list(speakers.values()),
        "metadata": {
            "language": language,
            "totalDuration": total_duration,
            "totalDurationFormatted": format_timestamp(total_duration),
            "totalSegments": len(formatted_segments),
            "totalSpeakers": len(speakers),
            "processedAt": datetime.now().isoformat(),
        },
    }

    if metadata:
        response["metadata"]["title"] = metadata.get("title", "Unknown")
        response["metadata"]["source"] = metadata.get("source", "Unknown")
        response["metadata"]["uploader"] = metadata.get("uploader", "")

    if "diarization_error" in result:
        response["metadata"]["diarizationError"] = result["diarization_error"]

    return response


def generate_markdown(formatted_result: dict) -> str:
    """
    Generate a Markdown transcript from formatted results.
    
    Creates a beautifully formatted .md file with:
    - Header with metadata
    - Speaker summary table
    - Full timeline with speaker labels
    """
    meta = formatted_result.get("metadata", {})
    segments = formatted_result.get("segments", [])
    speakers = formatted_result.get("speakers", [])

    lines = []

    # Header
    lines.append("# 📝 Meeting Transcript")
    lines.append("")
    
    title = meta.get("title", "Untitled")
    lines.append(f"**Title**: {title}")
    
    source = meta.get("source", "")
    if source:
        lines.append(f"**Source**: {source}")
    
    lines.append(f"**Language**: {meta.get('language', 'unknown').upper()}")
    lines.append(f"**Duration**: {meta.get('totalDurationFormatted', 'N/A')}")
    lines.append(f"**Speakers**: {meta.get('totalSpeakers', 0)}")
    lines.append(f"**Processed**: {meta.get('processedAt', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Speaker Summary Table
    if speakers:
        lines.append("## 👥 Speaker Summary")
        lines.append("")
        lines.append("| Speaker | Segments | Total Time |")
        lines.append("|---------|----------|------------|")
        for s in speakers:
            duration_fmt = format_timestamp(s.get("totalDuration", 0))
            lines.append(
                f"| {s['emoji']} **{s['id']}** | {s['segmentCount']} | {duration_fmt} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    # Timeline
    lines.append("## 📋 Full Transcript")
    lines.append("")

    current_speaker = None
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        emoji = seg.get("speakerEmoji", "⚪")
        start = seg.get("startFormatted", "00:00:00")
        end = seg.get("endFormatted", "00:00:00")
        text = seg.get("text", "")

        # Add speaker header when speaker changes
        if speaker != current_speaker:
            lines.append("")
            lines.append(f"### {emoji} {speaker}")
            current_speaker = speaker

        lines.append(f"**[{start} → {end}]**")
        lines.append(f"> {text}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "*Generated by WhisperX Meeting Transcriber*"
    )

    return "\n".join(lines)


def generate_srt(formatted_result: dict) -> str:
    """Generate SRT subtitle content from formatted results."""
    segments = formatted_result.get("segments", [])
    lines = []
    for idx, seg in enumerate(segments, 1):
        start = format_timestamp_precise(seg.get("start", 0)).replace(".", ",")
        end = format_timestamp_precise(seg.get("end", 0)).replace(".", ",")
        speaker = seg.get("speaker", "UNKNOWN")
        text = seg.get("text", "").strip()
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(f"[{speaker}]: {text}")
        lines.append("")
    return "\n".join(lines)


def generate_vtt(formatted_result: dict) -> str:
    """Generate WebVTT subtitle content from formatted results."""
    segments = formatted_result.get("segments", [])
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = format_timestamp_precise(seg.get("start", 0))
        end = format_timestamp_precise(seg.get("end", 0))
        speaker = seg.get("speaker", "UNKNOWN")
        text = seg.get("text", "").strip()
        lines.append(f"{start} --> {end}")
        lines.append(f"[{speaker}]: {text}")
        lines.append("")
    return "\n".join(lines)


def generate_txt(formatted_result: dict) -> str:
    """Generate plain text transcript from formatted results."""
    segments = formatted_result.get("segments", [])
    lines = []
    for seg in segments:
        start = seg.get("startFormatted", "00:00:00")
        end = seg.get("endFormatted", "00:00:00")
        speaker = seg.get("speaker", "UNKNOWN")
        text = seg.get("text", "").strip()
        lines.append(f"[{start} -> {end}] {speaker}: {text}")
    return "\n".join(lines)

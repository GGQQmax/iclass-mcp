"""
Alignment module: associates timestamped speech segments with active slide pages,
and formats Markdown and structured JSON notes artifacts.
"""

import json
import os
from typing import List, Tuple

from .models import SlidePage, TranscriptSegment, VideoNotes


def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    total_sec = max(0, int(seconds))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def align_transcripts_to_slides(
    slides: List[SlidePage],
    segments: List[TranscriptSegment],
) -> List[SlidePage]:
    """
    Associate each transcript segment with the slide page active at its start time.
    """
    if not slides:
        # If no slides were detected, create a single catch-all page
        end_time = max([s.end_seconds for s in segments], default=0.0)
        return [
            SlidePage(
                page_number=1,
                start_seconds=0.0,
                end_seconds=end_time,
                heading="Page 1",
                slide_text=[],
                transcript_segments=list(segments),
            )
        ]

    # Clear previous segments
    for slide in slides:
        slide.transcript_segments = []

    # Map segments to slides
    for seg in segments:
        assigned = False
        for slide in slides:
            # Overlap criteria: if segment start is within slide interval
            if slide.start_seconds <= seg.start_seconds < slide.end_seconds:
                slide.transcript_segments.append(seg)
                assigned = True
                break

        if not assigned:
            # If segment started before first slide or after last slide
            if seg.start_seconds < slides[0].start_seconds:
                slides[0].transcript_segments.append(seg)
            else:
                slides[-1].transcript_segments.append(seg)

    return slides


def format_page_markdown(page: SlidePage) -> str:
    """Format an individual slide page as Markdown."""
    lines = []
    lines.append(f"{page.heading}")
    time_str = f"Time: {format_timestamp(page.start_seconds)}–{format_timestamp(page.end_seconds)}"
    lines.append(time_str)

    lines.append("Slide text:")
    if page.slide_text:
        for item in page.slide_text:
            cleaned = item.strip()
            if not cleaned.startswith("-") and not cleaned.startswith("*"):
                cleaned = f"- {cleaned}"
            lines.append(cleaned)
    else:
        lines.append("(No slide text detected)")

    lines.append("Teacher explanation:")
    if page.transcript_segments:
        # Include verbatim text with optional segment timestamps
        speech_text = " ".join([seg.text for seg in page.transcript_segments if seg.text.strip()])
        lines.append(speech_text if speech_text else "(No spoken explanation)")
    else:
        lines.append("(No spoken explanation)")

    return "\n".join(lines)


def format_notes_markdown(notes: VideoNotes) -> str:
    """Format the full video lecture notes into human-readable Markdown."""
    lines = []
    lines.append(f"Title: {notes.title}")
    lines.append(f"Source: {notes.source}")
    lines.append(f"Duration: {format_timestamp(notes.duration_seconds)}")
    lines.append("")

    for page in notes.pages:
        lines.append(format_page_markdown(page))
        lines.append("")

    return "\n".join(lines).strip()


def write_notes_artifacts(
    notes: VideoNotes,
    output_dir: str,
) -> Tuple[str, str]:
    """
    Write notes.md and notes.json artifacts in the given output directory.
    Returns (notes_md_path, notes_json_path).
    """
    os.makedirs(output_dir, exist_ok=True)

    md_path = os.path.join(output_dir, "notes.md")
    json_path = os.path.join(output_dir, "notes.json")

    # 1. Write Markdown
    md_content = format_notes_markdown(notes)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 2. Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(notes.to_dict(), f, indent=2, ensure_ascii=False)

    return md_path, json_path

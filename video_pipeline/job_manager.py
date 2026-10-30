"""
Video-to-text background job manager and notes retrieval engine.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .aligner import (
    align_transcripts_to_slides,
    format_page_markdown,
    format_timestamp,
    write_notes_artifacts,
)
from .audio import extract_mono_audio, get_media_duration
from .downloader import acquire_source
from .models import JobRecord, JobStatus, SlidePage, VideoNotes
from .slide_detector import extract_and_detect_slides
from .transcription import get_transcriber


def get_default_cache_dir() -> str:
    """Return cache directory for video jobs."""
    custom = os.getenv("ICLASS_VIDEO_CACHE_DIR")
    if custom:
        return os.path.abspath(custom)
    return os.path.expanduser("~/.cache/iclass-mcp/video_jobs")


class VideoJobManager:
    """Manages asynchronous processing of video-to-text jobs and note queries."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or get_default_cache_dir()
        os.makedirs(self.cache_dir, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._jobs: Dict[str, JobRecord] = {}
        self._load_cached_jobs()

    def _load_cached_jobs(self):
        """Load persisted job records from cache directory."""
        if not os.path.exists(self.cache_dir):
            return
        for item in os.listdir(self.cache_dir):
            job_file = os.path.join(self.cache_dir, item, "job.json")
            if os.path.isfile(job_file):
                try:
                    with open(job_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        record = JobRecord.from_dict(data)
                        self._jobs[record.job_id] = record
                except Exception:
                    pass

    def _save_job(self, record: JobRecord):
        """Persist a job record to disk."""
        self._jobs[record.job_id] = record
        job_dir = record.work_dir
        os.makedirs(job_dir, exist_ok=True)
        job_file = os.path.join(job_dir, "job.json")
        try:
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def create_job(self, source: str, source_type: str = "unknown") -> JobRecord:
        """Create and register a new pending job record."""
        job_id = f"v2t_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        work_dir = os.path.join(self.cache_dir, job_id)
        os.makedirs(work_dir, exist_ok=True)

        record = JobRecord(
            job_id=job_id,
            status=JobStatus.QUEUED.value,
            stage="queued",
            source=source,
            source_type=source_type,
            work_dir=work_dir,
            progress=0.0,
        )
        self._save_job(record)
        return record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Get job record by ID."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        job_file = os.path.join(self.cache_dir, job_id, "job.json")
        if os.path.isfile(job_file):
            try:
                with open(job_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    record = JobRecord.from_dict(data)
                    self._jobs[job_id] = record
                    return record
            except Exception:
                pass
        return None

    async def start_job(
        self,
        source: str,
        source_type: Optional[str] = None,
        course_id: Optional[int] = None,
        activity_id: Optional[int] = None,
        language: str = "zh-TW",
        stt_backend: Optional[str] = None,
        api_instance: Optional[Any] = None,
    ) -> JobRecord:
        """
        Validate, create, and launch a video processing job in background.
        """
        record = self.create_job(source=source, source_type=source_type or "unknown")

        # Run pipeline in background
        asyncio.create_task(
            self._execute_pipeline(
                record=record,
                source=source,
                source_type=source_type,
                course_id=course_id,
                activity_id=activity_id,
                language=language,
                stt_backend=stt_backend,
                api_instance=api_instance,
            )
        )
        return record

    async def _execute_pipeline(
        self,
        record: JobRecord,
        source: str,
        source_type: Optional[str],
        course_id: Optional[int],
        activity_id: Optional[int],
        language: str,
        stt_backend: Optional[str],
        api_instance: Optional[Any],
    ):
        """Internal worker executing pipeline stages."""
        try:
            # Stage 1: Downloading / Acquiring
            record.status = JobStatus.DOWNLOADING.value
            record.stage = "downloading"
            record.progress = 0.1
            record.updated_at = time.time()
            self._save_job(record)

            video_path, title, duration, resolved_type = await acquire_source(
                source=source,
                work_dir=record.work_dir,
                source_type=source_type,
                course_id=course_id,
                activity_id=activity_id,
                api_instance=api_instance,
            )
            record.source_type = resolved_type
            record.title = title
            if duration <= 0:
                duration = get_media_duration(video_path)
            record.duration_seconds = duration
            self._save_job(record)

            # Stage 2: Audio Extraction & Transcription
            record.status = JobStatus.TRANSCRIBING.value
            record.stage = "transcribing"
            record.progress = 0.3
            record.updated_at = time.time()
            self._save_job(record)

            audio_path = os.path.join(record.work_dir, "audio.wav")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._executor,
                extract_mono_audio,
                video_path,
                audio_path,
            )

            # Transcribe
            transcriber = get_transcriber(stt_backend)
            segments = await loop.run_in_executor(
                self._executor,
                transcriber.transcribe,
                audio_path,
                language,
            )

            # Stage 3: Detecting Slides & OCR
            record.status = JobStatus.DETECTING_SLIDES.value
            record.stage = "detecting_slides"
            record.progress = 0.6
            record.updated_at = time.time()
            self._save_job(record)

            slides = await loop.run_in_executor(
                self._executor,
                extract_and_detect_slides,
                video_path,
                record.work_dir,
                2.0,  # sample every 2 sec
                0.12,  # diff threshold
                4.0,  # debounce
                duration,
            )

            # Stage 4: Aligning & Artifact Generation
            record.status = JobStatus.ALIGNING.value
            record.stage = "aligning"
            record.progress = 0.85
            record.updated_at = time.time()
            self._save_job(record)

            aligned_pages = align_transcripts_to_slides(slides, segments)
            record.total_pages = len(aligned_pages)

            notes = VideoNotes(
                source=source,
                title=title or "Lecture Notes",
                duration_seconds=duration,
                language=language,
                pages=aligned_pages,
                metadata={
                    "job_id": record.job_id,
                    "source_type": record.source_type,
                    "stt_backend": stt_backend or "auto",
                    "total_pages": len(aligned_pages),
                    "disclaimer": "Whisper speech transcription for zh-TW may contain dialect or mixed-language inaccuracies; refer to timestamps.",
                },
            )

            md_path, json_path = write_notes_artifacts(notes, record.work_dir)
            record.artifact_notes_md = md_path
            record.artifact_notes_json = json_path
            record.status = JobStatus.COMPLETE.value
            record.stage = "complete"
            record.progress = 1.0
            record.updated_at = time.time()
            self._save_job(record)

        except Exception as e:
            record.status = JobStatus.FAILED.value
            record.stage = "failed"
            record.error = str(e)
            record.updated_at = time.time()
            self._save_job(record)

    def load_notes_json(self, job_id: str) -> Optional[VideoNotes]:
        """Load completed VideoNotes from artifact json."""
        record = self.get_job(job_id)
        if not record or not record.artifact_notes_json:
            return None
        if not os.path.exists(record.artifact_notes_json):
            return None
        try:
            with open(record.artifact_notes_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                return VideoNotes.from_dict(data)
        except Exception:
            return None

    def query_notes(
        self,
        job_id: str,
        page: Optional[int] = None,
        query: Optional[str] = None,
        max_chars: int = 4000,
    ) -> Dict[str, Any]:
        """
        Query notes with mutual exclusion between page and query.
        """
        record = self.get_job(job_id)
        if not record:
            return {"error": f"Job ID not found: {job_id}"}

        if record.status == JobStatus.FAILED.value:
            return {
                "job_id": job_id,
                "status": "failed",
                "error": record.error,
                "message": f"Job processing failed: {record.error}",
            }

        if record.status != JobStatus.COMPLETE.value:
            return {
                "job_id": job_id,
                "status": record.status,
                "stage": record.stage,
                "progress": f"{int(record.progress * 100)}%",
                "message": f"Job is still {record.stage}. Please check back later using get_video_job('{job_id}').",
            }

        notes = self.load_notes_json(job_id)
        if not notes:
            return {"error": f"Notes artifact missing or unreadable for job {job_id}"}

        # Page and query mutually exclusive validation
        if page is not None and query is not None:
            return {
                "error": "Arguments 'page' and 'query' are mutually exclusive. Specify either a page number or a search query, not both."
            }

        # 1. Page query
        if page is not None:
            if page < 1 or page > len(notes.pages):
                return {
                    "error": f"Page {page} out of bounds. Lecture has {len(notes.pages)} pages (1-{len(notes.pages)})."
                }
            selected_page = notes.pages[page - 1]
            content = format_page_markdown(selected_page)
            if len(content) > max_chars:
                content = content[:max_chars] + "\n...(truncated to max_chars)"
            return {
                "job_id": job_id,
                "title": notes.title,
                "page": page,
                "total_pages": len(notes.pages),
                "content": content,
            }

        # 2. Text search query
        if query is not None:
            q_clean = query.strip().lower()
            if not q_clean:
                return {"error": "Search query cannot be empty."}

            matches: List[str] = []
            curr_chars = 0

            for p in notes.pages:
                slide_match = any(q_clean in line.lower() for line in p.slide_text)
                trans_matches = [
                    seg for seg in p.transcript_segments if q_clean in seg.text.lower()
                ]

                if slide_match or trans_matches:
                    entry_lines = [
                        f"### {p.heading} ({format_timestamp(p.start_seconds)}–{format_timestamp(p.end_seconds)})"
                    ]
                    if slide_match:
                        entry_lines.append("**Slide Match:**")
                        for line in p.slide_text:
                            if q_clean in line.lower():
                                entry_lines.append(f"- {line}")

                    if trans_matches:
                        entry_lines.append("**Spoken Excerpts:**")
                        for seg in trans_matches:
                            entry_lines.append(
                                f"- [{format_timestamp(seg.start_seconds)}] {seg.text}"
                            )

                    entry_text = "\n".join(entry_lines) + "\n"
                    if curr_chars + len(entry_text) > max_chars:
                        matches.append("\n...(additional matches omitted due to max_chars limit)")
                        break
                    matches.append(entry_text)
                    curr_chars += len(entry_text)

            if not matches:
                return {
                    "job_id": job_id,
                    "query": query,
                    "matches_found": 0,
                    "message": f"No matches found for '{query}' in lecture notes.",
                }

            return {
                "job_id": job_id,
                "query": query,
                "matches_found": len(matches),
                "results": "\n".join(matches),
            }

        # 3. Default: Table of Contents / Outline (conservative size)
        toc_lines = [
            f"# {notes.title}",
            f"**Source:** {notes.source}",
            f"**Duration:** {format_timestamp(notes.duration_seconds)}",
            f"**Total Pages:** {len(notes.pages)}",
            "",
            "## Table of Contents",
        ]
        for p in notes.pages:
            toc_lines.append(
                f"- Page {p.page_number}: {p.heading} ({format_timestamp(p.start_seconds)}–{format_timestamp(p.end_seconds)})"
            )
        toc_lines.append("")
        toc_lines.append("Use `get_video_notes(job_id, page=N)` to read a specific page or `get_video_notes(job_id, query='...')` to search.")

        toc_content = "\n".join(toc_lines)
        if len(toc_content) > max_chars:
            toc_content = toc_content[:max_chars] + "\n...(truncated)"

        return {
            "job_id": job_id,
            "title": notes.title,
            "total_pages": len(notes.pages),
            "outline": toc_content,
        }

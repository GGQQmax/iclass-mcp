"""
Video-to-Text lecture notes submodule pipeline for iclass-mcp.
"""

import shutil
import importlib.util
from typing import Dict

from .models import JobRecord, JobStatus, SlidePage, TranscriptSegment, VideoNotes
from .job_manager import VideoJobManager, get_default_cache_dir


def check_dependencies() -> Dict[str, bool]:
    """
    Check the status of system and Python dependencies required for the video pipeline.
    """
    return {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "yt-dlp": shutil.which("yt-dlp") is not None or importlib.util.find_spec("yt_dlp") is not None,
        "tesseract": shutil.which("tesseract") is not None,
        "pillow": importlib.util.find_spec("PIL") is not None,
        "numpy": importlib.util.find_spec("numpy") is not None,
        "whisper": (
            importlib.util.find_spec("faster_whisper") is not None
            or importlib.util.find_spec("whisper") is not None
        ),
    }


def is_available() -> bool:
    """
    Return True if minimal required video processing components (ffmpeg, pillow) are present.
    """
    deps = check_dependencies()
    return deps["ffmpeg"] and deps["pillow"]


__all__ = [
    "VideoJobManager",
    "VideoNotes",
    "SlidePage",
    "TranscriptSegment",
    "JobRecord",
    "JobStatus",
    "check_dependencies",
    "is_available",
    "get_default_cache_dir",
]

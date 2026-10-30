"""
Data models for the video-to-text lecture notes pipeline.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    DETECTING_SLIDES = "detecting_slides"
    ALIGNING = "aligning"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptSegment":
        return cls(
            start_seconds=float(data.get("start_seconds", 0.0)),
            end_seconds=float(data.get("end_seconds", 0.0)),
            text=str(data.get("text", "")),
            confidence=data.get("confidence"),
        )


@dataclass
class SlidePage:
    page_number: int
    start_seconds: float
    end_seconds: float
    heading: str
    slide_text: List[str] = field(default_factory=list)
    transcript_segments: List[TranscriptSegment] = field(default_factory=list)
    image_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["transcript_segments"] = [s.to_dict() for s in self.transcript_segments]
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlidePage":
        segments = [
            TranscriptSegment.from_dict(s)
            for s in data.get("transcript_segments", [])
        ]
        return cls(
            page_number=int(data.get("page_number", 1)),
            start_seconds=float(data.get("start_seconds", 0.0)),
            end_seconds=float(data.get("end_seconds", 0.0)),
            heading=str(data.get("heading", f"Page {data.get('page_number', 1)}")),
            slide_text=list(data.get("slide_text", [])),
            transcript_segments=segments,
            image_path=data.get("image_path"),
        )


@dataclass
class VideoNotes:
    source: str
    title: str
    duration_seconds: float
    language: str
    pages: List[SlidePage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "pages": [p.to_dict() for p in self.pages],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoNotes":
        pages = [SlidePage.from_dict(p) for p in data.get("pages", [])]
        return cls(
            source=str(data.get("source", "")),
            title=str(data.get("title", "")),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            language=str(data.get("language", "zh-TW")),
            pages=pages,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class JobRecord:
    job_id: str
    status: str
    stage: str
    source: str
    source_type: str
    work_dir: str
    progress: float = 0.0
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    total_pages: Optional[int] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: Optional[str] = None
    artifact_notes_md: Optional[str] = None
    artifact_notes_json: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobRecord":
        return cls(**data)

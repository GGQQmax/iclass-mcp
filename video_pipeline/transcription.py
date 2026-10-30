"""
Pluggable Speech-to-Text transcription interface and backends.
Includes specialized Traditional Chinese (zh-TW) prompting and verbatim text preservation.
"""

from abc import ABC, abstractmethod
import importlib.util
import os
from typing import List, Optional

from .models import TranscriptSegment

# Default Traditional Chinese prompt to guide Whisper towards zh-TW character representation
DEFAULT_ZH_TW_PROMPT = (
    "以下為繁體中文（台灣）的課堂演講與簡報說明，請使用繁體中文轉錄。"
)


class BaseTranscriber(ABC):
    """Abstract interface for speech transcription backends."""

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        language: str = "zh-TW",
        initial_prompt: Optional[str] = None,
    ) -> List[TranscriptSegment]:
        """
        Transcribe an audio file into timestamped speech segments.

        :param audio_path: Path to mono 16kHz WAV audio.
        :param language: Target language hint (e.g. 'zh-TW', 'en', 'auto').
        :param initial_prompt: Optional prompt text to bias vocabulary/script.
        :return: List of TranscriptSegment with start, end, and verbatim text.
        """
        pass


class FasterWhisperTranscriber(BaseTranscriber):
    """Faster-Whisper backend (CTranslate2). Fast and memory-efficient."""

    def __init__(self, model_size: Optional[str] = None, device: str = "auto"):
        self.model_size = model_size or os.getenv("WHISPER_MODEL", "base")
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise RuntimeError(
                    "faster-whisper is not installed. Run 'pip install faster-whisper' or run install.sh --with-video."
                )
            compute_type = "int8" if self.device in ("cpu", "auto") else "float16"
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=compute_type)
        return self._model

    def transcribe(
        self,
        audio_path: str,
        language: str = "zh-TW",
        initial_prompt: Optional[str] = None,
    ) -> List[TranscriptSegment]:
        model = self._get_model()

        # Whisper standard language code for Chinese is 'zh'
        whisper_lang = "zh" if language.lower().startswith("zh") else (None if language == "auto" else language)
        prompt = initial_prompt
        if not prompt and language.lower().replace("_", "-") in ("zh-tw", "zh-hk", "zh-hant"):
            prompt = DEFAULT_ZH_TW_PROMPT

        segments, _ = model.transcribe(
            audio_path,
            language=whisper_lang,
            initial_prompt=prompt,
            vad_filter=True,
        )

        results: List[TranscriptSegment] = []
        for s in segments:
            text = s.text.strip()
            if text:
                results.append(
                    TranscriptSegment(
                        start_seconds=round(s.start, 2),
                        end_seconds=round(s.end, 2),
                        text=text,
                    )
                )
        return results


class OpenAIWhisperTranscriber(BaseTranscriber):
    """Standard OpenAI Whisper backend."""

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or os.getenv("WHISPER_MODEL", "base")
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                import whisper
            except ImportError:
                raise RuntimeError(
                    "openai-whisper is not installed. Run 'pip install openai-whisper'."
                )
            self._model = whisper.load_model(self.model_size)
        return self._model

    def transcribe(
        self,
        audio_path: str,
        language: str = "zh-TW",
        initial_prompt: Optional[str] = None,
    ) -> List[TranscriptSegment]:
        model = self._get_model()

        whisper_lang = "zh" if language.lower().startswith("zh") else (None if language == "auto" else language)
        prompt = initial_prompt
        if not prompt and language.lower().replace("_", "-") in ("zh-tw", "zh-hk", "zh-hant"):
            prompt = DEFAULT_ZH_TW_PROMPT

        options = {}
        if whisper_lang:
            options["language"] = whisper_lang
        if prompt:
            options["initial_prompt"] = prompt

        result = model.transcribe(audio_path, **options)
        results: List[TranscriptSegment] = []
        for s in result.get("segments", []):
            text = s.get("text", "").strip()
            if text:
                results.append(
                    TranscriptSegment(
                        start_seconds=round(float(s.get("start", 0.0)), 2),
                        end_seconds=round(float(s.get("end", 0.0)), 2),
                        text=text,
                    )
                )
        return results


class MockTranscriber(BaseTranscriber):
    """Mock transcriber for unit tests or dry runs."""

    def __init__(self, mock_segments: Optional[List[TranscriptSegment]] = None):
        self.mock_segments = mock_segments or [
            TranscriptSegment(
                start_seconds=0.0,
                end_seconds=5.0,
                text="大家好，歡迎來到這堂課程。",
            ),
            TranscriptSegment(
                start_seconds=5.5,
                end_seconds=12.0,
                text="今天我們主要討論單元核心概念與作業說明。",
            ),
        ]

    def transcribe(
        self,
        audio_path: str,
        language: str = "zh-TW",
        initial_prompt: Optional[str] = None,
    ) -> List[TranscriptSegment]:
        return list(self.mock_segments)


def get_available_stt_backend() -> Optional[str]:
    """Return the name of the available STT backend, or None if none installed."""
    if importlib.util.find_spec("faster_whisper") is not None:
        return "faster-whisper"
    if importlib.util.find_spec("whisper") is not None:
        return "openai-whisper"
    return None


def get_transcriber(backend: Optional[str] = None) -> BaseTranscriber:
    """
    Factory function to retrieve a transcriber instance based on preference and availability.
    """
    if backend == "mock":
        return MockTranscriber()

    avail = get_available_stt_backend()
    if backend == "faster-whisper" or (backend is None and avail == "faster-whisper"):
        return FasterWhisperTranscriber()
    if backend == "openai-whisper" or (backend is None and avail == "openai-whisper"):
        return OpenAIWhisperTranscriber()

    if backend == "mock_fallback":
        return MockTranscriber()

    raise RuntimeError(
        "No speech-to-text backend found. Please install 'faster-whisper' (recommended) "
        "with 'pip install faster-whisper' or run './install.sh --with-video'."
    )

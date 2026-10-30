"""
Audio extraction and media inspection utilities using ffmpeg/ffprobe.
"""

import json
import os
import shutil
import subprocess
from typing import Optional, Tuple


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg executable is installed and available in PATH."""
    return shutil.which("ffmpeg") is not None


def is_ffprobe_available() -> bool:
    """Check if ffprobe executable is installed and available in PATH."""
    return shutil.which("ffprobe") is not None


def get_media_duration(video_path: str) -> float:
    """
    Get media duration in seconds using ffprobe or ffmpeg.
    """
    if is_ffprobe_available():
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            duration_str = res.stdout.strip()
            if duration_str:
                return float(duration_str)
        except Exception:
            pass

    # Fallback to ffmpeg -i parsing
    if is_ffmpeg_available():
        cmd = ["ffmpeg", "-i", video_path]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            # Duration: 00:01:23.45
            for line in res.stderr.splitlines():
                if "Duration:" in line:
                    part = line.split("Duration:")[1].split(",")[0].strip()
                    parts = part.split(":")
                    if len(parts) == 3:
                        h = float(parts[0])
                        m = float(parts[1])
                        s = float(parts[2])
                        return h * 3600 + m * 60 + s
        except Exception:
            pass

    return 0.0


def extract_mono_audio(
    video_path: str,
    output_wav_path: str,
    sample_rate: int = 16000,
) -> str:
    """
    Extract 16-bit PCM mono audio WAV file from video for speech recognition.

    :param video_path: Input video or audio file.
    :param output_wav_path: Target wav path.
    :param sample_rate: Audio sample rate in Hz (default: 16000 Hz).
    :return: Absolute path to the extracted WAV file.
    :raises RuntimeError: If ffmpeg is not available or extraction fails.
    """
    if not is_ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is not installed or not found in PATH. Please install ffmpeg to extract audio."
        )

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        output_wav_path,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,  # 10 min timeout for long videos
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg audio extraction failed: {e.stderr or str(e)}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg audio extraction timed out after 600s.")

    if not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) == 0:
        raise RuntimeError("Audio extraction produced an empty or missing file.")

    return output_wav_path

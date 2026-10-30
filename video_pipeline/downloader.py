"""
Source acquisition module for YouTube, iClass, and local media files.
"""

import json
import os
import re
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple


def is_ytdlp_available() -> bool:
    """Check if yt-dlp is available in PATH or python module."""
    if shutil.which("yt-dlp") is not None:
        return True
    try:
        import yt_dlp  # noqa
        return True
    except ImportError:
        return False


def infer_source_type(source: str, explicit_type: Optional[str] = None) -> str:
    """
    Infer the source type from URL or identifier.
    Returns: 'youtube', 'iclass_reference', 'iclass_activity', 'local_file', or 'url'
    """
    if explicit_type:
        return explicit_type.lower()

    source_strip = source.strip()
    if os.path.exists(source_strip):
        return "local_file"

    if re.search(r"(youtube\.com|youtu\.be)", source_strip, re.IGNORECASE):
        return "youtube"

    if source_strip.isdigit():
        return "iclass_reference"

    if source_strip.startswith("http://") or source_strip.startswith("https://"):
        return "url"

    return "unknown"


def download_youtube_video(
    url: str,
    output_dir: str,
    timeout_sec: int = 600,
) -> Tuple[str, str, float]:
    """
    Download video from YouTube using yt-dlp safely with argument list.

    :param url: YouTube video URL.
    :param output_dir: Work directory for downloaded video.
    :param timeout_sec: Subprocess execution timeout in seconds.
    :return: Tuple of (video_file_path, video_title, duration_seconds)
    """
    if not is_ytdlp_available():
        raise RuntimeError(
            "yt-dlp is not installed. Please install it with 'pip install yt-dlp' or your system package manager."
        )

    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, "video.%(ext)s")

    # 1. Fetch metadata first (fast)
    title = "YouTube Lecture"
    duration = 0.0

    meta_cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--skip-download",
        url,
    ]
    try:
        meta_res = subprocess.run(
            meta_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        meta = json.loads(meta_res.stdout)
        title = meta.get("title", title)
        duration = float(meta.get("duration", 0.0))
    except Exception:
        # If metadata query fails, we can proceed to download directly
        pass

    # 2. Download media
    # Request standard mp4/mkv or best available format
    dl_cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o",
        out_template,
        url,
    ]

    try:
        subprocess.run(
            dl_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_sec,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"yt-dlp download failed: {e.stderr or str(e)}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp download timed out after {timeout_sec}s.")

    # Find the downloaded file
    downloaded_files = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("video.") and not f.endswith(".part") and not f.endswith(".ytdl")
    ]

    if not downloaded_files:
        raise RuntimeError("yt-dlp completed but no video file was found in output directory.")

    video_path = downloaded_files[0]
    return video_path, title, duration


async def acquire_source(
    source: str,
    work_dir: str,
    source_type: Optional[str] = None,
    course_id: Optional[int] = None,
    activity_id: Optional[int] = None,
    api_instance: Optional[Any] = None,
) -> Tuple[str, str, float, str]:
    """
    Acquire the video from YouTube, iClass, or local file.

    :return: Tuple of (video_path, title, duration_seconds, resolved_source_type)
    """
    os.makedirs(work_dir, exist_ok=True)
    stype = infer_source_type(source, source_type)

    if activity_id is not None or stype == "iclass_activity":
        act_id = activity_id if activity_id is not None else int(source)
        if api_instance is None:
            raise RuntimeError("TronClass API instance required to fetch iClass activity video.")
        
        act_details = await api_instance.get_activitie(act_id)
        if isinstance(act_details, dict) and "error" in act_details:
            raise RuntimeError(f"Failed to fetch iClass activity {act_id}: {act_details['error']}")

        title = act_details.get("title", f"iClass Activity {act_id}")
        duration = 0.0

        # Check if it's an online_video with a link
        link = act_details.get("link")
        if not link and isinstance(act_details.get("data"), dict):
            link = act_details["data"].get("link")
            if act_details["data"].get("duration"):
                duration = float(act_details["data"]["duration"])

        if link and ("youtube.com" in link or "youtu.be" in link):
            vpath, ytitle, ydur = download_youtube_video(link, work_dir)
            return vpath, title or ytitle, duration or ydur, "youtube"

        # Check for uploads with reference_id
        uploads = act_details.get("uploads") or act_details.get("upload_references") or []
        target_ref_id = None
        for u in uploads:
            if isinstance(u, dict):
                ref_id = u.get("reference_id") or u.get("id")
                if ref_id:
                    target_ref_id = ref_id
                    break

        if target_ref_id:
            downloaded_path = await api_instance.download(target_ref_id, downloads_dir=work_dir)
            return downloaded_path, title, duration, "iclass_activity"

        if link:
            # External or direct link
            vpath, ytitle, ydur = download_youtube_video(link, work_dir)
            return vpath, title or ytitle, duration or ydur, "url"

        raise RuntimeError(f"Could not find any downloadable video stream or link in activity {act_id}.")

    elif stype == "iclass_reference":
        ref_id = int(source)
        if api_instance is None:
            raise RuntimeError("TronClass API instance required to download iClass reference video.")
        downloaded_path = await api_instance.download(ref_id, downloads_dir=work_dir)
        filename = os.path.basename(downloaded_path)
        title = os.path.splitext(filename)[0]
        return downloaded_path, title, 0.0, "iclass_reference"

    elif stype == "youtube":
        vpath, title, duration = download_youtube_video(source, work_dir)
        return vpath, title, duration, "youtube"

    elif stype == "local_file":
        if not os.path.exists(source):
            raise RuntimeError(f"Local file does not exist: {source}")
        filename = os.path.basename(source)
        title = os.path.splitext(filename)[0]
        return source, title, 0.0, "local_file"

    elif stype == "url":
        # Attempt yt-dlp which handles dozens of video sites and direct URLs
        vpath, title, duration = download_youtube_video(source, work_dir)
        return vpath, title, duration, "url"

    else:
        raise ValueError(f"Unsupported or unrecognized video source: {source}")

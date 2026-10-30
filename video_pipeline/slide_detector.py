"""
Slide change detection and OCR module.
Extracts candidate frames, detects visual transitions, runs Tesseract OCR,
and merges duplicate/noisy slide pages.
"""

from difflib import SequenceMatcher
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .models import SlidePage


def is_tesseract_available() -> bool:
    """Check if tesseract executable is installed and available in PATH."""
    return shutil.which("tesseract") is not None


def get_available_tesseract_languages() -> List[str]:
    """Return the list of installed Tesseract language packs."""
    if not is_tesseract_available():
        return []
    try:
        res = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        lines = res.stdout.strip().splitlines()
        # First line is usually "List of available languages..."
        langs = [line.strip() for line in lines if line.strip() and not line.startswith("List of")]
        return langs
    except Exception:
        return []


def resolve_ocr_languages(preferred_lang: Optional[str] = None) -> str:
    """
    Resolve best available Tesseract languages.
    Prefers 'chi_tra+eng' when Traditional Chinese or auto is requested, falling back to 'eng'.
    """
    avail = get_available_tesseract_languages()
    if preferred_lang:
        return preferred_lang

    if "chi_tra" in avail and "eng" in avail:
        return "chi_tra+eng"
    if "chi_tra" in avail:
        return "chi_tra"
    if "chi_sim" in avail and "eng" in avail:
        return "chi_sim+eng"
    if "eng" in avail:
        return "eng"
    if avail:
        return avail[0]
    return "eng"


def run_tesseract_ocr(image_path: str, lang_str: Optional[str] = None) -> List[str]:
    """
    Execute tesseract OCR on an image file and return cleaned text lines.
    """
    if not is_tesseract_available():
        return []

    langs = lang_str or resolve_ocr_languages()
    cmd = ["tesseract", image_path, "stdout", "-l", langs]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        raw_text = res.stdout
    except Exception:
        return []

    lines = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if len(cleaned) >= 2:  # ignore isolated single punctuation or single noisy chars
            lines.append(cleaned)
    return lines


def _calculate_image_difference(img1, img2) -> float:
    """
    Compute normalized mean absolute pixel difference between two PIL images.
    """
    try:
        from PIL import ImageChops, ImageStat
        diff = ImageChops.difference(img1, img2)
        stat = ImageStat.Stat(diff)
        # stat.mean returns average difference per channel [0..255]
        return (sum(stat.mean) / len(stat.mean)) / 255.0
    except Exception:
        return 0.0


def extract_and_detect_slides(
    video_path: str,
    work_dir: str,
    sample_interval_sec: float = 2.0,
    diff_threshold: float = 0.12,
    debounce_sec: float = 4.0,
    total_duration: float = 0.0,
    ocr_lang: Optional[str] = None,
) -> List[SlidePage]:
    """
    Sample video frames, detect slide transitions, perform OCR, and return detected slide pages.

    :param video_path: Input video file.
    :param work_dir: Directory to store extracted slide frames.
    :param sample_interval_sec: Time in seconds between sampled frames (default: 2s).
    :param diff_threshold: Visual change threshold between frames to consider a slide change (default: 0.12).
    :param debounce_sec: Minimum duration a slide must persist to be considered a stable page (default: 4s).
    :param total_duration: Known video duration in seconds.
    :param ocr_lang: Tesseract language code(s).
    :return: List of SlidePage objects.
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "Pillow is required for slide detection. Install it with 'pip install pillow' or run install.sh --with-video."
        )

    frames_dir = os.path.join(work_dir, "raw_frames")
    slides_dir = os.path.join(work_dir, "slides")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)

    # 1. Extract frames at fixed interval using ffmpeg
    fps_val = f"1/{sample_interval_sec}"
    frame_pattern = os.path.join(frames_dir, "frame_%05d.jpg")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vf",
        f"fps={fps_val}",
        "-q:v",
        "2",
        frame_pattern,
    ]

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to extract video frames for slide detection: {str(e)}")

    frame_files = sorted([
        f for f in os.listdir(frames_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    ])

    if not frame_files:
        # Fallback to single page if no frames extracted
        return [
            SlidePage(
                page_number=1,
                start_seconds=0.0,
                end_seconds=total_duration,
                heading="Page 1",
                slide_text=[],
            )
        ]

    # 2. Compare adjacent frames downsampled to 160x90 grayscale
    candidate_transitions: List[Tuple[float, str]] = []  # (timestamp_sec, frame_path)
    prev_thumb = None

    for idx, fname in enumerate(frame_files):
        fpath = os.path.join(frames_dir, fname)
        timestamp = idx * sample_interval_sec
        try:
            with Image.open(fpath) as img:
                thumb = img.convert("L").resize((160, 90))
                if prev_thumb is None:
                    candidate_transitions.append((timestamp, fpath))
                    prev_thumb = thumb
                else:
                    diff = _calculate_image_difference(prev_thumb, thumb)
                    if diff >= diff_threshold:
                        candidate_transitions.append((timestamp, fpath))
                        prev_thumb = thumb
        except Exception:
            continue

    if not candidate_transitions:
        candidate_transitions = [(0.0, os.path.join(frames_dir, frame_files[0]))]

    # 3. Debounce rapid visual fluctuations (transitions/fades)
    debounced_slides: List[Tuple[float, str]] = [candidate_transitions[0]]
    for t_sec, fpath in candidate_transitions[1:]:
        last_t, _ = debounced_slides[-1]
        if (t_sec - last_t) >= debounce_sec:
            debounced_slides.append((t_sec, fpath))

    # Calculate end times for each detected slide
    raw_pages: List[SlidePage] = []
    num_slides = len(debounced_slides)

    for i, (start_t, frame_path) in enumerate(debounced_slides):
        end_t = debounced_slides[i + 1][0] if (i + 1 < num_slides) else total_duration
        if end_t <= start_t:
            end_t = start_t + sample_interval_sec

        # Copy retained frame to slides/
        saved_img_name = f"slide_{i + 1:03d}.jpg"
        saved_img_path = os.path.join(slides_dir, saved_img_name)
        try:
            shutil.copy2(frame_path, saved_img_path)
        except Exception:
            saved_img_path = frame_path

        # 4. Run OCR
        ocr_lines = run_tesseract_ocr(saved_img_path, lang_str=ocr_lang)

        # Determine heading
        heading = f"Page {i + 1}"
        if ocr_lines:
            # First line as candidate heading if reasonable length
            first_line = ocr_lines[0].strip()
            if len(first_line) > 1:
                heading = f"Page {i + 1}: {first_line}"

        raw_pages.append(
            SlidePage(
                page_number=i + 1,
                start_seconds=round(start_t, 2),
                end_seconds=round(end_t, 2),
                heading=heading,
                slide_text=ocr_lines,
                image_path=saved_img_path,
            )
        )

    # 5. Merge adjacent slides if text is nearly identical (>85% similarity)
    merged_pages: List[SlidePage] = []
    for page in raw_pages:
        if not merged_pages:
            merged_pages.append(page)
            continue

        prev_page = merged_pages[-1]
        text1 = " ".join(prev_page.slide_text)
        text2 = " ".join(page.slide_text)

        is_duplicate = False
        if text1 and text2:
            sim = SequenceMatcher(None, text1, text2).ratio()
            if sim >= 0.85:
                is_duplicate = True
        elif not text1 and not text2:
            # Both slides had no OCR text; check if duration was very brief
            if (page.end_seconds - prev_page.start_seconds) < (debounce_sec * 2):
                is_duplicate = True

        if is_duplicate:
            # Extend previous slide's end time
            prev_page.end_seconds = page.end_seconds
            # Keep longer slide text if one has slightly more details
            if len(page.slide_text) > len(prev_page.slide_text):
                prev_page.slide_text = page.slide_text
                prev_page.heading = page.heading
        else:
            merged_pages.append(page)

    # Re-number pages sequentially
    for idx, page in enumerate(merged_pages):
        page.page_number = idx + 1
        if page.heading.startswith("Page "):
            # Re-index "Page N: ..." prefix
            parts = page.heading.split(":", 1)
            if len(parts) == 2:
                page.heading = f"Page {idx + 1}:{parts[1]}"
            else:
                page.heading = f"Page {idx + 1}"

    # Clean up raw extracted frames to save disk space
    try:
        shutil.rmtree(frames_dir)
    except Exception:
        pass

    return merged_pages

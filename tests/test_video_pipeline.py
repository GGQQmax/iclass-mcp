"""
Unit and integration tests for the Video-to-Text lecture notes pipeline.
"""

import json
import os
import shutil
import tempfile
import unittest

from video_pipeline.aligner import (
    align_transcripts_to_slides,
    format_notes_markdown,
    format_page_markdown,
    format_timestamp,
    write_notes_artifacts,
)
from video_pipeline.audio import is_ffmpeg_available
from video_pipeline.downloader import infer_source_type
from video_pipeline.job_manager import VideoJobManager
from video_pipeline.models import (
    JobRecord,
    JobStatus,
    SlidePage,
    TranscriptSegment,
    VideoNotes,
)
from video_pipeline.slide_detector import (
    resolve_ocr_languages,
)
from video_pipeline.transcription import (
    DEFAULT_ZH_TW_PROMPT,
    MockTranscriber,
    get_transcriber,
)


class TestVideoPipelineModels(unittest.TestCase):
    def test_transcript_segment_serde(self):
        seg = TranscriptSegment(start_seconds=1.5, end_seconds=4.2, text="這是第一段演講。")
        d = seg.to_dict()
        self.assertEqual(d["start_seconds"], 1.5)
        self.assertEqual(d["end_seconds"], 4.2)
        self.assertEqual(d["text"], "這是第一段演講。")

        restored = TranscriptSegment.from_dict(d)
        self.assertEqual(restored.start_seconds, seg.start_seconds)
        self.assertEqual(restored.text, seg.text)

    def test_slide_page_serde(self):
        page = SlidePage(
            page_number=1,
            start_seconds=0.0,
            end_seconds=60.0,
            heading="Page 1: 細胞結構",
            slide_text=["- 細胞膜", "- 細胞核"],
            transcript_segments=[
                TranscriptSegment(0.0, 10.0, "細胞膜控制物質進出。")
            ],
        )
        d = page.to_dict()
        self.assertEqual(d["page_number"], 1)
        self.assertEqual(len(d["transcript_segments"]), 1)

        restored = SlidePage.from_dict(d)
        self.assertEqual(restored.heading, "Page 1: 細胞結構")
        self.assertEqual(len(restored.slide_text), 2)
        self.assertEqual(len(restored.transcript_segments), 1)

    def test_video_notes_serde(self):
        notes = VideoNotes(
            source="https://youtu.be/sample",
            title="生物學導論",
            duration_seconds=120.0,
            language="zh-TW",
            pages=[
                SlidePage(
                    page_number=1,
                    start_seconds=0.0,
                    end_seconds=120.0,
                    heading="Page 1: 課程簡介",
                    slide_text=["- 課程評分標準"],
                )
            ],
        )
        d = notes.to_dict()
        self.assertEqual(d["title"], "生物學導論")
        self.assertEqual(d["language"], "zh-TW")

        restored = VideoNotes.from_dict(d)
        self.assertEqual(restored.source, notes.source)
        self.assertEqual(len(restored.pages), 1)


class TestAudioAndDownloader(unittest.TestCase):
    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(0), "00:00")
        self.assertEqual(format_timestamp(45), "00:45")
        self.assertEqual(format_timestamp(75), "01:15")
        self.assertEqual(format_timestamp(3665), "01:01:05")

    def test_infer_source_type(self):
        self.assertEqual(
            infer_source_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "youtube",
        )
        self.assertEqual(
            infer_source_type("https://youtu.be/dQw4w9WgXcQ"),
            "youtube",
        )
        self.assertEqual(infer_source_type("1234567"), "iclass_reference")
        self.assertEqual(
            infer_source_type("1234567", explicit_type="iclass_activity"),
            "iclass_activity",
        )
        self.assertEqual(infer_source_type("https://example.com/stream.m3u8"), "url")


class TestTranscription(unittest.TestCase):
    def test_mock_transcriber(self):
        transcriber = get_transcriber("mock")
        segments = transcriber.transcribe("dummy.wav", language="zh-TW")
        self.assertTrue(len(segments) >= 2)
        self.assertIn("課", segments[0].text)

    def test_zh_tw_default_prompt(self):
        self.assertIn("繁體中文", DEFAULT_ZH_TW_PROMPT)

    def test_missing_backend_raises(self):
        with self.assertRaises(RuntimeError):
            get_transcriber("non_existent_backend")


class TestSlideDetectionAndOCR(unittest.TestCase):
    def test_resolve_ocr_languages(self):
        # Should return available languages or fallback without crashing
        resolved = resolve_ocr_languages()
        self.assertTrue(isinstance(resolved, str))
        self.assertTrue(len(resolved) > 0)


class TestAlignerAndArtifacts(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_alignment_logic(self):
        slides = [
            SlidePage(1, 0.0, 30.0, "Page 1: 簡介"),
            SlidePage(2, 30.0, 90.0, "Page 2: 演算法"),
        ]
        segments = [
            TranscriptSegment(5.0, 10.0, "歡迎各位同學。"),
            TranscriptSegment(35.0, 45.0, "接下來我們看排序演算法。"),
            TranscriptSegment(50.0, 60.0, "快速排序法的複雜度是 O(n log n)。"),
        ]

        aligned = align_transcripts_to_slides(slides, segments)
        self.assertEqual(len(aligned[0].transcript_segments), 1)
        self.assertEqual(aligned[0].transcript_segments[0].text, "歡迎各位同學。")
        self.assertEqual(len(aligned[1].transcript_segments), 2)
        self.assertEqual(aligned[1].transcript_segments[1].text, "快速排序法的複雜度是 O(n log n)。")

    def test_markdown_and_json_artifacts(self):
        notes = VideoNotes(
            source="iClass",
            title="Introduction to Biology",
            duration_seconds=7101.0,  # 01:58:21
            language="zh-TW",
            pages=[
                SlidePage(
                    page_number=1,
                    start_seconds=0.0,
                    end_seconds=272.0,  # 04:32
                    heading="Page 1: Cell Structure",
                    slide_text=["- Cell membrane", "- Nucleus", "- Cytoplasm"],
                    transcript_segments=[
                        TranscriptSegment(
                            0.0,
                            10.0,
                            "The membrane controls what enters and leaves the cell...",
                        )
                    ],
                )
            ],
        )

        md = format_notes_markdown(notes)
        self.assertIn("Title: Introduction to Biology", md)
        self.assertIn("Source: iClass", md)
        self.assertIn("Duration: 01:58:21", md)
        self.assertIn("Page 1: Cell Structure", md)
        self.assertIn("Time: 00:00–04:32", md)
        self.assertIn("Cell membrane", md)
        self.assertIn("The membrane controls what enters and leaves the cell...", md)

        md_path, json_path = write_notes_artifacts(notes, self.test_dir)
        self.assertTrue(os.path.exists(md_path))
        self.assertTrue(os.path.exists(json_path))

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["title"], "Introduction to Biology")
            self.assertEqual(len(data["pages"]), 1)


class TestJobManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = VideoJobManager(cache_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_job_lifecycle_and_notes_query(self):
        # Create a synthetic completed job
        record = self.manager.create_job(source="https://youtu.be/sample", source_type="youtube")
        record.status = JobStatus.COMPLETE.value
        record.stage = "complete"
        record.progress = 1.0
        record.title = "作業系統實作"
        record.duration_seconds = 300.0

        notes = VideoNotes(
            source=record.source,
            title=record.title,
            duration_seconds=record.duration_seconds,
            language="zh-TW",
            pages=[
                SlidePage(
                    page_number=1,
                    start_seconds=0.0,
                    end_seconds=150.0,
                    heading="Page 1: Process and Thread",
                    slide_text=["- Process memory layout", "- Thread stack"],
                    transcript_segments=[
                        TranscriptSegment(10.0, 20.0, "行程是作業系統分配資源的基本單位。"),
                        TranscriptSegment(30.0, 40.0, "執行緒共用同一個行程的記憶體空間。"),
                    ],
                ),
                SlidePage(
                    page_number=2,
                    start_seconds=150.0,
                    end_seconds=300.0,
                    heading="Page 2: Deadlock Detection",
                    slide_text=["- Mutual exclusion", "- Hold and wait"],
                    transcript_segments=[
                        TranscriptSegment(160.0, 180.0, "死結的四個必要條件包含互斥與佔有並等待。"),
                    ],
                ),
            ],
        )
        md_path, json_path = write_notes_artifacts(notes, record.work_dir)
        record.artifact_notes_md = md_path
        record.artifact_notes_json = json_path
        self.manager._save_job(record)

        # 1. Test mutually exclusive parameters
        res = self.manager.query_notes(record.job_id, page=1, query="行程")
        self.assertIn("error", res)
        self.assertIn("mutually exclusive", res["error"])

        # 2. Test outline (neither page nor query)
        outline_res = self.manager.query_notes(record.job_id)
        self.assertIn("outline", outline_res)
        self.assertEqual(outline_res["total_pages"], 2)
        self.assertIn("Page 1: Process and Thread", outline_res["outline"])

        # 3. Test specific page
        page_res = self.manager.query_notes(record.job_id, page=1)
        self.assertEqual(page_res["page"], 1)
        self.assertIn("Process memory layout", page_res["content"])
        self.assertIn("行程是作業系統分配資源的基本單位", page_res["content"])

        # 4. Test page out of bounds
        err_res = self.manager.query_notes(record.job_id, page=99)
        self.assertIn("error", err_res)
        self.assertIn("out of bounds", err_res["error"])

        # 5. Test search query
        query_res = self.manager.query_notes(record.job_id, query="死結")
        self.assertIn("results", query_res)
        self.assertEqual(query_res["matches_found"], 1)
        self.assertIn("Deadlock Detection", query_res["results"])
        self.assertIn("死結的四個必要條件", query_res["results"])

    def test_end_to_end_pipeline_execution(self):
        import asyncio
        import subprocess

        # Create a synthetic 2-second video with ffmpeg
        video_file = os.path.join(self.test_dir, "synthetic_lecture.mp4")
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=320x240:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=f=1000:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            video_file,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=15)
        except Exception:
            self.skipTest("ffmpeg not available or failed to create synthetic video")

        record = self.manager.create_job(source=video_file, source_type="local_file")

        # Run pipeline synchronously in event loop with mock STT backend
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self.manager._execute_pipeline(
                    record=record,
                    source=video_file,
                    source_type="local_file",
                    course_id=None,
                    activity_id=None,
                    language="zh-TW",
                    stt_backend="mock",
                    api_instance=None,
                )
            )
        finally:
            loop.close()

        updated_record = self.manager.get_job(record.job_id)
        self.assertEqual(updated_record.status, JobStatus.COMPLETE.value)
        self.assertEqual(updated_record.stage, "complete")
        self.assertTrue(os.path.exists(updated_record.artifact_notes_md))
        self.assertTrue(os.path.exists(updated_record.artifact_notes_json))

        notes = self.manager.load_notes_json(record.job_id)
        self.assertIsNotNone(notes)
        self.assertTrue(len(notes.pages) >= 1)



if __name__ == "__main__":
    unittest.main()

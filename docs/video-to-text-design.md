# Video-to-text design

## Goal

Turn a lecture video into compact, timestamped notes that an AI can search and read without sending a two-hour video or a large set of frames to the model. The first version supports YouTube URLs and iClass video uploads.

The expected lecture format is a PowerPoint presentation with the teacher's voice recorded over it. The useful unit is a slide/page and its spoken explanation.

## User flow

1. The user provides a YouTube URL or an iClass video reference/activity.
2. The tool obtains the video through `yt-dlp` or the existing authenticated iClass API.
3. A local processing pipeline extracts audio, detects slide changes, recognizes slide text, and transcribes speech with timestamps.
4. The pipeline associates each speech segment with the slide visible at that time and writes a notes artifact.
5. MCP returns a short title, page count, and artifact ID. A separate read/search tool returns only requested pages or matching passages.

## Note format

Human-readable Markdown should be the default artifact, with structured JSON available for programmatic use. A page entry should follow this shape:

```text
Title: Introduction to Biology
Source: iClass
Duration: 01:58:21

Page 1: Cell Structure
Time: 00:00–04:32
Slide text:
- Cell membrane
- Nucleus
- Cytoplasm
Teacher explanation:
The membrane controls what enters and leaves the cell...
```

The JSON representation should retain `source`, `title`, `duration_seconds`, `pages`, and per-page `page_number`, `start_seconds`, `end_seconds`, `heading`, `slide_text`, and timestamped `transcript_segments`. Keep verbatim transcript content separate from any generated summary so users can distinguish recognition from interpretation.

## Processing pipeline

### 1. Acquire source

- YouTube: invoke `yt-dlp` as a subprocess, request the best available audio/video streams, and record the canonical URL and metadata. Make it possible to process audio-only when visual slide detection is unnecessary or video is unavailable.
- iClass: resolve the activity/upload metadata, then use the authenticated `TronClassAPI.download(reference_id)` path. Keep the source reference and course/activity identifiers in metadata. The downloader currently writes to `~/Downloads`; the video pipeline should eventually support an explicit job work directory to avoid filename collisions.
- Do not upload lecture media to a third-party service by default. Keep processing local unless a future provider is deliberately configured.

### 2. Extract speech

Extract mono audio for transcription. Produce timestamped segments, not just one transcript string. The initial implementation can use an optional local speech-to-text backend such as faster-whisper; backend choice should sit behind a small interface so another transcription service can be added later. Preserve the original transcript and language metadata.

### 3. Find slide pages

Sample video frames and compare them to detect visual changes. Only retain representative frames when the slide changes; do not send every frame to a vision model. OCR the retained frames to recover slide text. Merge adjacent detections when the slide image/text is effectively unchanged, and ignore brief transitions or fades.

If the original PowerPoint file can be identified alongside an iClass video, prefer extracting its slide text and page order, then align pages to detected timestamps. This is a follow-up integration: the initial workflow must work from video alone.

### 4. Align and write notes

Assign each transcript segment to the slide active at its timestamp. Use slide OCR text as the page heading/content, and keep teacher speech as timestamped explanation. Do not invent a heading when OCR finds none; use `Page N` and an optional short generated label only when explicitly marked as generated. Write Markdown and JSON next to the job output.

## MCP surface

Keep the first version small:

- `process_video(source, source_type?, course_id?, activity_id?)`: validate and acquire the source, start processing, and return a job ID/status. Source type can be inferred from a URL or iClass identifiers.
- `get_video_notes(job_id, page?, query?, max_chars?)`: return metadata and a selected page, or a small set of matching passages. Page and query should be mutually exclusive. Set a conservative output cap to control context use.
- `get_video_job(job_id)`: report progress, failure details, and artifact location.

Long-running work should not hold an MCP request open for the full duration of a lecture. Start with a local job record and status polling. Store artifacts in a configurable cache directory, use stable IDs, and document cleanup/retention. Avoid returning full transcripts by default.

## MVP boundaries

Include YouTube and iClass source acquisition, timestamped speech transcription, slide-change detection, OCR, page alignment, a Markdown/JSON artifact, and selective page retrieval. Defer multi-speaker diarization, semantic chapter summaries, PowerPoint discovery, cloud processing, and automatic video-question answering.

## Dependencies and operational considerations

- `yt-dlp` is an external executable/package and should be optional until installed; report a clear setup error when a YouTube job is requested without it.
- Local transcription and OCR/video processing add sizable dependencies and may need model downloads. Keep them optional and load them only when video tools are invoked.
- Enforce source size/duration limits, subprocess timeouts, safe temporary paths, and cleanup on failure. Never interpolate a user URL into a shell command; pass arguments as a list.
- Make processing stages observable (`downloading`, `transcribing`, `detecting_slides`, `aligning`, `complete`/`failed`) so an MCP client can report useful status.
- OCR/transcription are imperfect. Keep timestamps and original extracted text so a user can verify a page against the video.

## Acceptance criteria

- Both YouTube URLs and iClass video references reach the same normalized processing pipeline.
- A lecture produces one ordered entry per detected slide with start/end times, extracted slide text, and the speech aligned to that interval.
- The initial tool response stays small; a caller can fetch an individual page without retrieving the full artifact.
- A failed or unavailable optional dependency produces a specific job error and does not leave a partial artifact presented as complete.

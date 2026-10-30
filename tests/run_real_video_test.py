"""
Real-world test script for processing an iClass video activity.
Runs the pipeline through MCP tools and monitors progress to completion.
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import iclass_mcp_server


async def main():
    url = "https://iclass.tku.edu.tw/course/265086/learning-activity#/2039528"
    print(f"=== Starting Video-to-Text Test on: {url} ===")

    # 1. Start job
    start_res = await iclass_mcp_server.process_video(source=url)
    print("process_video returned:", start_res)

    job_id = start_res.get("job_id")
    if not job_id:
        print("Failed to start job:", start_res)
        sys.exit(1)

    # 2. Poll get_video_job until complete or failed
    last_stage = None
    last_progress = None
    start_time = time.time()

    while True:
        job = await iclass_mcp_server.get_video_job(job_id)
        status = job.get("status")
        stage = job.get("stage")
        progress = job.get("progress")

        if stage != last_stage or progress != last_progress:
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed}s] Status: {status} | Stage: {stage} | Progress: {progress}")
            last_stage = stage
            last_progress = progress

        if status == "complete":
            elapsed = int(time.time() - start_time)
            print(f"\n[✓] Job completed successfully in {elapsed}s!")
            print(f"Title: {job.get('title')}")
            print(f"Total Pages: {job.get('total_pages')}")
            print(f"Duration: {job.get('duration_seconds')}s")
            print(f"Artifact Markdown: {job.get('artifact_notes_md')}")
            break
        elif status == "failed":
            print(f"\n[✗] Job failed: {job.get('error')}")
            sys.exit(1)

        await asyncio.sleep(4)

    # 3. Test get_video_notes outline
    print("\n=== 1. Testing get_video_notes (Outline) ===")
    outline_res = await iclass_mcp_server.get_video_notes(job_id)
    print(outline_res.get("outline", outline_res))

    # 4. Test get_video_notes page 1
    print("\n=== 2. Testing get_video_notes (Page 1) ===")
    page1_res = await iclass_mcp_server.get_video_notes(job_id, page=1)
    print(page1_res.get("content", page1_res))

    # 5. Test get_video_notes keyword query
    print("\n=== 3. Testing get_video_notes (Query: '數位轉型') ===")
    query_res = await iclass_mcp_server.get_video_notes(job_id, query="數位轉型")
    print(f"Matches found: {query_res.get('matches_found', 0)}")
    print(query_res.get("results", query_res.get("message", query_res)))


if __name__ == "__main__":
    asyncio.run(main())

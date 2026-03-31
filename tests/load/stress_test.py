import asyncio
import aiohttp
import time
import sys

# Configuration
# Point to your API gateway (assuming it routes /api/v1 to port 8000 internally)
API_BASE_URL = "http://localhost:8085/api/v1" 
CONCURRENT_REQUESTS = 50  
TIMEOUT_SECONDS = 30

async def send_transcription_request(session, request_id):
    """Simulates a user requesting an upload URL, uploading a file, and starting the job."""
    start_time = time.time()
    try:
        # ---------------------------------------------------------
        # STEP 1: Get Upload URL & Create Job in DB
        # ---------------------------------------------------------
        presign_payload = {
            "filename": f"stress_test_video_{request_id}.mp4",
            "content_type": "video/mp4"
        }
        
        async with session.post(f"{API_BASE_URL}/upload/presign", json=presign_payload, timeout=TIMEOUT_SECONDS) as presign_res:
            if presign_res.status != 200:
                print(f"❌ Req {request_id:02d}: Presign Failed - Status {presign_res.status}")
                return
            
            data = await presign_res.json()
            job_id = data["job_id"]
            upload_url = data["upload_url"]
            file_identifier = data["file_identifier"]

        # ---------------------------------------------------------
        # STEP 2: Upload a tiny dummy file to the generated URL
        # ---------------------------------------------------------
        dummy_video_bytes = b"fake video content for stress test"
        
        # We use a PUT request here, just like the frontend does
        async with session.put(upload_url, data=dummy_video_bytes, timeout=TIMEOUT_SECONDS) as upload_res:
            if upload_res.status != 200:
                print(f"❌ Req {request_id:02d}: Upload Failed - Status {upload_res.status}")
                return

        # ---------------------------------------------------------
        # STEP 3: Trigger the Worker Queue
        # ---------------------------------------------------------
        start_payload = {
            "job_id": job_id,
            "file_identifier": file_identifier
        }
        
        async with session.post(f"{API_BASE_URL}/transcribe/start", json=start_payload, timeout=TIMEOUT_SECONDS) as start_res:
            duration = time.time() - start_time
            if start_res.status == 200:
                print(f"✅ Req {request_id:02d}: Job {job_id[:8]} Queued ({duration:.2f}s)")
            else:
                print(f"⚠️ Req {request_id:02d}: Start Failed - Status {start_res.status} ({duration:.2f}s)")
                
    except asyncio.TimeoutError:
        print(f"⏳ Req {request_id:02d}: Timed out!")
    except Exception as e:
        print(f"❌ Req {request_id:02d}: Failed - {str(e)}")

async def run_stress_test():
    print(f"🚀 Initializing Stress Test: Sending {CONCURRENT_REQUESTS} concurrent requests...")
    print(f"🔗 Targeting: {API_BASE_URL}")
    print("-" * 50)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(1, CONCURRENT_REQUESTS + 1):
            tasks.append(send_transcription_request(session, i))
        
        # Execute all requests concurrently
        start_test = time.time()
        await asyncio.gather(*tasks)
        total_duration = time.time() - start_test

    print("-" * 50)
    print(f"🏁 Stress Test Complete!")
    print(f"⏱️ Total Time: {total_duration:.2f} seconds")
    print(f"📊 Avg Throughput: {CONCURRENT_REQUESTS / total_duration:.2f} workflows/sec")
    print("\n👉 Check your Docker / Kubernetes logs to watch the queue drain!")

if __name__ == "__main__":
    try:
        asyncio.run(run_stress_test())
    except KeyboardInterrupt:
        print("\n🚫 Test aborted by user.")
        sys.exit(0)
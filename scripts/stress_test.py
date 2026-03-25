import asyncio
import aiohttp
import time
import sys

# Configuration
# Since you have NGINX setup, we point to the main LoadBalancer/Gateway URL
API_URL = "http://localhost/api/v1/transcribe"
CONCURRENT_REQUESTS = 50  # Number of videos to "upload" at once
TIMEOUT_SECONDS = 30

async def send_transcription_request(session, request_id):
    """Simulates a user submitting a video for transcription."""
    payload = {
        "video_url": f"https://www.youtube.com/watch?v=mock_id_{request_id}",
        "metadata": {"test_run": True}
    }
    
    start_time = time.time()
    try:
        async with session.post(API_URL, json=payload, timeout=TIMEOUT_SECONDS) as response:
            duration = time.time() - start_time
            if response.status == 202:
                print(f"✅ Request {request_id:02d}: Accepted ({duration:.2f}s)")
            else:
                print(f"⚠️ Request {request_id:02d}: Status {response.status} ({duration:.2f}s)")
    except Exception as e:
        print(f"❌ Request {request_id:02d}: Failed - {str(e)}")

async def run_stress_test():
    print(f"🚀 Initializing Stress Test: Sending {CONCURRENT_REQUESTS} concurrent requests...")
    print(f"🔗 Targeting: {API_URL}")
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
    print(f"📊 Avg Throughput: {CONCURRENT_REQUESTS / total_duration:.2f} requests/sec")
    print("\n👉 Check Grafana (http://localhost/grafana) to see KEDA scaling!")

if __name__ == "__main__":
    try:
        asyncio.run(run_stress_test())
    except KeyboardInterrupt:
        print("\n🚫 Test aborted by user.")
        sys.exit(0)
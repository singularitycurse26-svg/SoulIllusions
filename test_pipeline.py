import urllib.request, json, time, os

SERVER = "http://localhost:7860"
MOCK_BACKEND = "http://localhost:9000"

# Step 1: Set the mock backend URL
print("1. Connecting mock backend to SoulIllusions...")
payload = json.dumps({"url": MOCK_BACKEND}).encode("utf-8")
req = urllib.request.Request(f"{SERVER}/api/config/backend", data=payload, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=10) as resp:
    print(f"   Backend set: {resp.read().decode()}")

# Step 2: Verify backend status
print("\n2. Checking backend status...")
req2 = urllib.request.Request(f"{SERVER}/api/backend/status", headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req2, timeout=10) as resp2:
    status = json.loads(resp2.read().decode())
    print(f"   Status: {status['status']}")
    print(f"   GPU: {status.get('gpu', 'N/A')}")

# Step 3: Generate a test video
print("\n3. Submitting video generation request...")
gen_payload = {
    "prompt": "A man walking through a neon-lit dystopian city street at night, rain falling, cinematic",
    "model": "ltx",
    "style": "cinematic",
    "num_frames": 24,
    "fps": 24,
    "steps": 10,
    "width": 768,
    "height": 512,
}
req_data = json.dumps(gen_payload).encode("utf-8")
req3 = urllib.request.Request(f"{SERVER}/api/generate", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req3, timeout=30) as resp3:
    result = json.loads(resp3.read().decode())
    print(f"   Response: {json.dumps(result, indent=2)}")
    job_id = result.get("job_id")

if not job_id:
    print("ERROR: No job_id!")
    exit(1)

# Step 4: Poll for completion
print(f"\n4. Waiting for video (job: {job_id})...")
for i in range(30):
    time.sleep(2)
    req4 = urllib.request.Request(f"{MOCK_BACKEND}/api/status/{job_id}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req4, timeout=10) as resp4:
            st = json.loads(resp4.read().decode())
            print(f"   [{i*2}s] {st['status']}")
            if st["status"] == "complete":
                print(f"   Video file: {st.get('output')}")
                # Step 5: Download through SoulIllusions
                print("\n5. Downloading video through SoulIllusions...")
                req5 = urllib.request.Request(f"{MOCK_BACKEND}/api/download/{job_id}", headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req5, timeout=30) as resp5:
                    video_data = resp5.read()
                    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "test_video.mp4")
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(video_data)
                    print(f"   Video saved: {save_path}")
                    print(f"   Size: {len(video_data)/1024:.0f} KB")
                print("\n=== TEST PASSED! Full pipeline works! ===")
                break
            elif st["status"] == "failed":
                print(f"   FAILED: {st.get('error')}")
                break
    except Exception as e:
        print(f"   [{i*2}s] Error: {e}")
else:
    print("\nTimeout!")

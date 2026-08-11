import urllib.request, json

# Check mock backend directly
print("=== Mock Backend (port 9000) ===")
try:
    req = urllib.request.Request("http://localhost:9000/api/status", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"Status: {json.loads(resp.read().decode())}")
except Exception as e:
    print(f"Error: {e}")

# Check SoulIllusions server
print("\n=== SoulIllusions Server (port 7860) ===")
try:
    req = urllib.request.Request("http://localhost:7860/api/backend/status", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"Status: {json.loads(resp.read().decode())}")
except Exception as e:
    print(f"Error: {e}")

# Try generating directly through mock backend
print("\n=== Direct generate test on mock backend ===")
try:
    payload = json.dumps({
        "prompt": "test video",
        "model": "ltx",
        "num_frames": 12,
        "fps": 24,
        "width": 320,
        "height": 240,
    }).encode("utf-8")
    req = urllib.request.Request("http://localhost:9000/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        print(f"Generate: {result}")
        job_id = result.get("job_id")
        
    if job_id:
        import time
        for i in range(30):
            time.sleep(2)
            req2 = urllib.request.Request(f"http://localhost:9000/api/status/{job_id}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                st = json.loads(resp2.read().decode())
                print(f"  [{i*2}s] {st['status']}")
                if st["status"] in ("complete", "failed"):
                    print(f"  Full: {json.dumps(st, indent=2)}")
                    if st["status"] == "complete":
                        # Download it
                        req3 = urllib.request.Request(f"http://localhost:9000/api/download/{job_id}", headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req3, timeout=30) as resp3:
                            data = resp3.read()
                            save_path = r"C:\Users\hawpe\CascadeProjects\SoulIllusions\outputs\test_video.mp4"
                            import os
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(data)
                            print(f"\n  Video saved: {save_path}")
                            print(f"  Size: {len(data)/1024:.0f} KB")
                        print("\n=== PIPELINE TEST PASSED! ===")
                    break
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

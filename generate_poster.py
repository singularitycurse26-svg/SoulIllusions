import urllib.request, urllib.parse, os, json, time, sys

SERVER = "http://localhost:7860"

prompt = (
    "TV series poster for In Time, based on the 2011 film In Time starring Justin Timberlake and Amanda Seyfried. "
    "Dystopian future where time is currency and people stop aging at 25. "
    "A young man with tousled brown hair and determined expression in foreground, "
    "his forearm displaying a glowing neon green digital countdown clock. "
    "Behind him a wealthy young blonde woman in a silver dress looking back with defiance. "
    "Background splits between grimy industrial ghetto with orange streetlights and gleaming futuristic luxury skyline with green-lit towers. "
    "Dark gritty tone with neon green accents. Cinematic composition, dramatic lighting, high contrast, professional TV poster design. "
    "Space at top for title text"
)

save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "intime_poster.png")
os.makedirs(os.path.dirname(save_path), exist_ok=True)

def generate_via_gpu_backend():
    """Generate poster through SoulIllusions GPU backend (SDXL)."""
    print("Generating In Time TV poster via GPU backend (SDXL)...")
    payload = json.dumps({
        "prompt": prompt,
        "model": "sdxl",
        "aspect_ratio": "2:3",
        "quality": "pro",
        "style_preset": "poster",
        "guidance_scale": 8.0,
        "steps": 40,
        "batch_count": 1,
        "negative_prompt": "worst quality, low quality, blurry, distorted, deformed, ugly, bad anatomy, watermark, text artifact, extra fingers, missing fingers, cropped, out of frame"
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{SERVER}/api/image/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        job_id = result.get("job_id")

    if not job_id:
        print("ERROR: No job_id returned!")
        return False

    print(f"Job ID: {job_id}")
    print("Waiting for SDXL generation...")

    for i in range(120):
        time.sleep(5)
        try:
            req2 = urllib.request.Request(f"{SERVER}/api/image/status/{job_id}")
            with urllib.request.urlopen(req2, timeout=15) as resp2:
                status = json.loads(resp2.read().decode())
                print(f"  [{i*5}s] {status['status']}")
                if status['status'] == 'complete':
                    # Download through SoulIllusions
                    img_req = urllib.request.Request(f"{SERVER}/api/image/download/{job_id}")
                    with urllib.request.urlopen(img_req, timeout=30) as img_resp:
                        img_data = img_resp.read()
                        with open(save_path, "wb") as f:
                            f.write(img_data)
                    print(f"\nPoster saved to: {save_path}")
                    print(f"File size: {len(img_data) / 1024:.0f} KB")
                    return True
                elif status['status'] == 'failed':
                    print(f"FAILED: {status.get('error', 'Unknown')}")
                    return False
        except Exception as e:
            print(f"  [{i*5}s] Error: {e}")
    print("Timeout!")
    return False

def generate_via_pollinations():
    """Fallback: generate via free Pollinations.ai API (no GPU needed)."""
    print("Generating In Time TV poster via Pollinations.ai (fallback)...")
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=832&height=1216&nologo=true&seed=42"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        img_data = resp.read()
        with open(save_path, "wb") as f:
            f.write(img_data)
    print(f"\nPoster saved to: {save_path}")
    print(f"File size: {len(img_data) / 1024:.0f} KB")
    return True

# Try GPU backend first, fall back to Pollinations
try:
    req = urllib.request.Request(f"{SERVER}/api/backend/status", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        status = json.loads(resp.read().decode())
    if status.get("status") == "online":
        print(f"GPU backend online: {status.get('gpu', 'Unknown')}")
        success = generate_via_gpu_backend()
        if success:
            print("Done!")
            sys.exit(0)
    else:
        print(f"GPU backend offline: {status.get('error', 'Unknown')}")
except Exception as e:
    print(f"Could not reach SoulIllusions server: {e}")

print("\nFalling back to Pollinations.ai (free, no GPU)...")
generate_via_pollinations()
print("Done!")

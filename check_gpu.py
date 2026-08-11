import urllib.request, json

BACKEND = "https://free-donkeys-guess.loca.lt"

headers = {"User-Agent": "Mozilla/5.0"}

# Check if image endpoints are live
try:
    req = urllib.request.Request(f"{BACKEND}/api/image/options", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
        print("Image options endpoint: LIVE!")
        print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Image options endpoint: NOT LIVE - {e}")

# Check main status
try:
    req2 = urllib.request.Request(f"{BACKEND}/api/status", headers=headers)
    with urllib.request.urlopen(req2, timeout=15) as resp2:
        status = json.loads(resp2.read().decode())
        print(f"\nBackend status: {status['status']}")
        print(f"GPU: {status['gpu']}")
        print(f"VRAM free: {status['vram_free']}")
        print(f"Features: {status.get('features', [])}")
except Exception as e:
    print(f"Backend status check failed: {e}")

# Try root
try:
    req3 = urllib.request.Request(f"{BACKEND}/", headers=headers)
    with urllib.request.urlopen(req3, timeout=15) as resp3:
        root = json.loads(resp3.read().decode())
        print(f"\nRoot: {json.dumps(root, indent=2)}")
except Exception as e:
    print(f"Root check failed: {e}")

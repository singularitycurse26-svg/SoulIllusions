import urllib.request, json, sys

SERVER = "http://localhost:7860"

# Accept backend URL from command line: python connect_gpu.py https://your-url.lightning.ai:8000
if len(sys.argv) > 1:
    BACKEND_URL = sys.argv[1].strip().rstrip("/")
else:
    BACKEND_URL = input("Paste your GPU backend URL: ").strip().rstrip("/")

if not BACKEND_URL:
    print("No URL provided. Usage: python connect_gpu.py https://your-backend-url")
    sys.exit(1)

print(f"Connecting SoulIllusions to: {BACKEND_URL}")

# Set the backend URL
payload = json.dumps({"url": BACKEND_URL}).encode("utf-8")
req = urllib.request.Request(
    f"{SERVER}/api/config/backend",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read().decode())
    print(f"Set backend: {result}")

# Check backend status
req2 = urllib.request.Request(f"{SERVER}/api/backend/status")
with urllib.request.urlopen(req2) as resp2:
    status = json.loads(resp2.read().decode())
    print(f"\nBackend status: {json.dumps(status, indent=2)}")

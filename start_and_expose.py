import subprocess
import time
import sys
import os

WORK_DIR = '/teamspace/studios/this_studio'

# Start the backend in background
print("Starting lightning_backend.py in background...")
proc = subprocess.Popen(
    [sys.executable, os.path.join(WORK_DIR, 'lightning_backend.py')],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)
print(f"Backend PID: {proc.pid}")

# Wait for server to start
print("Waiting for server to start...")
for i in range(30):
    time.sleep(2)
    try:
        import urllib.request
        req = urllib.request.Request('http://localhost:8000/api/status')
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode()
            print(f"Server is up! Response: {data}")
            break
    except:
        print(f"  Waiting... ({i*2}s)")
else:
    print("Server didn't start in time!")
    proc.terminate()
    sys.exit(1)

# Expose port and get URL
print("Exposing port 8000...")
try:
    from lightning_sdk import Studio
    s = Studio()
    ports = s.add_ports(8000)
    if ports:
        url = ports[0].urls[0]
        print(f"PUBLIC_URL={url}")
        # Write to file for SCP retrieval
        with open(os.path.join(WORK_DIR, 'backend_url.txt'), 'w') as f:
            f.write(url)
        print(f"URL saved to {WORK_DIR}/backend_url.txt")
    else:
        print("Failed to expose port")
except Exception as e:
    print(f"Error exposing port: {e}")
    # Try alternate method
    try:
        import urllib.request
        # The URL pattern is predictable
        studio_id = os.environ.get('LIGHTNING_STUDIO_ID', '')
        if not studio_id:
            # Try to get from SDK
            from lightning_sdk import Studio
            s = Studio()
            studio_id = s._studio.id if hasattr(s, '_studio') else ''
        if studio_id:
            url = f"https://8000-{studio_id}.cloudspaces.litng.ai"
            print(f"PUBLIC_URL={url}")
            with open(os.path.join(WORK_DIR, 'backend_url.txt'), 'w') as f:
                f.write(url)
            print(f"URL saved to {WORK_DIR}/backend_url.txt")
    except Exception as e2:
        print(f"Alternate method also failed: {e2}")

print("\n=== DONE ===")
print("Backend is running. URL saved to backend_url.txt")
print("Keep this terminal open - the backend is running in background.")

"""Connect SoulIllusions to a Hugging Face Spaces GPU backend."""
import sys
import json
import urllib.request

def main():
    if len(sys.argv) < 2:
        print("Usage: python connect_hf.py <hf-space-url>")
        print("Example: python connect_hf.py https://yourusername-soulillusions-gpu-backend.hf.space")
        sys.exit(1)
    
    url = sys.argv[1].rstrip("/")
    
    # Test connection
    try:
        req = urllib.request.Request(
            f"{url}/api/status",
            data=json.dumps({"data": []}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode())
            data = raw.get("data", [{}])[0] if isinstance(raw, dict) else raw
            print(f"Connected! GPU: {data.get('gpu', 'Unknown')}")
            print(f"Models: {data.get('models', [])}")
    except Exception as e:
        print(f"Connection failed: {e}")
        print(f"Make sure the Space is running at: {url}")
        sys.exit(1)
    
    # Save to config
    from pathlib import Path
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
    else:
        config = {}
    
    config["gpu_backend_url"] = url
    config["backend_type"] = "gradio"
    config_path.write_text(json.dumps(config, indent=2))
    print(f"Saved to config.json")
    print(f"Backend type: gradio (HF Spaces ZeroGPU)")
    print(f"URL: {url}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SoulIllusions Kaggle Auto — Multi-account GPU automation.

Pushes the Kaggle notebook, waits for it to run, extracts the tunnel URL,
and connects SoulIllusions automatically. Rotates between 3 accounts for
90 hrs/week total GPU.

Usage:
    py kaggle_auto.py              # Start/rotate GPU backend
    py kaggle_auto.py --status     # Check current status
    py kaggle_auto.py --stop       # Stop current notebook
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).parent
ACCOUNTS_FILE = SCRIPT_DIR / "kaggle_accounts.json"
NOTEBOOK_FILE = SCRIPT_DIR / "SoulIllusions_Kaggle_Backend.ipynb"
CONFIG_FILE = SCRIPT_DIR / "config.json"
KAGGLE_META_DIR = SCRIPT_DIR / ".kaggle_meta"

WEEKLY_HOURS = 30
MAX_HOURS = 29  # safety margin


def load_accounts():
    if not ACCOUNTS_FILE.exists():
        print(f"Error: {ACCOUNTS_FILE} not found")
        sys.exit(1)
    return json.loads(ACCOUNTS_FILE.read_text())


def save_accounts(data):
    ACCOUNTS_FILE.write_text(json.dumps(data, indent=2))


def reset_weekly_if_needed(data):
    week_start = datetime.fromisoformat(data.get("week_start", "2026-01-01"))
    now = datetime.now()
    if (now - week_start).days >= 7:
        for acc in data["accounts"]:
            acc["hours_used"] = 0
            acc["last_session"] = None
        data["week_start"] = now.date().isoformat()
        data["active_account"] = 0
        save_accounts(data)
        print("[Weekly reset] All account quotas reset.")


def pick_account(data):
    for i, acc in enumerate(data["accounts"]):
        if acc["hours_used"] < MAX_HOURS:
            return i, acc
    print("All accounts exhausted for this week. Reset happens weekly.")
    sys.exit(1)


def set_kaggle_token(token):
    os.environ["KAGGLE_API_TOKEN"] = token
    token_file = Path.home() / ".kaggle" / "access_token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token)


def create_metadata(account_idx, slug):
    KAGGLE_META_DIR.mkdir(exist_ok=True)
    meta_dir = KAGGLE_META_DIR / f"account_{account_idx}"
    meta_dir.mkdir(exist_ok=True)

    accounts = json.loads(ACCOUNTS_FILE.read_text())
    username = accounts["accounts"][account_idx]["username"]
    meta = {
        "id": f"{username}/{slug}",
        "title": "SoulIllusions GPU Backend",
        "code_file": "SoulIllusions_Kaggle_Backend.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": "true",
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [],
        "kernel_sources": [],
        "competition_sources": [],
        "model_sources": [],
    }
    meta_path = meta_dir / "kernel-metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    import shutil
    nb_dest = meta_dir / "SoulIllusions_Kaggle_Backend.ipynb"
    shutil.copy2(NOTEBOOK_FILE, nb_dest)

    return meta_dir


def push_kernel(meta_dir, token):
    env = {**os.environ, "KAGGLE_API_TOKEN": token}
    # Use Python API directly for better accelerator control
    push_script = f"""
import json
from kaggle import KaggleApi
api = KaggleApi()
api.authenticate()
resp = api.kernels_push(folder=r'{meta_dir}', acc='NvidiaTeslaT4')
print(json.dumps({{"ref": resp.ref, "url": resp.url, "version": resp.version_number, "error": resp.error}}))
"""
    result = subprocess.run(
        [sys.executable, "-c", push_script],
        capture_output=True, text=True, env=env, timeout=120
    )
    if result.returncode != 0:
        print(f"Push failed: {result.stderr}")
        return False
    print(f"Push output: {result.stdout.strip()}")
    return True


def get_kernel_status(slug, account_idx, token):
    env = {**os.environ, "KAGGLE_API_TOKEN": token}
    accounts = json.loads(ACCOUNTS_FILE.read_text())
    username = accounts["accounts"][account_idx]["username"]
    kernel_id = f"{username}/{slug}"
    result = subprocess.run(
        [sys.executable, "-m", "kaggle", "kernels", "status", kernel_id],
        capture_output=True, text=True, env=env, timeout=30
    )
    return result.stdout.strip() + result.stderr.strip()


def pull_kernel_output(slug, account_idx, token, output_dir):
    env = {**os.environ, "KAGGLE_API_TOKEN": token}
    accounts = json.loads(ACCOUNTS_FILE.read_text())
    username = accounts["accounts"][account_idx]["username"]
    kernel_id = f"{username}/{slug}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "kaggle", "kernels", "output", kernel_id, "-p", str(output_dir)],
        capture_output=True, text=True, env=env, timeout=120
    )
    return result.returncode == 0, result.stdout + result.stderr


def extract_tunnel_info(output_dir):
    output_dir = Path(output_dir)
    info_path = output_dir / "tunnel_info.json"
    if info_path.exists():
        return json.loads(info_path.read_text())

    for log_file in output_dir.glob("*.log"):
        content = log_file.read_text(errors="replace")
        import re
        urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
        if urls:
            return {"url": urls[0], "terminal_token": None, "verified": False}

    return None


def connect_soulillusions(url):
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
    else:
        config = {}

    config["gpu_backend_url"] = url
    config["backend_type"] = "polling"
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"[Config] Saved backend URL to config.json")

    try:
        req = urllib.request.Request(f"{url}/api/status", headers={"User-Agent": "SoulIllusions/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            print(f"[Connected] GPU: {data.get('gpu')}, VRAM: {data.get('vram_total')}")
            return True
    except Exception as e:
        print(f"[Warning] URL saved but connection test failed: {e}")
        print(f"  The tunnel may still be warming up. Try again in 10 seconds.")
        return False


def cmd_start():
    data = load_accounts()
    reset_weekly_if_needed(data)
    data = load_accounts()

    acc_idx, acc = pick_account(data)
    print(f"[Account] Using account {acc_idx + 1} (hours used: {acc['hours_used']:.1f}/{MAX_HOURS})")

    set_kaggle_token(acc["token"])

    slug = data.get("kernel_slug", "soulillusions-gpu-backend")
    print(f"[Push] Creating notebook metadata...")
    meta_dir = create_metadata(acc_idx, slug)

    print(f"[Push] Pushing notebook to Kaggle (auto-runs with GPU)...")
    if not push_kernel(meta_dir, acc["token"]):
        print("[Fallback] Trying next account...")
        data["accounts"][acc_idx]["hours_used"] = MAX_HOURS
        save_accounts(data)
        return cmd_start()

    print(f"[Wait] Notebook is running on Kaggle. Waiting for tunnel URL...")
    output_dir = SCRIPT_DIR / ".kaggle_output" / f"account_{acc_idx}"

    tunnel_info = None
    for attempt in range(60):
        time.sleep(15)
        elapsed = (attempt + 1) * 15
        status = get_kernel_status(slug, acc_idx, acc["token"])
        print(f"  [{elapsed}s] Status: {status[:80]}")

        if "running" in status.lower() or "complete" in status.lower() or "error" in status.lower():
            ok, output = pull_kernel_output(slug, acc_idx, acc["token"], output_dir)
            if ok:
                tunnel_info = extract_tunnel_info(output_dir)
                if tunnel_info:
                    break
            if "error" in status.lower() and not tunnel_info:
                print(f"[Error] Notebook finished with error.")
                print(f"  Output: {output[:500]}")
                return

    if not tunnel_info:
        print("[Timeout] Could not extract tunnel URL after 15 minutes.")
        print("  The notebook may still be installing dependencies.")
        print("  Try: py kaggle_auto.py --status")
        return

    url = tunnel_info["url"]
    print(f"\n{'=' * 60}")
    print(f"  GPU Backend URL: {url}")
    if tunnel_info.get("terminal_token"):
        print(f"  Terminal: Enabled")
    print(f"{'=' * 60}\n")

    print("[Connect] Connecting SoulIllusions...")
    connect_soulillusions(url)

    data = load_accounts()
    data["active_account"] = acc_idx
    data["accounts"][acc_idx]["last_session"] = datetime.now().isoformat()
    save_accounts(data)

    print(f"\n[Done] SoulIllusions is connected to the Kaggle GPU backend.")
    print(f"  URL: {url}")
    print(f"  Account: {acc_idx + 1}")
    print(f"  Terminal token: {tunnel_info.get('terminal_token', 'N/A')}")


def cmd_status():
    data = load_accounts()
    print(f"Week started: {data.get('week_start')}")
    print(f"Active account: {data.get('active_account', 0) + 1}")
    print()
    for i, acc in enumerate(data["accounts"]):
        hours = acc.get("hours_used", 0)
        remaining = MAX_HOURS - hours
        marker = " <-- ACTIVE" if i == data.get("active_account", 0) else ""
        print(f"  Account {i + 1}: {hours:.1f}h used, {remaining:.1f}h remaining{marker}")

    url = ""
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
        url = config.get("gpu_backend_url", "")

    if url:
        print(f"\n  Backend URL: {url}")
        try:
            req = urllib.request.Request(f"{url}/api/status", headers={"User-Agent": "SoulIllusions/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                print(f"  Status: ONLINE")
                print(f"  GPU: {data.get('gpu')}")
                print(f"  VRAM: {data.get('vram_total')}")
        except Exception as e:
            print(f"  Status: OFFLINE ({e})")
    else:
        print(f"\n  No backend URL configured.")


def cmd_stop():
    data = load_accounts()
    slug = data.get("kernel_slug", "soulillusions-gpu-backend")
    acc_idx = data.get("active_account", 0)
    acc = data["accounts"][acc_idx]
    set_kaggle_token(acc["token"])
    username = data["accounts"][acc_idx]["username"]
    kernel_id = f"{username}/{slug}"
    result = subprocess.run(
        [sys.executable, "-m", "kaggle", "kernels", "status", kernel_id],
        capture_output=True, text=True, timeout=30
    )
    print(f"Kernel status: {result.stdout.strip()}")
    print("(To stop: go to Kaggle.com → Your Work → Stop the notebook)")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--start":
        cmd_start()
    elif sys.argv[1] == "--status":
        cmd_status()
    elif sys.argv[1] == "--stop":
        cmd_stop()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

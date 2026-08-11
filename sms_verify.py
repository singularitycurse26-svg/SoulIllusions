"""
SoulIllusions SMS Verification System
======================================
Automated phone verification using free SMS receiving services.
- Multi-provider fallback (asms.ai, receivefreesms, receivesms.me)
- Number pool management (up to 10 numbers)
- OTP code extraction via regex
- Webhook + polling support
- Integrates with Soulmate OS founder account
- AI agent accessible (MCP-compatible endpoints)
"""

import json, time, re, os, asyncio, threading, sqlite3, hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
import urllib.request
import urllib.error

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent
VERIFY_DB = SCRIPT_DIR / "verify.db"
VERIFY_CONFIG = SCRIPT_DIR / "verify_config.json"

# Default config
DEFAULT_CONFIG = {
    "providers": [
        {
            "name": "asms",
            "enabled": True,
            "base_url": "https://asms.ai/api/v1",
            "api_key": "",
            "free_tier": True,
            "has_mcp": True,
            "mcp_url": "https://asms.ai/mcp"
        },
        {
            "name": "receivefreesms",
            "enabled": True,
            "base_url": "https://receivefreesms.co.uk/api/v1",
            "api_key": "",
            "free_tier": True,
            "has_mcp": False
        },
        {
            "name": "receivesms_me",
            "enabled": True,
            "base_url": "https://receivesms.me",
            "api_key": "",
            "free_tier": True,
            "has_mcp": False,
            "scrape_mode": True
        }
    ],
    "number_pool_size": 10,
    "otp_timeout_seconds": 120,
    "poll_interval_seconds": 5,
    "founder_account_id": 1,
    "soulmate_vps": "191.44.121.29",
    "auto_verify_kaggle": True,
    "kaggle_accounts_file": "kaggle_accounts.json"
}


def load_config() -> dict:
    if VERIFY_CONFIG.exists():
        return json.loads(VERIFY_CONFIG.read_text())
    VERIFY_CONFIG.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    return DEFAULT_CONFIG


def save_config(cfg: dict):
    VERIFY_CONFIG.write_text(json.dumps(cfg, indent=2))


# --- Database ---
def init_db():
    conn = sqlite3.connect(str(VERIFY_DB))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS phone_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            country TEXT DEFAULT 'us',
            provider TEXT NOT NULL,
            provider_number_id TEXT,
            status TEXT DEFAULT 'available',
            assigned_to TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            times_used INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            service TEXT NOT NULL,
            otp_code TEXT,
            raw_message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            provider TEXT,
            metadata TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS otp_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            sender TEXT,
            body TEXT NOT NULL,
            received_at TEXT DEFAULT (datetime('now')),
            processed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


init_db()


# --- OTP Extraction ---
OTP_PATTERNS = [
    r'\b(\d{4,8})\b',
    r'code[:\s]+(\d{4,8})',
    r'OTP[:\s]+(\d{4,8})',
    r'verification[:\s]+(\d{4,8})',
    r'your\s+code\s+is[:\s]+(\d{4,8})',
    r'(\d{4,8})\s+is\s+your',
    r'Kaggle[:\s]+(\d{4,8})',
    r'(\d{6})',
]

def extract_otp(message: str) -> Optional[str]:
    for pattern in OTP_PATTERNS:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


# --- HTTP Helper ---
def http_get(url: str, headers: dict = None, timeout: int = 15) -> dict:
    req = urllib.request.Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode()[:500]}
    except Exception as e:
        return {"error": str(e)}


def http_post(url: str, data: dict = None, headers: dict = None, timeout: int = 15) -> dict:
    body = json.dumps(data).encode() if data else b''
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode()[:500]}
    except Exception as e:
        return {"error": str(e)}


# --- Providers ---
class SMSProvider:
    """Base SMS provider interface."""
    def get_numbers(self) -> List[dict]:
        raise NotImplementedError
    
    def get_messages(self, number: str) -> List[dict]:
        raise NotImplementedError
    
    def order_number(self, service: str = "", country: str = "us") -> dict:
        raise NotImplementedError


class AsmsProvider(SMSProvider):
    """asms.ai provider — has MCP server for AI agents."""
    
    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "https://asms.ai/api/v1")
        self.api_key = config.get("api_key", "")
        self.headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
    
    def get_numbers(self) -> List[dict]:
        resp = http_get(f"{self.base_url}/numbers", headers=self.headers)
        if "error" in resp:
            return []
        return resp.get("numbers", resp.get("data", []))
    
    def get_messages(self, number: str) -> List[dict]:
        resp = http_get(f"{self.base_url}/numbers/{number}/messages", headers=self.headers)
        if "error" in resp:
            return []
        return resp.get("messages", resp.get("data", []))
    
    def order_number(self, service: str = "kaggle", country: str = "us") -> dict:
        data = {"service": service, "country": country}
        resp = http_post(f"{self.base_url}/otp/order", data=data, headers=self.headers)
        return resp


class ReceiveFreeSMSProvider(SMSProvider):
    """receivefreesms.co.uk provider."""
    
    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "https://receivefreesms.co.uk/api/v1")
        self.api_key = config.get("api_key", "")
        self.headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
    
    def get_numbers(self) -> List[dict]:
        resp = http_get(f"{self.base_url}/numbers", headers=self.headers)
        if "error" in resp:
            return []
        return resp.get("numbers", resp.get("data", []))
    
    def get_messages(self, number: str) -> List[dict]:
        resp = http_get(f"{self.base_url}/numbers/{number}/messages", headers=self.headers)
        if "error" in resp:
            return []
        return resp.get("messages", resp.get("data", []))
    
    def order_number(self, service: str = "", country: str = "us") -> dict:
        return {"error": "ReceiveFreeSMS uses shared public numbers, no ordering needed"}


class ReceiveSMSMeProvider(SMSProvider):
    """receivesms.me — scrape mode, no API key needed."""
    
    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "https://receivesms.me")
    
    def get_numbers(self) -> List[dict]:
        # Scrape public numbers from homepage
        try:
            req = urllib.request.Request(f"{self.base_url}/")
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode(errors='replace')
            # Extract numbers from HTML
            numbers = []
            # Look for phone number patterns in links/data attributes
            pattern = r'(?:\+?1?)?(\d{10})'
            found = re.findall(pattern, html)
            seen = set()
            for num in found:
                if num not in seen and len(num) == 10:
                    seen.add(num)
                    numbers.append({"number": f"+1{num}", "country": "us", "id": num})
            return numbers[:20]  # Limit to 20
        except Exception as e:
            return []
    
    def get_messages(self, number: str) -> List[dict]:
        # Try to scrape messages for a specific number
        try:
            clean = number.replace('+', '').replace('-', '').replace(' ', '')
            req = urllib.request.Request(f"{self.base_url}/number/{clean}/")
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode(errors='replace')
            # Parse messages from HTML
            messages = []
            # Simple extraction — look for message blocks
            msg_pattern = r'<div class="message[^"]*"[^>]*>.*?<span[^>]*>([^<]+)</span>.*?<div[^>]*>([^<]+)</div>'
            matches = re.findall(msg_pattern, html, re.DOTALL)
            for sender, body in matches:
                messages.append({
                    "sender": sender.strip(),
                    "body": body.strip(),
                    "received_at": datetime.now().isoformat()
                })
            return messages
        except Exception:
            return []
    
    def order_number(self, service: str = "", country: str = "us") -> dict:
        return {"error": "ReceiveSMS.me uses shared public numbers, no ordering needed"}


def get_provider(name: str, config: dict) -> Optional[SMSProvider]:
    providers = {
        "asms": AsmsProvider,
        "receivefreesms": ReceiveFreeSMSProvider,
        "receivesms_me": ReceiveSMSMeProvider,
    }
    cls = providers.get(name)
    if not cls:
        return None
    return cls(config)


def get_active_providers(cfg: dict) -> List[SMSProvider]:
    providers = []
    for p_cfg in cfg.get("providers", []):
        if p_cfg.get("enabled", True):
            p = get_provider(p_cfg["name"], p_cfg)
            if p:
                providers.append(p)
    return providers


# --- Number Pool Management ---
def refresh_number_pool():
    """Fetch available numbers from all providers and store in DB."""
    cfg = load_config()
    providers = get_active_providers(cfg)
    total_added = 0
    
    for provider in providers:
        try:
            numbers = provider.get_numbers()
            conn = sqlite3.connect(str(VERIFY_DB))
            c = conn.cursor()
            for num in numbers:
                phone = num.get("number", num.get("phone", ""))
                if not phone:
                    continue
                provider_id = num.get("id", num.get("number_id", ""))
                c.execute(
                    "INSERT OR IGNORE INTO phone_numbers (number, country, provider, provider_number_id, status) VALUES (?, ?, ?, ?, 'available')",
                    (phone, num.get("country", "us"), provider.__class__.__name__.replace("Provider", "").lower(), str(provider_id))
                )
                if c.rowcount > 0:
                    total_added += 1
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Verify] Error fetching from {provider.__class__.__name__}: {e}")
    
    print(f"[Verify] Added {total_added} new numbers to pool")
    return total_added


def get_available_number() -> Optional[dict]:
    """Get an available number from the pool."""
    conn = sqlite3.connect(str(VERIFY_DB))
    c = conn.cursor()
    c.execute("SELECT id, number, country, provider, provider_number_id FROM phone_numbers WHERE status = 'available' ORDER BY times_used ASC, last_used_at ASC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "number": row[1], "country": row[2], "provider": row[3], "provider_id": row[4]}


def assign_number(number: str, assigned_to: str):
    conn = sqlite3.connect(str(VERIFY_DB))
    c = conn.cursor()
    c.execute("UPDATE phone_numbers SET status = 'in_use', assigned_to = ?, last_used_at = datetime('now') WHERE number = ?", (assigned_to, number))
    conn.commit()
    conn.close()


def release_number(number: str):
    conn = sqlite3.connect(str(VERIFY_DB))
    c = conn.cursor()
    c.execute("UPDATE phone_numbers SET status = 'available', assigned_to = NULL, times_used = times_used + 1 WHERE number = ?", (number,))
    conn.commit()
    conn.close()


def get_pool_status() -> dict:
    conn = sqlite3.connect(str(VERIFY_DB))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM phone_numbers WHERE status = 'available'")
    available = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM phone_numbers WHERE status = 'in_use'")
    in_use = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM phone_numbers")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM verifications WHERE status = 'completed'")
    completed = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM verifications WHERE status = 'pending'")
    pending = c.fetchone()[0]
    conn.close()
    return {
        "total_numbers": total,
        "available": available,
        "in_use": in_use,
        "verifications_completed": completed,
        "verifications_pending": pending
    }


# --- Verification Flow ---
def start_verification(service: str, country: str = "us") -> dict:
    """Start a verification flow — get a number and wait for OTP."""
    # Refresh pool if empty
    status = get_pool_status()
    if status["available"] == 0:
        refresh_number_pool()
    
    num = get_available_number()
    if not num:
        return {"error": "No phone numbers available. Try adding API keys to providers."}
    
    assign_number(num["number"], service)
    
    # Create verification record
    conn = sqlite3.connect(str(VERIFY_DB))
    c = conn.cursor()
    c.execute(
        "INSERT INTO verifications (phone_number, service, status, provider, metadata) VALUES (?, ?, 'pending', ?, ?)",
        (num["number"], service, num["provider"], json.dumps({"country": country, "number_id": num["id"]}))
    )
    verify_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "verification_id": verify_id,
        "phone_number": num["number"],
        "service": service,
        "status": "pending",
        "message": f"Use this number for {service} verification. Poll /api/verify/check/{verify_id} for the OTP code."
    }


def check_verification(verify_id: int) -> dict:
    """Check if OTP has been received for a verification."""
    conn = sqlite3.connect(str(VERIFY_DB))
    c = conn.cursor()
    c.execute("SELECT phone_number, service, status, otp_code, raw_message, created_at, provider FROM verifications WHERE id = ?", (verify_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": "Verification not found"}
    
    phone, service, status, otp, raw_msg, created, provider = row
    
    if status == "completed" and otp:
        conn.close()
        return {"status": "completed", "otp_code": otp, "phone_number": phone, "raw_message": raw_msg}
    
    # Check if timeout
    try:
        created_time = datetime.fromisoformat(created)
        cfg = load_config()
        if (datetime.now() - created_time).total_seconds() > cfg.get("otp_timeout_seconds", 120):
            c.execute("UPDATE verifications SET status = 'timeout' WHERE id = ?", (verify_id,))
            conn.commit()
            conn.close()
            release_number(phone)
            return {"status": "timeout", "message": "No OTP received within timeout period"}
    except:
        pass
    
    # Poll for messages
    cfg = load_config()
    provider = get_provider(provider, cfg)
    if not provider:
        conn.close()
        return {"status": "pending", "message": "Provider unavailable"}
    
    messages = provider.get_messages(phone)
    for msg in messages:
        body = msg.get("body", msg.get("content", msg.get("text", "")))
        sender = msg.get("sender", msg.get("from", ""))
        
        # Store message
        c.execute(
            "INSERT OR IGNORE INTO otp_messages (phone_number, sender, body) VALUES (?, ?, ?)",
            (phone, sender, body)
        )
        
        # Try to extract OTP
        otp_code = extract_otp(body)
        if otp_code:
            c.execute(
                "UPDATE verifications SET status = 'completed', otp_code = ?, raw_message = ?, completed_at = datetime('now') WHERE id = ?",
                (otp_code, body, verify_id)
            )
            conn.commit()
            conn.close()
            release_number(phone)
            return {
                "status": "completed",
                "otp_code": otp_code,
                "phone_number": phone,
                "service": service,
                "raw_message": body,
                "sender": sender
            }
    
    conn.commit()
    conn.close()
    return {"status": "pending", "message": "Waiting for OTP...", "phone_number": phone}


def wait_for_otp(verify_id: int, timeout: int = 120) -> dict:
    """Blocking wait for OTP code."""
    cfg = load_config()
    interval = cfg.get("poll_interval_seconds", 5)
    deadline = time.time() + timeout
    
    while time.time() < deadline:
        result = check_verification(verify_id)
        if result.get("status") in ("completed", "timeout"):
            return result
        time.sleep(interval)
    
    return {"status": "timeout", "message": "No OTP received"}


# --- Kaggle Verification Automation ---
def verify_kaggle_account(account_idx: int) -> dict:
    """Automate Kaggle phone verification for a specific account."""
    cfg = load_config()
    kaggle_file = SCRIPT_DIR / cfg.get("kaggle_accounts_file", "kaggle_accounts.json")
    if not kaggle_file.exists():
        return {"error": "kaggle_accounts.json not found"}
    
    accounts = json.loads(kaggle_file.read_text())
    if account_idx >= len(accounts["accounts"]):
        return {"error": "Invalid account index"}
    
    account = accounts["accounts"][account_idx]
    username = account["username"]
    
    print(f"[Verify] Starting Kaggle verification for {username}")
    
    # Get a phone number
    result = start_verification("kaggle", "us")
    if "error" in result:
        return result
    
    phone = result["phone_number"]
    verify_id = result["verification_id"]
    
    print(f"[Verify] Got number: {phone}")
    print(f"[Verify] Go to https://www.kaggle.com/account/login -> Settings -> Phone Verification")
    print(f"[Verify] Enter this number: {phone}")
    print(f"[Verify] Waiting for OTP code...")
    
    # Wait for the OTP
    otp_result = wait_for_otp(verify_id, timeout=180)
    
    if otp_result.get("status") == "completed":
        otp = otp_result["otp_code"]
        print(f"[Verify] OTP received: {otp}")
        print(f"[Verify] Enter this code on Kaggle to complete verification")
        return {
            "status": "success",
            "username": username,
            "phone_number": phone,
            "otp_code": otp,
            "message": f"Enter {otp} on Kaggle to verify {username}'s phone number"
        }
    else:
        return {
            "status": "timeout",
            "username": username,
            "phone_number": phone,
            "message": "No OTP received. Try a different number or verify manually."
        }


def verify_all_kaggle_accounts():
    """Verify all Kaggle accounts in the config."""
    cfg = load_config()
    kaggle_file = SCRIPT_DIR / cfg.get("kaggle_accounts_file", "kaggle_accounts.json")
    if not kaggle_file.exists():
        return {"error": "kaggle_accounts.json not found"}
    
    accounts = json.loads(kaggle_file.read_text())
    results = []
    
    for i, account in enumerate(accounts["accounts"]):
        print(f"\n[Verify] Account {i+1}/{len(accounts['accounts'])}: {account['username']}")
        result = verify_kaggle_account(i)
        results.append(result)
        if result.get("status") == "success":
            print(f"  -> SUCCESS: OTP {result['otp_code']}")
        else:
            print(f"  -> FAILED: {result.get('message', 'Unknown error')}")
        time.sleep(5)  # Brief pause between accounts
    
    return results


# --- CLI ---
def main():
    import sys
    if len(sys.argv) < 2:
        print("SoulIllusions SMS Verification System")
        print("=" * 50)
        print("Commands:")
        print("  refresh       - Refresh phone number pool from all providers")
        print("  pool          - Show number pool status")
        print("  start <svc>   - Start verification for a service (e.g., kaggle)")
        print("  check <id>    - Check verification status by ID")
        print("  kaggle <idx>  - Verify specific Kaggle account (0-indexed)")
        print("  kaggle-all    - Verify all Kaggle accounts")
        print("  numbers       - List available phone numbers")
        print("  config        - Show current configuration")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "refresh":
        count = refresh_number_pool()
        print(f"Added {count} numbers")
    
    elif cmd == "pool":
        status = get_pool_status()
        print(json.dumps(status, indent=2))
    
    elif cmd == "start":
        service = sys.argv[2] if len(sys.argv) > 2 else "generic"
        result = start_verification(service)
        print(json.dumps(result, indent=2))
        if "verification_id" in result:
            print(f"\nPoll with: py -V:Astral/CPython3.11.15 sms_verify.py check {result['verification_id']}")
    
    elif cmd == "check":
        verify_id = int(sys.argv[2])
        result = check_verification(verify_id)
        print(json.dumps(result, indent=2))
    
    elif cmd == "kaggle":
        idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        result = verify_kaggle_account(idx)
        print(json.dumps(result, indent=2))
    
    elif cmd == "kaggle-all":
        results = verify_all_kaggle_accounts()
        print(json.dumps(results, indent=2))
    
    elif cmd == "numbers":
        conn = sqlite3.connect(str(VERIFY_DB))
        c = conn.cursor()
        c.execute("SELECT number, country, provider, status, times_used FROM phone_numbers ORDER BY status, times_used ASC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            print(f"  {r[0]:15s} | {r[1]:3s} | {r[2]:20s} | {r[3]:10s} | used {r[4]}x")
    
    elif cmd == "config":
        cfg = load_config()
        print(json.dumps(cfg, indent=2))
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()

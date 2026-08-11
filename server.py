"""
SoulIllusions AI Video Maker - Local Server
100% Free, self-hosted text-to-video generation
Connects to Google Colab GPU backend via ngrok tunnel
"""
import os
import sys
import json
import time
import uuid
import asyncio
import webbrowser
import threading
from pathlib import Path
from typing import Optional

import urllib.request
import urllib.error
import shutil
import subprocess
import hashlib
import traceback
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Production suite integration
try:
    from production_suite import router as production_router
    PRODUCTION_AVAILABLE = True
except ImportError:
    PRODUCTION_AVAILABLE = False

# Action logger integration
try:
    from action_logger import get_logger
    action_logger = get_logger()
    ACTION_LOGGING = True
except ImportError:
    action_logger = None
    ACTION_LOGGING = False

# AI controller integration
try:
    from ai_controller import AIController
    AI_CONTROLLER_AVAILABLE = True
except ImportError:
    AI_CONTROLLER_AVAILABLE = False

# Paths (defined early for use in imports below)
APP_DIR = Path(__file__).parent
VIDEOS_DIR = APP_DIR / "videos"
VIDEOS_DIR.mkdir(exist_ok=True)
CONFIG_FILE = APP_DIR / "config.json"

# QC state tracking
qc_results = {}  # job_id -> {quality, issues, scores, auto_regenerated}
auto_download_tasks = {}  # job_id -> thread
_gradio_job_status = {}  # job_id -> status dict (for HF Spaces backend)

# Asset library integration
try:
    from asset_library import AssetLibrary, ASSET_CATEGORIES
    asset_library = AssetLibrary(str(APP_DIR / "asset_data"))
    ASSET_LIBRARY_AVAILABLE = True
except ImportError:
    asset_library = None
    ASSET_LIBRARY_AVAILABLE = False

# Script parser integration
try:
    from script_parser import ScriptParser
    script_parser = ScriptParser()
    SCRIPT_PARSER_AVAILABLE = True
except ImportError:
    script_parser = None
    SCRIPT_PARSER_AVAILABLE = False

ai_controller = None  # Initialized after app and config

# Default config
DEFAULT_CONFIG = {
    "gpu_backend_url": "",
    "backend_type": "auto",  # auto, polling, gradio
    "auto_open_browser": True,
    "port": 7860,
}

def detect_backend_type(url):
    """Auto-detect whether backend is a polling API (Lightning/Colab) or Gradio (HF Spaces)."""
    if not url:
        return "polling"
    if "hf.space" in url or "huggingface.co" in url:
        return "gradio"
    return "polling"

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

config = load_config()

app = FastAPI(title="SoulIllusions AI Video Maker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount production suite routes
if PRODUCTION_AVAILABLE:
    app.include_router(production_router)

# Initialize AI controller after app is ready
if AI_CONTROLLER_AVAILABLE:
    ai_controller = AIController(
        production_suite=production_router if PRODUCTION_AVAILABLE else None,
        server_app=None,  # Will use config dict directly
        action_logger=action_logger,
    )
    # Give it access to config
    class _ConfigHolder:
        def __init__(self, cfg):
            self.config = cfg
    ai_controller.server_app = _ConfigHolder(config)

# === Models ===
class GenerateRequest(BaseModel):
    prompt: str
    model: str = "auto"
    style: str = "cinematic"
    num_frames: int = 97
    fps: int = 24
    steps: int = 30
    seed: Optional[int] = None
    enhance: bool = True
    audio: bool = False
    upscale: int = 1
    interpolate_fps: int = 0
    # Advanced generation
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    guidance_scale: float = 5.0
    guidance_rescale: float = 0.0
    # Scheduler
    solver: str = "unipc"
    flow_shift: float = 5.0
    use_karras_sigmas: bool = False
    use_dynamic_shifting: bool = False
    timestep_spacing: str = "linspace"
    custom_timesteps: Optional[list] = None
    custom_sigmas: Optional[list] = None
    boundary_ratio: float = 0.875
    decode_timestep: float = 0.05
    decode_noise_scale: float = 0.025
    image_cond_noise_scale: float = 0.0
    denoise_strength: float = 1.0
    num_videos_per_prompt: int = 1
    creativity_scale: float = 0.5
    output_type: str = "pil"
    # Camera
    camera_enabled: bool = False
    camera_motion: str = "static"
    camera_direction: Optional[str] = None
    camera_speed: float = 0.5
    camera_intensity: float = 0.5
    camera_fov: float = 60.0
    camera_roll: float = 0.0
    camera_pitch: float = 0.0
    camera_yaw: float = 0.0
    # Motion
    motion_intensity: float = 0.5
    temporal_smoothing: bool = True
    flicker_elimination: bool = True
    # Post-processing
    upscale_model: str = "realesrgan_x2"
    interpolate_motion_blur: bool = False
    color_grading: Optional[dict] = None
    effects: Optional[dict] = None
    # Output encoding
    codec: str = "h264"
    crf: int = 23
    preset: str = "medium"
    tune: str = "none"
    bitrate: Optional[str] = None
    maxrate: Optional[str] = None
    bufsize: Optional[str] = None
    profile: str = "high"
    pixel_format: str = "yuv420p"
    # Audio
    native_audio: bool = False
    tts_text: Optional[str] = None
    tts_voice: str = "narrator_male"
    ambient_prompt: Optional[str] = None
    music_prompt: Optional[str] = None

class ImageGenRequest(BaseModel):
    prompt: str = ""
    model: str = "flux"
    negative_prompt: Optional[str] = None
    aspect_ratio: str = "1:1"
    quality: str = "standard"
    seed: Optional[int] = None
    batch_count: int = 1
    style_preset: str = "None"
    width: Optional[int] = None
    height: Optional[int] = None
    guidance_scale: float = 7.5
    steps: int = 25
    lora_model: Optional[str] = None
    lora_weight: float = 1.0
    reference_strength: int = 50
    image_mode: str = "t2i"
    reference_images: list = []
    # Image-to-video bridge
    send_to_video: bool = False
    video_model: str = "auto"
    video_style: str = "cinematic"
    video_num_frames: int = 97
    video_fps: int = 24
    video_steps: int = 30

class BackendUrlRequest(BaseModel):
    url: str

# === API ===
@app.get("/")
async def index():
    return HTMLResponse(get_html(), headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})

# === Action Logging API ===
@app.post("/api/log")
async def log_action(request: Request):
    """Receive and log a frontend UI action."""
    if not action_logger:
        return {"status": "logging_disabled"}
    try:
        body = await request.json()
        action_logger.log_ui(
            event_type=body.get("event_type", "unknown"),
            element_id=body.get("element_id", ""),
            element_type=body.get("element_type", "unknown"),
            value=body.get("value"),
            page=body.get("page"),
            extra=body.get("extra"),
        )
        return {"status": "logged"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/log/recent")
async def get_recent_logs(count: int = 50, category: str = None, source: str = None):
    if not action_logger:
        return {"events": [], "error": "logging_disabled"}
    return {"events": action_logger.get_recent_events(count=count, category=category, source=source)}

@app.get("/api/log/stats")
async def get_log_stats():
    if not action_logger:
        return {"error": "logging_disabled"}
    return action_logger.get_stats()

@app.get("/api/log/search")
async def search_logs(action_contains: str = None, source: str = None, result: str = None, limit: int = 50):
    if not action_logger:
        return {"events": [], "error": "logging_disabled"}
    return {"events": action_logger.search_events(action_contains=action_contains, source=source, result=result, limit=limit)}

@app.post("/api/log/note")
async def add_upgrade_note(request: Request):
    if not action_logger:
        return {"error": "logging_disabled"}
    try:
        body = await request.json()
        action_logger.note_upgrade_idea(
            idea=body.get("idea", ""),
            context=body.get("context"),
            severity=body.get("severity", "info"),
        )
        return {"status": "note_added"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/log/notes")
async def get_upgrade_notes():
    if not action_logger:
        return {"notes": "", "error": "logging_disabled"}
    import os
    path = action_logger.upgrade_notes_path
    if not os.path.exists(path):
        return {"notes": ""}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"notes": f.read()}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/log/toggle")
async def toggle_logging(request: Request):
    if not action_logger:
        return {"error": "logging_disabled"}
    try:
        body = await request.json()
        action_logger.set_enabled(body.get("enabled", True))
        return {"status": "ok", "enabled": action_logger.enabled}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# === AI Controller API ===
@app.get("/api/ai/tools")
async def list_ai_tools():
    if not ai_controller:
        return JSONResponse({"error": "AI controller not available"}, status_code=503)
    return {"tools": ai_controller.list_tools(), "resources": ai_controller.list_resources()}

@app.post("/api/ai/execute")
async def ai_execute(request: Request):
    if not ai_controller:
        return JSONResponse({"error": "AI controller not available"}, status_code=503)
    try:
        body = await request.json()
        tool_name = body.get("tool")
        params = body.get("params", {})
        if not tool_name:
            return JSONResponse({"error": "tool name required"}, status_code=400)
        result = ai_controller.execute(tool_name, params)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/ai/resource/{resource_name}")
async def ai_read_resource(resource_name: str):
    if not ai_controller:
        return JSONResponse({"error": "AI controller not available"}, status_code=503)
    return ai_controller.read_resource(resource_name)

@app.get("/api/ai/status")
async def ai_status():
    return {
        "ai_controller": "available" if ai_controller else "unavailable",
        "action_logger": "available" if action_logger else "unavailable",
        "action_logging_enabled": action_logger.enabled if action_logger else False,
        "tools_count": len(ai_controller._tools) if ai_controller else 0,
        "resources_count": len(ai_controller._resources) if ai_controller else 0,
    }

@app.get("/api/config")
async def get_config():
    return {
        "gpu_backend_url": config.get("gpu_backend_url", ""),
        "has_backend": bool(config.get("gpu_backend_url")),
    }

@app.post("/api/config/backend")
async def set_backend(req: BackendUrlRequest):
    url = req.url.strip().rstrip("/")
    config["gpu_backend_url"] = url
    save_config(config)
    if action_logger:
        action_logger.log("config.backend_set", {"url": url}, source="user")
    return {"status": "ok", "url": url}

@app.get("/api/backend/status")
async def backend_status():
    url = config.get("gpu_backend_url", "")
    if not url:
        return {"status": "offline", "error": "No backend URL configured"}
    btype = config.get("backend_type", "auto")
    if btype == "auto":
        btype = detect_backend_type(url)
    try:
        if btype == "gradio":
            # Gradio API: call the status endpoint
            req = urllib.request.Request(f"{url}/api/status", 
                data=json.dumps({"data": []}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
                method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read().decode())
                data = raw.get("data", [{}])[0] if isinstance(raw, dict) else raw
                return {"status": "online", **data}
        else:
            req = urllib.request.Request(f"{url}/api/status", headers={"User-Agent": "SoulIllusions/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return {"status": "online", **data}
    except Exception as e:
        return {"status": "offline", "error": str(e)}

@app.post("/api/generate")
async def generate(req: GenerateRequest):
    url = config.get("gpu_backend_url", "")
    if not url:
        if action_logger:
            action_logger.log("video.generate", {"error": "no_backend", "model": req.model}, source="user", result="failure")
        return JSONResponse({"error": "No GPU backend configured. Open the Colab notebook first."}, status_code=400)
    
    btype = config.get("backend_type", "auto")
    if btype == "auto":
        btype = detect_backend_type(url)
    
    if action_logger:
        action_logger.log_generation(
            model=req.model, prompt=req.prompt, style=req.style,
            frames=req.num_frames, fps=req.fps, steps=req.steps,
            seed=req.seed, status="started",
        )
    
    if btype == "gradio":
        # Gradio backend: synchronous call, returns result directly
        job_id = uuid.uuid4().hex[:12]
        t = threading.Thread(target=_gradio_generate_video, args=(job_id, url, req.dict()), daemon=True)
        auto_download_tasks[job_id] = t
        t.start()
        if action_logger:
            action_logger.log("video.generate", {"job_id": job_id, "model": req.model, "status": "queued"}, source="system")
        return {"job_id": job_id, "status": "processing", "model": req.model}
    
    # Polling backend (Lightning/Colab)
    try:
        payload = json.dumps(req.dict()).encode("utf-8")
        
        request = urllib.request.Request(
            f"{url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            job_id = data.get("job_id")
            if job_id:
                # Start auto-download background thread
                t = threading.Thread(target=_auto_download_video, args=(job_id, req.dict()), daemon=True)
                auto_download_tasks[job_id] = t
                t.start()
            if action_logger:
                action_logger.log("video.generate", {"job_id": job_id, "model": req.model, "status": "queued"}, source="system")
            return data
    except Exception as e:
        if action_logger:
            action_logger.log("video.generate", {"error": str(e), "model": req.model}, source="system", result="failure")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/status/{job_id}")
async def job_status(job_id: str):
    # Check if this is a Gradio job (tracked locally)
    if job_id in _gradio_job_status:
        return _gradio_job_status[job_id]
    
    url = config.get("gpu_backend_url", "")
    if not url:
        return JSONResponse({"error": "No backend URL"}, status_code=400)
    try:
        req = urllib.request.Request(
            f"{url}/api/status/{job_id}",
            headers={"User-Agent": "SoulIllusions/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    # Check if already downloaded locally by auto-download
    local_path = VIDEOS_DIR / f"soulillusions_{job_id}.mp4"
    if local_path.exists() and local_path.stat().st_size > 1000:
        return FileResponse(str(local_path), media_type="video/mp4", filename=f"soulillusions_{job_id}.mp4")
    
    # Fallback: download from backend
    url = config.get("gpu_backend_url", "")
    if not url:
        return JSONResponse({"error": "No backend URL"}, status_code=400)
    
    try:
        backend_url = f"{url}/api/download/{job_id}"
        req = urllib.request.Request(backend_url, headers={"User-Agent": "SoulIllusions/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        
        local_path.write_bytes(data)
        
        return FileResponse(str(local_path), media_type="video/mp4", filename=f"soulillusions_{job_id}.mp4")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/videos")
async def list_videos():
    videos = []
    for f in VIDEOS_DIR.glob("*.mp4"):
        stat = f.stat()
        job_id = f.stem.replace("soulillusions_", "")
        qc = qc_results.get(job_id, {})
        videos.append({
            "name": f.name,
            "size": stat.st_size,
            "size_mb": f"{stat.st_size / 1024 / 1024:.1f} MB",
            "created": stat.st_ctime,
            "url": f"/api/download/{job_id}",
            "qc_status": qc.get("quality", "pending"),
            "qc_issues": qc.get("issues", []),
            "auto_regenerated": qc.get("auto_regenerated", False),
        })
    videos.sort(key=lambda v: v["created"], reverse=True)
    return {"videos": videos}

# === Auto-Download System ===
def _gradio_generate_video(job_id, url, gen_params):
    """Gradio backend: call generate_video API synchronously, download result, run QC."""
    _gradio_job_status[job_id] = {"status": "processing", "progress": 0, "prompt": gen_params.get("prompt", ""), "model": gen_params.get("model", "ltx")}
    
    try:
        # Call Gradio API: POST /api/generate_video with data array
        payload = json.dumps({"data": [
            gen_params.get("prompt", ""),
            gen_params.get("model", "ltx"),
            gen_params.get("style", "cinematic"),
            gen_params.get("num_frames", 97),
            gen_params.get("fps", 24),
            gen_params.get("steps", 30),
            gen_params.get("seed"),
            gen_params.get("enhance", True),
            gen_params.get("negative_prompt"),
            gen_params.get("width", 768),
            gen_params.get("height", 512),
            gen_params.get("guidance_scale", 3.0),
            gen_params.get("guidance_rescale", 0.0),
            gen_params.get("solver", "unipc"),
            gen_params.get("flow_shift", 5.0),
            gen_params.get("use_karras_sigmas", False),
            gen_params.get("use_dynamic_shifting", False),
            gen_params.get("decode_timestep", 0.05),
            gen_params.get("decode_noise_scale", 0.025),
            gen_params.get("image_cond_noise_scale", 0.0),
            gen_params.get("num_videos_per_prompt", 1),
            gen_params.get("output_type", "pil"),
            gen_params.get("camera_enabled", False),
            gen_params.get("camera_motion", "static"),
            gen_params.get("camera_direction"),
            gen_params.get("camera_speed", 0.5),
            gen_params.get("camera_intensity", 0.5),
            gen_params.get("upscale", 1),
            gen_params.get("interpolate_fps", 0),
            gen_params.get("color_grading"),
            gen_params.get("effects"),
            gen_params.get("codec", "h264"),
            gen_params.get("crf", 23),
            gen_params.get("preset", "medium"),
            gen_params.get("tune"),
            gen_params.get("bitrate"),
            gen_params.get("maxrate"),
            gen_params.get("bufsize"),
            gen_params.get("profile"),
            gen_params.get("pixel_format"),
            gen_params.get("audio", False),
        ]}).encode("utf-8")
        
        req = urllib.request.Request(
            f"{url}/api/generate_video",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
            method="POST"
        )
        
        _gradio_job_status[job_id] = {"status": "processing", "progress": 0.5, "prompt": gen_params.get("prompt", ""), "model": gen_params.get("model", "ltx")}
        
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = json.loads(resp.read().decode())
        
        # Gradio returns {"data": [video_path, status_text], ...}
        data = raw.get("data", raw) if isinstance(raw, dict) else raw
        video_url = None
        if isinstance(data, list):
            video_url = data[0] if len(data) > 0 else None
        elif isinstance(data, dict):
            video_url = data.get("output") or data.get("video")
        
        if not video_url:
            _gradio_job_status[job_id] = {"status": "failed", "error": "No video URL in response", "prompt": gen_params.get("prompt", "")}
            return
        
        # Download the video from the Gradio file URL
        if video_url.startswith("/"):
            video_url = url + video_url
        
        dl_req = urllib.request.Request(video_url, headers={"User-Agent": "SoulIllusions/1.0"})
        with urllib.request.urlopen(dl_req, timeout=120) as dl_resp:
            video_data = dl_resp.read()
        
        local_path = VIDEOS_DIR / f"soulillusions_{job_id}.mp4"
        local_path.write_bytes(video_data)
        
        print(f"[Gradio] Saved {len(video_data)/1024:.0f}KB for job {job_id}")
        
        _gradio_job_status[job_id] = {"status": "complete", "progress": 1.0, "prompt": gen_params.get("prompt", ""), "output": str(local_path)}
        
        # Run QC check
        _run_video_qc(job_id, str(local_path), gen_params)
        
    except Exception as e:
        print(f"[Gradio] Error for job {job_id}: {e}")
        _gradio_job_status[job_id] = {"status": "failed", "error": str(e), "prompt": gen_params.get("prompt", "")}

def _gradio_generate_image(job_id, url, gen_params):
    """Gradio backend: call generate_image API synchronously, download result."""
    _gradio_job_status[job_id] = {"status": "processing", "prompt": gen_params.get("prompt", "")}
    
    try:
        payload = json.dumps({"data": [
            gen_params.get("prompt", ""),
            gen_params.get("negative_prompt", ""),
            gen_params.get("aspect_ratio", "2:3"),
            gen_params.get("quality", "pro"),
            gen_params.get("seed"),
            gen_params.get("batch_count", 1),
            gen_params.get("style_preset", "cinematic"),
            gen_params.get("width"),
            gen_params.get("height"),
            gen_params.get("guidance_scale", 7.5),
            gen_params.get("steps"),
        ]}).encode("utf-8")
        
        req = urllib.request.Request(
            f"{url}/api/generate_image",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = json.loads(resp.read().decode())
        
        data = raw.get("data", raw) if isinstance(raw, dict) else raw
        image_url = None
        if isinstance(data, list):
            image_url = data[0] if len(data) > 0 else None
        elif isinstance(data, dict):
            image_url = data.get("image") or data.get("url")
        
        if not image_url:
            _gradio_job_status[job_id] = {"status": "failed", "error": "No image URL in response"}
            return
        
        # Download the image
        if image_url.startswith("/"):
            image_url = url + image_url
        
        dl_req = urllib.request.Request(image_url, headers={"User-Agent": "SoulIllusions/1.0"})
        with urllib.request.urlopen(dl_req, timeout=60) as dl_resp:
            img_data = dl_resp.read()
        
        local_path = IMAGES_DIR / f"img_{job_id}.png"
        local_path.write_bytes(img_data)
        
        print(f"[Gradio] Saved image {len(img_data)/1024:.0f}KB for job {job_id}")
        
        _gradio_job_status[job_id] = {"status": "completed", "url": f"/api/image/download/{job_id}"}
        
    except Exception as e:
        print(f"[Gradio] Image error for job {job_id}: {e}")
        _gradio_job_status[job_id] = {"status": "failed", "error": str(e)}

def _auto_download_video(job_id, gen_params):
    """Background thread: polls GPU backend for completion, downloads video immediately, runs QC."""
    url = config.get("gpu_backend_url", "")
    if not url:
        return
    
    local_path = VIDEOS_DIR / f"soulillusions_{job_id}.mp4"
    
    # Poll for up to 20 minutes
    for attempt in range(400):
        time.sleep(3)
        try:
            req = urllib.request.Request(
                f"{url}/api/status/{job_id}",
                headers={"User-Agent": "SoulIllusions/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = json.loads(resp.read().decode())
            
            if status.get("status") == "complete":
                # Download immediately
                dl_req = urllib.request.Request(
                    f"{url}/api/download/{job_id}",
                    headers={"User-Agent": "SoulIllusions/1.0"}
                )
                with urllib.request.urlopen(dl_req, timeout=120) as dl_resp:
                    video_data = dl_resp.read()
                
                local_path.write_bytes(video_data)
                print(f"[Auto-Download] Saved {len(video_data)/1024:.0f}KB for job {job_id}")
                
                # Run QC check
                _run_video_qc(job_id, str(local_path), gen_params)
                return
                
            elif status.get("status") == "failed":
                print(f"[Auto-Download] Job {job_id} failed: {status.get('error')}")
                qc_results[job_id] = {"quality": "failed", "issues": [status.get("error", "Generation failed")], "auto_regenerated": False}
                return
        except Exception as e:
            print(f"[Auto-Download] Poll error for {job_id}: {e}")
    
    print(f"[Auto-Download] Timeout for job {job_id}")

# === Video Quality Checker ===
def _run_video_qc(job_id, video_path, gen_params):
    """Analyze video for defects: black frames, frozen frames, corruption, duration issues."""
    issues = []
    scores = {}
    
    try:
        import imageio
        reader = imageio.get_reader(video_path)
        meta = reader.get_meta_data()
        fps = meta.get("fps", 24)
        duration = meta.get("duration", 0)
        n_frames = 0
        
        frames_data = []
        prev_frame_hash = None
        black_frame_count = 0
        frozen_frame_count = 0
        
        for i, frame in enumerate(reader):
            n_frames += 1
            arr = None
            try:
                import numpy as np
                arr = np.array(frame)
                # Check for black frame
                if arr.mean() < 5:
                    black_frame_count += 1
                # Check for frozen frame (identical to previous)
                frame_hash = hashlib.md5(arr.tobytes()).hexdigest()
                if prev_frame_hash == frame_hash:
                    frozen_frame_count += 1
                prev_frame_hash = frame_hash
            except Exception:
                pass
            
            # Sample every 10th frame for speed
            if i % 10 != 0:
                try:
                    reader.get_next_data()
                except StopIteration:
                    break
        
        reader.close()
        
        # Score the video
        scores["total_frames"] = n_frames
        scores["duration_seconds"] = round(duration, 2)
        scores["fps"] = fps
        scores["black_frames"] = black_frame_count
        scores["frozen_frames"] = frozen_frame_count
        scores["black_frame_pct"] = round(black_frame_count / max(n_frames, 1) * 100, 1)
        scores["frozen_frame_pct"] = round(frozen_frame_count / max(n_frames, 1) * 100, 1)
        
        # Determine quality
        quality = "good"
        
        if n_frames < 5:
            issues.append("Video too short - likely corrupted")
            quality = "defective"
        
        if black_frame_count > n_frames * 0.3:
            issues.append(f"{black_frame_count} black frames ({scores['black_frame_pct']}%) - video may be mostly black")
            quality = "defective"
        elif black_frame_count > n_frames * 0.1:
            issues.append(f"{black_frame_count} black frames ({scores['black_frame_pct']}%) - some black frames detected")
            quality = "questionable"
        
        if frozen_frame_count > n_frames * 0.5:
            issues.append(f"{frozen_frame_count} frozen frames ({scores['frozen_frame_pct']}%) - video appears stuck/static")
            quality = "defective"
        elif frozen_frame_count > n_frames * 0.3:
            issues.append(f"{frozen_frame_count} frozen frames ({scores['frozen_frame_pct']}%) - significant static content")
            quality = "questionable"
        
        if duration < 0.5 and n_frames > 0:
            issues.append(f"Duration only {duration:.1f}s - very short video")
            quality = "questionable"
        
        # File size check
        file_size = os.path.getsize(video_path)
        if file_size < 5000:
            issues.append(f"File size only {file_size} bytes - likely corrupted")
            quality = "defective"
        
        scores["file_size_kb"] = round(file_size / 1024, 0)
        
    except Exception as e:
        issues.append(f"QC analysis failed: {str(e)}")
        quality = "unknown"
        scores["error"] = str(e)
    
    qc_results[job_id] = {
        "quality": quality,
        "issues": issues,
        "scores": scores,
        "auto_regenerated": False,
        "checked_at": time.time(),
    }
    
    print(f"[QC] Job {job_id}: {quality} - {issues if issues else 'No issues found'}")
    
    # Auto-regenerate if defective
    if quality == "defective" and not gen_params.get("_auto_regen"):
        _auto_regenerate_video(job_id, gen_params)

# === Auto-Regenerate ===
def _auto_regenerate_video(original_job_id, gen_params):
    """Re-generate a defective video with a new seed."""
    url = config.get("gpu_backend_url", "")
    if not url:
        return
    
    btype = config.get("backend_type", "auto")
    if btype == "auto":
        btype = detect_backend_type(url)
    
    print(f"[Auto-Regen] Re-generating defective video for job {original_job_id}")
    
    # New seed
    import random
    new_seed = random.randint(1, 999999)
    gen_params["seed"] = new_seed
    gen_params["_auto_regen"] = True  # Prevent infinite regen loop
    
    if btype == "gradio":
        # Gradio backend: start a new Gradio generation job
        new_job_id = uuid.uuid4().hex[:12]
        t = threading.Thread(target=_gradio_generate_video, args=(new_job_id, url, gen_params), daemon=True)
        auto_download_tasks[new_job_id] = t
        t.start()
        qc_results[original_job_id]["auto_regenerated"] = True
        qc_results[original_job_id]["regen_job_id"] = new_job_id
        qc_results[original_job_id]["regen_seed"] = new_seed
        print(f"[Auto-Regen] New Gradio job {new_job_id} started with seed {new_seed}")
        return
    
    # Polling backend
    try:
        payload = json.dumps(gen_params).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            new_job_id = data.get("job_id")
        
        if new_job_id:
            qc_results[original_job_id]["auto_regenerated"] = True
            qc_results[original_job_id]["regen_job_id"] = new_job_id
            qc_results[original_job_id]["regen_seed"] = new_seed
            
            # Start auto-download for the new job
            t = threading.Thread(target=_auto_download_video, args=(new_job_id, gen_params), daemon=True)
            auto_download_tasks[new_job_id] = t
            t.start()
            
            print(f"[Auto-Regen] New job {new_job_id} started with seed {new_seed}")
    except Exception as e:
        print(f"[Auto-Regen] Failed: {e}")

@app.get("/api/qc/{job_id}")
async def get_qc_status(job_id: str):
    """Get quality check results for a video."""
    if job_id not in qc_results:
        return {"quality": "pending", "issues": [], "message": "QC not yet run"}
    return qc_results[job_id]

@app.post("/api/qc/{job_id}/recheck")
async def recheck_video(job_id: str):
    """Manually re-run QC on a downloaded video."""
    local_path = VIDEOS_DIR / f"soulillusions_{job_id}.mp4"
    if not local_path.exists():
        return JSONResponse({"error": "Video not found locally"}, status_code=404)
    _run_video_qc(job_id, str(local_path), {})
    return qc_results.get(job_id, {"quality": "unknown"})

@app.post("/api/qc/{job_id}/regenerate")
async def manual_regenerate(job_id: str, req: Request):
    """Manually trigger regeneration of a defective video."""
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}
    url = config.get("gpu_backend_url", "")
    if not url:
        return JSONResponse({"error": "No backend URL"}, status_code=400)
    
    import random
    new_seed = body.get("seed") or random.randint(1, 999999)
    
    # Find original params from QC or use defaults
    gen_params = body.get("params", {
        "prompt": body.get("prompt", "cinematic scene"),
        "model": "ltx",
        "style": "cinematic",
        "num_frames": 97,
        "fps": 24,
        "steps": 30,
        "seed": new_seed,
        "enhance": True,
    })
    gen_params["seed"] = new_seed
    
    btype = config.get("backend_type", "auto")
    if btype == "auto":
        btype = detect_backend_type(url)
    
    if btype == "gradio":
        new_job_id = uuid.uuid4().hex[:12]
        t = threading.Thread(target=_gradio_generate_video, args=(new_job_id, url, gen_params), daemon=True)
        auto_download_tasks[new_job_id] = t
        t.start()
        return {"status": "regenerating", "new_job_id": new_job_id, "seed": new_seed}
    
    try:
        payload = json.dumps(gen_params).encode("utf-8")
        req2 = urllib.request.Request(
            f"{url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req2, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        new_job_id = data.get("job_id")
        
        if new_job_id:
            t = threading.Thread(target=_auto_download_video, args=(new_job_id, gen_params), daemon=True)
            auto_download_tasks[new_job_id] = t
            t.start()
            
            return {"status": "regenerating", "new_job_id": new_job_id, "seed": new_seed}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/styles")
async def get_styles():
    return {
        "styles": [
            {"id": "cinematic", "name": "Cinematic", "desc": "Dramatic lighting, film quality"},
            {"id": "realistic", "name": "Realistic", "desc": "Photorealistic, natural lighting"},
            {"id": "anime", "name": "Anime", "desc": "Cel shaded, vibrant colors"},
            {"id": "documentary", "name": "Documentary", "desc": "Natural, professional photography"},
            {"id": "music video", "name": "Music Video", "desc": "Dynamic lighting, stylized"},
            {"id": "social media", "name": "Social Media", "desc": "Bright, colorful, modern"},
            {"id": "noir", "name": "Film Noir", "desc": "High contrast, black & white"},
            {"id": "vintage", "name": "Vintage", "desc": "Film grain, warm tones, retro"},
            {"id": "cyberpunk", "name": "Cyberpunk", "desc": "Neon, dark, futuristic"},
            {"id": "fantasy", "name": "Fantasy", "desc": "Ethereal, magical, dreamlike"},
            {"id": "horror", "name": "Horror", "desc": "Dark, desaturated, eerie"},
            {"id": "romance", "name": "Romance", "desc": "Soft focus, warm, golden hour"},
            {"id": "action", "name": "Action", "desc": "High contrast, dynamic, intense"},
            {"id": "dreamy", "name": "Dreamy", "desc": "Soft, hazy, pastel tones"},
            {"id": "3d_render", "name": "3D Render", "desc": "CGI, octane render, unreal engine"},
            {"id": "watercolor", "name": "Watercolor", "desc": "Painted, artistic, flowing"},
            {"id": "comic_book", "name": "Comic Book", "desc": "Halftone, bold outlines, ink"},
            {"id": "claymation", "name": "Claymation", "desc": "Stop motion, clay texture"},
        ]
    }

@app.get("/api/settings/options")
async def get_settings_options():
    """Return all available setting options for the UI."""
    return {
        "aspect_ratios": {
            "16:9": "Widescreen (16:9)", "9:16": "Vertical (9:16)", "1:1": "Square (1:1)",
            "4:3": "Classic (4:3)", "21:9": "Cinematic (21:9)", "2.39:1": "Anamorphic (2.39:1)",
            "4:5": "Portrait (4:5)",
        },
        "quality_modes": {
            "draft": "Draft (Fast preview, ~10 steps)", "standard": "Standard (Balanced, ~30 steps)",
            "pro": "Pro (High quality, ~50 steps)", "turbo": "Turbo (Distilled, ~5 steps)",
            "ultra": "Ultra (Maximum quality, ~80 steps)",
        },
        "camera_presets": {
            "static": "Static", "pan_left": "Pan Left", "pan_right": "Pan Right",
            "tilt_up": "Tilt Up", "tilt_down": "Tilt Down", "zoom_in": "Zoom In",
            "zoom_out": "Zoom Out", "dolly_in": "Dolly In", "dolly_out": "Dolly Out",
            "dolly_zoom": "Dolly Zoom (Vertigo)", "orbit_left": "Orbit Left",
            "orbit_right": "Orbit Right", "crane_up": "Crane Up", "crane_down": "Crane Down",
            "pedestal_up": "Pedestal Up", "pedestal_down": "Pedestal Down",
            "tracking": "Tracking Shot", "handheld": "Handheld", "aerial": "Aerial Drone",
        },
        "schedulers": {
            "unipc": "UniPC (Default)", "euler": "Euler (Fast, anime)",
            "euler_ancestral": "Euler Ancestral (Creative)", "ddim": "DDIM (Classic)",
            "dpm_plus_plus": "DPM++ 2M Karras (High quality)",
            "flow_match_euler": "FlowMatch Euler (SD3/Flow)", "flow_match_heun": "FlowMatch Heun",
            "tcd": "TCD (Distilled)",
        },
        "codecs": {
            "h264": "H.264 (Best compatibility)", "h265": "H.265/HEVC (Better compression)",
            "vp9": "VP9 (Web-optimized)", "av1": "AV1 (Best compression, slow)",
        },
        "tune_options": {
            "none": "None", "film": "Film", "animation": "Animation",
            "stillimage": "Still Image", "fastdecode": "Fast Decode", "zerolatency": "Zero Latency",
        },
        "encoding_presets": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
        "transitions": {
            "cut": "Cut", "xfade": "Cross-fade", "fade": "Fade", "dissolve": "Dissolve",
            "wipe_left": "Wipe Left", "wipe_right": "Wipe Right", "slide": "Slide",
            "zoom": "Zoom", "flash": "Flash",
        },
        "upscale_models": {
            "none": "None", "realesrgan_x2": "Real-ESRGAN 2x", "realesrgan_x4": "Real-ESRGAN 4x",
            "realesrgan_anime": "Real-ESRGAN Anime", "lanczos_x2": "Lanczos 2x", "lanczos_x4": "Lanczos 4x",
        },
        "tts_voices": {
            "narrator_male": "Narrator (Male)", "narrator_female": "Narrator (Female)",
            "character_male": "Character (Male)", "character_female": "Character (Female)",
            "news_anchor": "News Anchor", "child": "Child", "elderly": "Elderly", "robot": "Robot/AI",
        },
        "setting_presets": {
            "cinematic_short": "Cinematic Short Film", "social_media_vertical": "Social Media (Vertical)",
            "anime_sequence": "Anime Sequence", "documentary_clip": "Documentary Clip",
            "fast_preview": "Fast Preview (Draft)", "music_video": "Music Video",
            "horror_atmosphere": "Horror Atmosphere",
        },
    }

@app.get("/api/settings/defaults")
async def get_default_settings():
    """Return the full default settings schema."""
    try:
        from settings_schema import get_default_settings as _gds, list_presets
        return {"defaults": _gds(), "presets": list_presets()}
    except ImportError:
        return {"error": "settings_schema not available"}

# === Image Generation API ===
IMAGES_DIR = VIDEOS_DIR.parent / "images"
IMAGES_DIR.mkdir(exist_ok=True)

@app.get("/api/image/models")
async def get_image_models():
    """List available image generation models (T2I and I2I)."""
    try:
        from settings_schema import T2I_MODELS, I2I_MODELS
        return {"t2i": T2I_MODELS, "i2i": I2I_MODELS}
    except ImportError:
        return {"error": "settings_schema not available"}

@app.get("/api/image/options")
async def get_image_options():
    """Return all image generation options (aspect ratios, quality presets, styles, enhance tags, quick prompts)."""
    try:
        from settings_schema import (
            IMAGE_ASPECT_RATIOS, IMAGE_QUALITY_PRESETS, IMAGE_STYLE_PRESETS,
            IMAGE_ENHANCE_TAGS, IMAGE_QUICK_PROMPTS, T2I_MODELS, I2I_MODELS
        )
        return {
            "aspect_ratios": {k: v["label"] for k, v in IMAGE_ASPECT_RATIOS.items()},
            "quality_presets": {k: v["label"] for k, v in IMAGE_QUALITY_PRESETS.items()},
            "style_presets": IMAGE_STYLE_PRESETS,
            "enhance_tags": IMAGE_ENHANCE_TAGS,
            "quick_prompts": IMAGE_QUICK_PROMPTS,
            "t2i_models": {k: {"label": v["label"], "desc": v["desc"], "resolutions": v["resolutions"], "aspect_ratios": v["aspect_ratios"]} for k, v in T2I_MODELS.items()},
            "i2i_models": {k: {"label": v["label"], "desc": v["desc"], "max_images": v["max_images"], "resolutions": v["resolutions"], "aspect_ratios": v["aspect_ratios"]} for k, v in I2I_MODELS.items()},
        }
    except ImportError:
        return {"error": "settings_schema not available"}

@app.post("/api/image/generate")
async def generate_image(req: ImageGenRequest):
    """Generate an image via the GPU backend."""
    url = config.get("gpu_backend_url", "")
    if not url:
        return JSONResponse({"error": "No GPU backend configured"}, status_code=400)
    
    btype = config.get("backend_type", "auto")
    if btype == "auto":
        btype = detect_backend_type(url)
    
    if btype == "gradio":
        # Gradio backend: synchronous call
        job_id = uuid.uuid4().hex[:12]
        t = threading.Thread(target=_gradio_generate_image, args=(job_id, url, req.model_dump()), daemon=True)
        t.start()
        if action_logger:
            action_logger.log("image.generate", {"model": req.model, "mode": req.image_mode, "aspect_ratio": req.aspect_ratio}, source="ui")
        return {"job_id": job_id, "status": "processing"}
    
    try:
        payload = req.model_dump()
        req_data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{url}/api/image/generate",
            data=req_data,
            headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        if action_logger:
            action_logger.log("image.generate", {"model": req.model, "mode": req.image_mode, "aspect_ratio": req.aspect_ratio}, source="ui")
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/image/status/{job_id}")
async def check_image_status(job_id: str):
    """Check image generation job status."""
    # Check if this is a Gradio job (tracked locally)
    if job_id in _gradio_job_status:
        return _gradio_job_status[job_id]
    
    url = config.get("gpu_backend_url", "")
    if not url:
        return JSONResponse({"error": "No GPU backend configured"}, status_code=400)
    try:
        request = urllib.request.Request(
            f"{url}/api/image/status/{job_id}",
            headers={"User-Agent": "SoulIllusions/1.0"}
        )
        with urllib.request.urlopen(request, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/image/download/{job_id}")
async def download_image(job_id: str):
    """Download a generated image from the backend and save locally."""
    # Check if already downloaded locally by Gradio backend
    local_path = IMAGES_DIR / f"img_{job_id}.png"
    if local_path.exists() and local_path.stat().st_size > 100:
        return FileResponse(str(local_path), media_type="image/png", filename=f"img_{job_id}.png")
    
    url = config.get("gpu_backend_url", "")
    if not url:
        return JSONResponse({"error": "No GPU backend configured"}, status_code=400)
    try:
        request = urllib.request.Request(
            f"{url}/api/image/download/{job_id}",
            headers={"User-Agent": "SoulIllusions/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            img_data = resp.read()
        filename = f"img_{job_id}.png"
        filepath = IMAGES_DIR / filename
        with open(filepath, "wb") as f:
            f.write(img_data)
        return FileResponse(filepath, media_type="image/png", filename=filename)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/images")
async def list_images():
    """List all locally saved images."""
    images = []
    if IMAGES_DIR.exists():
        for f in sorted(IMAGES_DIR.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True):
            images.append({
                "id": f.stem,
                "url": f"/api/image/file/{f.stem}",
                "filename": f.name,
                "size": f.stat().st_size,
                "created": f.stat().st_mtime,
            })
    return {"images": images}

@app.get("/api/image/file/{img_id}")
async def serve_image_file(img_id: str):
    """Serve a locally saved image file."""
    filepath = IMAGES_DIR / f"{img_id}.png"
    if not filepath.exists():
        return JSONResponse({"error": "Image not found"}, status_code=404)
    return FileResponse(filepath, media_type="image/png")

# === Asset Library API ===
@app.get("/api/assets/categories")
async def get_asset_categories():
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    return {"categories": asset_library.get_categories()}

@app.get("/api/assets")
async def list_assets(category: str = None, subtype: str = None, tag: str = None,
                      series_id: str = None, search: str = None, limit: int = 100):
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    return {"assets": asset_library.list_assets(category=category, subtype=subtype,
            tag=tag, series_id=series_id, search=search, limit=limit)}

@app.post("/api/assets/create")
async def create_asset(req: Request):
    if not ASSET_LIBRARY_AVAILABLE:
        return JSONResponse({"error": "Asset library not available"}, status_code=500)
    data = await req.json()
    try:
        asset = asset_library.create_asset(
            name=data["name"], category=data["category"],
            subtype=data.get("subtype", ""), description=data.get("description", ""),
            tags=data.get("tags", []), image_refs=data.get("image_refs", []),
            prompt=data.get("prompt", ""), negative_prompt=data.get("negative_prompt", ""),
            model=data.get("model", ""), settings=data.get("settings", {}),
            notes=data.get("notes", ""),
        )
        return {"asset": asset.to_dict(), "status": "created"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/assets/stats")
async def get_asset_stats():
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    return asset_library.stats()

@app.get("/api/assets/series/{series_id}")
async def get_series_assets(series_id: str):
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    return {"assets": asset_library.get_series_assets(series_id)}

@app.get("/api/assets/consistency/{series_id}")
async def get_consistency_refs(series_id: str, scene_prompt: str = ""):
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    refs = asset_library.get_consistency_refs(series_id, scene_prompt)
    enhanced_prompt = asset_library.build_generation_prompt(series_id, scene_prompt)
    return {"refs": refs, "enhanced_prompt": enhanced_prompt}

@app.get("/api/assets/{asset_id}")
async def get_asset(asset_id: str):
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    a = asset_library.get_asset(asset_id)
    if not a:
        return JSONResponse({"error": "Asset not found"}, status_code=404)
    return {"asset": a.to_dict()}

@app.put("/api/assets/{asset_id}")
async def update_asset(asset_id: str, req: Request):
    if not ASSET_LIBRARY_AVAILABLE:
        return JSONResponse({"error": "Asset library not available"}, status_code=500)
    data = await req.json()
    a = asset_library.update_asset(asset_id,
        name=data.get("name"), description=data.get("description"),
        tags=data.get("tags"), subtype=data.get("subtype"),
        locked=data.get("locked"), metadata=data.get("metadata"))
    if not a:
        return JSONResponse({"error": "Asset not found"}, status_code=404)
    return {"asset": a.to_dict(), "status": "updated"}

@app.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: str):
    if not ASSET_LIBRARY_AVAILABLE:
        return JSONResponse({"error": "Asset library not available"}, status_code=500)
    ok = asset_library.delete_asset(asset_id)
    return {"status": "deleted" if ok else "not_found"}

@app.post("/api/assets/{asset_id}/version")
async def add_asset_version(asset_id: str, req: Request):
    if not ASSET_LIBRARY_AVAILABLE:
        return JSONResponse({"error": "Asset library not available"}, status_code=500)
    data = await req.json()
    v = asset_library.add_version(asset_id,
        image_refs=data.get("image_refs", []),
        description=data.get("description"),
        prompt=data.get("prompt", ""), negative_prompt=data.get("negative_prompt", ""),
        model=data.get("model", ""), settings=data.get("settings", {}),
        notes=data.get("notes", ""))
    if not v:
        return JSONResponse({"error": "Asset not found"}, status_code=404)
    return {"version": v.to_dict(), "status": "added"}

@app.post("/api/assets/{asset_id}/rollback/{version_num}")
async def rollback_asset(asset_id: str, version_num: int):
    if not ASSET_LIBRARY_AVAILABLE:
        return JSONResponse({"error": "Asset library not available"}, status_code=500)
    ok = asset_library.rollback(asset_id, version_num)
    return {"status": "rolled_back" if ok else "failed"}

@app.get("/api/assets/{asset_id}/compare/{v1}/{v2}")
async def compare_asset_versions(asset_id: str, v1: int, v2: int):
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    return asset_library.compare_versions(asset_id, v1, v2)

@app.get("/api/assets/{asset_id}/archive")
async def get_asset_archive(asset_id: str):
    if not ASSET_LIBRARY_AVAILABLE:
        return {"error": "Asset library not available"}
    return asset_library.get_archive(asset_id)

@app.post("/api/assets/{asset_id}/bind")
async def bind_asset_to_series(asset_id: str, req: Request):
    if not ASSET_LIBRARY_AVAILABLE:
        return JSONResponse({"error": "Asset library not available"}, status_code=500)
    data = await req.json()
    ok = asset_library.bind_to_series(asset_id, data.get("series_id", ""),
        data.get("seasons", []), data.get("episodes", []))
    return {"status": "bound" if ok else "failed"}

# === Script Parser API ===
@app.post("/api/script/parse")
async def parse_script(req: Request):
    if not SCRIPT_PARSER_AVAILABLE:
        return JSONResponse({"error": "Script parser not available"}, status_code=500)
    data = await req.json()
    script_text = data.get("script_text", "")
    title = data.get("title", "")
    if not script_text:
        return JSONResponse({"error": "No script text provided"}, status_code=400)
    result = script_parser.parse_and_extract(script_text, title)
    if action_logger:
        action_logger.log("script.parse", result.get("metadata", {}), source="ui")
    return result

@app.post("/api/script/batch-prompts")
async def get_batch_prompts(req: Request):
    if not SCRIPT_PARSER_AVAILABLE:
        return JSONResponse({"error": "Script parser not available"}, status_code=500)
    data = await req.json()
    script_text = data.get("script_text", "")
    title = data.get("title", "")
    category = data.get("category")
    result = script_parser.parse(script_text, title)
    prompts = script_parser.generate_batch_prompts(result, category)
    return {"prompts": prompts, "metadata": result.metadata}

# === Bitrate Presets API ===
@app.get("/api/bitrate/presets")
async def get_bitrate_presets():
    try:
        from settings_schema import BITRATE_PRESETS, BITRATE_MODES
        return {"presets": {k: v for k, v in BITRATE_PRESETS.items()},
                "modes": BITRATE_MODES}
    except ImportError:
        return {"error": "settings_schema not available"}

# === HTML Frontend ===
def get_html():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SoulIllusions AI Video Maker</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg: #0a0a0f;
            --surface: #13131a;
            --surface2: #1a1a24;
            --border: #2a2a3a;
            --text: #e4e4e7;
            --muted: #71717a;
            --accent: #8b5cf6;
            --accent2: #ec4899;
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Animated background */
        .bg-glow {
            position: fixed;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at 30% 40%, rgba(139, 92, 246, 0.08) 0%, transparent 50%),
                        radial-gradient(circle at 70% 60%, rgba(236, 72, 153, 0.06) 0%, transparent 50%);
            z-index: 0;
            animation: glow-shift 20s ease-in-out infinite;
        }
        
        @keyframes glow-shift {
            0%, 100% { transform: translate(0, 0); }
            50% { transform: translate(-5%, -5%); }
        }
        
        .container {
            position: relative;
            z-index: 1;
            max-width: 1100px;
            margin: 0 auto;
            padding: 24px;
        }
        
        /* Header */
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 20px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 32px;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        
        .logo-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            box-shadow: 0 4px 20px rgba(139, 92, 246, 0.3);
        }
        
        .logo-text h1 {
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .logo-text p {
            font-size: 12px;
            color: var(--muted);
            margin-top: 2px;
        }
        
        .gpu-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            background: var(--surface);
            border: 1px solid var(--border);
            font-size: 13px;
        }
        
        .gpu-badge .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--error);
        }
        
        .gpu-badge.online .dot {
            background: var(--success);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Backend setup */
        .setup-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
        }
        
        .setup-card h2 {
            font-size: 18px;
            margin-bottom: 8px;
        }
        
        .setup-card p {
            color: var(--muted);
            font-size: 14px;
            margin-bottom: 20px;
            line-height: 1.6;
        }
        
        .setup-steps {
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .step {
            flex: 1;
            min-width: 200px;
            background: var(--surface2);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid var(--border);
        }
        
        .step-num {
            width: 28px;
            height: 28px;
            border-radius: 8px;
            background: var(--accent);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 10px;
        }
        
        .step h3 {
            font-size: 14px;
            margin-bottom: 4px;
        }
        
        .step p {
            font-size: 12px;
            margin: 0;
        }
        
        .input-group {
            display: flex;
            gap: 12px;
        }
        
        input[type="text"] {
            flex: 1;
            padding: 12px 16px;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            outline: none;
            transition: border 0.2s;
        }
        
        input[type="text"]:focus {
            border-color: var(--accent);
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(139, 92, 246, 0.3);
        }
        
        .btn-secondary {
            background: var(--surface2);
            color: var(--text);
            border: 1px solid var(--border);
        }
        
        .btn-secondary:hover {
            border-color: var(--accent);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Generate panel */
        .generate-panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
        }
        
        .generate-panel.disabled {
            opacity: 0.4;
            pointer-events: none;
        }
        
        .generate-panel h2 {
            font-size: 18px;
            margin-bottom: 20px;
        }
        
        textarea {
            width: 100%;
            min-height: 100px;
            padding: 16px;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: var(--text);
            font-size: 15px;
            font-family: inherit;
            resize: vertical;
            outline: none;
            transition: border 0.2s;
        }
        
        textarea:focus {
            border-color: var(--accent);
        }
        
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        
        .control {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        
        .control label {
            font-size: 12px;
            color: var(--muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        select {
            padding: 10px 14px;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            outline: none;
            cursor: pointer;
        }
        
        select:focus {
            border-color: var(--accent);
        }
        
        input[type="range"] {
            -webkit-appearance: none;
            width: 100%;
            height: 6px;
            background: var(--surface2);
            border-radius: 3px;
            outline: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: var(--accent);
            cursor: pointer;
        }
        
        .range-value {
            font-size: 13px;
            color: var(--accent);
            font-weight: 600;
        }
        
        .generate-btn-row {
            display: flex;
            gap: 12px;
            margin-top: 20px;
            align-items: center;
        }
        
        /* Progress */
        .progress-bar {
            flex: 1;
            height: 8px;
            background: var(--surface2);
            border-radius: 4px;
            overflow: hidden;
            display: none;
        }
        
        .progress-bar.active {
            display: block;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent), var(--accent2));
            width: 0%;
            transition: width 0.5s;
            border-radius: 4px;
        }
        
        .progress-text {
            font-size: 13px;
            color: var(--muted);
            min-width: 120px;
        }
        
        /* Video results */
        .results-section {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
        }
        
        .results-section h2 {
            font-size: 18px;
            margin-bottom: 20px;
        }
        
        .video-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .video-card {
            background: var(--surface2);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            transition: transform 0.2s;
        }
        
        .video-card:hover {
            transform: translateY(-2px);
            border-color: var(--accent);
        }
        
        .video-card video {
            width: 100%;
            display: block;
            background: #000;
        }
        
        .video-info {
            padding: 14px;
        }
        
        .video-info .name {
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 4px;
            word-break: break-all;
        }
        
        .video-info .meta {
            font-size: 12px;
            color: var(--muted);
            display: flex;
            justify-content: space-between;
        }
        
        .video-actions {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }
        
        .qc-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }
        .qc-good { background: rgba(34,197,94,0.15); color: #22c55e; }
        .qc-bad { background: rgba(239,68,68,0.15); color: #ef4444; }
        .qc-warn { background: rgba(245,158,11,0.15); color: #f59e0b; }
        .qc-pending { background: rgba(148,163,184,0.15); color: #94a3b8; }
        .qc-regen { background: rgba(99,102,241,0.15); color: #6366f1; }
        
        .qc-issues {
            margin-top: 6px;
            padding: 6px 8px;
            background: rgba(239,68,68,0.08);
            border-radius: 6px;
            font-size: 11px;
        }
        .qc-issue {
            color: #ef4444;
            padding: 2px 0;
        }
        
        .btn-warning {
            background: rgba(245,158,11,0.2);
            color: #f59e0b;
            border: 1px solid rgba(245,158,11,0.3);
        }
        .btn-warning:hover {
            background: rgba(245,158,11,0.3);
        }
        
        .btn-sm {
            padding: 6px 14px;
            font-size: 12px;
            border-radius: 8px;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--muted);
        }
        
        .empty-state .icon {
            font-size: 48px;
            margin-bottom: 12px;
            opacity: 0.3;
        }
        
        /* Toast */
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 14px 24px;
            border-radius: 12px;
            font-size: 14px;
            z-index: 1000;
            transform: translateX(400px);
            transition: transform 0.3s;
        }
        
        .toast.show {
            transform: translateX(0);
        }
        
        .toast.success {
            background: var(--success);
            color: white;
        }
        
        .toast.error {
            background: var(--error);
            color: white;
        }
        
        /* Colab link */
        .colab-link {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: #FFD700;
            color: #333;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
            transition: transform 0.2s;
        }
        
        .colab-link:hover {
            transform: translateY(-1px);
        }
        
        /* === Tab System === */
        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 24px;
            border-bottom: 2px solid var(--border);
        }
        .tab {
            padding: 12px 24px;
            background: transparent;
            border: none;
            color: var(--muted);
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }
        .tab:hover { color: var(--text); }
        .tab.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* === Production Suite === */
        .prod-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
        }
        .prod-card h2 {
            font-size: 20px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .prod-card h3 {
            font-size: 16px;
            margin-bottom: 12px;
            color: var(--accent);
        }
        .prod-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }
        @media (max-width: 700px) { .prod-grid { grid-template-columns: 1fr; } }
        .prod-input {
            width: 100%;
            padding: 10px 14px;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            outline: none;
            margin-bottom: 10px;
        }
        .prod-textarea {
            width: 100%;
            min-height: 200px;
            padding: 14px;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            outline: none;
            resize: vertical;
            font-family: 'Consolas', monospace;
            line-height: 1.6;
        }
        .prod-textarea.large {
            min-height: 400px;
        }
        .prod-label {
            font-size: 13px;
            color: var(--muted);
            margin-bottom: 6px;
            display: block;
        }
        .prod-select {
            width: 100%;
            padding: 10px 14px;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            outline: none;
            margin-bottom: 10px;
        }
        .prod-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            background: var(--accent);
            color: white;
        }
        .prod-btn:hover { opacity: 0.9; transform: translateY(-1px); }
        .prod-btn.secondary { background: var(--surface2); border: 1px solid var(--border); color: var(--text); }
        .prod-btn.danger { background: var(--error); }
        .prod-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .prod-btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
        
        /* Series List */
        .series-card {
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .series-card:hover { border-color: var(--accent); }
        .series-card h4 { font-size: 16px; margin-bottom: 6px; }
        .series-card p { font-size: 13px; color: var(--muted); }
        .series-card .meta { display: flex; gap: 16px; margin-top: 8px; font-size: 12px; color: var(--muted); }
        .series-card .meta span { display: flex; align-items: center; gap: 4px; }
        
        /* Timeline */
        .timeline {
            display: flex;
            gap: 2px;
            overflow-x: auto;
            padding: 12px;
            background: var(--surface2);
            border-radius: 12px;
            margin-bottom: 16px;
            min-height: 80px;
        }
        .timeline-scene {
            min-width: 60px;
            height: 60px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
            flex-shrink: 0;
            position: relative;
        }
        .timeline-scene.pending { background: var(--surface); color: var(--muted); border-color: var(--border); }
        .timeline-scene.generating { background: var(--warning); color: #000; animation: pulse 1.5s infinite; }
        .timeline-scene.complete { background: var(--success); color: #fff; }
        .timeline-scene.failed { background: var(--error); color: #fff; }
        .timeline-scene.retake { background: var(--accent); color: #fff; }
        .timeline-scene:hover { transform: scale(1.1); z-index: 10; }
        .timeline-scene.selected { border-color: var(--accent2); transform: scale(1.15); }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
        
        /* Scene Editor */
        .scene-editor {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-top: 16px;
        }
        @media (max-width: 700px) { .scene-editor { grid-template-columns: 1fr; } }
        .scene-preview {
            background: var(--surface2);
            border-radius: 12px;
            padding: 16px;
        }
        .scene-preview video {
            width: 100%;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .scene-info {
            font-size: 13px;
            color: var(--muted);
            line-height: 1.6;
        }
        .scene-info strong { color: var(--text); }
        
        /* Progress */
        .gen-progress {
            background: var(--surface2);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .gen-progress-bar {
            height: 8px;
            background: var(--border);
            border-radius: 4px;
            overflow: hidden;
            margin: 8px 0;
        }
        .gen-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent), var(--accent2));
            transition: width 0.5s;
        }
        .gen-stats { display: flex; gap: 20px; font-size: 13px; color: var(--muted); }
        .gen-stats span { display: flex; align-items: center; gap: 4px; }
        
        /* Episode List */
        .episode-card {
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            transition: all 0.2s;
        }
        .episode-card:hover { border-color: var(--accent); }
        .episode-card .ep-num { font-size: 12px; color: var(--muted); }
        .episode-card .ep-title { font-size: 15px; font-weight: 600; }
        .episode-card .ep-status {
            font-size: 11px;
            padding: 3px 10px;
            border-radius: 20px;
            font-weight: 600;
        }
        .ep-status.draft { background: var(--surface); color: var(--muted); }
        .ep-status.scripted { background: rgba(139,92,246,0.2); color: var(--accent); }
        .ep-status.broken_down { background: rgba(245,158,11,0.2); color: var(--warning); }
        .ep-status.generating { background: rgba(245,158,11,0.3); color: var(--warning); }
        .ep-status.assembled { background: rgba(34,197,94,0.2); color: var(--success); }
        .ep-status.complete { background: var(--success); color: #fff; }
        .ep-status.published { background: var(--accent); color: #fff; }
        
        .breadcrumb { display: flex; gap: 8px; align-items: center; font-size: 14px; margin-bottom: 16px; color: var(--muted); }
        .breadcrumb a { color: var(--accent); cursor: pointer; text-decoration: none; }
        .breadcrumb a:hover { text-decoration: underline; }
        .breadcrumb .sep { color: var(--border); }
        
        .char-list { display: flex; flex-direction: column; gap: 8px; }
        .char-item { background: var(--surface2); border-radius: 8px; padding: 10px 14px; font-size: 13px; }
        .char-item strong { color: var(--accent); }
        
        .info-banner {
            background: rgba(139,92,246,0.1);
            border: 1px solid rgba(139,92,246,0.3);
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 13px;
            color: var(--text);
            margin-bottom: 16px;
        }
        .info-banner.warning {
            background: rgba(245,158,11,0.1);
            border-color: rgba(245,158,11,0.3);
        }
        
        /* === Narrative Memory UI === */
        .memory-panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
        }
        .memory-panel h4 {
            color: var(--accent);
            margin-bottom: 10px;
            font-size: 14px;
        }
        .memory-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
        }
        .memory-badge.on {
            background: rgba(34,197,94,0.15);
            color: #22c55e;
            border: 1px solid rgba(34,197,94,0.3);
        }
        .memory-badge.off {
            background: rgba(239,68,68,0.15);
            color: #ef4444;
            border: 1px solid rgba(239,68,68,0.3);
        }
        .memory-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-top: 10px;
        }
        .memory-item {
            background: var(--surface2);
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 12px;
        }
        .memory-item .label {
            color: var(--muted);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .memory-item .value {
            color: var(--text);
            font-weight: 500;
        }
        .narrative-stack-viz {
            display: flex;
            flex-direction: column-reverse;
            gap: 4px;
            margin: 10px 0;
        }
        .stack-layer {
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 3px solid;
        }
        .stack-layer.main { background: rgba(59,130,246,0.1); border-color: #3b82f6; }
        .stack-layer.flashback { background: rgba(168,85,247,0.1); border-color: #a855f7; }
        .stack-layer.dream { background: rgba(236,72,153,0.1); border-color: #ec4899; }
        .stack-layer.memory { background: rgba(245,158,11,0.1); border-color: #f59e0b; }
        .stack-layer.vision { background: rgba(16,185,129,0.1); border-color: #10b981; }
        .stack-layer.parallel { background: rgba(99,102,241,0.1); border-color: #6366f1; }
        .stack-layer.active {
            box-shadow: 0 0 0 2px rgba(139,92,246,0.3);
        }
        .urgency-bar {
            height: 6px;
            border-radius: 3px;
            background: var(--surface2);
            overflow: hidden;
            margin-top: 4px;
        }
        .urgency-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }
        .urgency-fill.low { background: #22c55e; }
        .urgency-fill.mid { background: #f59e0b; }
        .urgency-fill.high { background: #ef4444; }
        .learning-card {
            background: var(--surface2);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            font-size: 12px;
        }
        .learning-score {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 11px;
        }
        .learning-score.good { background: rgba(34,197,94,0.2); color: #22c55e; }
        .learning-score.mid { background: rgba(245,158,11,0.2); color: #f59e0b; }
        .learning-score.low { background: rgba(239,68,68,0.2); color: #ef4444; }
        .scene-memory-tag {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            margin: 1px;
            background: var(--surface2);
            color: var(--muted);
        }
        .scene-memory-tag.char { color: #3b82f6; }
        .scene-memory-tag.loc { color: #10b981; }
        .scene-memory-tag.tone { color: #f59e0b; }
        .scene-memory-tag.urgency { color: #ef4444; }
        .scene-memory-tag.timeline { color: #a855f7; }
        .memory-tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 12px;
        }
        .memory-tab {
            padding: 6px 14px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--surface);
            color: var(--muted);
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
        }
        .memory-tab.active {
            background: var(--accent);
            color: white;
            border-color: var(--accent);
        }
        /* === Settings Panel === */
        .settings-tabs {
            display: flex;
            gap: 2px;
            margin-bottom: 16px;
            flex-wrap: wrap;
            border-bottom: 1px solid var(--border);
        }
        .settings-tab {
            padding: 8px 16px;
            border: none;
            background: transparent;
            color: var(--muted);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }
        .settings-tab:hover { color: var(--text); }
        .settings-tab.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
        }
        .settings-panel { display: none; }
        .settings-panel.active { display: block; }
        .settings-section {
            background: var(--surface);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid var(--border);
        }
        .settings-section h4 {
            font-size: 13px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        .settings-row {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 8px;
        }
        .settings-row .control { flex: 1; min-width: 140px; }
        .settings-row .control label { font-size: 12px; }
        .settings-row .control select,
        .settings-row .control input {
            font-size: 13px;
            padding: 8px 12px;
        }
        .slider-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
        .slider-row label { min-width: 120px; font-size: 12px; color: var(--muted); }
        .slider-row input[type="range"] { flex: 1; }
        .slider-row .val { min-width: 40px; text-align: right; font-size: 12px; color: var(--text); font-weight: 600; }
        .checkbox-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
            font-size: 13px;
            color: var(--text);
            cursor: pointer;
        }
        .checkbox-row input { cursor: pointer; }
        .preset-bar {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .preset-btn {
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid var(--border);
            background: var(--surface2);
            color: var(--text);
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .preset-btn:hover {
            border-color: var(--accent);
            color: var(--accent);
        }
        .collapsible-header {
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
        }
        .collapsible-header h4 { margin: 0; }
        .collapsible-header::after { content: '▼'; font-size: 10px; color: var(--muted); transition: transform 0.2s; }
        .collapsible-header.collapsed::after { transform: rotate(-90deg); }
        .collapsible-body { overflow: hidden; transition: max-height 0.3s; }
        .collapsible-body.collapsed { max-height: 0; }

        /* === Image Studio === */
        .img-studio { max-width: 900px; margin: 0 auto; padding: 20px 0; }
        .img-hero { text-align: center; padding: 40px 20px; transition: all 0.5s; }
        .img-hero h2 { font-size: 2.5em; font-weight: 900; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 10px; }
        .img-hero p { color: var(--muted); font-size: 0.9em; }
        .img-prompt-bar { background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 16px; margin: 20px 0; box-shadow: 0 4px 30px rgba(0,0,0,0.3); }
        .img-prompt-row { display: flex; align-items: flex-start; gap: 12px; }
        .img-prompt-row textarea { flex: 1; background: transparent; border: none; color: var(--text); font-size: 1.1em; resize: none; outline: none; min-height: 44px; max-height: 200px; padding: 8px 0; }
        .img-upload-btn { width: 44px; height: 44px; border-radius: 12px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 20px; color: var(--muted); transition: all 0.2s; flex-shrink: 0; }
        .img-upload-btn:hover { background: rgba(255,255,255,0.1); color: var(--accent); }
        .img-upload-btn.active { background: var(--accent); color: #000; border-color: var(--accent); }
        .img-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-top: 12px; border-top: 1px solid var(--border); margin-top: 8px; }
        .img-ctrl-btn { display: flex; align-items: center; gap: 6px; padding: 8px 14px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 10px; cursor: pointer; font-size: 0.8em; font-weight: 600; color: var(--text); transition: all 0.2s; white-space: nowrap; }
        .img-ctrl-btn:hover { background: rgba(255,255,255,0.1); }
        .img-ctrl-btn svg { opacity: 0.6; }
        .img-gen-btn { background: var(--accent); color: #000; padding: 12px 28px; border-radius: 14px; font-weight: 800; font-size: 0.9em; border: none; cursor: pointer; transition: all 0.2s; margin-left: auto; }
        .img-gen-btn:hover { box-shadow: 0 0 20px var(--accent); transform: scale(1.03); }
        .img-gen-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .img-dropdown { position: absolute; background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 12px; box-shadow: 0 8px 40px rgba(0,0,0,0.5); z-index: 100; max-height: 400px; overflow-y: auto; min-width: 240px; }
        .img-dropdown-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 10px; cursor: pointer; transition: background 0.15s; }
        .img-dropdown-item:hover { background: rgba(255,255,255,0.05); }
        .img-dropdown-item.selected { background: rgba(255,255,255,0.08); border: 1px solid var(--border); }
        .img-dropdown-item .model-icon { width: 36px; height: 36px; border-radius: 10px; background: var(--accent-dim); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.8em; flex-shrink: 0; }
        .img-dropdown-item .model-info { flex: 1; }
        .img-dropdown-item .model-name { font-size: 0.85em; font-weight: 700; }
        .img-dropdown-item .model-desc { font-size: 0.7em; color: var(--muted); }
        .img-dropdown-search { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; color: var(--text); font-size: 0.8em; outline: none; margin-bottom: 8px; }
        .img-adv-panel { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px; margin-top: 12px; }
        .img-adv-panel h3 { font-size: 0.85em; font-weight: 700; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .img-adv-panel .close-adv { cursor: pointer; color: var(--muted); font-size: 1.2em; }
        .img-adv-row { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 12px; }
        .img-adv-field { flex: 1; min-width: 180px; }
        .img-adv-field label { font-size: 0.7em; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); display: block; margin-bottom: 4px; }
        .img-adv-field input[type="text"], .img-adv-field input[type="number"] { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; color: var(--text); font-size: 0.85em; outline: none; }
        .img-adv-field input[type="range"] { width: 100%; accent-color: var(--accent); }
        .img-adv-field .range-val { font-size: 0.75em; font-weight: 700; color: var(--accent); float: right; }
        .img-style-presets { display: flex; flex-wrap: wrap; gap: 6px; }
        .img-style-btn { padding: 5px 12px; border-radius: 8px; font-size: 0.75em; font-weight: 600; background: rgba(255,255,255,0.05); border: 1px solid var(--border); cursor: pointer; transition: all 0.15s; color: var(--muted); }
        .img-style-btn:hover { background: rgba(255,255,255,0.1); }
        .img-style-btn.active { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }
        .img-tools-panel { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px; margin-top: 12px; }
        .img-tools-panel h3 { font-size: 0.85em; font-weight: 700; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .img-quick-prompts { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 6px; margin-bottom: 12px; }
        .img-quick-btn { padding: 8px 10px; border-radius: 8px; font-size: 0.75em; font-weight: 600; background: rgba(255,255,255,0.05); border: 1px solid var(--border); cursor: pointer; transition: all 0.15s; text-align: left; color: var(--muted); }
        .img-quick-btn:hover { background: rgba(255,255,255,0.1); color: var(--accent); border-color: var(--accent); }
        .img-enhance-tags { display: flex; flex-wrap: wrap; gap: 4px; }
        .img-tag-btn { padding: 4px 10px; border-radius: 20px; font-size: 0.7em; font-weight: 600; background: rgba(255,255,255,0.05); border: 1px solid var(--border); cursor: pointer; transition: all 0.15s; color: var(--muted); }
        .img-tag-btn:hover { background: rgba(255,255,255,0.1); }
        .img-tag-btn.active { background: var(--accent); color: #000; border-color: var(--accent); }
        .img-enhanced-display { background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 8px; padding: 10px; font-size: 0.8em; min-height: 36px; margin: 8px 0; color: var(--muted); }
        .img-canvas { position: fixed; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 200; background: var(--bg); opacity: 0; pointer-events: none; transition: all 0.5s; }
        .img-canvas.active { opacity: 1; pointer-events: auto; }
        .img-canvas img { max-height: 70vh; max-width: 85vw; border-radius: 20px; box-shadow: 0 8px 40px rgba(0,0,0,0.5); border: 1px solid var(--border); object-fit: contain; }
        .img-canvas-controls { margin-top: 20px; display: flex; gap: 12px; }
        .img-canvas-controls button { padding: 10px 24px; border-radius: 12px; font-size: 0.85em; font-weight: 700; border: 1px solid var(--border); cursor: pointer; transition: all 0.2s; background: rgba(255,255,255,0.1); color: var(--text); }
        .img-canvas-controls button:hover { background: rgba(255,255,255,0.2); }
        .img-canvas-controls .btn-primary { background: var(--accent); color: #000; border: none; }
        .img-canvas-controls .btn-primary:hover { box-shadow: 0 0 20px var(--accent); }
        .img-history { position: fixed; right: 0; top: 0; height: 100vh; width: 80px; background: rgba(0,0,0,0.6); backdrop-filter: blur(20px); border-left: 1px solid var(--border); z-index: 150; display: flex; flex-direction: column; align-items: center; padding: 16px 8px; gap: 8px; overflow-y: auto; transform: translateX(100%); opacity: 0; transition: all 0.4s; }
        .img-history.active { transform: translateX(0); opacity: 1; }
        .img-history-label { font-size: 0.6em; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: var(--muted); margin-bottom: 8px; }
        .img-history-thumb { width: 100%; aspect-ratio: 1; border-radius: 10px; overflow: hidden; cursor: pointer; border: 2px solid var(--border); transition: all 0.2s; position: relative; }
        .img-history-thumb:hover { border-color: var(--accent); }
        .img-history-thumb.active { border-color: var(--accent); box-shadow: 0 0 15px var(--accent-dim); }
        .img-history-thumb img { width: 100%; height: 100%; object-fit: cover; }
        .img-history-thumb .thumb-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.6); opacity: 0; display: flex; align-items: center; justify-content: center; transition: opacity 0.2s; }
        .img-history-thumb:hover .thumb-overlay { opacity: 1; }
        .img-ref-preview { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
        .img-ref-thumb { position: relative; width: 60px; height: 60px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
        .img-ref-thumb img { width: 100%; height: 100%; object-fit: cover; }
        .img-ref-thumb .ref-remove { position: absolute; top: 2px; right: 2px; width: 18px; height: 18px; border-radius: 50%; background: rgba(0,0,0,0.7); color: #fff; font-size: 10px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .img-progress { width: 100%; max-width: 900px; margin: 16px auto; }
        .img-progress-bar { height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden; }
        .img-progress-fill { height: 100%; background: var(--accent); transition: width 0.3s; width: 0%; }
        .img-progress-text { text-align: center; font-size: 0.8em; color: var(--muted); margin-top: 6px; }
        .img-mode-badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.65em; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
        .img-mode-badge.t2i { background: var(--accent-dim); color: var(--accent); }
        .img-mode-badge.i2i { background: rgba(168,85,247,0.15); color: #a855f7; }
        /* === Asset Library === */
        .asset-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; min-height: 600px; }
        .asset-sidebar { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px; overflow-y: auto; max-height: calc(100vh - 200px); }
        .asset-main { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; overflow-y: auto; max-height: calc(100vh - 200px); }
        .asset-search { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; color: var(--text); font-size: 0.85em; outline: none; margin-bottom: 12px; }
        .asset-cat-list { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
        .asset-cat-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 10px; cursor: pointer; font-size: 0.85em; color: var(--muted); transition: all 0.15s; }
        .asset-cat-item:hover { background: rgba(255,255,255,0.05); color: var(--text); }
        .asset-cat-item.active { background: var(--accent-dim); color: var(--accent); }
        .asset-cat-item .cat-icon { font-size: 1.2em; }
        .asset-cat-item .cat-count { margin-left: auto; font-size: 0.75em; background: rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 10px; }
        .asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
        .asset-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 12px; cursor: pointer; transition: all 0.2s; position: relative; }
        .asset-card:hover { border-color: var(--accent); transform: translateY(-2px); }
        .asset-card.selected { border-color: var(--accent); box-shadow: 0 0 20px var(--accent-dim); }
        .asset-card.locked::after { content: "\\1F512"; position: absolute; top: 8px; right: 8px; font-size: 0.7em; opacity: 0.6; }
        .asset-card img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 10px; margin-bottom: 8px; background: var(--surface2); }
        .asset-card .asset-name { font-size: 0.85em; font-weight: 700; margin-bottom: 2px; }
        .asset-card .asset-cat { font-size: 0.7em; color: var(--muted); }
        .asset-card .asset-ver { font-size: 0.65em; color: var(--accent); margin-top: 4px; }
        .asset-detail { display: flex; flex-direction: column; gap: 16px; }
        .asset-detail-header { display: flex; align-items: flex-start; gap: 16px; }
        .asset-detail-img { width: 200px; height: 200px; object-fit: cover; border-radius: 14px; border: 1px solid var(--border); }
        .asset-detail-info { flex: 1; }
        .asset-detail-info h2 { font-size: 1.2em; margin-bottom: 4px; }
        .asset-detail-info .asset-tag { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.7em; font-weight: 600; background: var(--accent-dim); color: var(--accent); margin-right: 4px; margin-bottom: 4px; }
        .asset-detail-info .asset-desc { font-size: 0.85em; color: var(--muted); margin-top: 8px; line-height: 1.5; }
        .asset-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .asset-btn { padding: 8px 16px; border-radius: 10px; font-size: 0.8em; font-weight: 600; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; transition: all 0.15s; }
        .asset-btn:hover { background: rgba(255,255,255,0.08); }
        .asset-btn.primary { background: var(--accent); color: #000; border-color: var(--accent); }
        .asset-btn.primary:hover { box-shadow: 0 0 15px var(--accent-dim); }
        .asset-btn.danger { color: #ef4444; border-color: rgba(239,68,68,0.3); }
        .asset-btn.danger:hover { background: rgba(239,68,68,0.1); }
        .asset-version-list { display: flex; flex-direction: column; gap: 8px; }
        .asset-version-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 10px; background: var(--surface); border: 1px solid var(--border); cursor: pointer; transition: all 0.15s; }
        .asset-version-item:hover { background: rgba(255,255,255,0.05); }
        .asset-version-item.current { border-color: var(--accent); background: var(--accent-dim); }
        .asset-version-item img { width: 48px; height: 48px; object-fit: cover; border-radius: 8px; }
        .asset-version-item .ver-info { flex: 1; }
        .asset-version-item .ver-num { font-size: 0.85em; font-weight: 700; }
        .asset-version-item .ver-date { font-size: 0.7em; color: var(--muted); }
        .asset-version-item .ver-actions { display: flex; gap: 4px; }
        .asset-version-item .ver-actions button { padding: 4px 10px; border-radius: 6px; font-size: 0.7em; border: 1px solid var(--border); background: var(--surface2); color: var(--text); cursor: pointer; }
        .asset-empty { text-align: center; padding: 60px 20px; color: var(--muted); }
        .asset-empty h3 { font-size: 1.1em; margin-bottom: 8px; }
        .asset-empty p { font-size: 0.85em; }
        .script-drop { border: 2px dashed var(--border); border-radius: 16px; padding: 40px 20px; text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 16px; }
        .script-drop:hover { border-color: var(--accent); background: var(--accent-dim); }
        .script-drop.dragover { border-color: var(--accent); background: var(--accent-dim); }
        .script-drop h3 { font-size: 1em; margin-bottom: 6px; }
        .script-drop p { font-size: 0.8em; color: var(--muted); }
        .script-results { display: flex; flex-direction: column; gap: 12px; }
        .script-entity { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 12px; background: var(--surface); border: 1px solid var(--border); }
        .script-entity .entity-icon { font-size: 1.5em; }
        .script-entity .entity-info { flex: 1; }
        .script-entity .entity-name { font-size: 0.9em; font-weight: 700; }
        .script-entity .entity-prompt { font-size: 0.75em; color: var(--muted); margin-top: 2px; }
        .script-entity .entity-actions { display: flex; gap: 6px; }
        .script-stats { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
        .script-stat { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 16px; text-align: center; }
        .script-stat .stat-num { font-size: 1.5em; font-weight: 800; color: var(--accent); }
        .script-stat .stat-label { font-size: 0.7em; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
        .bitrate-control { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .bitrate-control select { background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 8px; padding: 6px 12px; color: var(--text); font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="bg-glow"></div>
    
    <div class="container">
        <!-- Header -->
        <header>
            <div class="logo">
                <div class="logo-icon">S</div>
                <div class="logo-text">
                    <h1>SoulIllusions</h1>
                    <p>AI Video Maker &mdash; 100% Free</p>
                </div>
            </div>
            <div class="gpu-badge" id="gpuBadge">
                <div class="dot"></div>
                <span id="gpuStatus">Not connected</span>
            </div>
        </header>
        
        <!-- Tabs -->
        <div class="tabs">
            <button class="tab active" onclick="switchTab('maker')">Video Maker</button>
            <button class="tab" onclick="switchTab('image')">Image Studio</button>
            <button class="tab" onclick="switchTab('assets')">Asset Library</button>
            <button class="tab" onclick="switchTab('production')">Production Suite</button>
        </div>
        
        <!-- Tab: Video Maker -->
        <div class="tab-content active" id="tab-maker">
        
        <!-- Backend Setup -->
        <div class="setup-card" id="setupCard">
            <h2>Connect GPU Backend</h2>
            <p>This app uses a free Google Colab GPU (T4) to generate real motion video from text. Follow these steps:</p>
            
            <div class="setup-steps">
                <div class="step">
                    <div class="step-num">1</div>
                    <h3>Open Colab Notebook</h3>
                    <p>Upload SoulIllusions_GPU_Backend.ipynb to Google Colab</p>
                </div>
                <div class="step">
                    <div class="step-num">2</div>
                    <h3>Enable GPU & Run</h3>
                    <p>Runtime &rarr; T4 GPU &rarr; Run all cells</p>
                </div>
                <div class="step">
                    <div class="step-num">3</div>
                    <h3>Copy the URL</h3>
                    <p>Copy the ngrok URL shown at the bottom of the notebook</p>
                </div>
                <div class="step">
                    <div class="step-num">4</div>
                    <h3>Paste it below</h3>
                    <p>Connect and start generating videos!</p>
                </div>
            </div>
            
            <div class="input-group">
                <input type="text" id="backendUrl" placeholder="https://xxxx.ngrok-free.app" />
                <button class="btn btn-primary" onclick="connectBackend()">Connect</button>
            </div>
        </div>
        
        <!-- Generate Panel -->
        <div class="generate-panel disabled" id="generatePanel">
            <h2>Create Video</h2>
            <textarea id="prompt" placeholder="Describe the video you want to create...&#10;Example: A cat walking on a beach at sunset, waves crashing, golden hour lighting"></textarea>
            
            <!-- Preset Bar -->
            <div class="preset-bar" id="presetBar">
                <span style="font-size:12px;color:var(--muted);line-height:28px;">Presets:</span>
                <button class="preset-btn" onclick="applyPreset('cinematic_short')">Cinematic Short</button>
                <button class="preset-btn" onclick="applyPreset('social_media_vertical')">Social Media</button>
                <button class="preset-btn" onclick="applyPreset('anime_sequence')">Anime</button>
                <button class="preset-btn" onclick="applyPreset('documentary_clip')">Documentary</button>
                <button class="preset-btn" onclick="applyPreset('fast_preview')">Fast Preview</button>
                <button class="preset-btn" onclick="applyPreset('music_video')">Music Video</button>
                <button class="preset-btn" onclick="applyPreset('horror_atmosphere')">Horror</button>
            </div>
            
            <!-- Settings Tabs -->
            <div class="settings-tabs">
                <button class="settings-tab active" onclick="switchSettingsTab('basic')">Basic</button>
                <button class="settings-tab" onclick="switchSettingsTab('advanced')">Advanced</button>
                <button class="settings-tab" onclick="switchSettingsTab('camera')">Camera</button>
                <button class="settings-tab" onclick="switchSettingsTab('postprocess')">Post-Process</button>
                <button class="settings-tab" onclick="switchSettingsTab('output')">Output</button>
                <button class="settings-tab" onclick="switchSettingsTab('audio')">Audio</button>
            </div>
            
            <!-- Tab: Basic -->
            <div class="settings-panel active" id="settings-basic">
                <div class="settings-section">
                    <h4>Generation</h4>
                    <div class="settings-row">
                        <div class="control">
                            <label>Model</label>
                            <select id="model">
                                <option value="auto">Auto (LTX-Video - Fastest)</option>
                                <option value="ltx">LTX-Video (768x512, 24fps, ~30-60s)</option>
                                <option value="wan22">Wan 2.2 TI2V-5B (720P, Best Quality)</option>
                                <option value="motif">Motif-Video 2B (720P, GGUF, Balanced)</option>
                                <option value="helios">Helios-Distilled (Real-time, Minute-scale)</option>
                                <option value="holocine">HoloCine (Multi-shot Narrative)</option>
                            </select>
                        </div>
                        <div class="control">
                            <label>Style</label>
                            <select id="style">
                                <option value="cinematic">Cinematic</option>
                                <option value="realistic">Realistic</option>
                                <option value="anime">Anime</option>
                                <option value="documentary">Documentary</option>
                                <option value="music video">Music Video</option>
                                <option value="social media">Social Media</option>
                                <option value="noir">Film Noir</option>
                                <option value="vintage">Vintage</option>
                                <option value="cyberpunk">Cyberpunk</option>
                                <option value="fantasy">Fantasy</option>
                                <option value="horror">Horror</option>
                                <option value="romance">Romance</option>
                                <option value="action">Action</option>
                                <option value="dreamy">Dreamy</option>
                                <option value="3d_render">3D Render</option>
                                <option value="watercolor">Watercolor</option>
                                <option value="comic_book">Comic Book</option>
                                <option value="claymation">Claymation</option>
                            </select>
                        </div>
                    </div>
                    <div class="settings-row">
                        <div class="control">
                            <label>Quality Mode</label>
                            <select id="qualityMode" onchange="applyQualityMode()">
                                <option value="draft">Draft (Fast, ~10 steps)</option>
                                <option value="standard" selected>Standard (Balanced, ~30 steps)</option>
                                <option value="pro">Pro (High quality, ~50 steps)</option>
                                <option value="turbo">Turbo (Distilled, ~5 steps)</option>
                                <option value="ultra">Ultra (Maximum, ~80 steps)</option>
                            </select>
                        </div>
                        <div class="control">
                            <label>Aspect Ratio</label>
                            <select id="aspectRatio" onchange="applyAspectRatio()">
                                <option value="16:9">Widescreen (16:9)</option>
                                <option value="9:16">Vertical (9:16)</option>
                                <option value="1:1">Square (1:1)</option>
                                <option value="4:3">Classic (4:3)</option>
                                <option value="21:9">Cinematic (21:9)</option>
                                <option value="2.39:1">Anamorphic (2.39:1)</option>
                                <option value="4:5">Portrait (4:5)</option>
                            </select>
                        </div>
                    </div>
                    <div class="settings-row">
                        <div class="control">
                            <label>Seed (optional)</label>
                            <input type="text" id="seed" placeholder="Random" style="padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;outline:none;" />
                        </div>
                    </div>
                    <label class="checkbox-row">
                        <input type="checkbox" id="enhancePrompt" checked />
                        Prompt Enhancement (6-Dimension Framework)
                    </label>
                </div>
                <div class="settings-section">
                    <h4>Resolution & Frames</h4>
                    <div class="slider-row">
                        <label>Frames</label>
                        <input type="range" id="frames" min="25" max="201" value="97" step="8" oninput="updateRange('frames', 'framesValue')" />
                        <span class="val" id="framesValue">97</span>
                    </div>
                    <div class="slider-row">
                        <label>FPS</label>
                        <input type="range" id="fps" min="8" max="60" value="24" step="1" oninput="updateRange('fps', 'fpsValue')" />
                        <span class="val" id="fpsValue">24</span>
                    </div>
                    <div class="slider-row">
                        <label>Width</label>
                        <input type="range" id="resWidth" min="256" max="1920" value="1280" step="16" oninput="updateRange('resWidth', 'resWidthValue')" />
                        <span class="val" id="resWidthValue">1280</span>
                    </div>
                    <div class="slider-row">
                        <label>Height</label>
                        <input type="range" id="resHeight" min="256" max="1920" value="720" step="16" oninput="updateRange('resHeight', 'resHeightValue')" />
                        <span class="val" id="resHeightValue">720</span>
                    </div>
                </div>
            </div>
            
            <!-- Tab: Advanced -->
            <div class="settings-panel" id="settings-advanced">
                <div class="settings-section">
                    <h4>Quality & Fidelity</h4>
                    <div class="slider-row">
                        <label>Inference Steps</label>
                        <input type="range" id="steps" min="1" max="100" value="30" step="1" oninput="updateRange('steps', 'stepsValue')" />
                        <span class="val" id="stepsValue">30</span>
                    </div>
                    <div class="slider-row">
                        <label>Guidance Scale</label>
                        <input type="range" id="guidanceScale" min="1" max="15" value="5" step="0.5" oninput="updateRange('guidanceScale', 'guidanceScaleValue')" />
                        <span class="val" id="guidanceScaleValue">5.0</span>
                    </div>
                    <div class="slider-row">
                        <label>Guidance Rescale</label>
                        <input type="range" id="guidanceRescale" min="0" max="1" value="0" step="0.1" oninput="updateRange('guidanceRescale', 'guidanceRescaleValue')" />
                        <span class="val" id="guidanceRescaleValue">0.0</span>
                    </div>
                    <div class="slider-row">
                        <label>Creativity Scale</label>
                        <input type="range" id="creativityScale" min="0" max="1" value="0.5" step="0.1" oninput="updateRange('creativityScale', 'creativityScaleValue')" />
                        <span class="val" id="creativityScaleValue">0.5</span>
                    </div>
                </div>
                <div class="settings-section">
                    <h4>Negative Prompt</h4>
                    <textarea id="negativePrompt" placeholder="What you don't want in the video..." style="width:100%;min-height:60px;padding:10px 14px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;resize:vertical;">blurry, distorted, low quality, deformed, ugly, watermark, text, logo, jpeg artifacts, extra limbs, poorly drawn hands, poorly drawn face, disfigured, mutated, bad anatomy</textarea>
                </div>
                <div class="settings-section">
                    <h4>Scheduler</h4>
                    <div class="settings-row">
                        <div class="control">
                            <label>Solver</label>
                            <select id="solver">
                                <option value="unipc">UniPC (Default, balanced)</option>
                                <option value="euler">Euler (Fast, anime style)</option>
                                <option value="euler_ancestral">Euler Ancestral (Creative)</option>
                                <option value="ddim">DDIM (Classic, deterministic)</option>
                                <option value="dpm_plus_plus">DPM++ 2M Karras (High quality)</option>
                                <option value="flow_match_euler">FlowMatch Euler (SD3/Flow)</option>
                                <option value="flow_match_heun">FlowMatch Heun (Higher quality)</option>
                                <option value="tcd">TCD (Distilled models)</option>
                            </select>
                        </div>
                    </div>
                    <div class="slider-row">
                        <label>Flow Shift</label>
                        <input type="range" id="flowShift" min="1" max="12" value="5" step="0.5" oninput="updateRange('flowShift', 'flowShiftValue')" />
                        <span class="val" id="flowShiftValue">5.0</span>
                    </div>
                    <label class="checkbox-row">
                        <input type="checkbox" id="useKarras" />
                        Use Karras Sigmas
                    </label>
                    <label class="checkbox-row">
                        <input type="checkbox" id="useDynamicShifting" />
                        Dynamic Shifting
                    </label>
                </div>
                <div class="settings-section">
                    <h4>LTX-Video Decode Parameters</h4>
                    <div class="slider-row">
                        <label>Decode Timestep</label>
                        <input type="range" id="decodeTimestep" min="0.01" max="0.1" value="0.05" step="0.005" oninput="updateRange('decodeTimestep', 'decodeTimestepValue')" />
                        <span class="val" id="decodeTimestepValue">0.05</span>
                    </div>
                    <div class="slider-row">
                        <label>Decode Noise Scale</label>
                        <input type="range" id="decodeNoiseScale" min="0" max="0.1" value="0.025" step="0.005" oninput="updateRange('decodeNoiseScale', 'decodeNoiseScaleValue')" />
                        <span class="val" id="decodeNoiseScaleValue">0.025</span>
                    </div>
                </div>
            </div>
            
            <!-- Tab: Camera -->
            <div class="settings-panel" id="settings-camera">
                <div class="settings-section">
                    <h4>Camera Control</h4>
                    <label class="checkbox-row">
                        <input type="checkbox" id="cameraEnabled" />
                        Enable Camera Motion
                    </label>
                    <div class="settings-row">
                        <div class="control">
                            <label>Camera Preset</label>
                            <select id="cameraPreset" onchange="applyCameraPreset()">
                                <option value="static">Static (No movement)</option>
                                <option value="pan_left">Pan Left</option>
                                <option value="pan_right">Pan Right</option>
                                <option value="tilt_up">Tilt Up</option>
                                <option value="tilt_down">Tilt Down</option>
                                <option value="zoom_in">Zoom In</option>
                                <option value="zoom_out">Zoom Out</option>
                                <option value="dolly_in">Dolly In</option>
                                <option value="dolly_out">Dolly Out</option>
                                <option value="dolly_zoom">Dolly Zoom (Vertigo)</option>
                                <option value="orbit_left">Orbit Left</option>
                                <option value="orbit_right">Orbit Right</option>
                                <option value="crane_up">Crane Up</option>
                                <option value="crane_down">Crane Down</option>
                                <option value="tracking">Tracking Shot</option>
                                <option value="handheld">Handheld (Shaky cam)</option>
                                <option value="aerial">Aerial Drone</option>
                            </select>
                        </div>
                    </div>
                    <div class="slider-row">
                        <label>Camera Speed</label>
                        <input type="range" id="cameraSpeed" min="0.1" max="1" value="0.5" step="0.1" oninput="updateRange('cameraSpeed', 'cameraSpeedValue')" />
                        <span class="val" id="cameraSpeedValue">0.5</span>
                    </div>
                    <div class="slider-row">
                        <label>Camera Intensity</label>
                        <input type="range" id="cameraIntensity" min="0" max="1" value="0.5" step="0.1" oninput="updateRange('cameraIntensity', 'cameraIntensityValue')" />
                        <span class="val" id="cameraIntensityValue">0.5</span>
                    </div>
                    <div class="slider-row">
                        <label>Field of View</label>
                        <input type="range" id="cameraFov" min="20" max="120" value="60" step="5" oninput="updateRange('cameraFov', 'cameraFovValue')" />
                        <span class="val" id="cameraFovValue">60</span>
                    </div>
                </div>
                <div class="settings-section">
                    <h4>Motion Control</h4>
                    <div class="slider-row">
                        <label>Motion Intensity</label>
                        <input type="range" id="motionIntensity" min="0" max="1" value="0.5" step="0.1" oninput="updateRange('motionIntensity', 'motionIntensityValue')" />
                        <span class="val" id="motionIntensityValue">0.5</span>
                    </div>
                    <label class="checkbox-row">
                        <input type="checkbox" id="temporalSmoothing" checked />
                        Temporal Smoothing
                    </label>
                    <label class="checkbox-row">
                        <input type="checkbox" id="flickerElimination" checked />
                        Flicker Elimination
                    </label>
                </div>
            </div>
            
            <!-- Tab: Post-Process -->
            <div class="settings-panel" id="settings-postprocess">
                <div class="settings-section">
                    <h4>Super-Resolution</h4>
                    <label class="checkbox-row">
                        <input type="checkbox" id="upscaleEnabled" />
                        Enable Upscaling
                    </label>
                    <div class="settings-row">
                        <div class="control">
                            <label>Upscale Model</label>
                            <select id="upscaleModel">
                                <option value="realesrgan_x2">Real-ESRGAN 2x</option>
                                <option value="realesrgan_x4">Real-ESRGAN 4x</option>
                                <option value="realesrgan_anime">Real-ESRGAN Anime</option>
                                <option value="lanczos_x2">Lanczos 2x (Fast)</option>
                                <option value="lanczos_x4">Lanczos 4x (Fast)</option>
                            </select>
                        </div>
                        <div class="control">
                            <label>Scale Factor</label>
                            <select id="upscaleScale">
                                <option value="2">2x</option>
                                <option value="4">4x</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="settings-section">
                    <h4>Frame Interpolation</h4>
                    <label class="checkbox-row">
                        <input type="checkbox" id="interpolateEnabled" />
                        Enable Frame Interpolation
                    </label>
                    <div class="settings-row">
                        <div class="control">
                            <label>Target FPS</label>
                            <select id="interpolateFps">
                                <option value="30">30 FPS</option>
                                <option value="60">60 FPS</option>
                                <option value="120">120 FPS</option>
                            </select>
                        </div>
                    </div>
                    <label class="checkbox-row">
                        <input type="checkbox" id="interpolateMotionBlur" />
                        Motion Blur on Interpolated Frames
                    </label>
                </div>
                <div class="settings-section">
                    <h4>Color Grading</h4>
                    <label class="checkbox-row">
                        <input type="checkbox" id="colorGradingEnabled" />
                        Enable Color Grading
                    </label>
                    <div class="slider-row">
                        <label>Contrast</label>
                        <input type="range" id="cgContrast" min="-1" max="1" value="0" step="0.05" oninput="updateRange('cgContrast', 'cgContrastValue')" />
                        <span class="val" id="cgContrastValue">0.00</span>
                    </div>
                    <div class="slider-row">
                        <label>Saturation</label>
                        <input type="range" id="cgSaturation" min="-1" max="1" value="0" step="0.05" oninput="updateRange('cgSaturation', 'cgSaturationValue')" />
                        <span class="val" id="cgSaturationValue">0.00</span>
                    </div>
                    <div class="slider-row">
                        <label>Temperature</label>
                        <input type="range" id="cgTemperature" min="-1" max="1" value="0" step="0.05" oninput="updateRange('cgTemperature', 'cgTemperatureValue')" />
                        <span class="val" id="cgTemperatureValue">0.00</span>
                    </div>
                    <div class="slider-row">
                        <label>Brightness</label>
                        <input type="range" id="cgBrightness" min="-1" max="1" value="0" step="0.05" oninput="updateRange('cgBrightness', 'cgBrightnessValue')" />
                        <span class="val" id="cgBrightnessValue">0.00</span>
                    </div>
                    <div class="slider-row">
                        <label>Hue Shift</label>
                        <input type="range" id="cgHue" min="-1" max="1" value="0" step="0.05" oninput="updateRange('cgHue', 'cgHueValue')" />
                        <span class="val" id="cgHueValue">0.00</span>
                    </div>
                    <div class="slider-row">
                        <label>Gamma</label>
                        <input type="range" id="cgGamma" min="-1" max="1" value="0" step="0.05" oninput="updateRange('cgGamma', 'cgGammaValue')" />
                        <span class="val" id="cgGammaValue">0.00</span>
                    </div>
                </div>
                <div class="settings-section">
                    <h4>Effects</h4>
                    <label class="checkbox-row"><input type="checkbox" id="fxVignette" /> Vignette</label>
                    <div class="slider-row">
                        <label>Vignette Intensity</label>
                        <input type="range" id="fxVignetteIntensity" min="0" max="1" value="0.3" step="0.05" oninput="updateRange('fxVignetteIntensity', 'fxVignetteIntensityValue')" />
                        <span class="val" id="fxVignetteIntensityValue">0.30</span>
                    </div>
                    <label class="checkbox-row"><input type="checkbox" id="fxFilmGrain" /> Film Grain</label>
                    <div class="slider-row">
                        <label>Grain Amount</label>
                        <input type="range" id="fxFilmGrainAmount" min="0" max="0.5" value="0.15" step="0.05" oninput="updateRange('fxFilmGrainAmount', 'fxFilmGrainAmountValue')" />
                        <span class="val" id="fxFilmGrainAmountValue">0.15</span>
                    </div>
                    <label class="checkbox-row"><input type="checkbox" id="fxSharpen" /> Sharpen</label>
                    <div class="slider-row">
                        <label>Sharpen Amount</label>
                        <input type="range" id="fxSharpenAmount" min="0" max="2" value="0.5" step="0.1" oninput="updateRange('fxSharpenAmount', 'fxSharpenAmountValue')" />
                        <span class="val" id="fxSharpenAmountValue">0.50</span>
                    </div>
                    <label class="checkbox-row"><input type="checkbox" id="fxGlow" /> Glow</label>
                    <label class="checkbox-row"><input type="checkbox" id="fxBloom" /> Bloom</label>
                </div>
            </div>
            
            <!-- Tab: Output -->
            <div class="settings-panel" id="settings-output">
                <div class="settings-section">
                    <h4>Encoding</h4>
                    <div class="settings-row">
                        <div class="control">
                            <label>Codec</label>
                            <select id="codec">
                                <option value="h264">H.264 (Best compatibility)</option>
                                <option value="h265">H.265/HEVC (Better compression)</option>
                                <option value="vp9">VP9 (Web-optimized)</option>
                                <option value="av1">AV1 (Best compression, slow)</option>
                            </select>
                        </div>
                        <div class="control">
                            <label>Encoding Preset</label>
                            <select id="encPreset">
                                <option value="ultrafast">Ultrafast</option>
                                <option value="superfast">Superfast</option>
                                <option value="veryfast">Very Fast</option>
                                <option value="faster">Faster</option>
                                <option value="fast">Fast</option>
                                <option value="medium" selected>Medium</option>
                                <option value="slow">Slow</option>
                                <option value="slower">Slower</option>
                                <option value="veryslow">Very Slow</option>
                            </select>
                        </div>
                    </div>
                    <div class="settings-row">
                        <div class="control">
                            <label>Bitrate Preset</label>
                            <select id="bitratePreset" onchange="applyBitratePreset()">
                                <option value="auto">Auto (CRF-based)</option>
                                <option value="low_720">Low (720p ~2 Mbps)</option>
                                <option value="medium_1080">Medium (1080p ~5 Mbps)</option>
                                <option value="high_1080">High (1080p ~8 Mbps)</option>
                                <option value="ultra_4k">Ultra (4K ~25 Mbps)</option>
                                <option value="streaming">Streaming (1080p ~4 Mbps)</option>
                                <option value="cinema">Cinema Quality (~15 Mbps)</option>
                                <option value="archive">Archive Master (~50 Mbps)</option>
                            </select>
                        </div>
                        <div class="control">
                            <label>Tune</label>
                            <select id="encTune">
                                <option value="none">None</option>
                                <option value="film">Film (Live-action)</option>
                                <option value="animation">Animation</option>
                                <option value="stillimage">Still Image</option>
                                <option value="fastdecode">Fast Decode</option>
                                <option value="zerolatency">Zero Latency</option>
                            </select>
                        </div>
                        <div class="control">
                            <label>CRF Quality</label>
                            <select id="crf">
                                <option value="18">18 (Near-lossless)</option>
                                <option value="20">20 (High quality)</option>
                                <option value="23" selected>23 (Default)</option>
                                <option value="26">26 (Smaller file)</option>
                                <option value="30">30 (Small file)</option>
                            </select>
                        </div>
                    </div>
                    <div class="settings-row">
                        <div class="control">
                            <label>Profile</label>
                            <select id="encProfile">
                                <option value="baseline">Baseline</option>
                                <option value="main">Main</option>
                                <option value="high" selected>High</option>
                            </select>
                        </div>
                        <div class="control">
                            <label>Pixel Format</label>
                            <select id="pixelFormat">
                                <option value="yuv420p" selected>yuv420p (8-bit)</option>
                                <option value="yuv420p10le">yuv420p10le (10-bit HDR)</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Tab: Audio -->
            <div class="settings-panel" id="settings-audio">
                <div class="settings-section">
                    <h4>Audio Generation</h4>
                    <label class="checkbox-row"><input type="checkbox" id="audioEnabled" /> Enable Audio</label>
                    <label class="checkbox-row"><input type="checkbox" id="nativeAudio" /> Native Audio (Model-generated)</label>
                </div>
                <div class="settings-section">
                    <h4>Text-to-Speech</h4>
                    <label class="checkbox-row"><input type="checkbox" id="ttsEnabled" /> Enable TTS</label>
                    <div class="settings-row">
                        <div class="control">
                            <label>Voice</label>
                            <select id="ttsVoice">
                                <option value="narrator_male">Narrator (Male, deep)</option>
                                <option value="narrator_female">Narrator (Female, warm)</option>
                                <option value="character_male">Character (Male)</option>
                                <option value="character_female">Character (Female)</option>
                                <option value="news_anchor">News Anchor</option>
                                <option value="child">Child</option>
                                <option value="elderly">Elderly</option>
                                <option value="robot">Robot/AI</option>
                            </select>
                        </div>
                    </div>
                    <textarea id="ttsText" placeholder="Dialogue text for TTS..." style="width:100%;min-height:60px;padding:10px 14px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;resize:vertical;margin-top:8px;"></textarea>
                </div>
                <div class="settings-section">
                    <h4>Ambient & Music</h4>
                    <label class="checkbox-row"><input type="checkbox" id="ambientEnabled" /> Ambient Sound</label>
                    <input type="text" id="ambientPrompt" placeholder="e.g. forest birds, city traffic, ocean waves..." style="width:100%;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;margin-bottom:8px;" />
                    <label class="checkbox-row"><input type="checkbox" id="musicEnabled" /> Background Music</label>
                    <input type="text" id="musicPrompt" placeholder="e.g. orchestral, ambient piano, electronic beat..." style="width:100%;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;margin-top:4px;" />
                </div>
            </div>
            
            <div class="generate-btn-row">
                <button class="btn btn-primary" id="generateBtn" onclick="generateVideo()">
                    Generate Video
                </button>
                <div class="progress-bar" id="progressBar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-text" id="progressText"></div>
            </div>
        </div>
        
        <!-- Results -->
        <div class="results-section">
            <h2>Your Videos</h2>
            <div id="videoGrid" class="video-grid">
                <div class="empty-state">
                    <div class="icon">&#127916;</div>
                    <p>No videos yet. Create your first one above!</p>
                </div>
            </div>
        </div>
        </div><!-- /tab-maker -->
        
        <!-- Tab: Image Studio -->
        <div class="tab-content" id="tab-image">
            <div class="img-studio" id="imgStudio">
                <!-- Hero -->
                <div class="img-hero" id="imgHero">
                    <h2>Image Studio</h2>
                    <p>Generate stunning AI images &mdash; then animate them into video</p>
                </div>
                
                <!-- Prompt Bar -->
                <div class="img-prompt-bar">
                    <div class="img-prompt-row">
                        <div class="img-upload-btn" id="imgUploadBtn" onclick="imgUploadClick()" title="Upload reference image (switches to I2I mode)">&#128206;</div>
                        <textarea id="imgPrompt" placeholder="Describe the image you want to create..." rows="1"></textarea>
                    </div>
                    <div class="img-ref-preview" id="imgRefPreview" style="display:none;"></div>
                    <div class="img-controls">
                        <span class="img-mode-badge t2i" id="imgModeBadge">T2I</span>
                        <button class="img-ctrl-btn" id="imgModelBtn" onclick="imgToggleDropdown('model')">
                            <span style="font-size:14px;">&#9881;</span>
                            <span id="imgModelLabel">FLUX.1</span>
                            <span style="font-size:8px;opacity:0.4;">&#9660;</span>
                        </button>
                        <button class="img-ctrl-btn" id="imgArBtn" onclick="imgToggleDropdown('ar')">
                            <span style="font-size:14px;">&#9633;</span>
                            <span id="imgArLabel">1:1</span>
                            <span style="font-size:8px;opacity:0.4;">&#9660;</span>
                        </button>
                        <button class="img-ctrl-btn" id="imgQualityBtn" onclick="imgToggleDropdown('quality')">
                            <span style="font-size:14px;">&#9733;</span>
                            <span id="imgQualityLabel">Standard</span>
                            <span style="font-size:8px;opacity:0.4;">&#9660;</span>
                        </button>
                        <button class="img-ctrl-btn" id="imgAdvBtn" onclick="imgToggleAdvanced()">
                            <span style="font-size:14px;">&#9881;</span>
                            <span id="imgAdvLabel">Advanced</span>
                        </button>
                        <button class="img-ctrl-btn" id="imgToolsBtn" onclick="imgToggleTools()">
                            <span style="font-size:14px;">&#128295;</span>
                            <span>Tools</span>
                        </button>
                        <button class="img-gen-btn" id="imgGenBtn" onclick="generateImage()">Generate</button>
                    </div>
                </div>
                
                <!-- Image Progress -->
                <div class="img-progress" id="imgProgress" style="display:none;">
                    <div class="img-progress-bar"><div class="img-progress-fill" id="imgProgressFill"></div></div>
                    <div class="img-progress-text" id="imgProgressText">Generating...</div>
                </div>
                
                <!-- Advanced Panel -->
                <div class="img-adv-panel" id="imgAdvPanel" style="display:none;">
                    <h3>Advanced Options <span class="close-adv" onclick="imgToggleAdvanced()">&times;</span></h3>
                    <div class="img-adv-row">
                        <div class="img-adv-field">
                            <label>Style Preset</label>
                            <div class="img-style-presets" id="imgStylePresets"></div>
                        </div>
                    </div>
                    <div class="img-adv-row">
                        <div class="img-adv-field">
                            <label>Negative Prompt</label>
                            <input type="text" id="imgNegPrompt" placeholder="What to avoid in the image..." />
                        </div>
                    </div>
                    <div class="img-adv-row">
                        <div class="img-adv-field">
                            <label>Guidance Scale <span class="range-val" id="imgGuidanceVal">7.5</span></label>
                            <input type="range" id="imgGuidanceSlider" min="1" max="20" step="0.5" value="7.5" />
                        </div>
                        <div class="img-adv-field">
                            <label>Steps <span class="range-val" id="imgStepsVal">25</span></label>
                            <input type="range" id="imgStepsSlider" min="1" max="50" step="1" value="25" />
                        </div>
                    </div>
                    <div class="img-adv-row">
                        <div class="img-adv-field">
                            <label>Seed</label>
                            <input type="number" id="imgSeed" value="-1" placeholder="-1 for random" />
                        </div>
                        <div class="img-adv-field">
                            <label>Batch Count <span class="range-val" id="imgBatchVal">1</span></label>
                            <input type="range" id="imgBatchSlider" min="1" max="4" step="1" value="1" />
                        </div>
                    </div>
                    <div class="img-adv-row">
                        <div class="img-adv-field">
                            <label>Custom Width (optional)</label>
                            <input type="number" id="imgWidth" placeholder="Auto from aspect ratio" />
                        </div>
                        <div class="img-adv-field">
                            <label>Custom Height (optional)</label>
                            <input type="number" id="imgHeight" placeholder="Auto from aspect ratio" />
                        </div>
                    </div>
                    <div class="img-adv-row">
                        <div class="img-adv-field">
                            <label>Reference Strength <span class="range-val" id="imgRefStrengthVal">50%</span></label>
                            <input type="range" id="imgRefStrengthSlider" min="0" max="100" step="5" value="50" />
                        </div>
                        <div class="img-adv-field">
                            <label>LoRA Model (optional)</label>
                            <input type="text" id="imgLora" placeholder="Civitai LoRA model ID" />
                        </div>
                    </div>
                </div>
                
                <!-- Tools Panel -->
                <div class="img-tools-panel" id="imgToolsPanel" style="display:none;">
                    <h3>Quick Tools <span class="close-adv" onclick="imgToggleTools()">&times;</span></h3>
                    <label style="font-size:0.7em;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);display:block;margin-bottom:6px;">Quick Starters</label>
                    <div class="img-quick-prompts" id="imgQuickPrompts"></div>
                    <label style="font-size:0.7em;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);display:block;margin-bottom:6px;margin-top:12px;">Prompt Enhancer</label>
                    <input type="text" id="imgBasePrompt" placeholder="Enter your base prompt..." style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:8px;padding:8px 12px;color:var(--text);font-size:0.85em;outline:none;margin-bottom:8px;" />
                    <div class="img-enhance-tags" id="imgEnhanceTags"></div>
                    <div class="img-enhanced-display" id="imgEnhancedDisplay">Enhanced prompt will appear here...</div>
                    <div style="display:flex;gap:8px;">
                        <button class="img-ctrl-btn" onclick="imgCopyEnhanced()">Copy</button>
                        <button class="img-gen-btn" style="margin-left:0;padding:8px 16px;font-size:0.8em;" onclick="imgUseEnhanced()">Use in Prompt</button>
                    </div>
                </div>
                
                <!-- Image Result Canvas -->
                <div class="img-canvas" id="imgCanvas">
                    <img id="imgResult" src="" alt="Generated image" />
                    <div class="img-canvas-controls">
                        <button onclick="imgRegenerate()">Regenerate</button>
                        <button onclick="imgDownload()">Download</button>
                        <button class="btn-primary" onclick="imgSendToVideo()">Send to Video</button>
                        <button onclick="imgNewPrompt()">New</button>
                    </div>
                </div>
                
                <!-- History Sidebar -->
                <div class="img-history" id="imgHistory">
                    <div class="img-history-label">History</div>
                    <div id="imgHistoryList"></div>
                </div>
            </div>
        </div><!-- /tab-image -->
        
        <!-- Tab: Asset Library -->
        <div class="tab-content" id="tab-assets">
            <div class="asset-layout">
                <!-- Sidebar -->
                <div class="asset-sidebar">
                    <input class="asset-search" id="assetSearch" placeholder="Search assets..." oninput="assetSearchHandler()" />
                    <div class="asset-cat-list" id="assetCatList"></div>
                    <button class="asset-btn primary" style="width:100%;margin-bottom:8px;" onclick="assetShowCreate()">+ New Asset</button>
                    <button class="asset-btn" style="width:100%;margin-bottom:8px;" onclick="assetShowScriptDrop()">Drop Script</button>
                    <div id="assetStats" style="margin-top:12px;font-size:0.75em;color:var(--muted);"></div>
                </div>
                <!-- Main -->
                <div class="asset-main" id="assetMain">
                    <div class="asset-empty" id="assetEmpty">
                        <h3>Asset Library</h3>
                        <p>Drop in a movie script to auto-extract characters, locations, and props &mdash;<br>or create assets manually. Lock assets to enforce consistency across all video scenes.</p>
                    </div>
                    <div id="assetGridContainer" style="display:none;">
                        <div class="asset-grid" id="assetGrid"></div>
                    </div>
                    <div id="assetDetailContainer" style="display:none;"></div>
                    <div id="assetScriptContainer" style="display:none;">
                        <div class="script-drop" id="scriptDropZone" onclick="scriptBrowseClick()">
                            <h3>&#128221; Drop Movie Script Here</h3>
                            <p>Upload a .txt, .fountain, or .pdf screenplay &mdash; we'll extract characters, locations, vehicles, objects, and creatures</p>
                        </div>
                        <input type="file" id="scriptFileInput" accept=".txt,.fountain,.md,.pdf" style="display:none;" onchange="scriptFileSelected(event)" />
                        <div id="scriptResults" style="display:none;"></div>
                    </div>
                    <div id="assetCreateContainer" style="display:none;">
                        <h3 style="margin-bottom:16px;">Create New Asset</h3>
                        <div style="display:flex;flex-direction:column;gap:12px;max-width:500px;">
                            <input type="text" id="newAssetName" placeholder="Asset name (e.g. 'Detective Sarah Connor')" style="background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--text);font-size:0.9em;outline:none;" />
                            <select id="newAssetCategory" onchange="newAssetCatChanged()" style="background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--text);font-size:0.85em;">
                                <option value="">Select category...</option>
                            </select>
                            <select id="newAssetSubtype" style="display:none;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--text);font-size:0.85em;"></select>
                            <textarea id="newAssetDesc" placeholder="Description (e.g. 'Tall woman in her 30s, dark hair, leather jacket, determined eyes')" rows="3" style="background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--text);font-size:0.85em;outline:none;resize:vertical;"></textarea>
                            <input type="text" id="newAssetTags" placeholder="Tags (comma-separated, e.g. 'hero, lead, season1')" style="background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--text);font-size:0.85em;outline:none;" />
                            <div style="display:flex;gap:8px;">
                                <button class="asset-btn primary" onclick="assetCreateSubmit()">Create Asset</button>
                                <button class="asset-btn" onclick="assetShowGrid()">Cancel</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div><!-- /tab-assets -->
        
        <!-- Tab: Production Suite -->
        <div class="tab-content" id="tab-production">
            <div id="prodView">
                <!-- Production suite content gets dynamically loaded here -->
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        let pollInterval = null;
        let currentJobId = null;
        
        // === ACTION TELEMETRY ===
        // Captures every user interaction and sends to /api/log
        // Can be toggled off later for performance
        const TELEMETRY_ENABLED = true;
        let _telemetryBuffer = [];
        let _telemetryFlushTimer = null;
        
        function _getActiveTab() {
            const active = document.querySelector('.tab-content:not([style*="display: none"])');
            return active ? active.id : 'unknown';
        }
        
        function _getElementInfo(el) {
            const tag = el.tagName.toLowerCase();
            const type = el.getAttribute('type') || '';
            const id = el.id || el.getAttribute('data-id') || el.className || tag;
            let elType = 'other';
            if (tag === 'button' || tag === 'a') elType = 'button';
            else if (tag === 'select') elType = 'select';
            else if (tag === 'input') elType = type || 'input';
            else if (tag === 'textarea') elType = 'textarea';
            else if (el.classList.contains('tab-btn')) elType = 'tab';
            else if (tag === 'input' && type === 'range') elType = 'slider';
            else if (tag === 'input' && type === 'checkbox') elType = 'checkbox';
            return { id: id, type: elType, tag: tag };
        }
        
        function _sendTelemetry(eventType, elementId, elementType, value, extra) {
            if (!TELEMETRY_ENABLED) return;
            const payload = {
                event_type: eventType,
                element_id: elementId,
                element_type: elementType,
                value: value !== undefined ? String(value).substring(0, 200) : null,
                page: _getActiveTab(),
                extra: extra || {},
            };
            _telemetryBuffer.push(payload);
            
            // Batch send every 2 seconds or when buffer hits 10
            if (_telemetryFlushTimer) clearTimeout(_telemetryFlushTimer);
            if (_telemetryBuffer.length >= 10) {
                _flushTelemetry();
            } else {
                _telemetryFlushTimer = setTimeout(_flushTelemetry, 2000);
            }
        }
        
        async function _flushTelemetry() {
            if (_telemetryBuffer.length === 0) return;
            const batch = _telemetryBuffer.splice(0);
            for (const payload of batch) {
                try {
                    await fetch('/api/log', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload),
                    });
                } catch (e) { /* silent fail */ }
            }
        }
        
        // Global click listener — captures every button press
        document.addEventListener('click', function(e) {
            const el = e.target.closest('button, a, .tab-btn, [onclick]') || e.target;
            const info = _getElementInfo(el);
            _sendTelemetry('click', info.id, info.type, null, {
                text: (el.textContent || '').trim().substring(0, 50),
            });
        }, true);
        
        // Global change listener — captures select, checkbox, input changes
        document.addEventListener('change', function(e) {
            const el = e.target;
            const info = _getElementInfo(el);
            let value = el.value;
            if (el.type === 'checkbox') value = el.checked;
            _sendTelemetry('change', info.id, info.type, value);
        }, true);
        
        // Global input listener — captures text input (debounced via buffer)
        let _inputTimer = null;
        document.addEventListener('input', function(e) {
            const el = e.target;
            if (el.tagName === 'INPUT' && el.type === 'range') {
                // Slider — log on release (change event handles this)
                return;
            }
            const info = _getElementInfo(el);
            if (_inputTimer) clearTimeout(_inputTimer);
            _inputTimer = setTimeout(() => {
                _sendTelemetry('input', info.id, info.type, el.value);
            }, 1000);
        }, true);
        
        // Tab switch listener - disabled wrapper that was causing issues
        // (switchTab is logged via the global click listener above)
        
        // Page unload — flush remaining telemetry
        window.addEventListener('beforeunload', function() {
            if (_telemetryBuffer.length > 0) {
                for (const payload of _telemetryBuffer) {
                    navigator.sendBeacon('/api/log', JSON.stringify(payload));
                }
            }
        });
        
        // Check backend status on load
        async function init() {
            const cfg = await fetch('/api/config').then(r => r.json());
            if (cfg.gpu_backend_url) {
                document.getElementById('backendUrl').value = cfg.gpu_backend_url;
                checkBackend();
            }
            loadVideos();
            imgInit();
            assetInit();
            setInterval(checkBackend, 30000);
        }
        
        async function checkBackend() {
            const status = await fetch('/api/backend/status').then(r => r.json());
            const badge = document.getElementById('gpuBadge');
            const statusText = document.getElementById('gpuStatus');
            const panel = document.getElementById('generatePanel');
            
            if (status.status === 'online') {
                badge.classList.add('online');
                statusText.textContent = status.gpu || 'GPU Connected';
                panel.classList.remove('disabled');
            } else {
                badge.classList.remove('online');
                statusText.textContent = 'Not connected';
                panel.classList.add('disabled');
            }
        }
        
        async function connectBackend() {
            const url = document.getElementById('backendUrl').value.trim();
            if (!url) {
                showToast('Enter a URL first', 'error');
                return;
            }
            
            const resp = await fetch('/api/config/backend', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            }).then(r => r.json());
            
            if (resp.status === 'ok') {
                showToast('Backend connected!', 'success');
                checkBackend();
            } else {
                showToast('Failed to connect', 'error');
            }
        }
        
        function updateRange(id, valueId) {
            const el = document.getElementById(id);
            const valEl = document.getElementById(valueId);
            if (el && valEl) {
                const v = parseFloat(el.value);
                valEl.textContent = (id === 'guidanceScale' || id === 'flowShift' || id === 'cameraFov' || id === 'fxSharpenAmount') ? v.toFixed(1) : 
                    (id.startsWith('cg') || id === 'guidanceRescale' || id === 'creativityScale' || id === 'cameraSpeed' || id === 'cameraIntensity' || id === 'motionIntensity' || id === 'fxVignetteIntensity' || id === 'fxFilmGrainAmount') ? v.toFixed(2) : v;
            }
        }
        
        function switchSettingsTab(tabName) {
            document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
            const btn = document.querySelector('.settings-tab[onclick*="' + tabName + '"]');
            if (btn) btn.classList.add('active');
            const panel = document.getElementById('settings-' + tabName);
            if (panel) panel.classList.add('active');
        }
        
        function applyQualityMode() {
            const mode = document.getElementById('qualityMode').value;
            const modeMap = {
                draft: {steps: 10, guidance: 3.0, rescale: 0.0},
                standard: {steps: 30, guidance: 5.0, rescale: 0.0},
                pro: {steps: 50, guidance: 5.0, rescale: 0.7},
                turbo: {steps: 5, guidance: 1.0, rescale: 0.7},
                ultra: {steps: 80, guidance: 6.0, rescale: 0.7},
            };
            const m = modeMap[mode];
            if (m) {
                document.getElementById('steps').value = m.steps;
                document.getElementById('stepsValue').textContent = m.steps;
                document.getElementById('guidanceScale').value = m.guidance;
                document.getElementById('guidanceScaleValue').textContent = m.guidance.toFixed(1);
                document.getElementById('guidanceRescale').value = m.rescale;
                document.getElementById('guidanceRescaleValue').textContent = m.rescale.toFixed(1);
            }
        }
        
        function applyAspectRatio() {
            const ratio = document.getElementById('aspectRatio').value;
            const ratioMap = {
                '16:9': [1280, 720], '9:16': [720, 1280], '1:1': [1024, 1024],
                '4:3': [1024, 768], '21:9': [1280, 544], '2.39:1': [1280, 536], '4:5': [896, 1120],
            };
            const dims = ratioMap[ratio];
            if (dims) {
                document.getElementById('resWidth').value = dims[0];
                document.getElementById('resWidthValue').textContent = dims[0];
                document.getElementById('resHeight').value = dims[1];
                document.getElementById('resHeightValue').textContent = dims[1];
            }
        }
        
        function applyCameraPreset() {
            const preset = document.getElementById('cameraPreset').value;
            document.getElementById('cameraEnabled').checked = preset !== 'static';
        }
        
        function applyPreset(presetName) {
            const presets = {
                cinematic_short: {style:'cinematic',qualityMode:'pro',aspectRatio:'21:9',frames:121,fps:24,cameraEnabled:true,cameraPreset:'dolly_in',cameraSpeed:0.3,colorGradingEnabled:true,cgContrast:0.15,cgSaturation:-0.05,cgTemperature:-0.1,fxVignette:true,fxFilmGrain:true,codec:'h264',crf:'20',encPreset:'slow',encTune:'film'},
                social_media_vertical: {style:'social_media',qualityMode:'standard',aspectRatio:'9:16',frames:49,fps:30,colorGradingEnabled:true,cgSaturation:0.2,fxSharpen:true,codec:'h264',crf:'21',encPreset:'fast'},
                anime_sequence: {style:'anime',qualityMode:'pro',aspectRatio:'16:9',frames:97,fps:24,guidanceScale:7,solver:'euler',upscaleEnabled:true,upscaleModel:'realesrgan_anime',upscaleScale:'2',colorGradingEnabled:true,cgSaturation:0.15,cgContrast:0.1,codec:'h264',crf:'20',encTune:'animation'},
                documentary_clip: {style:'documentary',qualityMode:'pro',aspectRatio:'16:9',frames:121,fps:24,cameraEnabled:true,cameraPreset:'handheld',cameraSpeed:0.2,colorGradingEnabled:true,cgTemperature:0.05,cgSaturation:-0.1,codec:'h264',crf:'19',encPreset:'slow',encTune:'film'},
                fast_preview: {qualityMode:'draft',aspectRatio:'16:9',frames:33,fps:12,upscaleEnabled:false,interpolateEnabled:false,colorGradingEnabled:false,codec:'h264',crf:'28',encPreset:'ultrafast'},
                music_video: {style:'music_video',qualityMode:'pro',aspectRatio:'16:9',frames:121,fps:30,cameraEnabled:true,cameraPreset:'tracking',cameraSpeed:0.7,colorGradingEnabled:true,cgSaturation:0.3,cgContrast:0.2,fxGlow:true,fxBloom:true,codec:'h264',crf:'20'},
                horror_atmosphere: {style:'horror',qualityMode:'pro',aspectRatio:'21:9',frames:97,fps:24,guidanceScale:6,cameraEnabled:true,cameraPreset:'handheld',cameraSpeed:0.15,colorGradingEnabled:true,cgSaturation:-0.4,cgContrast:0.3,cgTemperature:-0.2,fxVignette:true,fxFilmGrain:true,codec:'h264',crf:'22',encPreset:'slow',encTune:'film'},
            };
            const p = presets[presetName];
            if (!p) return;
            for (const [key, val] of Object.entries(p)) {
                const el = document.getElementById(key);
                if (!el) continue;
                if (el.type === 'checkbox') el.checked = val;
                else el.value = val;
                if (el.type === 'range') {
                    const valEl = document.getElementById(key + 'Value');
                    if (valEl) valEl.textContent = val;
                }
            }
            if (p.aspectRatio) applyAspectRatio();
            if (p.qualityMode) applyQualityMode();
            if (p.cameraPreset) applyCameraPreset();
            showToast('Preset applied: ' + presetName.replace(/_/g, ' '), 'success');
        }
        
        function _getVal(id) {
            const el = document.getElementById(id);
            return el ? el.value : null;
        }
        function _getInt(id, def) {
            const el = document.getElementById(id);
            if (!el) return def;
            const v = parseInt(el.value);
            return isNaN(v) ? def : v;
        }
        function _getFloat(id, def) {
            const el = document.getElementById(id);
            if (!el) return def;
            const v = parseFloat(el.value);
            return isNaN(v) ? def : v;
        }
        function _getBool(id, def) {
            const el = document.getElementById(id);
            return el ? el.checked : def;
        }
        
        async function generateVideo() {
            const prompt = document.getElementById('prompt').value.trim();
            if (!prompt) {
                showToast('Enter a description first', 'error');
                return;
            }
            
            const btn = document.getElementById('generateBtn');
            btn.disabled = true;
            btn.textContent = 'Generating...';
            
            const seedVal = document.getElementById('seed').value.trim();
            
            // Build color grading object
            const colorGrading = _getBool('colorGradingEnabled', false) ? {
                contrast: _getFloat('cgContrast', 0),
                saturation: _getFloat('cgSaturation', 0),
                temperature: _getFloat('cgTemperature', 0),
                brightness: _getFloat('cgBrightness', 0),
                hue: _getFloat('cgHue', 0),
                gamma: _getFloat('cgGamma', 0),
            } : null;
            
            // Build effects object
            const effects = {
                vignette_enabled: _getBool('fxVignette', false),
                vignette_intensity: _getFloat('fxVignetteIntensity', 0.3),
                film_grain_enabled: _getBool('fxFilmGrain', false),
                film_grain_amount: _getFloat('fxFilmGrainAmount', 0.15),
                sharpen_enabled: _getBool('fxSharpen', false),
                sharpen_amount: _getFloat('fxSharpenAmount', 0.5),
                glow_enabled: _getBool('fxGlow', false),
                bloom_enabled: _getBool('fxBloom', false),
            };
            
            // Camera direction from preset
            const camPreset = _getVal('cameraPreset') || 'static';
            const camDirection = camPreset.includes('left') ? 'left' : camPreset.includes('right') ? 'right' :
                camPreset.includes('up') ? 'up' : camPreset.includes('down') ? 'down' :
                camPreset.includes('in') ? 'in' : camPreset.includes('out') ? 'out' : null;
            const camMotion = camPreset.replace(/_(left|right|up|down|in|out)$/, '');
            
            const payload = {
                prompt,
                model: _getVal('model') || 'auto',
                style: _getVal('style') || 'cinematic',
                num_frames: _getInt('frames', 97),
                fps: _getInt('fps', 24),
                steps: _getInt('steps', 30),
                seed: seedVal ? parseInt(seedVal) : null,
                enhance: _getBool('enhancePrompt', true),
                // Advanced
                negative_prompt: document.getElementById('negativePrompt')?.value || null,
                width: _getInt('resWidth', null),
                height: _getInt('resHeight', null),
                guidance_scale: _getFloat('guidanceScale', 5.0),
                guidance_rescale: _getFloat('guidanceRescale', 0.0),
                creativity_scale: _getFloat('creativityScale', 0.5),
                // Scheduler
                solver: _getVal('solver') || 'unipc',
                flow_shift: _getFloat('flowShift', 5.0),
                use_karras_sigmas: _getBool('useKarras', false),
                use_dynamic_shifting: _getBool('useDynamicShifting', false),
                decode_timestep: _getFloat('decodeTimestep', 0.05),
                decode_noise_scale: _getFloat('decodeNoiseScale', 0.025),
                // Camera
                camera_enabled: _getBool('cameraEnabled', false),
                camera_motion: camMotion,
                camera_direction: camDirection,
                camera_speed: _getFloat('cameraSpeed', 0.5),
                camera_intensity: _getFloat('cameraIntensity', 0.5),
                camera_fov: _getFloat('cameraFov', 60),
                // Motion
                motion_intensity: _getFloat('motionIntensity', 0.5),
                temporal_smoothing: _getBool('temporalSmoothing', true),
                flicker_elimination: _getBool('flickerElimination', true),
                // Post-processing
                upscale: _getBool('upscaleEnabled', false) ? _getInt('upscaleScale', 2) : 1,
                upscale_model: _getVal('upscaleModel') || 'realesrgan_x2',
                interpolate_fps: _getBool('interpolateEnabled', false) ? _getInt('interpolateFps', 0) : 0,
                interpolate_motion_blur: _getBool('interpolateMotionBlur', false),
                color_grading: colorGrading,
                effects: effects,
                // Output
                codec: _getVal('codec') || 'h264',
                crf: _getInt('crf', 23),
                preset: _getVal('encPreset') || 'medium',
                tune: _getVal('encTune') || 'none',
                bitrate_preset: _getVal('bitratePreset') || 'auto',
                profile: _getVal('encProfile') || 'high',
                pixel_format: _getVal('pixelFormat') || 'yuv420p',
                // Audio
                audio: _getBool('audioEnabled', false),
                native_audio: _getBool('nativeAudio', false),
                tts_text: _getBool('ttsEnabled', false) ? (document.getElementById('ttsText')?.value || null) : null,
                tts_voice: _getVal('ttsVoice') || 'narrator_male',
                ambient_prompt: _getBool('ambientEnabled', false) ? (document.getElementById('ambientPrompt')?.value || null) : null,
                music_prompt: _getBool('musicEnabled', false) ? (document.getElementById('musicPrompt')?.value || null) : null,
            };

            const resp = await fetch('/api/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(r => r.json());
            
            if (resp.error) {
                showToast(resp.error, 'error');
                btn.disabled = false;
                btn.textContent = 'Generate Video';
                return;
            }
            
            currentJobId = resp.job_id;
            document.getElementById('progressBar').classList.add('active');
            document.getElementById('progressText').textContent = 'Processing...';
            
            // Poll for status
            pollInterval = setInterval(pollStatus, 3000);
        }

        function applyBitratePreset() {
            const preset = document.getElementById('bitratePreset').value;
            const presets = {
                'auto': { crf: '23', disableCrf: false },
                'low_720': { crf: null, disableCrf: true },
                'medium_1080': { crf: null, disableCrf: true },
                'high_1080': { crf: null, disableCrf: true },
                'ultra_4k': { crf: null, disableCrf: true },
                'streaming': { crf: null, disableCrf: true },
                'cinema': { crf: null, disableCrf: true },
                'archive': { crf: null, disableCrf: true },
            };
            const p = presets[preset] || presets['auto'];
            const crfSelect = document.getElementById('crf');
            if (p.disableCrf) {
                crfSelect.disabled = true;
                crfSelect.style.opacity = '0.4';
            } else {
                crfSelect.disabled = false;
                crfSelect.style.opacity = '1';
            }
            if (p.crf) crfSelect.value = p.crf;
            showToast(`Bitrate preset: ${preset}`, 'success');
        }

        async function pollStatus() {
            if (!currentJobId) return;
            
            const status = await fetch(`/api/status/${currentJobId}`).then(r => r.json());
            
            if (status.status === 'complete') {
                clearInterval(pollInterval);
                document.getElementById('progressFill').style.width = '100%';
                document.getElementById('progressText').textContent = 'Downloading video...';
                showToast('Video generated! Auto-downloading...', 'success');
                
                // Wait for auto-download to finish, then load and play
                await waitForAutoDownload(currentJobId);
                
                document.getElementById('progressText').textContent = 'Done!';
                showToast('Video ready to watch!', 'success');
                
                setTimeout(() => {
                    document.getElementById('progressBar').classList.remove('active');
                    document.getElementById('progressFill').style.width = '0%';
                    document.getElementById('progressText').textContent = '';
                    document.getElementById('generateBtn').disabled = false;
                    document.getElementById('generateBtn').textContent = 'Generate Video';
                    loadVideos();
                }, 1000);
                
                currentJobId = null;
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                showToast('Generation failed: ' + (status.error || 'Unknown error'), 'error');
                document.getElementById('progressBar').classList.remove('active');
                document.getElementById('progressText').textContent = '';
                document.getElementById('generateBtn').disabled = false;
                document.getElementById('generateBtn').textContent = 'Generate Video';
                currentJobId = null;
            } else {
                document.getElementById('progressText').textContent = 'Generating on GPU...';
            }
        }
        
        async function waitForAutoDownload(jobId) {
            // Poll local download endpoint until video is available locally
            for (let i = 0; i < 60; i++) {
                try {
                    const resp = await fetch(`/api/download/${jobId}`, { method: 'HEAD' });
                    if (resp.ok) return;
                } catch(e) {}
                await new Promise(r => setTimeout(r, 1000));
            }
        }
        
        async function loadVideos() {
            const data = await fetch('/api/videos').then(r => r.json());
            const grid = document.getElementById('videoGrid');
            
            if (!data.videos || data.videos.length === 0) {
                grid.innerHTML = '<div class="empty-state"><div class="icon">&#127916;</div><p>No videos yet. Create your first one above!</p></div>';
                return;
            }
            
            grid.innerHTML = data.videos.map(v => {
                const jobId = v.name.replace('soulillusions_', '').replace('.mp4', '');
                const qcStatus = v.qc_status || 'pending';
                const qcBadge = qcStatus === 'good' ? '<span class="qc-badge qc-good" title="Quality checked: Good">&#9989; Good</span>' :
                    qcStatus === 'defective' ? '<span class="qc-badge qc-bad" title="Defective video">&#10060; Defective</span>' :
                    qcStatus === 'questionable' ? '<span class="qc-badge qc-warn" title="Some issues detected">&#9888; Questionable</span>' :
                    qcStatus === 'failed' ? '<span class="qc-badge qc-bad" title="Generation failed">&#10060; Failed</span>' :
                    '<span class="qc-badge qc-pending" title="Quality check pending">&#8987; Checking</span>';
                const regenBadge = v.auto_regenerated ? '<span class="qc-badge qc-regen" title="Auto-regenerated">&#128260; Auto-fixed</span>' : '';
                const issuesList = (v.qc_issues && v.qc_issues.length > 0) ? 
                    `<div class="qc-issues">${v.qc_issues.map(i => `<div class="qc-issue">${i}</div>`).join('')}</div>` : '';
                const regenBtn = (qcStatus === 'defective' || qcStatus === 'questionable') ? 
                    `<button class="btn btn-warning btn-sm" onclick="regenerateVideo('${jobId}')">Regenerate</button>` : '';
                
                return `
                <div class="video-card">
                    <video controls preload="auto" src="/api/download/${jobId}"></video>
                    <div class="video-info">
                        <div class="name">${v.name}</div>
                        <div class="meta">
                            <span>${v.size_mb}</span>
                            <span>${new Date(v.created * 1000).toLocaleDateString()}</span>
                            ${qcBadge} ${regenBadge}
                        </div>
                        ${issuesList}
                        <div class="video-actions">
                            <a class="btn btn-secondary btn-sm" href="/api/download/${jobId}" download>Download</a>
                            ${regenBtn}
                        </div>
                    </div>
                </div>`;
            }).join('');
        }
        
        async function regenerateVideo(jobId) {
            showToast('Regenerating video with new seed...', 'success');
            const resp = await fetch(`/api/qc/${jobId}/regenerate`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            }).then(r => r.json());
            if (resp.status === 'regenerating') {
                showToast(`New generation started (seed: ${resp.seed})`, 'success');
                setTimeout(() => loadVideos(), 3000);
            } else {
                showToast(resp.error || 'Regeneration failed', 'error');
            }
        }
        
        function showToast(msg, type) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = `toast ${type} show`;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
        
        // === Tab System ===
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const btn = document.querySelector('.tab[onclick*="' + tab + '"]');
            if (btn) btn.classList.add('active');
            const content = document.getElementById('tab-' + tab);
            if (content) content.classList.add('active');
            if (tab === 'production') loadSeriesList();
        }
        
        // === Production Suite ===
        let prodState = { series: null, season: null, episode: null, scene: null };
        let genPollInterval = null;
        
        async function prodFetch(path, opts = {}) {
            const resp = await fetch('/api/production' + path, opts);
            return resp.json();
        }
        
        async function prodPost(path, body) {
            return prodFetch(path, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        }
        
        async function prodPut(path, body) {
            return prodFetch(path, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        }
        
        // Series List View
        async function loadSeriesList() {
            const data = await prodFetch('/series');
            const view = document.getElementById('prodView');
            const series = data.series || [];
            
            view.innerHTML = `
                <div class="prod-card">
                    <h2>&#127916; Production Suite</h2>
                    <p style="color:var(--muted);margin-bottom:20px;">Manage series, seasons, episodes, and scenes for long-form AI video production.</p>
                    
                    <h3>Create New Series</h3>
                    <div class="prod-grid">
                        <div>
                            <label class="prod-label">Series Title</label>
                            <input class="prod-input" id="newSeriesTitle" placeholder="In Time Television" />
                        </div>
                        <div>
                            <label class="prod-label">Genre</label>
                            <select class="prod-select" id="newSeriesGenre">
                                <option value="sci-fi">Sci-Fi</option>
                                <option value="drama">Drama</option>
                                <option value="action">Action</option>
                                <option value="thriller">Thriller</option>
                                <option value="fantasy">Fantasy</option>
                            </select>
                        </div>
                    </div>
                    <label class="prod-label">Concept / Logline</label>
                    <input class="prod-input" id="newSeriesConcept" placeholder="In a future where time is currency, the rich live forever and the poor fight for every second..." />
                    <label class="prod-label">Description</label>
                    <textarea class="prod-textarea" id="newSeriesDesc" placeholder="Detailed series description..."></textarea>
                    <div class="prod-grid" style="margin-top:10px;">
                        <div>
                            <label class="prod-label">Seasons Planned</label>
                            <input class="prod-input" id="newSeriesSeasons" type="number" value="8" />
                        </div>
                        <div>
                            <label class="prod-label">Episodes per Season</label>
                            <input class="prod-input" id="newSeriesEpisodes" type="number" value="16" />
                        </div>
                    </div>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="createSeries()">Create Series</button>
                    </div>
                </div>
                
                <div class="prod-card">
                    <h3>Your Series</h3>
                    ${series.length === 0 ? '<p style="color:var(--muted);">No series yet. Create one above to get started.</p>' : 
                    series.map(s => `
                        <div class="series-card" onclick="openSeries('${s.id}')">
                            <h4>${s.title}</h4>
                            <p>${s.description || 'No description'}</p>
                            <div class="meta">
                                <span>&#128269; ${s.genre}</span>
                                <span>&#128193; ${s.seasons_completed}/${s.seasons_planned} seasons</span>
                                <span>&#127916; ${s.episodes_completed} episodes</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        async function createSeries() {
            const title = document.getElementById('newSeriesTitle').value.trim();
            if (!title) { showToast('Enter a title', 'error'); return; }
            
            const resp = await prodPost('/series/create', {
                title: title,
                concept: document.getElementById('newSeriesConcept').value.trim(),
                description: document.getElementById('newSeriesDesc').value.trim(),
                genre: document.getElementById('newSeriesGenre').value,
                seasons_planned: parseInt(document.getElementById('newSeriesSeasons').value) || 8,
                episodes_per_season: parseInt(document.getElementById('newSeriesEpisodes').value) || 16,
            });
            
            if (resp.status === 'created') {
                showToast('Series created!', 'success');
                loadSeriesList();
            } else {
                showToast(resp.error || 'Failed to create', 'error');
            }
        }
        
        // Series Detail View
        async function openSeries(id) {
            prodState.series = id;
            const data = await prodFetch('/series/' + id);
            const view = document.getElementById('prodView');
            const seasons = data.seasons || {};
            
            let seasonsHtml = '';
            for (let s = 1; s <= data.seasons_planned; s++) {
                const season = seasons[String(s)];
                const epCount = season ? Object.keys(season.episodes || {}).length : 0;
                const status = season ? season.status : 'not started';
                seasonsHtml += `
                    <div class="episode-card" onclick="openSeason(${s})">
                        <div>
                            <span class="ep-num">Season ${s}</span>
                            <div class="ep-title">${epCount} / ${data.episodes_per_season} episodes</div>
                        </div>
                        <span class="ep-status draft">${status}</span>
                    </div>
                `;
            }
            
            // Characters
            const chars = data.characters || {};
            let charsHtml = Object.keys(chars).length > 0 ?
                Object.values(chars).map(c => `
                    <div class="char-item">
                        <strong>${c.name}</strong> - ${c.appearance || 'No appearance set'}<br>
                        <span style="color:var(--muted);">${c.personality || ''}</span>
                    </div>
                `).join('') : '<p style="color:var(--muted);">No characters defined yet.</p>';
            
            view.innerHTML = `
                <div class="breadcrumb">
                    <a onclick="loadSeriesList()">All Series</a>
                    <span class="sep">/</span>
                    <span>${data.title}</span>
                </div>
                
                <div class="prod-card">
                    <h2>${data.title}</h2>
                    <p style="color:var(--muted);margin-bottom:16px;">${data.description || ''}</p>
                    ${data.concept ? `<div class="info-banner"><strong>Concept:</strong> ${data.concept}</div>` : ''}
                    
                    <div class="prod-grid">
                        <div>
                            <h3>World Bible</h3>
                            <textarea class="prod-textarea" id="worldBible" placeholder="Define the world, rules, setting, history...">${data.world_bible || ''}</textarea>
                            <button class="prod-btn secondary" onclick="saveWorldBible()">Save World Bible</button>
                        </div>
                        <div>
                            <h3>Characters</h3>
                            <div class="char-list" style="margin-bottom:12px;">${charsHtml}</div>
                            <label class="prod-label">Add Character</label>
                            <input class="prod-input" id="charName" placeholder="Character name" />
                            <input class="prod-input" id="charAppearance" placeholder="Appearance description" />
                            <input class="prod-input" id="charPersonality" placeholder="Personality traits" />
                            <button class="prod-btn secondary" onclick="addCharacter()">Add Character</button>
                        </div>
                    </div>
                </div>
                
                <div class="prod-card">
                    <h3>Seasons</h3>
                    ${seasonsHtml}
                </div>
            `;
        }
        
        async function saveWorldBible() {
            const text = document.getElementById('worldBible').value;
            const resp = await prodPut('/series/' + prodState.series, { world_bible: text });
            if (resp.status === 'updated') showToast('World bible saved', 'success');
        }
        
        async function addCharacter() {
            const name = document.getElementById('charName').value.trim();
            if (!name) { showToast('Enter a name', 'error'); return; }
            const resp = await prodPost('/series/' + prodState.series + '/characters', {
                name: name,
                appearance: document.getElementById('charAppearance').value.trim(),
                personality: document.getElementById('charPersonality').value.trim(),
            });
            if (resp.status === 'added') {
                showToast('Character added', 'success');
                openSeries(prodState.series);
            }
        }
        
        // Season View
        async function openSeason(seasonNum) {
            prodState.season = seasonNum;
            const data = await prodFetch('/series/' + prodState.series);
            const view = document.getElementById('prodView');
            const season = (data.seasons || {})[String(seasonNum)] || { episodes: {} };
            const episodes = season.episodes || {};
            
            let epsHtml = '';
            for (let e = 1; e <= data.episodes_per_season; e++) {
                const ep = episodes[String(e)];
                const status = ep ? ep.status : 'not created';
                const title = ep ? ep.title : `Episode ${e}`;
                epsHtml += `
                    <div class="episode-card" onclick="openEpisode(${e})">
                        <div>
                            <span class="ep-num">S${seasonNum}E${e}</span>
                            <div class="ep-title">${title}</div>
                        </div>
                        <span class="ep-status ${status}">${status}</span>
                    </div>
                `;
            }
            
            view.innerHTML = `
                <div class="breadcrumb">
                    <a onclick="loadSeriesList()">All Series</a>
                    <span class="sep">/</span>
                    <a onclick="openSeries('${prodState.series}')">${data.title}</a>
                    <span class="sep">/</span>
                    <span>Season ${seasonNum}</span>
                </div>
                
                <div class="prod-card">
                    <h2>Season ${seasonNum}</h2>
                    <div class="prod-btn-row" style="margin-bottom:20px;">
                        <button class="prod-btn" onclick="showCreateEpisode()">+ Create Episode</button>
                        <button class="prod-btn secondary" onclick="reviewSeason()">Review Season</button>
                    </div>
                    <div id="createEpForm" style="display:none;margin-bottom:20px;">
                        <h3>New Episode</h3>
                        <label class="prod-label">Episode Number</label>
                        <input class="prod-input" id="newEpNum" type="number" value="1" min="1" />
                        <label class="prod-label">Title</label>
                        <input class="prod-input" id="newEpTitle" placeholder="Episode title" />
                        <label class="prod-label">Synopsis</label>
                        <textarea class="prod-textarea" id="newEpSynopsis" placeholder="Brief synopsis..."></textarea>
                        <button class="prod-btn" onclick="createEpisode()">Create</button>
                    </div>
                    ${epsHtml}
                </div>
            `;
        }
        
        function showCreateEpisode() {
            const form = document.getElementById('createEpForm');
            form.style.display = form.style.display === 'none' ? 'block' : 'none';
        }
        
        async function createEpisode() {
            const epNum = parseInt(document.getElementById('newEpNum').value);
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${epNum}`, {
                title: document.getElementById('newEpTitle').value.trim(),
                synopsis: document.getElementById('newEpSynopsis').value.trim(),
            });
            if (resp.status === 'created') {
                showToast('Episode created', 'success');
                openEpisode(epNum);
            } else {
                showToast(resp.error || 'Failed', 'error');
            }
        }
        
        // Episode View (Script + Breakdown + Timeline)
        async function openEpisode(epNum) {
            prodState.episode = epNum;
            const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${epNum}`);
            if (data.error) { showToast(data.error, 'error'); return; }
            
            const view = document.getElementById('prodView');
            const hasScript = (data.script_raw || '').length > 0;
            const hasEnhanced = (data.script_enhanced || '').length > 0;
            const hasScenes = data.scene_count > 0;
            
            view.innerHTML = `
                <div class="breadcrumb">
                    <a onclick="loadSeriesList()">All Series</a>
                    <span class="sep">/</span>
                    <a onclick="openSeries('${prodState.series}')">Series</a>
                    <span class="sep">/</span>
                    <a onclick="openSeason(${prodState.season})">Season ${prodState.season}</a>
                    <span class="sep">/</span>
                    <span>${data.title}</span>
                </div>
                
                <div class="prod-card">
                    <h2>${data.title}</h2>
                    <p style="color:var(--muted);margin-bottom:16px;">${data.synopsis || ''}</p>
                    <div class="meta" style="display:flex;gap:20px;font-size:13px;color:var(--muted);margin-bottom:20px;">
                        <span>Status: <strong style="color:var(--text)">${data.status}</strong></span>
                        <span>Scenes: <strong style="color:var(--text)">${data.scene_count || 0}</strong></span>
                        <span>Generated: <strong style="color:var(--text)">${data.generated_scenes || 0}</strong></span>
                        <span>Target: <strong style="color:var(--text)">${Math.floor(data.target_duration/60)}min</strong></span>
                    </div>
                    
                    <h3>&#128221; Script</h3>
                    ${!hasScript ? `
                        <div class="info-banner">Upload or paste a script to get started. You can paste a rough draft and the system will enhance it.</div>
                    ` : ''}
                    <label class="prod-label">Script ${hasScript ? `(${data.script_raw.split(/\\s+/).length} words)` : ''}</label>
                    <textarea class="prod-textarea large" id="scriptText" placeholder="Paste your episode script here...">${data.script_raw || ''}</textarea>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="uploadScript()">Save Script</button>
                        ${hasScript ? `
                            <button class="prod-btn secondary" onclick="enhanceScript()">Enhance Script</button>
                            <select class="prod-select" id="enhanceLevel" style="width:auto;margin-bottom:0;">
                                <option value="basic">Basic</option>
                                <option value="detailed" selected>Detailed</option>
                                <option value="cinematic">Cinematic</option>
                                <option value="book-level">Book-Level</option>
                            </select>
                        ` : ''}
                    </div>
                    
                    ${hasEnhanced ? `
                        <div style="margin-top:16px;">
                            <label class="prod-label">Enhanced Script (${data.script_enhanced.split(/\\s+/).length} words)</label>
                            <textarea class="prod-textarea large" id="enhancedScript">${data.script_enhanced}</textarea>
                        </div>
                    ` : ''}
                </div>
                
                ${hasScript ? `
                <div class="prod-card">
                    <h3>&#127917; Scene Breakdown</h3>
                    <p style="color:var(--muted);margin-bottom:16px;">Break the script into individual scenes for generation.</p>
                    <div class="prod-grid">
                        <div>
                            <label class="prod-label">Scene Duration (seconds)</label>
                            <input class="prod-input" id="sceneDuration" type="number" value="5" min="2" max="18" />
                        </div>
                        <div>
                            <label class="prod-label">Model</label>
                            <select class="prod-select" id="breakdownModel">
                                <option value="ltx">LTX-Video (Fast)</option>
                                <option value="wan">Wan 2.1 1.3B (Best Motion)</option>
                                <option value="cogvideox">CogVideoX-2B (Balanced)</option>
                            </select>
                        </div>
                        <div>
                            <label class="prod-label">Style</label>
                            <select class="prod-select" id="breakdownStyle">
                                <option value="cinematic">Cinematic</option>
                                <option value="realistic">Realistic</option>
                                <option value="anime">Anime</option>
                            </select>
                        </div>
                        <div>
                            <label class="prod-label">Frames per scene</label>
                            <input class="prod-input" id="breakdownFrames" type="number" value="97" />
                        </div>
                    </div>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="breakdownEpisode()">Break Down into Scenes</button>
                        ${hasScenes ? '<button class="prod-btn secondary" onclick="loadTimeline()">View Timeline</button>' : ''}
                    </div>
                </div>
                ` : ''}
                
                <div id="timelineSection"></div>
                <div id="sceneEditorSection"></div>
                <div id="genProgressSection"></div>
                <div id="memorySection"></div>
            `;
            
            if (hasScenes) loadTimeline();
            loadMemoryPanel();
        }
        
        async function uploadScript() {
            const text = document.getElementById('scriptText').value.trim();
            if (!text) { showToast('Script is empty', 'error'); return; }
            
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/script/upload`, {
                script_text: text
            });
            if (resp.status === 'uploaded') {
                showToast(`Script saved (${resp.word_count} words)`, 'success');
                openEpisode(prodState.episode);
            }
        }
        
        async function enhanceScript() {
            const level = document.getElementById('enhanceLevel').value;
            showToast('Enhancing script...', 'success');
            
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/script/enhance`, {
                enhancement_level: level
            });
            if (resp.status === 'enhanced') {
                showToast(`Enhanced ${resp.expansion_ratio} expansion`, 'success');
                openEpisode(prodState.episode);
            } else {
                showToast(resp.error || 'Failed', 'error');
            }
        }
        
        async function breakdownEpisode() {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/breakdown`, {
                scene_duration: parseInt(document.getElementById('sceneDuration').value) || 5,
                model: document.getElementById('breakdownModel').value,
                style: document.getElementById('breakdownStyle').value,
                num_frames: parseInt(document.getElementById('breakdownFrames').value) || 97,
            });
            if (resp.status === 'broken_down') {
                showToast(`${resp.scene_count} scenes created`, 'success');
                loadTimeline();
            } else {
                showToast(resp.error || 'Failed', 'error');
            }
        }
        
        // Timeline View
        async function loadTimeline() {
            const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes`);
            const section = document.getElementById('timelineSection');
            const scenes = data.scenes || [];
            
            if (scenes.length === 0) { section.innerHTML = ''; return; }
            
            const completed = scenes.filter(s => s.status === 'complete').length;
            const failed = scenes.filter(s => s.status === 'failed').length;
            const generating = scenes.filter(s => s.status === 'generating').length;
            
            section.innerHTML = `
                <div class="prod-card">
                    <h3>&#128197; Timeline (${scenes.length} scenes)</h3>
                    <div class="gen-stats" style="margin-bottom:12px;">
                        <span style="color:var(--success)">&#9989; ${completed} complete</span>
                        <span style="color:var(--warning)">&#9203; ${generating} generating</span>
                        <span style="color:var(--error)">&#10060; ${failed} failed</span>
                        <span style="color:var(--muted)">&#9201; ~${Math.floor(scenes.length * (scenes[0]?.duration || 5) / 60)}min total</span>
                    </div>
                    <div class="timeline">
                        ${scenes.map(s => `
                            <div class="timeline-scene ${s.status}" onclick="openScene(${s.scene_number})" title="Scene ${s.scene_number}: ${s.prompt.substring(0,80)}...">
                                ${s.scene_number}
                            </div>
                        `).join('')}
                    </div>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="generateAll()">Generate All Scenes</button>
                        <button class="prod-btn secondary" onclick="assembleEpisode()">Assemble Episode</button>
                        <button class="prod-btn secondary" onclick="uploadToSoulTube()">Upload to SoulTube</button>
                    </div>
                </div>
            `;
        }
        
        // Scene Editor
        async function openScene(sceneNum) {
            prodState.scene = sceneNum;
            const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}`);
            if (data.error) { showToast(data.error, 'error'); return; }
            
            // Also load scene memory and assessment
            const [sceneMem, assessment, adjustments] = await Promise.all([
                prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/memory`).catch(() => null),
                prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/assessment`).catch(() => null),
                prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/adjustments`).catch(() => null),
            ]);
            
            const section = document.getElementById('sceneEditorSection');
            const hasVideo = data.status === 'complete' && data.video_path;
            const videoUrl = `/api/production/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/video`;
            
            // Build memory tags
            let memTagsHtml = '';
            if (sceneMem && !sceneMem.error) {
                if (sceneMem.characters_on_screen && sceneMem.characters_on_screen.length > 0) {
                    memTagsHtml += sceneMem.characters_on_screen.map(c => `<span class="scene-memory-tag char">&#128100; ${c}</span>`).join('');
                }
                if (sceneMem.location && sceneMem.location !== 'unknown') {
                    memTagsHtml += `<span class="scene-memory-tag loc">&#128205; ${sceneMem.location}</span>`;
                }
                if (sceneMem.emotional_tone && sceneMem.emotional_tone !== 'neutral') {
                    memTagsHtml += `<span class="scene-memory-tag tone">&#127917; ${sceneMem.emotional_tone}</span>`;
                }
                if (sceneMem.timeline_id && sceneMem.timeline_id !== 'main') {
                    memTagsHtml += `<span class="scene-memory-tag timeline">&#128260; ${sceneMem.timeline_id}</span>`;
                }
                if (sceneMem.urgency_score !== undefined) {
                    const urg = sceneMem.urgency_score;
                    const urgClass = urg > 0.7 ? 'high' : urg > 0.4 ? 'mid' : 'low';
                    memTagsHtml += `<span class="scene-memory-tag urgency">&#9889; ${(urg*100).toFixed(0)}%</span>`;
                }
            }
            
            // Build assessment HTML
            let assessHtml = '';
            if (assessment && !assessment.error) {
                const score = assessment.overall_score || 0;
                const scoreClass = score > 0.7 ? 'good' : score > 0.4 ? 'mid' : 'low';
                assessHtml = `
                    <div class="learning-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                            <strong>&#128269; Quality Assessment</strong>
                            <span class="learning-score ${scoreClass}">${(score*100).toFixed(0)}%</span>
                        </div>
                        ${assessment.issues && assessment.issues.length > 0 ? 
                            `<div style="color:var(--error);margin-bottom:4px;">${assessment.issues.map(i => `&#9888; ${i}`).join('<br>')}</div>` : ''}
                        ${assessment.adjustments && assessment.adjustments.length > 0 ?
                            `<div style="color:var(--warning);">${assessment.adjustments.slice(0,3).map(a => `&#128161; ${a}`).join('<br>')}</div>` : ''}
                    </div>
                `;
            }
            
            // Build adjustments HTML
            let adjHtml = '';
            if (adjustments && adjustments.adjustments && adjustments.adjustments.length > 0) {
                adjHtml = `
                    <div class="memory-item" style="margin-top:10px;">
                        <div class="label">Learnings Applied (${adjustments.count})</div>
                        <div style="margin-top:4px;">${adjustments.adjustments.map(a => `<div style="margin-bottom:2px;">&#128161; ${a}</div>`).join('')}</div>
                    </div>
                `;
            }
            
            section.innerHTML = `
                <div class="prod-card">
                    <h3>Scene ${sceneNum} ${data.retake_count > 0 ? `(Retake #${data.retake_count})` : ''}</h3>
                    ${memTagsHtml ? `<div style="margin-bottom:12px;">${memTagsHtml}</div>` : ''}
                    <div class="scene-editor">
                        <div class="scene-preview">
                            <h4>Preview</h4>
                            ${hasVideo ? `<video src="${videoUrl}" controls></video>` : '<p style="color:var(--muted);padding:20px 0;">No video generated yet.</p>'}
                            <div class="scene-info">
                                <strong>Status:</strong> ${data.status}<br>
                                <strong>Duration:</strong> ${data.duration}s<br>
                                <strong>Model:</strong> ${data.model}<br>
                                <strong>Retakes:</strong> ${data.retake_count || 0}<br>
                                ${data.error ? `<strong style="color:var(--error)">Error:</strong> ${data.error}` : ''}
                            </div>
                            ${assessHtml}
                            <div class="prod-btn-row">
                                <button class="prod-btn" onclick="retakeScene()">Retake Scene</button>
                                ${hasVideo ? '<button class="prod-btn secondary" onclick="closeScene()">Close</button>' : ''}
                            </div>
                        </div>
                        <div>
                            <h4>Edit Prompt</h4>
                            <label class="prod-label">Generation Prompt</label>
                            <textarea class="prod-textarea" id="scenePrompt">${data.prompt}</textarea>
                            <label class="prod-label">Seed (optional)</label>
                            <input class="prod-input" id="sceneSeed" type="number" value="${data.seed || ''}" placeholder="Random" />
                            <div class="prod-grid" style="margin-top:10px;">
                                <div>
                                    <label class="prod-label">Model</label>
                                    <select class="prod-select" id="sceneModel">
                                        <option value="ltx" ${data.model==='ltx'?'selected':''}>LTX-Video</option>
                                        <option value="wan" ${data.model==='wan'?'selected':''}>Wan 2.1</option>
                                        <option value="cogvideox" ${data.model==='cogvideox'?'selected':''}>CogVideoX-2B</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="prod-label">Transition</label>
                                    <select class="prod-select" id="sceneTransition">
                                        <option value="cut" ${data.transition==='cut'?'selected':''}>Cut</option>
                                        <option value="fade" ${data.transition==='fade'?'selected':''}>Fade</option>
                                        <option value="dissolve" ${data.transition==='dissolve'?'selected':''}>Dissolve</option>
                                        <option value="wipe" ${data.transition==='wipe'?'selected':''}>Wipe</option>
                                    </select>
                                </div>
                            </div>
                            <div class="prod-btn-row">
                                <button class="prod-btn secondary" onclick="saveScene(${sceneNum})">Save Changes</button>
                                <button class="prod-btn secondary" onclick="assessScene(${sceneNum})">Assess Quality</button>
                            </div>
                            ${adjHtml}
                        </div>
                    </div>
                </div>
            `;
        }
        
        function closeScene() {
            document.getElementById('sceneEditorSection').innerHTML = '';
            prodState.scene = null;
        }
        
        async function saveScene(sceneNum) {
            const resp = await prodPut(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}`, {
                prompt: document.getElementById('scenePrompt').value,
                seed: parseInt(document.getElementById('sceneSeed').value) || null,
                model: document.getElementById('sceneModel').value,
                transition: document.getElementById('sceneTransition').value,
            });
            if (resp.status === 'updated') showToast('Scene saved', 'success');
        }
        
        async function retakeScene() {
            const prompt = document.getElementById('scenePrompt').value;
            const seed = parseInt(document.getElementById('sceneSeed').value) || null;
            
            showToast('Starting retake...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${prodState.scene}/retake`, {
                prompt_override: prompt,
                seed: seed,
            });
            if (resp.status === 'retake_started') {
                showToast(`Retake #${resp.retake_count} started`, 'success');
                pollGeneration();
            }
        }
        
        async function generateAll() {
            if (!confirm('Generate all pending scenes? This will take a while.')) return;
            
            showToast('Starting batch generation...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/generate`, {});
            if (resp.status === 'started') {
                showToast(`Generating ${resp.total_scenes} scenes...`, 'success');
                pollGeneration();
            } else if (resp.status === 'no_work') {
                showToast('All scenes already generated', 'success');
            } else {
                showToast(resp.error || 'Failed to start', 'error');
            }
        }
        
        function pollGeneration() {
            if (genPollInterval) clearInterval(genPollInterval);
            genPollInterval = setInterval(async () => {
                const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/generate/status`);
                
                const section = document.getElementById('genProgressSection');
                if (!section) return;
                
                if (data.status === 'idle' || data.status === 'complete') {
                    if (data.status === 'complete') {
                        section.innerHTML = `
                            <div class="gen-progress">
                                <h3>Generation Complete</h3>
                                <div class="gen-stats">
                                    <span style="color:var(--success)">&#9989; ${data.completed} completed</span>
                                    <span style="color:var(--error)">&#10060; ${data.failed} failed</span>
                                </div>
                            </div>
                        `;
                        loadTimeline();
                        clearInterval(genPollInterval);
                        genPollInterval = null;
                    }
                    return;
                }
                
                const pct = data.total_scenes > 0 ? (data.completed / data.total_scenes) * 100 : 0;
                section.innerHTML = `
                    <div class="gen-progress">
                        <h3>Generating... Scene ${data.current_scene} of ${data.total_scenes}</h3>
                        <div class="gen-progress-bar">
                            <div class="gen-progress-fill" style="width:${pct}%"></div>
                        </div>
                        <div class="gen-stats">
                            <span style="color:var(--success)">&#9989; ${data.completed} done</span>
                            <span style="color:var(--error)">&#10060; ${data.failed} failed</span>
                            <span style="color:var(--muted)">${Math.round(pct)}%</span>
                        </div>
                        ${data.errors.length > 0 ? `<div style="margin-top:8px;font-size:12px;color:var(--error);">${data.errors.slice(-3).join('<br>')}</div>` : ''}
                    </div>
                `;
                loadTimeline();
            }, 5000);
        }
        
        async function assembleEpisode() {
            showToast('Assembling episode...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/assemble`, {});
            if (resp.status === 'assembled') {
                showToast(`Assembled ${resp.scenes_assembled} scenes (${resp.file_size_mb})`, 'success');
            } else {
                showToast(resp.error || 'Assembly failed', 'error');
            }
        }
        
        async function uploadToSoulTube() {
            const url = prompt('SoulTube API URL:', 'https://your-soulmate-url.com');
            if (!url) return;
            
            showToast('Uploading to SoulTube...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/upload`, {
                soultube_api_url: url,
            });
            if (resp.status === 'uploaded') {
                showToast(`Uploaded! SoulTube ID: ${resp.soultube_id}`, 'success');
            } else {
                showToast(resp.error || 'Upload failed', 'error');
            }
        }
        
        async function reviewSeason() {
            showToast('Reviewing season...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/review`, {
                review_scope: 'season',
                review_depth: 'thorough'
            });
            if (resp.review_notes) {
                const notes = resp.review_notes;
                const view = document.getElementById('prodView');
                view.innerHTML = `
                    <div class="breadcrumb">
                        <a onclick="loadSeriesList()">All Series</a>
                        <span class="sep">/</span>
                        <a onclick="openSeries('${prodState.series}')">Series</a>
                        <span class="sep">/</span>
                        <a onclick="openSeason(${prodState.season})">Season ${prodState.season}</a>
                        <span class="sep">/</span>
                        <span>Review</span>
                    </div>
                    <div class="prod-card">
                        <h2>&#128269; Season ${prodState.season} Review</h2>
                        <div class="info-banner">${notes.overall_assessment}</div>
                        
                        <h3>Strengths</h3>
                        ${notes.strengths.map(s => `<div style="color:var(--success);margin-bottom:4px;">&#9989; ${s}</div>`).join('') || '<p style="color:var(--muted)">None identified</p>'}
                        
                        <h3 style="margin-top:16px;">Weaknesses</h3>
                        ${notes.weaknesses.map(w => `<div style="color:var(--error);margin-bottom:4px;">&#10060; ${w}</div>`).join('') || '<p style="color:var(--muted)">None identified</p>'}
                        
                        <h3 style="margin-top:16px;">Suggestions for Next Season</h3>
                        ${notes.suggestions.map(s => `<div style="margin-bottom:4px;">&#128161; ${s}</div>`).join('')}
                        
                        ${notes.pacing_notes.length > 0 ? `
                        <h3 style="margin-top:16px;">Pacing Notes</h3>
                        ${notes.pacing_notes.map(p => `<div style="margin-bottom:4px;color:var(--warning);">&#9203; ${p}</div>`).join('')}
                        ` : ''}
                        
                        <div class="prod-btn-row" style="margin-top:20px;">
                            <button class="prod-btn secondary" onclick="openSeason(${prodState.season})">Back to Season</button>
                        </div>
                    </div>
                `;
            }
        }
        
        // === Narrative Memory UI ===
        
        async function loadMemoryPanel() {
            const section = document.getElementById('memorySection');
            if (!section) return;
            
            // Check memory engine status
            const status = await prodFetch('/memory/status').catch(() => ({enabled: false}));
            if (!status.enabled) {
                section.innerHTML = `
                    <div class="memory-panel">
                        <h4>&#129504; Narrative Memory Engine</h4>
                        <span class="memory-badge off">DISABLED</span>
                        <p style="color:var(--muted);font-size:12px;margin-top:8px;">Memory engine not loaded. Ensure narrative_memory.py is present.</p>
                    </div>
                `;
                return;
            }
            
            // Load series memory, narrative stack, and learnings in parallel
            const [seriesMem, stackInfo, learnings] = await Promise.all([
                prodState.series ? prodFetch(`/series/${prodState.series}/memory`).catch(() => null) : null,
                prodState.series && prodState.season && prodState.episode ? 
                    prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack`).catch(() => null) : null,
                prodState.series ? prodFetch(`/series/${prodState.series}/learnings`).catch(() => null) : null,
            ]);
            
            // Build narrative stack visualization
            let stackHtml = '';
            if (stackInfo && !stackInfo.error) {
                const stack = stackInfo.stack || [];
                const active = stackInfo.active_timeline || 'main';
                if (stack.length > 0) {
                    stackHtml = '<div class="narrative-stack-viz">';
                    stackHtml += `<div class="stack-layer main ${active === 'main' ? 'active' : ''}">
                        <span>&#128193; Main Timeline</span>
                        <span style="font-size:10px;color:var(--muted);">depth 0</span>
                    </div>`;
                    stack.forEach((layer, i) => {
                        const layerType = layer.timeline_id ? layer.timeline_id.split('_')[0] : 'nested';
                        const isActive = layer.timeline_id === active;
                        stackHtml += `<div class="stack-layer ${layerType} ${isActive ? 'active' : ''}">
                            <span>&#128260; ${layer.timeline_id || 'nested'}</span>
                            <span style="font-size:10px;color:var(--muted);">depth ${layer.depth || i+1} &middot; scene ${layer.scene_number || '?'}</span>
                        </div>`;
                    });
                    stackHtml += '</div>';
                } else {
                    stackHtml = '<p style="color:var(--muted);font-size:12px;">No nested stories active. Main timeline.</p>';
                }
            }
            
            // Build learning summary
            let learnHtml = '';
            if (learnings && !learnings.error && learnings.total_learnings > 0) {
                const score = learnings.avg_score || 0;
                const scoreClass = score > 0.7 ? 'good' : score > 0.4 ? 'mid' : 'low';
                learnHtml = `
                    <div class="memory-grid">
                        <div class="memory-item">
                            <div class="label">Total Learnings</div>
                            <div class="value">${learnings.total_learnings}</div>
                        </div>
                        <div class="memory-item">
                            <div class="label">Avg Quality Score</div>
                            <div class="value"><span class="learning-score ${scoreClass}">${(score*100).toFixed(0)}%</span></div>
                        </div>
                        <div class="memory-item">
                            <div class="label">Score Trend</div>
                            <div class="value">${learnings.score_trend === 'improving' ? '&#128200; Improving' : '&#128193; Stable'}</div>
                        </div>
                        <div class="memory-item">
                            <div class="label">Total Retakes</div>
                            <div class="value">${learnings.total_retakes || 0}</div>
                        </div>
                    </div>
                    ${learnings.common_issues && learnings.common_issues.length > 0 ? `
                        <div style="margin-top:10px;">
                            <div class="label" style="color:var(--muted);font-size:11px;text-transform:uppercase;margin-bottom:4px;">Common Issues</div>
                            ${learnings.common_issues.slice(0,3).map(i => `<div style="font-size:11px;color:var(--error);margin-bottom:2px;">&#9888; ${i.issue} (${i.count}x)</div>`).join('')}
                        </div>
                    ` : ''}
                `;
            } else {
                learnHtml = '<p style="color:var(--muted);font-size:12px;">No learnings yet. Generate scenes to start the learning loop.</p>';
            }
            
            // Build character visual anchors
            let charAnchorsHtml = '';
            if (seriesMem && !seriesMem.error && seriesMem.visual_anchors) {
                const anchors = seriesMem.visual_anchors;
                const charCount = Object.keys(anchors).length;
                if (charCount > 0) {
                    charAnchorsHtml = '<div class="memory-grid">';
                    for (const [charId, anchor] of Object.entries(anchors)) {
                        charAnchorsHtml += `
                            <div class="memory-item">
                                <div class="label">${charId}</div>
                                <div class="value" style="font-size:11px;">${anchor.scene_count || 0} scenes &middot; last: ${anchor.last_seen_scene || 'never'}</div>
                            </div>
                        `;
                    }
                    charAnchorsHtml += '</div>';
                }
            }
            
            section.innerHTML = `
                <div class="memory-panel">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <h4>&#129504; Narrative Memory Engine</h4>
                        <span class="memory-badge on">ACTIVE</span>
                    </div>
                    
                    <div class="memory-tabs">
                        <div class="memory-tab active" onclick="switchMemoryTab('stack', this)">Narrative Stack</div>
                        <div class="memory-tab" onclick="switchMemoryTab('learn', this)">Learning</div>
                        <div class="memory-tab" onclick="switchMemoryTab('anchors', this)">Visual Anchors</div>
                    </div>
                    
                    <div id="memTab-stack" class="mem-tab-content">
                        ${stackHtml || '<p style="color:var(--muted);font-size:12px;">No episode selected.</p>'}
                        ${prodState.series && prodState.season && prodState.episode ? `
                            <div class="prod-btn-row" style="margin-top:10px;">
                                <button class="prod-btn secondary" style="font-size:12px;padding:6px 12px;" onclick="scanNestedStories()">Scan Script for Nested Stories</button>
                                <button class="prod-btn secondary" style="font-size:12px;padding:6px 12px;" onclick="pushNestedStory()">Push Timeline</button>
                                <button class="prod-btn secondary" style="font-size:12px;padding:6px 12px;" onclick="popNestedStory()">Pop Timeline</button>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div id="memTab-learn" class="mem-tab-content" style="display:none;">
                        ${learnHtml}
                    </div>
                    
                    <div id="memTab-anchors" class="mem-tab-content" style="display:none;">
                        ${charAnchorsHtml || '<p style="color:var(--muted);font-size:12px;">No visual anchors yet.</p>'}
                    </div>
                </div>
            `;
        }
        
        function switchMemoryTab(tab, el) {
            document.querySelectorAll('.memory-tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            document.querySelectorAll('.mem-tab-content').forEach(c => c.style.display = 'none');
            document.getElementById('memTab-' + tab).style.display = 'block';
        }
        
        async function scanNestedStories() {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack/scan`, {});
            if (resp.nested_regions) {
                if (resp.count > 0) {
                    showToast(`Found ${resp.count} nested story regions!`, 'success');
                    const details = resp.nested_regions.map(r => 
                        `${r.type}: lines ${r.start_line}-${r.end_line || 'end'}${r.note ? ' (' + r.note + ')' : ''}`
                    ).join('\\n');
                    alert(`Nested stories detected:\\n\\n${details}`);
                } else {
                    showToast('No nested stories found in script', 'success');
                }
                loadMemoryPanel();
            } else {
                showToast(resp.error || 'Scan failed', 'error');
            }
        }
        
        async function pushNestedStory() {
            const type = prompt('Timeline type (flashback/dream/memory/vision/parallel):', 'flashback');
            if (!type) return;
            const sceneNum = prodState.scene || 1;
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack/push`, {
                type: type,
                scene_number: sceneNum,
            });
            if (resp.status === 'pushed') {
                showToast(`Pushed ${type} timeline (depth ${resp.depth})`, 'success');
                loadMemoryPanel();
            } else {
                showToast(resp.error || 'Push failed', 'error');
            }
        }
        
        async function popNestedStory() {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack/pop`, {});
            if (resp.status === 'popped') {
                showToast(`Popped to ${resp.restored_timeline} (scene ${resp.restored_scene})`, 'success');
                loadMemoryPanel();
            } else {
                showToast(resp.message || 'Pop failed', 'error');
            }
        }
        
        async function assessScene(sceneNum) {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/assess`, {});
            if (resp.overall_score !== undefined) {
                showToast(`Quality: ${(resp.overall_score*100).toFixed(0)}%`, 'success');
                openScene(sceneNum);
            } else {
                showToast(resp.error || 'Assessment failed', 'error');
            }
        }
        
        // ==================== IMAGE STUDIO ====================
        let imgState = {
            model: 'flux', modelName: 'FLUX.1',
            aspectRatio: '1:1', quality: 'standard',
            imageMode: 't2i', referenceImages: [],
            stylePreset: 'None', enhanceTags: new Set(),
            imageOptions: null, imageHistory: [],
            currentImageUrl: null, currentJobId: null,
            imgPollInterval: null,
        };

        async function imgInit() {
            try {
                const resp = await fetch('/api/image/options').then(r => r.json());
                if (resp.error) return;
                imgState.imageOptions = resp;
                imgRenderStylePresets();
                imgRenderQuickPrompts();
                imgRenderEnhanceTags();
                imgLoadHistory();
            } catch(e) { console.warn('Image options not loaded:', e); }
            // Auto-grow textarea
            const ta = document.getElementById('imgPrompt');
            if (ta) {
                ta.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
                });
            }
            // Slider listeners
            const gs = document.getElementById('imgGuidanceSlider');
            if (gs) gs.oninput = (e) => { document.getElementById('imgGuidanceVal').textContent = e.target.value; };
            const ss = document.getElementById('imgStepsSlider');
            if (ss) ss.oninput = (e) => { document.getElementById('imgStepsVal').textContent = e.target.value; };
            const bs = document.getElementById('imgBatchSlider');
            if (bs) bs.oninput = (e) => { document.getElementById('imgBatchVal').textContent = e.target.value; };
            const rs = document.getElementById('imgRefStrengthSlider');
            if (rs) rs.oninput = (e) => { document.getElementById('imgRefStrengthVal').textContent = e.target.value + '%'; };
        }

        function imgRenderStylePresets() {
            const container = document.getElementById('imgStylePresets');
            if (!container || !imgState.imageOptions) return;
            container.innerHTML = '';
            imgState.imageOptions.style_presets.forEach(s => {
                const btn = document.createElement('button');
                btn.className = 'img-style-btn' + (s === imgState.stylePreset ? ' active' : '');
                btn.textContent = s;
                btn.onclick = () => {
                    imgState.stylePreset = s;
                    container.querySelectorAll('.img-style-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                };
                container.appendChild(btn);
            });
        }

        function imgRenderQuickPrompts() {
            const container = document.getElementById('imgQuickPrompts');
            if (!container || !imgState.imageOptions) return;
            container.innerHTML = '';
            imgState.imageOptions.quick_prompts.forEach(q => {
                const btn = document.createElement('button');
                btn.className = 'img-quick-btn';
                btn.textContent = q.label;
                btn.onclick = () => {
                    document.getElementById('imgPrompt').value = q.prompt;
                    document.getElementById('imgToolsPanel').style.display = 'none';
                };
                container.appendChild(btn);
            });
        }

        function imgRenderEnhanceTags() {
            const container = document.getElementById('imgEnhanceTags');
            if (!container || !imgState.imageOptions) return;
            container.innerHTML = '';
            const tags = imgState.imageOptions.enhance_tags;
            Object.entries(tags).forEach(([category, tagList]) => {
                tagList.forEach(tag => {
                    const btn = document.createElement('button');
                    btn.className = 'img-tag-btn';
                    btn.textContent = tag;
                    btn.onclick = () => {
                        if (imgState.enhanceTags.has(tag)) {
                            imgState.enhanceTags.delete(tag);
                            btn.classList.remove('active');
                        } else {
                            imgState.enhanceTags.add(tag);
                            btn.classList.add('active');
                        }
                        imgUpdateEnhancedPrompt();
                    };
                    container.appendChild(btn);
                });
            });
        }

        function imgUpdateEnhancedPrompt() {
            const base = (document.getElementById('imgBasePrompt')?.value || '').trim();
            const tags = Array.from(imgState.enhanceTags).join(', ');
            const enhanced = [base, tags].filter(p => p).join(', ');
            const display = document.getElementById('imgEnhancedDisplay');
            if (display) {
                display.textContent = enhanced || 'Enhanced prompt will appear here...';
                display.style.color = enhanced ? 'var(--text)' : 'var(--muted)';
            }
        }

        function imgCopyEnhanced() {
            const text = document.getElementById('imgEnhancedDisplay')?.textContent || '';
            if (text && text !== 'Enhanced prompt will appear here...') {
                navigator.clipboard.writeText(text);
                showToast('Copied to clipboard', 'success');
            }
        }

        function imgUseEnhanced() {
            const text = document.getElementById('imgEnhancedDisplay')?.textContent || '';
            if (text && text !== 'Enhanced prompt will appear here...') {
                document.getElementById('imgPrompt').value = text;
                document.getElementById('imgToolsPanel').style.display = 'none';
            }
        }

        function imgToggleAdvanced() {
            const panel = document.getElementById('imgAdvPanel');
            const isVisible = panel.style.display !== 'none';
            panel.style.display = isVisible ? 'none' : 'block';
            document.getElementById('imgAdvLabel').textContent = isVisible ? 'Advanced' : 'Less';
        }

        function imgToggleTools() {
            const panel = document.getElementById('imgToolsPanel');
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }

        function imgToggleDropdown(type) {
            // Remove any existing dropdown
            const existing = document.querySelector('.img-dropdown');
            if (existing) { existing.remove(); return; }
            if (!imgState.imageOptions) return;
            const dd = document.createElement('div');
            dd.className = 'img-dropdown';
            if (type === 'model') {
                const models = imgState.imageMode === 't2i' ? imgState.imageOptions.t2i_models : imgState.imageOptions.i2i_models;
                const search = document.createElement('input');
                search.type = 'text'; search.placeholder = 'Search models...'; search.className = 'img-dropdown-search';
                dd.appendChild(search);
                const list = document.createElement('div');
                const renderList = (filter) => {
                    list.innerHTML = '';
                    Object.entries(models).forEach(([id, m]) => {
                        if (filter && !m.label.toLowerCase().includes(filter.toLowerCase()) && !id.toLowerCase().includes(filter.toLowerCase())) return;
                        const item = document.createElement('div');
                        item.className = 'img-dropdown-item' + (id === imgState.model ? ' selected' : '');
                        item.innerHTML = `<div class="model-icon">${m.label.charAt(0)}</div><div class="model-info"><div class="model-name">${m.label}</div><div class="model-desc">${m.desc}</div></div>`;
                        item.onclick = () => {
                            imgState.model = id; imgState.modelName = m.label;
                            document.getElementById('imgModelLabel').textContent = m.label;
                            // Update available ARs
                            const ars = m.aspect_ratios || Object.keys(imgState.imageOptions.aspect_ratios);
                            if (ars.length > 0 && !ars.includes(imgState.aspectRatio)) {
                                imgState.aspectRatio = ars[0];
                                document.getElementById('imgArLabel').textContent = ars[0];
                            }
                            dd.remove();
                        };
                        list.appendChild(item);
                    });
                };
                renderList('');
                search.oninput = (e) => renderList(e.target.value);
                dd.appendChild(list);
            } else if (type === 'ar') {
                const models = imgState.imageMode === 't2i' ? imgState.imageOptions.t2i_models : imgState.imageOptions.i2i_models;
                const modelInfo = models[imgState.model];
                const ars = modelInfo ? (modelInfo.aspect_ratios || Object.keys(imgState.imageOptions.aspect_ratios)) : Object.keys(imgState.imageOptions.aspect_ratios);
                ars.forEach(r => {
                    const item = document.createElement('div');
                    item.className = 'img-dropdown-item' + (r === imgState.aspectRatio ? ' selected' : '');
                    const label = imgState.imageOptions.aspect_ratios[r] || r;
                    item.innerHTML = `<div class="model-icon" style="font-size:0.6em;">${r}</div><div class="model-info"><div class="model-name">${label}</div></div>`;
                    item.onclick = () => {
                        imgState.aspectRatio = r;
                        document.getElementById('imgArLabel').textContent = r;
                        dd.remove();
                    };
                    dd.appendChild(item);
                });
            } else if (type === 'quality') {
                Object.entries(imgState.imageOptions.quality_presets).forEach(([id, label]) => {
                    const item = document.createElement('div');
                    item.className = 'img-dropdown-item' + (id === imgState.quality ? ' selected' : '');
                    item.innerHTML = `<div class="model-icon" style="font-size:0.6em;">&#9733;</div><div class="model-info"><div class="model-name">${label}</div></div>`;
                    item.onclick = () => {
                        imgState.quality = id;
                        document.getElementById('imgQualityLabel').textContent = label;
                        dd.remove();
                    };
                    dd.appendChild(item);
                });
            }
            // Position near button
            const btn = type === 'model' ? document.getElementById('imgModelBtn') : type === 'ar' ? document.getElementById('imgArBtn') : document.getElementById('imgQualityBtn');
            const rect = btn.getBoundingClientRect();
            dd.style.position = 'fixed';
            dd.style.bottom = (window.innerHeight - rect.top + 8) + 'px';
            dd.style.left = rect.left + 'px';
            document.body.appendChild(dd);
            // Close on outside click
            setTimeout(() => {
                document.addEventListener('click', function close(e) {
                    if (!dd.contains(e.target) && e.target !== btn) { dd.remove(); document.removeEventListener('click', close); }
                });
            }, 100);
        }

        function imgUploadClick() {
            const input = document.createElement('input');
            input.type = 'file'; input.accept = 'image/*'; input.multiple = true;
            input.onchange = (e) => {
                const files = Array.from(e.target.files);
                if (files.length === 0) return;
                imgState.referenceImages = [];
                files.forEach(f => {
                    const url = URL.createObjectURL(f);
                    imgState.referenceImages.push(url);
                });
                imgSwitchMode(true);
                imgRenderRefPreview();
            };
            input.click();
        }

        function imgSwitchMode(toI2I) {
            imgState.imageMode = toI2I ? 'i2i' : 't2i';
            const badge = document.getElementById('imgModeBadge');
            badge.textContent = toI2I ? 'I2I' : 'T2I';
            badge.className = 'img-mode-badge ' + (toI2I ? 'i2i' : 't2i');
            const uploadBtn = document.getElementById('imgUploadBtn');
            uploadBtn.classList.toggle('active', toI2I);
            // Switch model to first available in new mode
            if (imgState.imageOptions) {
                const models = toI2I ? imgState.imageOptions.i2i_models : imgState.imageOptions.t2i_models;
                const firstKey = Object.keys(models)[0];
                if (firstKey) {
                    imgState.model = firstKey;
                    imgState.modelName = models[firstKey].label;
                    document.getElementById('imgModelLabel').textContent = models[firstKey].label;
                    // Update AR if needed
                    const ars = models[firstKey].aspect_ratios;
                    if (ars && !ars.includes(imgState.aspectRatio)) {
                        imgState.aspectRatio = ars[0];
                        document.getElementById('imgArLabel').textContent = ars[0];
                    }
                }
            }
            const ta = document.getElementById('imgPrompt');
            ta.placeholder = toI2I ? 'Describe how to transform this image (optional)...' : 'Describe the image you want to create...';
        }

        function imgRenderRefPreview() {
            const container = document.getElementById('imgRefPreview');
            container.innerHTML = '';
            container.style.display = imgState.referenceImages.length > 0 ? 'flex' : 'none';
            imgState.referenceImages.forEach((url, i) => {
                const thumb = document.createElement('div');
                thumb.className = 'img-ref-thumb';
                thumb.innerHTML = `<img src="${url}" /><div class="ref-remove" onclick="imgRemoveRef(${i})">&times;</div>`;
                container.appendChild(thumb);
            });
        }

        function imgRemoveRef(idx) {
            imgState.referenceImages.splice(idx, 1);
            imgRenderRefPreview();
            if (imgState.referenceImages.length === 0) imgSwitchMode(false);
        }

        async function generateImage() {
            const prompt = document.getElementById('imgPrompt').value.trim();
            if (imgState.imageMode === 't2i' && !prompt) { showToast('Enter a prompt first', 'error'); return; }
            if (imgState.imageMode === 'i2i' && imgState.referenceImages.length === 0) { showToast('Upload a reference image', 'error'); return; }

            const btn = document.getElementById('imgGenBtn');
            btn.disabled = true;
            btn.textContent = 'Generating...';
            document.getElementById('imgHero').style.opacity = '0.3';
            document.getElementById('imgProgress').style.display = 'block';
            document.getElementById('imgProgressFill').style.width = '10%';
            document.getElementById('imgProgressText').textContent = 'Submitting...';

            const payload = {
                prompt: prompt,
                model: imgState.model,
                negative_prompt: document.getElementById('imgNegPrompt')?.value || null,
                aspect_ratio: imgState.aspectRatio,
                quality: imgState.quality,
                seed: parseInt(document.getElementById('imgSeed')?.value) || null,
                batch_count: parseInt(document.getElementById('imgBatchSlider')?.value) || 1,
                style_preset: imgState.stylePreset,
                width: parseInt(document.getElementById('imgWidth')?.value) || null,
                height: parseInt(document.getElementById('imgHeight')?.value) || null,
                guidance_scale: parseFloat(document.getElementById('imgGuidanceSlider')?.value) || 7.5,
                steps: parseInt(document.getElementById('imgStepsSlider')?.value) || 25,
                lora_model: document.getElementById('imgLora')?.value || null,
                lora_weight: 1.0,
                reference_strength: parseInt(document.getElementById('imgRefStrengthSlider')?.value) || 50,
                image_mode: imgState.imageMode,
                reference_images: imgState.imageMode === 'i2i' ? imgState.referenceImages : [],
            };

            try {
                const resp = await fetch('/api/image/generate', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                }).then(r => r.json());

                if (resp.error) throw new Error(resp.error);
                const jobId = resp.job_id || resp.id;
                if (jobId) {
                    imgState.currentJobId = jobId;
                    imgPollImage(jobId, prompt);
                } else if (resp.url) {
                    imgShowResult(resp.url, prompt);
                } else {
                    throw new Error('No job ID or URL in response');
                }
            } catch(e) {
                btn.disabled = false;
                btn.textContent = 'Generate';
                document.getElementById('imgHero').style.opacity = '1';
                document.getElementById('imgProgress').style.display = 'none';
                showToast('Error: ' + e.message, 'error');
            }
        }

        async function imgPollImage(jobId, prompt) {
            let attempts = 0;
            const maxAttempts = 120;
            imgState.imgPollInterval = setInterval(async () => {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(imgState.imgPollInterval);
                    imgResetGenBtn();
                    showToast('Image generation timed out', 'error');
                    return;
                }
                try {
                    const status = await fetch(`/api/image/status/${jobId}`).then(r => r.json());
                    const pct = Math.min(95, 10 + attempts * 0.7);
                    document.getElementById('imgProgressFill').style.width = pct + '%';
                    document.getElementById('imgProgressText').textContent = status.status || 'Processing...';
                    if (status.status === 'completed' || status.status === 'succeeded' || status.status === 'success') {
                        clearInterval(imgState.imgPollInterval);
                        const url = status.url || status.image_url || status.output_url;
                        if (url) {
                            imgShowResult(url, prompt);
                        } else {
                            // Try downloading
                            const dlUrl = `/api/image/download/${jobId}`;
                            imgShowResult(dlUrl, prompt);
                        }
                    } else if (status.status === 'failed' || status.status === 'error') {
                        clearInterval(imgState.imgPollInterval);
                        imgResetGenBtn();
                        showToast('Generation failed: ' + (status.error || 'Unknown'), 'error');
                    }
                } catch(e) { /* keep polling */ }
            }, 2000);
        }

        function imgShowResult(url, prompt) {
            document.getElementById('imgProgressFill').style.width = '100%';
            document.getElementById('imgProgressText').textContent = 'Done!';
            setTimeout(() => {
                document.getElementById('imgProgress').style.display = 'none';
            }, 1000);
            imgState.currentImageUrl = url;
            const canvas = document.getElementById('imgCanvas');
            const img = document.getElementById('imgResult');
            img.src = url;
            img.onload = () => {
                canvas.classList.add('active');
            };
            // Add to history
            imgAddToHistory({ url, prompt, model: imgState.model, timestamp: Date.now() });
            imgResetGenBtn();
        }

        function imgResetGenBtn() {
            const btn = document.getElementById('imgGenBtn');
            btn.disabled = false;
            btn.textContent = 'Generate';
            document.getElementById('imgHero').style.opacity = '1';
        }

        function imgAddToHistory(entry) {
            imgState.imageHistory.unshift(entry);
            imgState.imageHistory = imgState.imageHistory.slice(0, 50);
            try { localStorage.setItem('soul_img_history', JSON.stringify(imgState.imageHistory)); } catch(e) {}
            imgRenderHistory();
        }

        function imgRenderHistory() {
            const list = document.getElementById('imgHistoryList');
            if (!list) return;
            list.innerHTML = '';
            if (imgState.imageHistory.length === 0) {
                document.getElementById('imgHistory').classList.remove('active');
                return;
            }
            document.getElementById('imgHistory').classList.add('active');
            imgState.imageHistory.forEach((entry, idx) => {
                const thumb = document.createElement('div');
                thumb.className = 'img-history-thumb' + (idx === 0 ? ' active' : '');
                thumb.innerHTML = `<img src="${entry.url}" alt="${(entry.prompt||'').substring(0,20)}" /><div class="thumb-overlay"><span style="font-size:10px;">&#8595;</span></div>`;
                thumb.onclick = () => {
                    imgState.currentImageUrl = entry.url;
                    document.getElementById('imgResult').src = entry.url;
                    document.getElementById('imgCanvas').classList.add('active');
                    list.querySelectorAll('.img-history-thumb').forEach(t => t.classList.remove('active'));
                    thumb.classList.add('active');
                };
                thumb.querySelector('.thumb-overlay').onclick = (e) => {
                    e.stopPropagation();
                    imgDownloadImage(entry.url);
                };
                list.appendChild(thumb);
            });
        }

        function imgLoadHistory() {
            try {
                const saved = JSON.parse(localStorage.getItem('soul_img_history') || '[]');
                imgState.imageHistory = saved;
                imgRenderHistory();
            } catch(e) {}
        }

        function imgRegenerate() {
            document.getElementById('imgCanvas').classList.remove('active');
            generateImage();
        }

        function imgDownload() {
            if (imgState.currentImageUrl) imgDownloadImage(imgState.currentImageUrl);
        }

        async function imgDownloadImage(url) {
            try {
                const resp = await fetch(url);
                const blob = await resp.blob();
                const blobUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl; a.download = `soulillusions_${Date.now()}.png`;
                document.body.appendChild(a); a.click(); document.body.removeChild(a);
                URL.revokeObjectURL(blobUrl);
            } catch(e) { window.open(url, '_blank'); }
        }

        function imgNewPrompt() {
            document.getElementById('imgCanvas').classList.remove('active');
            document.getElementById('imgPrompt').value = '';
            document.getElementById('imgPrompt').focus();
            imgState.referenceImages = [];
            imgRenderRefPreview();
            imgSwitchMode(false);
        }

        function imgSendToVideo() {
            if (!imgState.currentImageUrl) return;
            // Switch to Video Maker tab and pre-fill with image as first frame
            switchTab('maker');
            showToast('Image loaded! Use it as a reference in your video prompt.', 'success');
            // Add a note to the prompt area about the image
            const promptArea = document.getElementById('prompt');
            if (promptArea && !promptArea.value) {
                promptArea.value = '[First frame from Image Studio] ';
                promptArea.focus();
            }
            // Store the image URL for potential use in generation
            window._imgToVideoUrl = imgState.currentImageUrl;
        }

        // ==================== ASSET LIBRARY ====================
        let assetState = {
            categories: null, assets: [], currentCategory: null,
            selectedAsset: null, searchQuery: '',
        };

        async function assetInit() {
            try {
                const resp = await fetch('/api/assets/categories').then(r => r.json());
                if (resp.error) return;
                assetState.categories = resp.categories;
                assetRenderCategories();
                assetLoadStats();
            } catch(e) { console.warn('Asset library init failed:', e); }
            // Script drop zone drag events
            const dz = document.getElementById('scriptDropZone');
            if (dz) {
                dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('dragover'); });
                dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
                dz.addEventListener('drop', (e) => {
                    e.preventDefault(); dz.classList.remove('dragover');
                    const file = e.dataTransfer.files[0];
                    if (file) scriptProcessFile(file);
                });
            }
        }

        function assetRenderCategories() {
            const list = document.getElementById('assetCatList');
            if (!list || !assetState.categories) return;
            list.innerHTML = '';
            // "All" option
            const allItem = document.createElement('div');
            allItem.className = 'asset-cat-item' + (!assetState.currentCategory ? ' active' : '');
            allItem.innerHTML = '<span class="cat-icon">&#9634;</span> All Assets<span class="cat-count" id="catCountAll">0</span>';
            allItem.onclick = () => { assetState.currentCategory = null; assetRenderCategories(); assetLoadGrid(); };
            list.appendChild(allItem);
            Object.entries(assetState.categories).forEach(([key, cat]) => {
                const item = document.createElement('div');
                item.className = 'asset-cat-item' + (assetState.currentCategory === key ? ' active' : '');
                item.innerHTML = `<span class="cat-icon">${cat.icon}</span> ${cat.label}<span class="cat-count" id="catCount_${key}">0</span>`;
                item.onclick = () => { assetState.currentCategory = key; assetRenderCategories(); assetLoadGrid(); };
                list.appendChild(item);
            });
        }

        async function assetLoadStats() {
            try {
                const stats = await fetch('/api/assets/stats').then(r => r.json());
                if (stats.error) return;
                const el = document.getElementById('assetStats');
                if (el) el.innerHTML = `${stats.total_assets} assets &middot; ${stats.total_versions} versions &middot; ${stats.locked_assets} locked`;
                // Update category counts
                Object.entries(stats.by_category || {}).forEach(([cat, count]) => {
                    const c = document.getElementById('catCount_' + cat);
                    if (c) c.textContent = count;
                });
                const allCount = document.getElementById('catCountAll');
                if (allCount) allCount.textContent = stats.total_assets;
            } catch(e) {}
        }

        async function assetLoadGrid() {
            assetShowView('grid');
            const params = new URLSearchParams();
            if (assetState.currentCategory) params.set('category', assetState.currentCategory);
            if (assetState.searchQuery) params.set('search', assetState.searchQuery);
            try {
                const resp = await fetch('/api/assets?' + params.toString()).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                assetState.assets = resp.assets || [];
                assetRenderGrid();
            } catch(e) { showToast('Failed to load assets', 'error'); }
        }

        function assetRenderGrid() {
            const grid = document.getElementById('assetGrid');
            grid.innerHTML = '';
            if (assetState.assets.length === 0) {
                grid.innerHTML = '<div class="asset-empty"><h3>No assets found</h3><p>Create a new asset or drop a script to get started.</p></div>';
                return;
            }
            assetState.assets.forEach(a => {
                const card = document.createElement('div');
                card.className = 'asset-card' + (a.locked ? ' locked' : '');
                const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
                const imgSrc = v && v.image_refs && v.image_refs[0] ? v.image_refs[0] : '';
                card.innerHTML = `
                    ${imgSrc ? `<img src="${imgSrc}" loading="lazy" />` : `<div style="aspect-ratio:1;background:var(--surface2);border-radius:10px;margin-bottom:8px;display:flex;align-items:center;justify-content:center;font-size:2em;opacity:0.3;">${(assetState.categories[a.category]||{}).icon||'?'}</div>`}
                    <div class="asset-name">${a.name}</div>
                    <div class="asset-cat">${a.subtype || a.category}</div>
                    <div class="asset-ver">v${a.current_version} &middot; ${(a.versions||[]).length} versions</div>
                `;
                card.onclick = () => assetShowDetail(a.asset_id);
                grid.appendChild(card);
            });
        }

        async function assetShowDetail(assetId) {
            assetShowView('detail');
            try {
                const resp = await fetch('/api/assets/' + assetId).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                const a = resp.asset;
                assetState.selectedAsset = a;
                const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
                const imgSrc = v && v.image_refs && v.image_refs[0] ? v.image_refs[0] : '';
                const catInfo = assetState.categories[a.category] || {icon: '?', label: a.category};
                const container = document.getElementById('assetDetailContainer');
                container.innerHTML = `
                    <div class="asset-detail">
                        <div class="asset-detail-header">
                            ${imgSrc ? `<img class="asset-detail-img" src="${imgSrc}" />` : `<div class="asset-detail-img" style="display:flex;align-items:center;justify-content:center;font-size:3em;opacity:0.3;">${catInfo.icon}</div>`}
                            <div class="asset-detail-info">
                                <h2>${catInfo.icon} ${a.name}</h2>
                                <span class="asset-tag">${catInfo.label}</span>
                                ${a.subtype ? `<span class="asset-tag">${a.subtype}</span>` : ''}
                                ${a.locked ? '<span class="asset-tag" style="background:rgba(34,197,94,0.15);color:#22c55e;">Locked</span>' : ''}
                                ${(a.tags||[]).map(t => `<span class="asset-tag">${t}</span>`).join('')}
                                <div class="asset-desc">${a.description || 'No description'}</div>
                                <div class="asset-actions">
                                    <button class="asset-btn primary" onclick="assetSendToImageStudio('${a.asset_id}')">Send to Image Studio</button>
                                    <button class="asset-btn" onclick="assetSendToVideo('${a.asset_id}')">Send to Video</button>
                                    <button class="asset-btn" onclick="assetToggleLock('${a.asset_id}', ${!a.locked})">${a.locked ? 'Unlock' : 'Lock'} (Consistency)</button>
                                    <button class="asset-btn" onclick="assetAddVersionPrompt('${a.asset_id}')">+ New Version</button>
                                    <button class="asset-btn" onclick="assetBindSeriesPrompt('${a.asset_id}')">Bind to Series</button>
                                    <button class="asset-btn danger" onclick="assetDelete('${a.asset_id}')">Delete</button>
                                </div>
                            </div>
                        </div>
                        <div>
                            <h3 style="font-size:0.9em;margin-bottom:12px;">Version Archive (${(a.versions||[]).length})</h3>
                            <div class="asset-version-list" id="versionList"></div>
                        </div>
                    </div>
                `;
                assetRenderVersions(a);
            } catch(e) { showToast('Failed to load asset', 'error'); }
        }

        function assetRenderVersions(a) {
            const list = document.getElementById('versionList');
            if (!list) return;
            list.innerHTML = '';
            (a.versions || []).sort((x,y) => y.version - x.version).forEach(v => {
                const item = document.createElement('div');
                item.className = 'asset-version-item' + (v.version === a.current_version ? ' current' : '');
                const imgSrc = v.image_refs && v.image_refs[0] ? v.image_refs[0] : '';
                const date = new Date(v.timestamp * 1000).toLocaleDateString();
                item.innerHTML = `
                    ${imgSrc ? `<img src="${imgSrc}" />` : '<div style="width:48px;height:48px;border-radius:8px;background:var(--surface2);display:flex;align-items:center;justify-content:center;font-size:1.2em;opacity:0.3;">?</div>'}
                    <div class="ver-info">
                        <div class="ver-num">Version ${v.version}${v.version === a.current_version ? ' (Current)' : ''}</div>
                        <div class="ver-date">${date} ${v.notes ? '&middot; ' + v.notes : ''}</div>
                    </div>
                    <div class="ver-actions">
                        ${v.version !== a.current_version ? `<button onclick="assetRollback('${a.asset_id}', ${v.version})">Restore</button>` : ''}
                        <button onclick="assetCompareVersions('${a.asset_id}', ${v.version})">View</button>
                    </div>
                `;
                list.appendChild(item);
            });
        }

        function assetShowView(view) {
            document.getElementById('assetEmpty').style.display = view === 'empty' ? 'block' : 'none';
            document.getElementById('assetGridContainer').style.display = view === 'grid' ? 'block' : 'none';
            document.getElementById('assetDetailContainer').style.display = view === 'detail' ? 'block' : 'none';
            document.getElementById('assetScriptContainer').style.display = view === 'script' ? 'block' : 'none';
            document.getElementById('assetCreateContainer').style.display = view === 'create' ? 'block' : 'none';
        }

        function assetShowGrid() {
            assetLoadGrid();
        }

        function assetShowCreate() {
            assetShowView('create');
            const sel = document.getElementById('newAssetCategory');
            sel.innerHTML = '<option value="">Select category...</option>';
            if (assetState.categories) {
                Object.entries(assetState.categories).forEach(([key, cat]) => {
                    sel.innerHTML += `<option value="${key}">${cat.icon} ${cat.label}</option>`;
                });
            }
        }

        function newAssetCatChanged() {
            const cat = document.getElementById('newAssetCategory').value;
            const subSel = document.getElementById('newAssetSubtype');
            if (!cat || !assetState.categories || !assetState.categories[cat]) {
                subSel.style.display = 'none';
                return;
            }
            const subtypes = assetState.categories[cat].subtypes;
            subSel.style.display = 'block';
            subSel.innerHTML = '<option value="">Any subtype</option>' + subtypes.map(s => `<option value="${s}">${s}</option>`).join('');
        }

        async function assetCreateSubmit() {
            const name = document.getElementById('newAssetName').value.trim();
            const category = document.getElementById('newAssetCategory').value;
            const subtype = document.getElementById('newAssetSubtype').value;
            const desc = document.getElementById('newAssetDesc').value.trim();
            const tagsStr = document.getElementById('newAssetTags').value.trim();
            if (!name || !category) { showToast('Name and category required', 'error'); return; }
            const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];
            try {
                const resp = await fetch('/api/assets/create', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name, category, subtype, description: desc, tags })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast('Asset created', 'success');
                assetLoadStats();
                assetShowDetail(resp.asset.asset_id);
            } catch(e) { showToast('Create failed', 'error'); }
        }

        async function assetToggleLock(assetId, lock) {
            try {
                const resp = await fetch('/api/assets/' + assetId, {
                    method: 'PUT', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ locked: lock })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast(lock ? 'Asset locked for consistency' : 'Asset unlocked', 'success');
                assetShowDetail(assetId);
                assetLoadStats();
            } catch(e) { showToast('Failed', 'error'); }
        }

        async function assetDelete(assetId) {
            if (!confirm('Delete this asset and all versions?')) return;
            try {
                await fetch('/api/assets/' + assetId, { method: 'DELETE' });
                showToast('Asset deleted', 'success');
                assetLoadStats();
                assetLoadGrid();
            } catch(e) { showToast('Delete failed', 'error'); }
        }

        async function assetRollback(assetId, versionNum) {
            try {
                const resp = await fetch(`/api/assets/${assetId}/rollback/${versionNum}`, { method: 'POST' }).then(r => r.json());
                if (resp.status === 'rolled_back') {
                    showToast(`Restored to version ${versionNum}`, 'success');
                    assetShowDetail(assetId);
                } else { showToast('Rollback failed', 'error'); }
            } catch(e) { showToast('Rollback failed', 'error'); }
        }

        function assetCompareVersions(assetId, versionNum) {
            // Simple: just show the version image in a new tab
            const a = assetState.selectedAsset;
            if (!a) return;
            const v = (a.versions || []).find(v => v.version === versionNum);
            if (v && v.image_refs && v.image_refs[0]) window.open(v.image_refs[0], '_blank');
        }

        async function assetAddVersionPrompt(assetId) {
            const url = prompt('Enter image URL for new version:');
            if (!url) return;
            const notes = prompt('Version notes (optional):') || '';
            try {
                const resp = await fetch(`/api/assets/${assetId}/version`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ image_refs: [url], notes })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast('Version added', 'success');
                assetShowDetail(assetId);
                assetLoadStats();
            } catch(e) { showToast('Failed to add version', 'error'); }
        }

        async function assetBindSeriesPrompt(assetId) {
            const seriesId = prompt('Enter Series ID to bind this asset to:');
            if (!seriesId) return;
            try {
                const resp = await fetch(`/api/assets/${assetId}/bind`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ series_id: seriesId })
                }).then(r => r.json());
                if (resp.status === 'bound') {
                    showToast('Asset bound to series', 'success');
                    assetShowDetail(assetId);
                } else { showToast('Bind failed', 'error'); }
            } catch(e) { showToast('Bind failed', 'error'); }
        }

        function assetSendToImageStudio(assetId) {
            const a = assetState.selectedAsset;
            if (!a) return;
            const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
            if (v && v.image_refs && v.image_refs[0]) {
                switchTab('image');
                // Pre-fill the image prompt with the asset's prompt
                const ta = document.getElementById('imgPrompt');
                if (ta && v.prompt) ta.value = v.prompt;
                // If there are reference images, switch to I2I mode
                if (v.image_refs.length > 0) {
                    imgState.referenceImages = [...v.image_refs];
                    imgSwitchMode(true);
                    imgRenderRefPreview();
                }
                showToast(`Loaded "${a.name}" into Image Studio`, 'success');
            } else {
                showToast('No image in this asset', 'error');
            }
        }

        function assetSendToVideo(assetId) {
            const a = assetState.selectedAsset;
            if (!a) return;
            const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
            if (v && v.image_refs && v.image_refs[0]) {
                switchTab('maker');
                window._imgToVideoUrl = v.image_refs[0];
                const promptArea = document.getElementById('prompt');
                if (promptArea) {
                    const tag = `@${a.name.toLowerCase().replace(/\s+/g, '_')}`;
                    promptArea.value = `${tag}: ${v.description || a.description || ''}`;
                    promptArea.focus();
                }
                showToast(`Asset "${a.name}" sent to Video Maker as reference`, 'success');
            } else {
                showToast('No image in this asset', 'error');
            }
        }

        function assetSearchHandler() {
            assetState.searchQuery = document.getElementById('assetSearch').value.trim();
            assetLoadGrid();
        }

        function assetShowScriptDrop() {
            assetShowView('script');
        }

        function scriptBrowseClick() {
            document.getElementById('scriptFileInput').click();
        }

        function scriptFileSelected(event) {
            const file = event.target.files[0];
            if (file) scriptProcessFile(file);
        }

        async function scriptProcessFile(file) {
            const text = await file.text();
            const title = file.name.replace(/\.[^.]+$/, '');
            showToast('Parsing script...', 'success');
            try {
                const resp = await fetch('/api/script/parse', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ script_text: text, title })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                scriptRenderResults(resp, title);
            } catch(e) { showToast('Script parse failed', 'error'); }
        }

        function scriptRenderResults(result, title) {
            const container = document.getElementById('scriptResults');
            container.style.display = 'block';
            const m = result.metadata || {};
            const entityIcons = { character: '\\uD83C\\uDFAD', location: '\\uD83C\\uDFD8\\uFE0F', vehicle: '\\uD83D\\uDE97', object: '\\uD83D\\uDCE6', creature: '\\uD83E\\uDD81', building: '\\uD83C\\uDFDB\\uFE0F' };
            let html = `<h3 style="margin-bottom:8px;">\\uD83C\\uDFAC ${result.title || title}</h3>`;
            html += '<div class="script-stats">';
            html += `<div class="script-stat"><div class="stat-num">${m.total_scenes||0}</div><div class="stat-label">Scenes</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_characters||0}</div><div class="stat-label">Characters</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_locations||0}</div><div class="stat-label">Locations</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_vehicles||0}</div><div class="stat-label">Vehicles</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_objects||0}</div><div class="stat-label">Props</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_creatures||0}</div><div class="stat-label">Creatures</div></div>`;
            html += '</div>';
            html += '<div style="display:flex;gap:8px;margin-bottom:16px;">';
            html += '<button class="asset-btn primary" onclick="scriptCreateAllAssets()">Create All Assets</button>';
            html += '<button class="asset-btn" onclick="scriptSendAllToImageStudio()">Generate All Images</button>';
            html += '</div>';
            html += '<div class="script-results">';
            (result.entities || []).forEach((e, i) => {
                const icon = entityIcons[e.entity_type] || '\\u2753';
                html += `<div class="script-entity">
                    <div class="entity-icon">${icon}</div>
                    <div class="entity-info">
                        <div class="entity-name">${e.name} <span style="font-size:0.7em;color:var(--muted);">(${e.entity_type}${e.subtype ? '/' + e.subtype : ''})</span></div>
                        <div class="entity-prompt">${(e.suggested_prompt || '').substring(0, 120)}...</div>
                    </div>
                    <div class="entity-actions">
                        <button class="asset-btn" style="padding:6px 12px;font-size:0.75em;" onclick="scriptCreateOneAsset(${i})">Create Asset</button>
                        <button class="asset-btn" style="padding:6px 12px;font-size:0.75em;" onclick="scriptSendOneToImageStudio(${i})">Generate</button>
                    </div>
                </div>`;
            });
            html += '</div>';
            container.innerHTML = html;
            container._parsedData = result;
        }

        async function scriptCreateAllAssets() {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities) return;
            let created = 0;
            for (const e of data.entities) {
                try {
                    const resp = await fetch('/api/assets/create', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            name: e.name, category: e.entity_type === 'creature' ? 'character' : e.entity_type,
                            subtype: e.subtype || '', description: e.description || '',
                            tags: [e.entity_type], prompt: e.suggested_prompt,
                        })
                    }).then(r => r.json());
                    if (!resp.error) created++;
                } catch(e) {}
            }
            showToast(`${created} assets created from script`, 'success');
            assetLoadStats();
            assetLoadGrid();
        }

        function scriptSendAllToImageStudio() {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities) return;
            switchTab('image');
            // Load first entity prompt
            if (data.entities.length > 0) {
                document.getElementById('imgPrompt').value = data.entities[0].suggested_prompt;
                showToast(`Loaded first of ${data.entities.length} prompts. Generate each in Image Studio.`, 'success');
            }
        }

        function scriptCreateOneAsset(idx) {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities || !data.entities[idx]) return;
            const e = data.entities[idx];
            fetch('/api/assets/create', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: e.name, category: e.entity_type === 'creature' ? 'character' : e.entity_type,
                    subtype: e.subtype || '', description: e.description || '',
                    tags: [e.entity_type], prompt: e.suggested_prompt,
                })
            }).then(r => r.json()).then(resp => {
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast(`Asset "${e.name}" created`, 'success');
                assetLoadStats();
            });
        }

        function scriptSendOneToImageStudio(idx) {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities || !data.entities[idx]) return;
            const e = data.entities[idx];
            switchTab('image');
            document.getElementById('imgPrompt').value = e.suggested_prompt;
            showToast(`Loaded prompt for "${e.name}"`, 'success');
        }

        init();
    </script>
</body>
</html>'''


# ==================== SOULILLUSIONS PRIME API ====================
import subprocess as _subproc

@app.get("/api/prime/status")
async def prime_status():
    try:
        result = _subproc.run(["prime-agent", "status"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            import json as _json
            data = _json.loads(result.stdout.strip()) if result.stdout.strip().startswith("{") else {}
            return {"status": "online", "model": data.get("model", "unknown"), "sessions": data.get("sessions", 0), "skills": data.get("skills", 0), "memories": data.get("memories", 0)}
        return {"status": "offline", "error": "Prime Agent not installed or not running"}
    except FileNotFoundError:
        return {"status": "offline", "error": "Prime Agent CLI not found"}
    except Exception as e:
        return {"status": "offline", "error": str(e)}

@app.post("/api/prime/prompt")
async def prime_prompt(request: Request):
    try:
        body = await request.json()
        prompt = body.get("prompt", "")
        if not prompt:
            return JSONResponse({"error": "No prompt provided"}, status_code=400)
        result = _subproc.run(["prime-agent", "-p", prompt], capture_output=True, text=True, timeout=120)
        response = result.stdout.strip() or result.stderr.strip() or "No output"
        return {"response": response, "returncode": result.returncode}
    except FileNotFoundError:
        return JSONResponse({"error": "Prime Agent CLI not found. Install it on your VPS."}, status_code=503)
    except _subproc.TimeoutExpired:
        return JSONResponse({"error": "Prime Agent timed out (120s)"}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/prime/goal")
async def prime_set_goal(request: Request):
    try:
        body = await request.json()
        goal = body.get("goal", "")
        if not goal:
            return JSONResponse({"error": "No goal provided"}, status_code=400)
        result = _subproc.run(["prime-agent", "goal", goal], capture_output=True, text=True, timeout=30)
        return {"status": "ok", "goal": goal, "output": result.stdout.strip()}
    except FileNotFoundError:
        return JSONResponse({"error": "Prime Agent CLI not found"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/prime/autonomous")
async def prime_toggle_autonomous(request: Request):
    try:
        body = await request.json()
        enabled = body.get("enabled", False)
        cmd = ["prime-agent", "autonomous", "--on"] if enabled else ["prime-agent", "autonomous", "--off"]
        result = _subproc.run(cmd, capture_output=True, text=True, timeout=30)
        return {"status": "ok", "enabled": enabled, "output": result.stdout.strip()}
    except FileNotFoundError:
        return JSONResponse({"error": "Prime Agent CLI not found"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/prime/skills")
async def prime_get_skills():
    try:
        result = _subproc.run(["prime-agent", "skills", "list"], capture_output=True, text=True, timeout=30)
        import json as _json
        if result.stdout.strip().startswith("["):
            skills = _json.loads(result.stdout.strip())
            return {"skills": skills}
        return {"skills": [], "raw": result.stdout.strip()}
    except FileNotFoundError:
        return JSONResponse({"error": "Prime Agent CLI not found"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/prime/memories")
async def prime_get_memories():
    try:
        result = _subproc.run(["prime-agent", "memories", "list"], capture_output=True, text=True, timeout=30)
        import json as _json
        if result.stdout.strip().startswith("["):
            memories = _json.loads(result.stdout.strip())
            return {"memories": memories}
        return {"memories": [], "raw": result.stdout.strip()}
    except FileNotFoundError:
        return JSONResponse({"error": "Prime Agent CLI not found"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/prime/sessions")
async def prime_get_sessions():
    try:
        result = _subproc.run(["prime-agent", "agents"], capture_output=True, text=True, timeout=30)
        import json as _json
        if result.stdout.strip().startswith("["):
            sessions = _json.loads(result.stdout.strip())
            return {"sessions": sessions}
        return {"sessions": [], "raw": result.stdout.strip()}
    except FileNotFoundError:
        return JSONResponse({"error": "Prime Agent CLI not found"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== TERMINAL API ====================
@app.get("/api/terminal/status")
async def terminal_status():
    gpu_account = "None"
    gpu_hours = "--"
    environment = "local"
    terminal_token = None
    try:
        accounts_path = APP_DIR / "kaggle_accounts.json"
        if accounts_path.exists():
            acc_data = json.loads(accounts_path.read_text())
            active_idx = acc_data.get("active_account", 0)
            accounts = acc_data.get("accounts", [])
            if active_idx < len(accounts):
                acc = accounts[active_idx]
                gpu_account = acc.get("username", "unknown")
                hours_used = acc.get("hours_used", 0)
                gpu_hours = f"{max(0, 29 - hours_used):.1f}h"
            environment = "kaggle"
    except Exception:
        pass
    backend_url = config.get("gpu_backend_url", "")
    if backend_url:
        try:
            req = urllib.request.Request(f"{backend_url}/api/status", headers={"User-Agent": "SoulIllusions/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                bdata = json.loads(resp.read().decode())
                terminal_token = bdata.get("terminal_token")
                environment = bdata.get("gpu", "kaggle")
        except Exception:
            pass
    return {"gpu_account": gpu_account, "gpu_hours": gpu_hours, "environment": environment, "terminal_token": terminal_token}

@app.post("/api/terminal/exec")
async def terminal_exec(request: Request):
    try:
        body = await request.json()
        command = body.get("command", "")
        if not command:
            return JSONResponse({"error": "No command provided"}, status_code=400)
        backend_url = config.get("gpu_backend_url", "")
        if not backend_url:
            return JSONResponse({"error": "No GPU backend connected"}, status_code=400)
        token = body.get("token", "")
        if not token:
            try:
                req = urllib.request.Request(f"{backend_url}/api/status", headers={"User-Agent": "SoulIllusions/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    bdata = json.loads(resp.read().decode())
                    token = bdata.get("terminal_token", "")
            except Exception:
                pass
        payload = json.dumps({"token": token, "command": command}).encode()
        req = urllib.request.Request(f"{backend_url}/api/terminal/exec", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=65) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/terminal/push")
async def terminal_push(request: Request):
    try:
        body = await request.json()
        filename = body.get("filename", "")
        content = body.get("content", "")
        if not filename or not content:
            return JSONResponse({"error": "filename and content required"}, status_code=400)
        backend_url = config.get("gpu_backend_url", "")
        if not backend_url:
            return JSONResponse({"error": "No GPU backend connected"}, status_code=400)
        cmd = f"cat > {filename} << 'SOULILLUSIONS_EOF'\n{content}\nSOULILLUSIONS_EOF"
        token = body.get("token", "")
        if not token:
            try:
                req = urllib.request.Request(f"{backend_url}/api/status", headers={"User-Agent": "SoulIllusions/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    bdata = json.loads(resp.read().decode())
                    token = bdata.get("terminal_token", "")
            except Exception:
                pass
        payload = json.dumps({"token": token, "command": cmd}).encode()
        req = urllib.request.Request(f"{backend_url}/api/terminal/exec", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=65) as resp:
            result = json.loads(resp.read().decode())
            return {"status": "ok", "filename": filename, "result": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/terminal/update")
async def terminal_update():
    try:
        result = _subproc.run(["git", "pull"], capture_output=True, text=True, timeout=60, cwd=str(APP_DIR))
        return {"status": "ok", "stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "returncode": result.returncode}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/terminal/switch-gpu")
async def terminal_switch_gpu():
    try:
        accounts_path = APP_DIR / "kaggle_accounts.json"
        if not accounts_path.exists():
            return JSONResponse({"error": "No kaggle_accounts.json found"}, status_code=400)
        acc_data = json.loads(accounts_path.read_text())
        active_idx = acc_data.get("active_account", 0)
        accounts = acc_data.get("accounts", [])
        next_idx = (active_idx + 1) % len(accounts)
        acc_data["active_account"] = next_idx
        accounts_path.write_text(json.dumps(acc_data, indent=2))
        auto_script = APP_DIR / "kaggle_auto.py"
        if auto_script.exists():
            result = _subproc.run([sys.executable, str(auto_script), "--start"], capture_output=True, text=True, timeout=600)
            return {"status": "ok", "account": next_idx + 1, "output": result.stdout[-500:]}
        return JSONResponse({"error": "kaggle_auto.py not found"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== SOULILLUSIONS AGENT API ====================
import importlib as _importlib

def _get_agent_module():
    try:
        return _importlib.import_module("soulillusions_agent")
    except Exception as e:
        return None

@app.get("/api/agent/status")
async def agent_status():
    mod = _get_agent_module()
    if not mod:
        return {"running": False, "mode": "local", "model": "qwen2.5:7b", "always_on": True,
                "session": None, "projects": {"active": 0, "completed": 0}, "memories": 0,
                "sub_agents": {}, "error": "soulillusions_agent.py not available"}
    try:
        agent = mod.get_agent()
        return agent.get_status()
    except Exception as e:
        return {"running": False, "error": str(e)}

@app.post("/api/agent/start")
async def agent_start():
    mod = _get_agent_module()
    if not mod:
        return JSONResponse({"error": "soulillusions_agent.py not available"}, status_code=503)
    try:
        agent = mod.get_agent()
        return agent.start()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/agent/stop")
async def agent_stop():
    mod = _get_agent_module()
    if not mod:
        return JSONResponse({"error": "soulillusions_agent.py not available"}, status_code=503)
    try:
        agent = mod.get_agent()
        return agent.stop()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/agent/prompt")
async def agent_prompt(request: Request):
    mod = _get_agent_module()
    if not mod:
        return JSONResponse({"error": "soulillusions_agent.py not available"}, status_code=503)
    try:
        body = await request.json()
        prompt = body.get("prompt", "")
        if not prompt:
            return JSONResponse({"error": "No prompt provided"}, status_code=400)
        agent = mod.get_agent()
        return agent.send_prompt(prompt)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/agent/goal")
async def agent_goal(request: Request):
    mod = _get_agent_module()
    if not mod:
        return JSONResponse({"error": "soulillusions_agent.py not available"}, status_code=503)
    try:
        body = await request.json()
        goal = body.get("goal", "")
        if not goal:
            return JSONResponse({"error": "No goal provided"}, status_code=400)
        agent = mod.get_agent()
        return agent.set_goal(goal)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/agent/actions")
async def agent_actions(limit: int = 50):
    mod = _get_agent_module()
    if not mod:
        return {"actions": []}
    try:
        agent = mod.get_agent()
        return agent.get_actions(limit)
    except Exception as e:
        return {"actions": [], "error": str(e)}

@app.get("/api/agent/projects")
async def agent_projects():
    mod = _get_agent_module()
    if not mod:
        return {"projects": []}
    try:
        agent = mod.get_agent()
        return agent.get_projects()
    except Exception as e:
        return {"projects": [], "error": str(e)}

@app.get("/api/agent/memories")
async def agent_memories():
    mod = _get_agent_module()
    if not mod:
        return {"memories": []}
    try:
        agent = mod.get_agent()
        return agent.get_memories()
    except Exception as e:
        return {"memories": [], "error": str(e)}


# ==================== TEXT-TO-GAMES API ====================
def _get_games_module():
    try:
        return _importlib.import_module("text_to_games")
    except Exception:
        return None

@app.post("/api/games/create")
async def games_create(request: Request):
    mod = _get_games_module()
    if not mod:
        return JSONResponse({"error": "text_to_games.py not available"}, status_code=503)
    try:
        body = await request.json()
        prompt = body.get("prompt", "")
        genre = body.get("genre", "")
        title = body.get("title", "")
        use_ai = body.get("use_ai", True)
        if not prompt:
            return JSONResponse({"error": "No prompt provided"}, status_code=400)
        mgr = mod.get_game_manager()
        result = mgr.create_game(prompt, genre, title, use_ai=use_ai, created_by="user")
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/games/list")
async def games_list(limit: int = 50, genre: str = ""):
    mod = _get_games_module()
    if not mod:
        return {"games": []}
    try:
        mgr = mod.get_game_manager()
        games = mgr.list_games(limit, genre if genre else "")
        return {"games": games}
    except Exception as e:
        return {"games": [], "error": str(e)}

@app.get("/api/games/play/{game_id}")
async def games_play(game_id: int):
    mod = _get_games_module()
    if not mod:
        return JSONResponse({"error": "text_to_games.py not available"}, status_code=503)
    try:
        mgr = mod.get_game_manager()
        game = mgr.get_game(game_id)
        if not game:
            return JSONResponse({"error": "Game not found"}, status_code=404)
        html = mgr.get_game_html(game_id)
        if not html:
            return JSONResponse({"error": "Game HTML not found"}, status_code=404)
        mgr.play_game(game_id)  # increment play count
        return {"html": html, "title": game["title"], "genre": game["genre"]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/games/rate/{game_id}")
async def games_rate(game_id: int, request: Request):
    mod = _get_games_module()
    if not mod:
        return JSONResponse({"error": "text_to_games.py not available"}, status_code=503)
    try:
        body = await request.json()
        rating = body.get("rating", 3)
        mgr = mod.get_game_manager()
        return mgr.rate_game(game_id, rating)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/api/games/delete/{game_id}")
async def games_delete(game_id: int):
    mod = _get_games_module()
    if not mod:
        return JSONResponse({"error": "text_to_games.py not available"}, status_code=503)
    try:
        mgr = mod.get_game_manager()
        return mgr.delete_game(game_id)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/games/genres")
async def games_genres():
    mod = _get_games_module()
    if not mod:
        return {"genres": ["platformer", "shooter", "puzzle", "racing", "arcade"]}
    try:
        mgr = mod.get_game_manager()
        return {"genres": mgr.get_genres()}
    except Exception as e:
        return {"genres": [], "error": str(e)}


# ==================== PHONE VERIFICATION API ====================
def _get_verify_module():
    try:
        return _importlib.import_module("sms_verify")
    except Exception:
        return None

@app.get("/api/verify/status")
async def verify_status():
    mod = _get_verify_module()
    if not mod:
        return {"total_numbers": 0, "available": 0, "in_use": 0,
                "verifications_completed": 0, "verifications_pending": 0,
                "error": "sms_verify.py not available"}
    try:
        return mod.get_pool_status()
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/verify/refresh")
async def verify_refresh():
    mod = _get_verify_module()
    if not mod:
        return JSONResponse({"error": "sms_verify.py not available"}, status_code=503)
    try:
        count = mod.refresh_number_pool()
        return {"added": count, "status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/verify/start")
async def verify_start(request: Request):
    mod = _get_verify_module()
    if not mod:
        return JSONResponse({"error": "sms_verify.py not available"}, status_code=503)
    try:
        body = await request.json()
        service = body.get("service", "generic")
        country = body.get("country", "us")
        return mod.start_verification(service, country)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/verify/check/{verify_id}")
async def verify_check(verify_id: int):
    mod = _get_verify_module()
    if not mod:
        return JSONResponse({"error": "sms_verify.py not available"}, status_code=503)
    try:
        return mod.check_verification(verify_id)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/verify/numbers")
async def verify_numbers():
    mod = _get_verify_module()
    if not mod:
        return {"numbers": []}
    try:
        conn = sqlite3.connect(str(mod.VERIFY_DB))
        c = conn.cursor()
        c.execute("SELECT number, country, provider, status, times_used FROM phone_numbers ORDER BY status, times_used ASC LIMIT 50")
        rows = c.fetchall()
        conn.close()
        return {"numbers": [{"number": r[0], "country": r[1], "provider": r[2], "status": r[3], "times_used": r[4]} for r in rows]}
    except Exception as e:
        return {"numbers": [], "error": str(e)}

@app.post("/api/verify/kaggle-all")
async def verify_kaggle_all():
    mod = _get_verify_module()
    if not mod:
        return JSONResponse({"error": "sms_verify.py not available"}, status_code=503)
    try:
        results = mod.verify_all_kaggle_accounts()
        return {"results": results}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# === Main ===
def open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{config.get('port', 7860)}")

if __name__ == "__main__":
    port = config.get("port", 7860)
    
    if config.get("auto_open_browser", True):
        threading.Thread(target=open_browser, daemon=True).start()
    
    print(f"\n  SoulIllusions AI Video Maker")
    print(f"  Running on http://localhost:{port}")
    print(f"  100% Free - Open Source - No API Keys Needed")
    if PRODUCTION_AVAILABLE:
        print(f"  Production Suite: ENABLED (Series/Episode/Scene management)")
        try:
            from narrative_memory import MemoryStore
            print(f"  Narrative Memory Engine: ENABLED (Persistent memory, Narrative Stack, Recursive Learning)")
        except:
            print(f"  Narrative Memory Engine: DISABLED (narrative_memory.py not found)")
    if ACTION_LOGGING:
        print(f"  Action Logger: ENABLED (Telemetry, upgrade notes at logs/upgrade_notes.md)")
    if ai_controller:
        tool_count = len(ai_controller._tools)
        print(f"  AI Controller: ENABLED ({tool_count} tools, /api/ai/execute)")
    print()
    
    uvicorn.run(app, host="127.0.0.1", port=port)

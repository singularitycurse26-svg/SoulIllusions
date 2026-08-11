"""
SoulIllusions Mock GPU Backend - Tests the full video generation pipeline locally.
Generates real test videos using ffmpeg (no GPU needed).
Run this, then set backend URL to http://localhost:9000 in SoulIllusions.
"""
import uvicorn
import threading
import time
import uuid
import os
import json
import math
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

app = FastAPI(title="SoulIllusions Mock GPU Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

generation_status = {}
image_status = {}

class GenRequest(BaseModel):
    prompt: str
    model: str = "ltx"
    style: str = "cinematic"
    num_frames: int = 97
    fps: int = 24
    steps: int = 30
    seed: Optional[int] = None
    enhance: bool = True
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    guidance_scale: float = 5.0
    upscale: int = 1
    interpolate_fps: int = 0
    audio: bool = False

class ImageGenRequest(BaseModel):
    prompt: str = ""
    model: str = "sdxl"
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

def make_test_video(prompt, width=768, height=512, fps=24, num_frames=24, output_path=None):
    """Generate a real test video using imageio + numpy - no ffmpeg needed."""
    import numpy as np
    import imageio
    
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4().hex[:8]}.mp4")
    
    frames = []
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Animated gradient background
        for y in range(height):
            for x in range(0, width, 4):
                t = (i / num_frames) * 2 * math.pi
                r = int(128 + 100 * math.sin(t + x * 0.01))
                g = int(50 + 80 * math.sin(t + y * 0.01 + 2))
                b = int(100 + 100 * math.sin(t + (x + y) * 0.005 + 4))
                frame[y, x:x+4] = [max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))]
        # Add a white rectangle in center as "text area"
        cx, cy = width // 2, height // 2
        frame[cy-30:cy+30, cx-150:cx+150] = [255, 255, 255]
        # Dark overlay on the rectangle
        frame[cy-28:cy+28, cx-148:cx+148] = [26, 26, 46]
        frames.append(frame)
    
    imageio.mimsave(output_path, frames, fps=fps, codec='libx264')
    return output_path

def make_test_image(prompt, width=832, height=1216):
    """Generate a real test image using PIL - no ffmpeg needed."""
    from PIL import Image, ImageDraw, ImageFont
    
    output_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4().hex[:8]}.png")
    
    img = Image.new('RGB', (width, height), color=(26, 26, 46))
    draw = ImageDraw.Draw(img)
    
    # Draw gradient bars
    for y in range(height):
        r = int(20 + 60 * math.sin(y * 0.005))
        g = int(15 + 40 * math.sin(y * 0.003 + 1))
        b = int(40 + 80 * math.sin(y * 0.004 + 2))
        draw.line([(0, y), (width, y)], fill=(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))
    
    # Draw prompt text in center
    safe_prompt = prompt[:60]
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    
    # Draw text box
    bbox = draw.textbbox((0, 0), safe_prompt, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (width - tw) // 2
    ty = (height - th) // 2
    draw.rectangle([tx-15, ty-15, tx+tw+15, ty+th+15], fill=(0, 0, 0, 200))
    draw.text((tx, ty), safe_prompt, fill=(255, 255, 255), font=font)
    
    img.save(output_path)
    return output_path

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SoulIllusions Mock GPU Backend (TEST MODE)",
        "gpu": "Mock (ffmpeg test pattern)",
        "version": "test-1.0",
    }

@app.get("/api/status")
async def status():
    return {
        "status": "online",
        "gpu": "Mock GPU (ffmpeg test pattern generator)",
        "vram_total": "N/A (mock)",
        "vram_free": "N/A (mock)",
        "models": ["ltx-video"],
        "features": ["prompt-enhancement", "image-generation", "video-generation"],
        "queue": len([k for k, v in generation_status.items() if v["status"] == "processing"]),
    }

@app.get("/api/models")
async def models():
    return {"models": [{"id": "ltx", "name": "LTX-Video (Mock)", "desc": "Test mode", "resolution": "768x512", "fps": 24}]}

@app.get("/api/styles")
async def styles():
    return {"styles": ["cinematic", "realistic", "anime"]}

@app.get("/api/settings/defaults")
async def defaults():
    return {
        "aspect_ratios": {"16:9": {"width": 1280, "height": 720}, "9:16": {"width": 720, "height": 1280}, "1:1": {"width": 1024, "height": 1024}},
        "quality_modes": {"draft": {"steps": 10, "guidance": 3.0}, "standard": {"steps": 30, "guidance": 5.0}},
        "styles": ["cinematic", "realistic", "anime"],
    }

@app.post("/api/generate")
async def generate(req: GenRequest, bg: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    generation_status[job_id] = {"status": "processing", "progress": 0, "prompt": req.prompt, "model": req.model, "output": None}
    
    w = req.width or 768
    h = req.height or 512
    
    def run():
        try:
            print(f"[MOCK] Generating test video: {req.prompt[:50]}...")
            time.sleep(2)  # Simulate processing delay
            output_path = make_test_video(req.prompt, width=w, height=h, fps=req.fps, num_frames=req.num_frames)
            generation_status[job_id] = {"status": "complete", "progress": 1.0, "prompt": req.prompt, "output": output_path}
            print(f"[MOCK] Video ready: {output_path}")
        except Exception as e:
            generation_status[job_id] = {"status": "failed", "prompt": req.prompt, "output": None, "error": str(e)}
            print(f"[MOCK] Failed: {e}")
    
    bg.add_task(run)
    return {"job_id": job_id, "status": "processing", "model": req.model}

@app.get("/api/status/{job_id}")
async def job_status(job_id: str):
    if job_id not in generation_status:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return generation_status[job_id]

@app.get("/api/download/{job_id}")
async def download(job_id: str):
    j = generation_status.get(job_id)
    if not j or j["status"] != "complete" or not j["output"]:
        return JSONResponse({"error": "Not ready"}, status_code=400)
    return FileResponse(j["output"], media_type="video/mp4", filename=f"test_{job_id}.mp4")

# Image endpoints
@app.get("/api/image/options")
async def img_opts():
    return {
        "models": [{"id": "sdxl", "name": "SDXL (Mock)", "desc": "Test mode"}],
        "style_presets": ["None", "cinematic", "poster", "sci-fi"],
        "aspect_ratios": {"1:1": {"width": 1024, "height": 1024}, "2:3": {"width": 832, "height": 1216}, "16:9": {"width": 1344, "height": 768}},
        "quality_modes": {"standard": {"steps": 25, "guidance": 7.5}},
    }

@app.post("/api/image/generate")
async def gen_img(req: ImageGenRequest, bg: BackgroundTasks):
    jid = uuid.uuid4().hex[:12]
    image_status[jid] = {"status": "processing", "progress": 0, "prompt": req.prompt, "images": []}
    am = {"1:1": (1024, 1024), "2:3": (832, 1216), "16:9": (1344, 768), "9:16": (768, 1344)}
    w, h = am.get(req.aspect_ratio, (1024, 1024))
    if req.width: w = req.width
    if req.height: h = req.height
    
    def run():
        try:
            print(f"[MOCK] Generating test image: {req.prompt[:50]}...")
            time.sleep(1)
            path = make_test_image(req.prompt, width=w, height=h)
            image_status[jid] = {"status": "complete", "progress": 1.0, "prompt": req.prompt, "images": [path]}
            print(f"[MOCK] Image ready: {path}")
        except Exception as e:
            image_status[jid] = {"status": "failed", "progress": 0, "error": str(e), "images": []}
    
    bg.add_task(run)
    return {"job_id": jid, "status": "processing"}

@app.get("/api/image/status/{job_id}")
async def img_stat(job_id: str):
    return image_status.get(job_id, JSONResponse({"error": "Not found"}, status_code=404))

@app.get("/api/image/download/{job_id}")
async def img_dl(job_id: str):
    j = image_status.get(job_id)
    if not j or j["status"] != "complete" or not j["images"]:
        return JSONResponse({"error": "Not ready"}, status_code=400)
    return FileResponse(j["images"][0], media_type="image/png")

if __name__ == "__main__":
    print("=" * 60)
    print("  SoulIllusions MOCK GPU Backend - TEST MODE")
    print("  Generates real test videos/images using ffmpeg")
    print("  No GPU needed - just tests the pipeline")
    print("=" * 60)
    print("\n  Starting on http://localhost:9000")
    print("  Set this URL in SoulIllusions as the GPU backend\n")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")

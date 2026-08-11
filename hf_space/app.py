"""
SoulIllusions GPU Backend - Hugging Face Spaces Edition
Uses ZeroGPU (A100 80GB) with @spaces.GPU decorator.

API Endpoints (Gradio Blocks API):
- /api/status → backend status
- /api/generate_image → synchronous SDXL image generation
- /api/generate_video → synchronous LTX-Video generation

All generation is synchronous (blocks until done) because ZeroGPU
allocates GPU per-call and releases after.
"""
import os
import time
import uuid
import gc
import tempfile
import json
import torch
import numpy as np
import gradio as gr
import spaces

# === Paths ===
OUTPUT_DIR = tempfile.mkdtemp()
IMG_DIR = os.path.join(OUTPUT_DIR, 'images')
VID_DIR = os.path.join(OUTPUT_DIR, 'videos')
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(VID_DIR, exist_ok=True)

# === Model Cache ===
_pipes = {}

# === Prompt Enhancement ===
STYLE_MODIFIERS = {
    'cinematic': {
        'camera': 'cinematic camera, slow dolly push-in, shallow depth of field',
        'lighting': 'dramatic lighting, golden hour, high contrast, film still',
        'quality': 'movie quality, 4k, highly detailed, professional cinematography',
        'negative': 'static shot, flat lighting, low contrast, amateur, blurry',
    },
    'realistic': {
        'camera': 'handheld camera, natural movement, documentary style',
        'lighting': 'natural lighting, soft ambient light, realistic shadows',
        'quality': 'photorealistic, ultra realistic, 8k, professional photo',
        'negative': 'cartoon, anime, stylized, artificial lighting, oversaturated',
    },
    'anime': {
        'camera': 'dynamic anime camera, expressive angles, smooth panning',
        'lighting': 'vibrant lighting, cel shaded, studio quality lighting',
        'quality': 'anime style, cel shaded, vibrant colors, detailed background, studio quality',
        'negative': 'realistic, photorealistic, dark, muted colors, 3d render',
    },
    'poster': {
        'camera': 'dramatic composition, hero shot, centered framing',
        'lighting': 'dramatic lighting, rim light, high contrast, poster quality',
        'quality': 'movie poster quality, ultra detailed, professional, striking visual',
        'negative': 'amateur, low quality, blurry, flat lighting, boring composition',
    },
}

NEGATIVE_PROMPT = (
    "worst quality, inconsistent motion, blurry, jittery, distorted, "
    "low resolution, artifacts, static, overexposed, identity drift, "
    "deformation, flickering, ghosting, smearing, duplication, "
    "mutated proportions, inconsistent clothing, flat colors, desaturated"
)

def enhance_prompt(prompt, style='cinematic'):
    mod = STYLE_MODIFIERS.get(style, STYLE_MODIFIERS['cinematic'])
    enhanced = (
        f"{prompt}. "
        f"{mod['camera']}. "
        f"{mod['lighting']}. "
        f"{mod['quality']}. "
        f"Smooth temporal motion, consistent identity throughout. "
        f"Professional grade output."
    )
    negative = f"{NEGATIVE_PROMPT}, {mod['negative']}"
    return enhanced, negative

# === SDXL Image Generation ===
def _load_sdxl():
    if 'sdxl' not in _pipes:
        from diffusers import StableDiffusionXLPipeline
        print("[Loading SDXL...]")
        _pipes['sdxl'] = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            cache_dir="/tmp/model_cache",
        )
        _pipes['sdxl'].watermark = None
    return _pipes['sdxl']

def _unload_sdxl():
    if 'sdxl' in _pipes:
        del _pipes['sdxl']
        gc.collect()
        torch.cuda.empty_cache()

# === LTX Video Generation ===
def _load_ltx():
    if 'ltx' not in _pipes:
        from diffusers import LTXPipeline
        print("[Loading LTX-Video...]")
        _pipes['ltx'] = LTXPipeline.from_pretrained(
            "Lightricks/LTX-Video",
            torch_dtype=torch.bfloat16,
            cache_dir="/tmp/model_cache",
        )
        _pipes['ltx'].vae.enable_tiling()
    return _pipes['ltx']

def _unload_ltx():
    if 'ltx' in _pipes:
        del _pipes['ltx']
        gc.collect()
        torch.cuda.empty_cache()

# === GPU Functions ===
@spaces.GPU(duration=120)
def generate_image_gpu(prompt, negative_prompt, width, height, steps, seed, guidance_scale, batch_count, style_preset):
    pipe = _load_sdxl()
    pipe.to('cuda')
    
    if seed is not None:
        generator = torch.Generator('cuda').manual_seed(seed)
    else:
        generator = None
    
    images = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        generator=generator,
        num_images_per_prompt=batch_count,
    ).images
    
    paths = []
    for i, img in enumerate(images):
        path = os.path.join(IMG_DIR, f"img_{uuid.uuid4().hex[:8]}.png")
        img.save(path)
        paths.append(path)
    
    pipe.to('cpu')
    return paths

@spaces.GPU(duration=300)
def generate_video_gpu(prompt, negative_prompt, num_frames, fps, width, height,
                       steps, seed, guidance_scale, guidance_rescale,
                       solver, flow_shift, use_karras, use_dynamic_shifting,
                       decode_timestep, decode_noise_scale, image_cond_noise_scale,
                       num_videos_per_prompt, output_type, camera_enabled,
                       camera_motion, camera_direction, camera_speed,
                       camera_intensity, upscale, interpolate_fps,
                       color_grading, effects, codec, crf, preset,
                       tune, bitrate, maxrate, bufsize, profile, pixel_format, audio):
    pipe = _load_ltx()
    pipe.to('cuda')
    
    if seed is None:
        seed = int(time.time())
    
    generator = torch.Generator('cuda').manual_seed(seed)
    
    from diffusers import LTXVideoScheduler
    scheduler = LTXVideoScheduler.from_config(pipe.scheduler.config)
    
    pipe.scheduler = scheduler
    
    video_generator = torch.Generator('cuda').manual_seed(seed)
    
    kwargs = dict(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        guidance_rescale=guidance_rescale,
        generator=video_generator,
        num_videos_per_prompt=num_videos_per_prompt,
        output_type=output_type,
        decode_timestep=decode_timestep,
        decode_noise_scale=decode_noise_scale,
        image_cond_noise_scale=image_cond_noise_scale,
    )
    
    result = pipe(**kwargs)
    frames = result.frames
    
    if isinstance(frames, list):
        frames = frames[0]
    
    import imageio
    output_path = os.path.join(VID_DIR, f"vid_{uuid.uuid4().hex[:8]}.mp4")
    
    if output_type == 'pil':
        frames_np = [np.array(f) for f in frames]
        imageio.mimsave(output_path, frames_np, fps=fps, codec='libx264',
                        quality=8, macro_block_size=1)
    else:
        imageio.mimsave(output_path, frames, fps=fps, codec='libx264',
                        quality=8, macro_block_size=1)
    
    pipe.to('cpu')
    return output_path

# === API Functions ===
def api_status():
    return {
        "status": "online",
        "gpu": "ZeroGPU (A100 80GB)",
        "vram_total": "80 GB",
        "vram_free": "80 GB",
        "models": ["sdxl", "ltx-video"],
        "features": ["prompt-enhancement", "image-generation", "video-generation"],
        "queue": 0,
    }

def api_generate_image(prompt, negative_prompt="", aspect_ratio="1:1",
                       quality="standard", seed=None, batch_count=1,
                       style_preset="cinematic", width=None, height=None,
                       guidance_scale=7.5, steps=None):
    am = {'1:1': (1024, 1024), '16:9': (1344, 768), '9:16': (768, 1344),
          '4:3': (1152, 896), '3:4': (896, 1152), '2:3': (832, 1216),
          '3:2': (1216, 832)}
    w, h = am.get(aspect_ratio, (1024, 1024))
    if width:
        w = width
    if height:
        h = height
    qs = {'draft': 10, 'standard': 25, 'pro': 40, 'ultra': 60}
    actual_steps = qs.get(quality, steps or 25)
    
    enhanced, neg = enhance_prompt(prompt, style_preset)
    if negative_prompt:
        neg = f"{neg}, {negative_prompt}"
    
    try:
        paths = generate_image_gpu(
            prompt=enhanced, negative_prompt=neg,
            width=w, height=h, steps=actual_steps, seed=seed,
            guidance_scale=guidance_scale, batch_count=batch_count,
            style_preset=style_preset)
        return {"status": "complete", "images": paths, "image": paths[0] if paths else None}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

def api_generate_video(prompt, model="ltx", style="cinematic",
                       num_frames=97, fps=24, steps=30, seed=None,
                       enhance=True, negative_prompt=None,
                       width=768, height=512,
                       guidance_scale=3.0, guidance_rescale=0.0,
                       solver="unipc", flow_shift=5.0,
                       use_karras_sigmas=False, use_dynamic_shifting=False,
                       decode_timestep=0.05, decode_noise_scale=0.025,
                       image_cond_noise_scale=0.0,
                       num_videos_per_prompt=1, output_type="pil",
                       camera_enabled=False, camera_motion="static",
                       camera_direction=None, camera_speed=0.5,
                       camera_intensity=0.5, upscale=1, interpolate_fps=0,
                       color_grading=None, effects=None,
                       codec="h264", crf=23, preset="medium",
                       tune=None, bitrate=None, maxrate=None,
                       bufsize=None, profile=None, pixel_format=None,
                       audio=False):
    if enhance:
        enhanced, neg = enhance_prompt(prompt, style)
    else:
        enhanced = prompt
        neg = negative_prompt or NEGATIVE_PROMPT
    
    if negative_prompt:
        neg = f"{neg}, {negative_prompt}"
    
    try:
        output_path = generate_video_gpu(
            prompt=enhanced, negative_prompt=neg,
            num_frames=num_frames, fps=fps, width=width, height=height,
            steps=steps, seed=seed, guidance_scale=guidance_scale,
            guidance_rescale=guidance_rescale, solver=solver, flow_shift=flow_shift,
            use_karras=use_karras_sigmas, use_dynamic_shifting=use_dynamic_shifting,
            decode_timestep=decode_timestep, decode_noise_scale=decode_noise_scale,
            image_cond_noise_scale=image_cond_noise_scale,
            num_videos_per_prompt=num_videos_per_prompt, output_type=output_type,
            camera_enabled=camera_enabled, camera_motion=camera_motion,
            camera_direction=camera_direction, camera_speed=camera_speed,
            camera_intensity=camera_intensity, upscale=upscale,
            interpolate_fps=interpolate_fps, color_grading=color_grading,
            effects=effects, codec=codec, crf=crf, preset=preset,
            tune=tune, bitrate=bitrate, maxrate=maxrate, bufsize=bufsize,
            profile=profile, pixel_format=pixel_format, audio=audio)
        return {"status": "complete", "output": output_path}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

# === Gradio Interface ===
with gr.Blocks(title="SoulIllusions GPU Backend") as app:
    gr.Markdown("# SoulIllusions GPU Backend")
    gr.Markdown("ZeroGPU (A100 80GB) - SDXL Image + LTX-Video Generation")
    
    with gr.Tab("Image Generation"):
        img_prompt = gr.Textbox(label="Prompt", lines=3)
        img_negative = gr.Textbox(label="Negative Prompt", lines=2)
        img_aspect = gr.Dropdown(["1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2"],
                                 value="2:3", label="Aspect Ratio")
        img_quality = gr.Dropdown(["draft", "standard", "pro", "ultra"],
                                  value="pro", label="Quality")
        img_style = gr.Dropdown(["cinematic", "realistic", "anime", "poster"],
                                value="cinematic", label="Style")
        img_seed = gr.Number(label="Seed", value=-1)
        img_btn = gr.Button("Generate Image")
        img_output = gr.Image(label="Result", type="filepath")
        img_status = gr.Textbox(label="Status")
        
        def img_gen(prompt, negative, aspect, quality, style, seed):
            s = None if seed < 0 else int(seed)
            result = api_generate_image(
                prompt=prompt, negative_prompt=negative,
                aspect_ratio=aspect, quality=quality, seed=s,
                style_preset=style)
            if result["status"] == "complete":
                return result["image"], "Done!"
            return None, f"Failed: {result.get('error')}"
        
        img_btn.click(img_gen,
                      inputs=[img_prompt, img_negative, img_aspect, img_quality, img_style, img_seed],
                      outputs=[img_output, img_status],
                      api_name="generate_image")
    
    with gr.Tab("Video Generation"):
        vid_prompt = gr.Textbox(label="Prompt", lines=3)
        vid_style = gr.Dropdown(["cinematic", "realistic", "anime", "documentary", "music video"],
                                value="cinematic", label="Style")
        vid_frames = gr.Slider(16, 161, value=97, step=1, label="Frames")
        vid_fps = gr.Slider(8, 60, value=24, label="FPS")
        vid_steps = gr.Slider(10, 80, value=30, label="Steps")
        vid_seed = gr.Number(label="Seed", value=-1)
        vid_btn = gr.Button("Generate Video")
        vid_output = gr.Video(label="Result")
        vid_status = gr.Textbox(label="Status")
        
        def vid_gen(prompt, style, frames, fps, steps, seed):
            s = None if seed < 0 else int(seed)
            result = api_generate_video(
                prompt=prompt, style=style,
                num_frames=int(frames), fps=int(fps), steps=int(steps), seed=s)
            if result["status"] == "complete":
                return result["output"], "Done!"
            return None, f"Failed: {result.get('error')}"
        
        vid_btn.click(vid_gen,
                      inputs=[vid_prompt, vid_style, vid_frames, vid_fps, vid_steps, vid_seed],
                      outputs=[vid_output, vid_status],
                      api_name="generate_video")
    
    with gr.Tab("Status"):
        status_btn = gr.Button("Check Status")
        status_out = gr.JSON(label="Backend Status")
        status_btn.click(api_status, outputs=[status_out], api_name="status")

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)

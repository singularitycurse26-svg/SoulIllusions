"""
SoulIllusions Comprehensive Settings Schema

Defines every parameter for video generation, camera control, motion control,
post-processing, color grading, output encoding, and audio — organized into
10 categories with defaults, validation, and preset profiles.

Based on research of:
- Wan 2.2, LTX-Video, Motif-Video, Helios, HoloCine model parameters
- Runway Gen-3, Kling 3.0, Pika Labs UI controls
- DaVinci Resolve & Premiere Pro color grading and editing tools
- FFmpeg encoding and post-processing pipelines
"""

import json
import copy
from typing import Optional, Dict, Any


# === ASPECT RATIO PRESETS ===
ASPECT_RATIOS = {
    "16:9": {"width": 1280, "height": 720, "label": "Widescreen (16:9)"},
    "9:16": {"width": 720, "height": 1280, "label": "Vertical (9:16)"},
    "1:1": {"width": 1024, "height": 1024, "label": "Square (1:1)"},
    "4:3": {"width": 1024, "height": 768, "label": "Classic (4:3)"},
    "21:9": {"width": 1280, "height": 544, "label": "Cinematic (21:9)"},
    "2.39:1": {"width": 1280, "height": 536, "label": "Anamorphic (2.39:1)"},
    "4:5": {"width": 896, "height": 1120, "label": "Portrait (4:5)"},
}

# === QUALITY MODE PRESETS ===
QUALITY_MODES = {
    "draft": {"label": "Draft (Fast preview)", "num_inference_steps": 10, "guidance_scale": 3.0, "guidance_rescale": 0.0, "description": "Quick low-quality preview, ~10 steps"},
    "standard": {"label": "Standard (Balanced)", "num_inference_steps": 30, "guidance_scale": 5.0, "guidance_rescale": 0.0, "description": "Good quality, reasonable speed, ~30 steps"},
    "pro": {"label": "Pro (High quality)", "num_inference_steps": 50, "guidance_scale": 5.0, "guidance_rescale": 0.7, "description": "High quality, slower, ~50 steps"},
    "turbo": {"label": "Turbo (Distilled fast)", "num_inference_steps": 5, "guidance_scale": 1.0, "guidance_rescale": 0.7, "description": "Uses distilled models, 4-10 steps, fastest"},
    "ultra": {"label": "Ultra (Maximum quality)", "num_inference_steps": 80, "guidance_scale": 6.0, "guidance_rescale": 0.7, "description": "Maximum quality, very slow, ~80 steps"},
}

# === CAMERA MOTION PRESETS ===
CAMERA_PRESETS = {
    "static": {"label": "Static (No movement)", "motion": "static"},
    "pan_left": {"label": "Pan Left", "motion": "pan", "direction": "left", "speed": 0.5},
    "pan_right": {"label": "Pan Right", "motion": "pan", "direction": "right", "speed": 0.5},
    "tilt_up": {"label": "Tilt Up", "motion": "tilt", "direction": "up", "speed": 0.5},
    "tilt_down": {"label": "Tilt Down", "motion": "tilt", "direction": "down", "speed": 0.5},
    "zoom_in": {"label": "Zoom In", "motion": "zoom", "direction": "in", "speed": 0.5},
    "zoom_out": {"label": "Zoom Out", "motion": "zoom", "direction": "out", "speed": 0.5},
    "dolly_in": {"label": "Dolly In", "motion": "dolly", "direction": "in", "speed": 0.5},
    "dolly_out": {"label": "Dolly Out", "motion": "dolly", "direction": "out", "speed": 0.5},
    "dolly_zoom": {"label": "Dolly Zoom (Vertigo)", "motion": "dolly_zoom", "speed": 0.5},
    "orbit_left": {"label": "Orbit Left", "motion": "orbit", "direction": "left", "speed": 0.5},
    "orbit_right": {"label": "Orbit Right", "motion": "orbit", "direction": "right", "speed": 0.5},
    "crane_up": {"label": "Crane Up", "motion": "crane", "direction": "up", "speed": 0.5},
    "crane_down": {"label": "Crane Down", "motion": "crane", "direction": "down", "speed": 0.5},
    "pedestal_up": {"label": "Pedestal Up", "motion": "pedestal", "direction": "up", "speed": 0.5},
    "pedestal_down": {"label": "Pedestal Down", "motion": "pedestal", "direction": "down", "speed": 0.5},
    "tracking": {"label": "Tracking Shot", "motion": "tracking", "speed": 0.5},
    "handheld": {"label": "Handheld (Shaky cam)", "motion": "handheld", "speed": 0.3},
    "aerial": {"label": "Aerial Drone", "motion": "aerial", "speed": 0.4},
    "custom": {"label": "Custom Trajectory", "motion": "custom"},
}

# === SCHEDULER OPTIONS ===
SCHEDULERS = {
    "unipc": "UniPCMultistepScheduler (Default, balanced)",
    "euler": "EulerDiscreteScheduler (Fast, anime style)",
    "euler_ancestral": "EulerAncestralDiscreteScheduler (More creative)",
    "ddim": "DDIMScheduler (Classic, deterministic)",
    "dpm_plus_plus": "DPM++ 2M SDE Karras (High quality)",
    "flow_match_euler": "FlowMatchEulerDiscreteScheduler (SD3/Flow models)",
    "flow_match_heun": "FlowMatchHeunDiscreteScheduler (Higher quality flow)",
    "tcd": "TCDScheduler (For distilled models)",
}

# === CODEC OPTIONS ===
CODECS = {
    "h264": {"encoder": "libx264", "label": "H.264 (Best compatibility)", "default_crf": 23},
    "h265": {"encoder": "libx265", "label": "H.265/HEVC (Better compression)", "default_crf": 28},
    "vp9": {"encoder": "libvpx-vp9", "label": "VP9 (Web-optimized)", "default_crf": 31},
    "av1": {"encoder": "libsvtav1", "label": "AV1 (Best compression, slow)", "default_crf": 30},
}

ENCODING_PRESETS = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"]

TUNE_OPTIONS = {
    "none": "No tuning", "film": "Film (Live-action)", "animation": "Animation (Cartoon/anime)",
    "stillimage": "Still Image (Low motion)", "fastdecode": "Fast Decode", "zerolatency": "Zero Latency (Live)",
}

STYLE_PRESETS = {
    "cinematic": "Cinematic", "realistic": "Realistic", "anime": "Anime", "documentary": "Documentary",
    "music_video": "Music Video", "social_media": "Social Media", "noir": "Film Noir", "vintage": "Vintage",
    "cyberpunk": "Cyberpunk", "fantasy": "Fantasy", "horror": "Horror", "romance": "Romance",
    "action": "Action", "dreamy": "Dreamy", "3d_render": "3D Render", "watercolor": "Watercolor",
    "comic_book": "Comic Book", "claymation": "Claymation",
}

TRANSITION_TYPES = {
    "cut": "Cut", "xfade": "Cross-fade", "fade": "Fade through black", "dissolve": "Dissolve",
    "wipe_left": "Wipe Left", "wipe_right": "Wipe Right", "slide": "Slide", "zoom": "Zoom", "flash": "Flash",
}

UPSCALE_MODELS = {
    "none": "No upscaling", "realesrgan_x2": "Real-ESRGAN 2x", "realesrgan_x4": "Real-ESRGAN 4x",
    "realesrgan_anime": "Real-ESRGAN Anime", "lanczos_x2": "Lanczos 2x", "lanczos_x4": "Lanczos 4x",
}

TTS_VOICES = {
    "narrator_male": "Narrator (Male)", "narrator_female": "Narrator (Female)",
    "character_male": "Character (Male)", "character_female": "Character (Female)",
    "news_anchor": "News Anchor", "child": "Child", "elderly": "Elderly", "robot": "Robot/AI",
}

# === BITRATE PRESETS ===
BITRATE_MODES = {
    "crf": "CRF (Constant Rate Factor - quality-based, recommended)",
    "cbr": "CBR (Constant Bitrate - streaming)",
    "vbr": "VBR (Variable Bitrate - balanced)",
    "vbr_2pass": "VBR 2-Pass (Best quality/size ratio, slower)",
}

BITRATE_PRESETS = {
    "auto": {"label": "Auto (CRF-based)", "bitrate": None, "maxrate": None, "bufsize": None, "crf": 23, "mode": "crf"},
    "low_720": {"label": "Low (720p ~2 Mbps)", "bitrate": "2M", "maxrate": "2.5M", "bufsize": "4M", "crf": None, "mode": "vbr"},
    "medium_1080": {"label": "Medium (1080p ~5 Mbps)", "bitrate": "5M", "maxrate": "6M", "bufsize": "10M", "crf": None, "mode": "vbr"},
    "high_1080": {"label": "High (1080p ~8 Mbps)", "bitrate": "8M", "maxrate": "10M", "bufsize": "15M", "crf": None, "mode": "vbr"},
    "ultra_4k": {"label": "Ultra (4K ~25 Mbps)", "bitrate": "25M", "maxrate": "30M", "bufsize": "50M", "crf": None, "mode": "vbr"},
    "streaming": {"label": "Streaming (1080p ~4 Mbps)", "bitrate": "4M", "maxrate": "4.5M", "bufsize": "8M", "crf": None, "mode": "cbr"},
    "cinema": {"label": "Cinema Quality (~15 Mbps)", "bitrate": "15M", "maxrate": "20M", "bufsize": "30M", "crf": None, "mode": "vbr_2pass"},
    "archive": {"label": "Archive Master (~50 Mbps)", "bitrate": "50M", "maxrate": "60M", "bufsize": "100M", "crf": None, "mode": "vbr_2pass"},
}


DEFAULT_SETTINGS = {
    "generation": {
        "prompt": "", "negative_prompt": "blurry, distorted, low quality, deformed, ugly, watermark, text, logo, jpeg artifacts, extra limbs, poorly drawn hands, poorly drawn face, disfigured, mutated, bad anatomy, cloned face, long neck, missing limbs",
        "model": "auto", "style": "cinematic", "seed": None, "enhance_prompt": True, "quality_mode": "standard",
    },
    "resolution": {"aspect_ratio": "16:9", "width": 1280, "height": 720, "scale_factor": 1.0, "custom_resolution": False},
    "quality": {"num_inference_steps": 30, "guidance_scale": 5.0, "guidance_rescale": 0.0, "num_frames": 97, "fps": 24, "num_videos_per_prompt": 1, "creativity_scale": 0.5},
    "scheduler": {"solver": "unipc", "flow_shift": 5.0, "use_karras_sigmas": False, "use_dynamic_shifting": False, "timestep_spacing": "linspace", "custom_timesteps": None, "custom_sigmas": None, "boundary_ratio": 0.875, "decode_timestep": 0.05, "decode_noise_scale": 0.025, "image_cond_noise_scale": 0.0, "denoise_strength": 1.0},
    "camera": {"enabled": False, "preset": "static", "motion": "static", "direction": None, "speed": 0.5, "intensity": 0.5, "trajectory": None, "fov": 60.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    "motion": {"motion_brush_enabled": False, "motion_brush_regions": [], "object_drag_enabled": False, "object_drag_points": [], "motion_intensity": 0.5, "temporal_smoothing": True, "flicker_elimination": True},
    "postprocess": {
        "upscale_enabled": False, "upscale_model": "realesrgan_x2", "upscale_scale": 2,
        "interpolate_enabled": False, "interpolate_target_fps": 60, "interpolate_motion_blur": False,
        "color_grading_enabled": False,
        "color": {"lift": 0.0, "gamma": 0.0, "gain": 0.0, "contrast": 0.0, "brightness": 0.0, "saturation": 0.0, "hue": 0.0, "temperature": 0.0, "tint": 0.0, "midtone_detail": 0.0, "color_boost": 0.0, "shadows": 0.0, "highlights": 0.0},
        "effects": {"vignette_enabled": False, "vignette_intensity": 0.3, "vignette_feather": 50, "lens_flare_enabled": False, "lens_flare_intensity": 0.5, "glow_enabled": False, "glow_intensity": 0.3, "glow_radius": 10, "film_grain_enabled": False, "film_grain_amount": 0.15, "sharpen_enabled": False, "sharpen_amount": 0.5, "noise_reduction_enabled": False, "noise_reduction_strength": 0.5, "bloom_enabled": False, "bloom_intensity": 0.3, "bloom_threshold": 0.7},
        "transitions": {"type": "xfade", "duration": 0.5},
        "title_card_enabled": False, "title_text": "", "title_duration": 3.0, "shot_match_enabled": False,
    },
    "output": {"codec": "h264", "crf": 23, "preset": "medium", "tune": "none", "bitrate": None, "maxrate": None, "bufsize": None, "bitrate_preset": "auto", "profile": "high", "level": "auto", "pixel_format": "yuv420p", "two_pass": False, "hardware_accel": "none", "container": "mp4"},
    "audio": {"enabled": False, "native_audio": False, "tts_enabled": False, "tts_text": "", "tts_voice": "narrator_male", "ambient_enabled": False, "ambient_prompt": "", "music_enabled": False, "music_prompt": "", "music_volume": 0.5, "dialogue_volume": 1.0, "ambient_volume": 0.3, "audio_codec": "aac", "audio_bitrate": "128k", "sample_rate": 44100},
    "advanced": {"output_type": "pil", "strength": 1.0, "style_reference": None, "seed_batch_count": 1, "seed_batch_offset": 0, "cache_model": True, "cpu_offload": False, "sequential_offload": False, "vae_slicing": False, "tiling": False, "attention_slicing": False, "xformers": False, "torch_compile": False, "half_precision": True, "gguf_quantization": None},
}

SETTING_PRESETS = {
    "cinematic_short": {"label": "Cinematic Short Film", "settings": {"generation": {"style": "cinematic", "quality_mode": "pro", "enhance_prompt": True}, "resolution": {"aspect_ratio": "21:9", "width": 1280, "height": 544}, "quality": {"num_frames": 121, "fps": 24}, "camera": {"enabled": True, "preset": "dolly_in", "speed": 0.3}, "postprocess": {"color_grading_enabled": True, "color": {"contrast": 0.15, "saturation": -0.05, "temperature": -0.1}, "effects": {"vignette_enabled": True, "vignette_intensity": 0.4, "film_grain_enabled": True, "film_grain_amount": 0.1}}, "output": {"codec": "h264", "crf": 20, "preset": "slow", "tune": "film"}}},
    "social_media_vertical": {"label": "Social Media (Vertical)", "settings": {"generation": {"style": "social_media", "quality_mode": "standard"}, "resolution": {"aspect_ratio": "9:16", "width": 720, "height": 1280}, "quality": {"num_frames": 49, "fps": 30}, "postprocess": {"color_grading_enabled": True, "color": {"saturation": 0.2, "color_boost": 0.3}, "effects": {"sharpen_enabled": True, "sharpen_amount": 0.3}}, "output": {"codec": "h264", "crf": 21, "preset": "fast"}}},
    "anime_sequence": {"label": "Anime Sequence", "settings": {"generation": {"style": "anime", "quality_mode": "pro", "negative_prompt": "3d, realistic, photorealistic, deformed, ugly"}, "resolution": {"aspect_ratio": "16:9", "width": 1280, "height": 720}, "quality": {"num_frames": 97, "fps": 24, "guidance_scale": 7.0}, "scheduler": {"solver": "euler"}, "postprocess": {"upscale_enabled": True, "upscale_model": "realesrgan_anime", "upscale_scale": 2, "color_grading_enabled": True, "color": {"saturation": 0.15, "contrast": 0.1}}, "output": {"codec": "h264", "crf": 20, "preset": "medium", "tune": "animation"}}},
    "documentary_clip": {"label": "Documentary Clip", "settings": {"generation": {"style": "documentary", "quality_mode": "pro"}, "resolution": {"aspect_ratio": "16:9", "width": 1280, "height": 720}, "quality": {"num_frames": 121, "fps": 24}, "camera": {"enabled": True, "preset": "handheld", "speed": 0.2}, "postprocess": {"color_grading_enabled": True, "color": {"temperature": 0.05, "saturation": -0.1}}, "output": {"codec": "h264", "crf": 19, "preset": "slow", "tune": "film"}}},
    "fast_preview": {"label": "Fast Preview (Draft)", "settings": {"generation": {"quality_mode": "draft"}, "resolution": {"aspect_ratio": "16:9", "width": 768, "height": 432}, "quality": {"num_frames": 33, "fps": 12}, "postprocess": {"upscale_enabled": False, "interpolate_enabled": False, "color_grading_enabled": False}, "output": {"codec": "h264", "crf": 28, "preset": "ultrafast"}}},
    "music_video": {"label": "Music Video", "settings": {"generation": {"style": "music_video", "quality_mode": "pro"}, "resolution": {"aspect_ratio": "16:9", "width": 1280, "height": 720}, "quality": {"num_frames": 121, "fps": 30}, "camera": {"enabled": True, "preset": "tracking", "speed": 0.7}, "postprocess": {"color_grading_enabled": True, "color": {"saturation": 0.3, "contrast": 0.2, "color_boost": 0.4}, "effects": {"glow_enabled": True, "glow_intensity": 0.5, "bloom_enabled": True, "bloom_intensity": 0.4}}, "output": {"codec": "h264", "crf": 20, "preset": "medium"}}},
    "horror_atmosphere": {"label": "Horror Atmosphere", "settings": {"generation": {"style": "horror", "quality_mode": "pro", "negative_prompt": "bright, colorful, cheerful, sunny, warm"}, "resolution": {"aspect_ratio": "21:9", "width": 1280, "height": 544}, "quality": {"num_frames": 97, "fps": 24, "guidance_scale": 6.0}, "camera": {"enabled": True, "preset": "handheld", "speed": 0.15}, "postprocess": {"color_grading_enabled": True, "color": {"saturation": -0.4, "contrast": 0.3, "temperature": -0.2, "highlights": -0.1, "shadows": -0.2}, "effects": {"vignette_enabled": True, "vignette_intensity": 0.6, "film_grain_enabled": True, "film_grain_amount": 0.25, "noise_reduction_enabled": False}}, "output": {"codec": "h264", "crf": 22, "preset": "slow", "tune": "film"}}},
}


class SettingsSchema:
    """Manages SoulIllusions video generation settings with validation and presets."""

    def __init__(self, settings: dict = None):
        self.settings = self._deep_merge(copy.deepcopy(DEFAULT_SETTINGS), settings or {})

    def _deep_merge(self, base: dict, override: dict) -> dict:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def get(self, category: str = None, key: str = None, default=None):
        if category is None:
            return copy.deepcopy(self.settings)
        cat = self.settings.get(category, {})
        if key is None:
            return copy.deepcopy(cat)
        return cat.get(key, default)

    def set(self, category: str, key: str, value):
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value

    def update(self, category: str, updates: dict):
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category].update(updates)

    def apply_preset(self, preset_name: str):
        if preset_name not in SETTING_PRESETS:
            raise ValueError(f"Unknown preset: {preset_name}")
        self.settings = self._deep_merge(copy.deepcopy(DEFAULT_SETTINGS), SETTING_PRESETS[preset_name]["settings"])

    def apply_quality_mode(self, mode: str):
        if mode not in QUALITY_MODES:
            raise ValueError(f"Unknown quality mode: {mode}")
        qm = QUALITY_MODES[mode]
        self.settings["quality"]["num_inference_steps"] = qm["num_inference_steps"]
        self.settings["quality"]["guidance_scale"] = qm["guidance_scale"]
        self.settings["quality"]["guidance_rescale"] = qm["guidance_rescale"]
        self.settings["generation"]["quality_mode"] = mode

    def apply_aspect_ratio(self, ratio: str):
        if ratio not in ASPECT_RATIOS:
            raise ValueError(f"Unknown aspect ratio: {ratio}")
        ar = ASPECT_RATIOS[ratio]
        self.settings["resolution"]["width"] = ar["width"]
        self.settings["resolution"]["height"] = ar["height"]
        self.settings["resolution"]["aspect_ratio"] = ratio

    def apply_camera_preset(self, preset: str):
        if preset not in CAMERA_PRESETS:
            raise ValueError(f"Unknown camera preset: {preset}")
        cam = CAMERA_PRESETS[preset]
        self.settings["camera"]["preset"] = preset
        self.settings["camera"]["motion"] = cam.get("motion", "static")
        self.settings["camera"]["direction"] = cam.get("direction")
        self.settings["camera"]["speed"] = cam.get("speed", 0.5)
        self.settings["camera"]["enabled"] = preset != "static"

    def apply_bitrate_preset(self, preset_name: str):
        if preset_name not in BITRATE_PRESETS:
            raise ValueError(f"Unknown bitrate preset: {preset_name}")
        bp = BITRATE_PRESETS[preset_name]
        self.settings["output"]["bitrate_preset"] = preset_name
        self.settings["output"]["bitrate"] = bp["bitrate"]
        self.settings["output"]["maxrate"] = bp["maxrate"]
        self.settings["output"]["bufsize"] = bp["bufsize"]
        if bp["crf"] is not None:
            self.settings["output"]["crf"] = bp["crf"]
        mode = bp["mode"]
        self.settings["output"]["two_pass"] = (mode == "vbr_2pass")

    def to_dict(self) -> dict:
        return copy.deepcopy(self.settings)

    def to_json(self) -> str:
        return json.dumps(self.settings, indent=2, default=str)

    def to_backend_payload(self) -> dict:
        s = self.settings
        return {
            "prompt": s["generation"]["prompt"], "negative_prompt": s["generation"]["negative_prompt"],
            "model": s["generation"]["model"], "style": s["generation"]["style"], "seed": s["generation"]["seed"],
            "enhance": s["generation"]["enhance_prompt"],
            "width": s["resolution"]["width"], "height": s["resolution"]["height"],
            "num_frames": s["quality"]["num_frames"], "fps": s["quality"]["fps"],
            "num_inference_steps": s["quality"]["num_inference_steps"], "guidance_scale": s["quality"]["guidance_scale"],
            "guidance_rescale": s["quality"]["guidance_rescale"], "num_videos_per_prompt": s["quality"]["num_videos_per_prompt"],
            "creativity_scale": s["quality"]["creativity_scale"],
            "solver": s["scheduler"]["solver"], "flow_shift": s["scheduler"]["flow_shift"],
            "use_karras_sigmas": s["scheduler"]["use_karras_sigmas"], "use_dynamic_shifting": s["scheduler"]["use_dynamic_shifting"],
            "timestep_spacing": s["scheduler"]["timestep_spacing"], "custom_timesteps": s["scheduler"]["custom_timesteps"],
            "custom_sigmas": s["scheduler"]["custom_sigmas"], "boundary_ratio": s["scheduler"]["boundary_ratio"],
            "decode_timestep": s["scheduler"]["decode_timestep"], "decode_noise_scale": s["scheduler"]["decode_noise_scale"],
            "image_cond_noise_scale": s["scheduler"]["image_cond_noise_scale"], "denoise_strength": s["scheduler"]["denoise_strength"],
            "camera_enabled": s["camera"]["enabled"], "camera_motion": s["camera"]["motion"],
            "camera_direction": s["camera"]["direction"], "camera_speed": s["camera"]["speed"],
            "camera_intensity": s["camera"]["intensity"], "camera_fov": s["camera"]["fov"],
            "camera_roll": s["camera"]["roll"], "camera_pitch": s["camera"]["pitch"], "camera_yaw": s["camera"]["yaw"],
            "motion_intensity": s["motion"]["motion_intensity"], "temporal_smoothing": s["motion"]["temporal_smoothing"],
            "flicker_elimination": s["motion"]["flicker_elimination"],
            "upscale": s["postprocess"]["upscale_scale"] if s["postprocess"]["upscale_enabled"] else 1,
            "upscale_model": s["postprocess"]["upscale_model"],
            "interpolate_fps": s["postprocess"]["interpolate_target_fps"] if s["postprocess"]["interpolate_enabled"] else 0,
            "interpolate_motion_blur": s["postprocess"]["interpolate_motion_blur"],
            "color_grading": s["postprocess"]["color"] if s["postprocess"]["color_grading_enabled"] else None,
            "effects": s["postprocess"]["effects"],
            "transition_type": s["postprocess"]["transitions"]["type"], "transition_duration": s["postprocess"]["transitions"]["duration"],
            "title_card": s["postprocess"]["title_text"] if s["postprocess"]["title_card_enabled"] else None,
            "title_duration": s["postprocess"]["title_duration"], "shot_match": s["postprocess"]["shot_match_enabled"],
            "codec": s["output"]["codec"], "crf": s["output"]["crf"], "preset": s["output"]["preset"],
            "tune": s["output"]["tune"], "bitrate": s["output"]["bitrate"], "maxrate": s["output"]["maxrate"],
            "bufsize": s["output"]["bufsize"], "profile": s["output"]["profile"], "pixel_format": s["output"]["pixel_format"],
            "two_pass": s["output"]["two_pass"], "container": s["output"]["container"],
            "audio": s["audio"]["enabled"], "native_audio": s["audio"]["native_audio"],
            "tts_text": s["audio"]["tts_text"] if s["audio"]["tts_enabled"] else None, "tts_voice": s["audio"]["tts_voice"],
            "ambient_prompt": s["audio"]["ambient_prompt"] if s["audio"]["ambient_enabled"] else None,
            "music_prompt": s["audio"]["music_prompt"] if s["audio"]["music_enabled"] else None,
            "audio_codec": s["audio"]["audio_codec"], "audio_bitrate": s["audio"]["audio_bitrate"],
            "output_type": s["advanced"]["output_type"], "strength": s["advanced"]["strength"],
            "cpu_offload": s["advanced"]["cpu_offload"], "half_precision": s["advanced"]["half_precision"],
            "gguf_quantization": s["advanced"]["gguf_quantization"], "torch_compile": s["advanced"]["torch_compile"],
            "xformers": s["advanced"]["xformers"], "vae_slicing": s["advanced"]["vae_slicing"], "tiling": s["advanced"]["tiling"],
        }

    def to_ffmpeg_filter_string(self) -> str:
        filters = []
        c = self.settings["postprocess"]["color"]
        e = self.settings["postprocess"]["effects"]
        if self.settings["postprocess"]["color_grading_enabled"]:
            if c["contrast"] != 0: filters.append(f"eq=contrast={1.0 + c['contrast']}")
            if c["brightness"] != 0 or c["gamma"] != 0: filters.append(f"eq=brightness={c.get('brightness', 0):.2f}:gamma={1.0 + c['gamma']:.2f}")
            if c["saturation"] != 0: filters.append(f"eq=saturation={1.0 + c['saturation']:.2f}")
            if c["temperature"] != 0: filters.append(f"colorbalance=rs={c['temperature'] * 0.3}:bs={-c['temperature'] * 0.3}")
            if c["tint"] != 0: filters.append(f"colorbalance=gs={c['tint'] * 0.3}")
            if c["hue"] != 0: filters.append(f"hue=h={c['hue'] * 180}")
        if e["vignette_enabled"]: filters.append(f"vignette=PI/{5 + e['vignette_intensity'] * 10}")
        if e["film_grain_enabled"]: filters.append(f"noise=alls={int(e['film_grain_amount'] * 100)}:allf=t")
        if e["sharpen_enabled"]: filters.append(f"unsharp=5:5:{e['sharpen_amount'] * 1.5}:5:5:{e['sharpen_amount'] * 1.5}")
        if e["glow_enabled"]: filters.append(f"gblur=sigma={e['glow_radius']},mix={e['glow_intensity']}")
        if e["bloom_enabled"]: filters.append(f"smartblur=lr=1:lt=0.1,eq=brightness={e['bloom_intensity'] * 0.1}")
        return ",".join(filters) if filters else None

    def to_ffmpeg_encode_args(self) -> list:
        o = self.settings["output"]
        codec_info = CODECS.get(o["codec"], CODECS["h264"])
        args = ["-c:v", codec_info["encoder"]]
        if o.get("crf") is not None and not o.get("bitrate"): args.extend(["-crf", str(o["crf"])])
        if o.get("bitrate"): args.extend(["-b:v", str(o["bitrate"])])
        if o.get("maxrate"): args.extend(["-maxrate", str(o["maxrate"])])
        if o.get("bufsize"): args.extend(["-bufsize", str(o["bufsize"])])
        args.extend(["-preset", o.get("preset", "medium")])
        if o.get("tune") and o["tune"] != "none": args.extend(["-tune", o["tune"]])
        if o.get("profile") and o["profile"] != "auto": args.extend(["-profile:v", o["profile"]])
        if o.get("pixel_format"): args.extend(["-pix_fmt", o["pixel_format"]])
        a = self.settings["audio"]
        if a["enabled"]:
            args.extend(["-c:a", a.get("audio_codec", "aac"), "-b:a", a.get("audio_bitrate", "128k"), "-ar", str(a.get("sample_rate", 44100))])
        else:
            args.extend(["-an"])
        return args

    def get_camera_prompt_suffix(self) -> str:
        if not self.settings["camera"]["enabled"]:
            return ""
        cam = self.settings["camera"]
        speed = cam["speed"]
        speed_words = {0.1: "very slow", 0.3: "slow", 0.5: "moderate", 0.7: "fast", 0.9: "very fast"}
        speed_str = "moderate"
        for threshold, word in sorted(speed_words.items()):
            if speed <= threshold:
                speed_str = word
                break
        descriptions = {
            "static": "static camera", "pan": f"{speed_str} pan {cam.get('direction', 'left')}",
            "tilt": f"{speed_str} tilt {cam.get('direction', 'up')}", "zoom": f"{speed_str} zoom {cam.get('direction', 'in')}",
            "dolly": f"{speed_str} dolly {cam.get('direction', 'in')}", "dolly_zoom": f"{speed_str} dolly zoom",
            "orbit": f"{speed_str} orbit {cam.get('direction', 'left')}", "crane": f"{speed_str} crane {cam.get('direction', 'up')}",
            "pedestal": f"{speed_str} pedestal {cam.get('direction', 'up')}", "tracking": f"{speed_str} tracking shot",
            "handheld": "handheld camera, slight shake", "aerial": "aerial drone shot", "custom": "custom camera movement",
        }
        desc = descriptions.get(cam["motion"], "")
        return f", {desc} camera movement" if desc else ""

    def validate(self) -> list:
        warnings = []
        s = self.settings
        if s["quality"]["num_inference_steps"] < 1: warnings.append("num_inference_steps must be >= 1")
        if s["quality"]["num_inference_steps"] > 100: warnings.append("num_inference_steps > 100 will be very slow")
        if s["quality"]["guidance_scale"] < 1.0: warnings.append("guidance_scale < 1.0 may produce poor results")
        if s["quality"]["guidance_scale"] > 15.0: warnings.append("guidance_scale > 15.0 may cause artifacts")
        if s["resolution"]["width"] % 16 != 0 or s["resolution"]["height"] % 16 != 0: warnings.append("Resolution should be multiples of 16")
        if s["quality"]["num_frames"] < 9: warnings.append("num_frames < 9 will produce very short video")
        if s["quality"]["num_frames"] > 201: warnings.append("num_frames > 201 may cause OOM errors")
        if s["postprocess"]["upscale_enabled"] and s["postprocess"]["upscale_scale"] > 4: warnings.append("upscale_scale > 4 not supported")
        if s["output"]["crf"] < 0 or s["output"]["crf"] > 51: warnings.append("CRF must be 0-51")
        return warnings

    def save_to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, default=str)

    @classmethod
    def load_from_file(cls, path: str) -> "SettingsSchema":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def from_request(cls, req_dict: dict) -> "SettingsSchema":
        schema = cls()
        g = schema.settings["generation"]
        g["prompt"] = req_dict.get("prompt", g["prompt"])
        g["negative_prompt"] = req_dict.get("negative_prompt", g["negative_prompt"])
        g["model"] = req_dict.get("model", g["model"])
        g["style"] = req_dict.get("style", g["style"])
        g["seed"] = req_dict.get("seed", g["seed"])
        g["enhance_prompt"] = req_dict.get("enhance", g["enhance_prompt"])
        r = schema.settings["resolution"]
        if req_dict.get("width"): r["width"] = req_dict["width"]; r["custom_resolution"] = True
        if req_dict.get("height"): r["height"] = req_dict["height"]; r["custom_resolution"] = True
        q = schema.settings["quality"]
        q["num_frames"] = req_dict.get("num_frames", q["num_frames"])
        q["fps"] = req_dict.get("fps", q["fps"])
        q["num_inference_steps"] = req_dict.get("steps", q["num_inference_steps"])
        q["guidance_scale"] = req_dict.get("guidance_scale", q["guidance_scale"])
        q["guidance_rescale"] = req_dict.get("guidance_rescale", q["guidance_rescale"])
        sc = schema.settings["scheduler"]
        sc["solver"] = req_dict.get("solver", sc["solver"])
        sc["flow_shift"] = req_dict.get("flow_shift", sc["flow_shift"])
        pp = schema.settings["postprocess"]
        pp["upscale_enabled"] = req_dict.get("upscale", 1) > 1
        pp["upscale_scale"] = max(1, req_dict.get("upscale", 1))
        pp["interpolate_enabled"] = req_dict.get("interpolate_fps", 0) > 0
        pp["interpolate_target_fps"] = max(0, req_dict.get("interpolate_fps", 0))
        au = schema.settings["audio"]
        au["enabled"] = req_dict.get("audio", False)
        au["native_audio"] = req_dict.get("native_audio", False)
        return schema


def get_default_settings() -> dict:
    return copy.deepcopy(DEFAULT_SETTINGS)

def list_presets() -> dict:
    return {k: v["label"] for k, v in SETTING_PRESETS.items()}

def list_aspect_ratios() -> dict:
    return {k: v["label"] for k, v in ASPECT_RATIOS.items()}

def list_quality_modes() -> dict:
    return {k: v["label"] for k, v in QUALITY_MODES.items()}

def list_camera_presets() -> dict:
    return {k: v["label"] for k, v in CAMERA_PRESETS.items()}

def list_styles() -> dict:
    return STYLE_PRESETS

def list_codecs() -> dict:
    return {k: v["label"] for k, v in CODECS.items()}

def list_schedulers() -> dict:
    return SCHEDULERS

def apply_preset(preset_name: str) -> dict:
    """Apply a named preset and return the full settings dict."""
    schema = SettingsSchema()
    schema.apply_preset(preset_name)
    return schema.to_dict()


# === IMAGE GENERATION MODELS ===
T2I_MODELS = {
    "flux": {"label": "FLUX.1", "desc": "High-fidelity general generation", "resolutions": ["1K", "2K", "4K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:2", "21:9"]},
    "sdxl": {"label": "Stable Diffusion XL", "desc": "Versatile, fast, LoRA support", "resolutions": ["1024x1024", "1024x768", "768x1024"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:2"]},
    "sd15": {"label": "Stable Diffusion 1.5", "desc": "Fast, huge LoRA ecosystem", "resolutions": ["512x512", "512x768", "768x512"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:2"]},
    "nano_banana": {"label": "Nano Banana Pro", "desc": "Reasoning engine, perfect text, 4K", "resolutions": ["1K", "2K", "4K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "4:5", "21:9"]},
    "seedream": {"label": "Seedream 5.0", "desc": "High quality, style transfer", "resolutions": ["1K", "2K", "4K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:2"]},
    "gpt_image": {"label": "GPT Image 2", "desc": "Graphic design, UI, banners, typography", "resolutions": ["1K", "2K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3"]},
}

I2I_MODELS = {
    "kontext": {"label": "FLUX Kontext Pro", "desc": "High-quality image editing", "max_images": 1, "resolutions": ["1K", "2K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3"]},
    "seedream_edit": {"label": "Seedream 5.0 Edit", "desc": "Natural language style transfer", "max_images": 1, "resolutions": ["1K", "2K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3"]},
    "nano_banana_edit": {"label": "Nano Banana Pro Edit", "desc": "Brush-to-edit inpainting, up to 14 references", "max_images": 14, "resolutions": ["1K", "2K", "4K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "4:5"]},
    "seededit_v3": {"label": "Seededit v3", "desc": "Precise editing control", "max_images": 1, "resolutions": ["1K", "2K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3"]},
    "upscaler": {"label": "AI Upscaler", "desc": "Resolution enhancement up to 4K", "max_images": 1, "resolutions": ["2K", "4K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3"]},
    "bg_remover": {"label": "Background Remover", "desc": "Clean background removal", "max_images": 1, "resolutions": ["1K", "2K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3"]},
    "face_swap": {"label": "Face Swap", "desc": "Accurate face blending", "max_images": 2, "resolutions": ["1K", "2K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3"]},
    "image_extender": {"label": "Image Extender", "desc": "Expand canvas beyond edges", "max_images": 1, "resolutions": ["1K", "2K"], "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "21:9"]},
}

IMAGE_QUALITY_PRESETS = {
    "draft": {"label": "Draft (Fast)", "steps": 10, "guidance_scale": 3.0, "desc": "Quick low-quality preview"},
    "standard": {"label": "Standard", "steps": 25, "guidance_scale": 7.5, "desc": "Good quality, reasonable speed"},
    "high": {"label": "High Quality", "steps": 40, "guidance_scale": 7.5, "desc": "High quality, slower"},
    "ultra": {"label": "Ultra (4K)", "steps": 50, "guidance_scale": 8.0, "desc": "Maximum quality, very slow"},
}

IMAGE_STYLE_PRESETS = [
    "None", "Photorealistic", "Cinematic", "Anime", "Oil Painting", "Watercolor",
    "Digital Art", "Concept Art", "Cyberpunk", "3D Render", "Comic Book",
    "Noir", "Vintage", "Fantasy", "Horror", "Minimalist", "Surreal",
]

IMAGE_ENHANCE_TAGS = {
    "lighting": ["golden hour", "blue hour", "studio lighting", "natural light", "dramatic lighting", "soft light", "rim light", "backlit"],
    "mood": ["serene", "dramatic", "mysterious", "ethereal", "moody", "vibrant", "melancholic", "epic"],
    "composition": ["wide shot", "close-up", "aerial view", "low angle", "high angle", "symmetrical", "rule of thirds", "centered"],
    "quality": ["highly detailed", "8K", "sharp focus", "ultra realistic", "masterpiece", "award winning", "professional photography", "trending on artstation"],
    "effects": ["bokeh", "depth of field", "motion blur", "long exposure", "HDR", "film grain", "lens flare", "volumetric fog"],
}

IMAGE_QUICK_PROMPTS = [
    {"label": "Portrait", "prompt": "A stunning portrait of a person, professional photography, soft studio lighting, shallow depth of field, 85mm lens"},
    {"label": "Landscape", "prompt": "Breathtaking mountain landscape at sunset, golden hour lighting, wide angle, dramatic clouds, ultra detailed"},
    {"label": "Character", "prompt": "Full body character design, fantasy warrior in ornate armor, dramatic pose, concept art style, highly detailed"},
    {"label": "Product", "prompt": "Professional product photography of a luxury watch on marble surface, studio lighting, sharp focus, commercial quality"},
    {"label": "Scene", "prompt": "A cozy coffee shop interior, warm ambient lighting, steam rising from coffee cup, cinematic atmosphere, detailed"},
    {"label": "Abstract", "prompt": "Abstract digital art, flowing colors and geometric shapes, vibrant palette, 3D render, ultra detailed"},
    {"label": "Sci-Fi", "prompt": "Futuristic city skyline at night, neon lights, flying vehicles, cyberpunk aesthetic, cinematic, ultra detailed"},
    {"label": "Nature", "prompt": "Enchanted forest with bioluminescent plants, mystical atmosphere, god rays through trees, fantasy, highly detailed"},
]

DEFAULT_IMAGE_SETTINGS = {
    "model": "flux",
    "prompt": "",
    "negative_prompt": "blurry, distorted, low quality, deformed, ugly, watermark, text, logo, jpeg artifacts, extra limbs, poorly drawn hands, poorly drawn face, disfigured, mutated, bad anatomy, cloned face, long neck, missing limbs",
    "aspect_ratio": "1:1",
    "quality": "standard",
    "seed": None,
    "batch_count": 1,
    "style_preset": "None",
    "width": None,
    "height": None,
    "guidance_scale": 7.5,
    "steps": 25,
    "lora_model": "",
    "lora_weight": 1.0,
    "reference_strength": 50,
    "image_mode": "t2i",
    "reference_images": [],
}

IMAGE_ASPECT_RATIOS = {
    "1:1": {"width": 1024, "height": 1024, "label": "Square (1:1)"},
    "16:9": {"width": 1280, "height": 720, "label": "Widescreen (16:9)"},
    "9:16": {"width": 720, "height": 1280, "label": "Vertical (9:16)"},
    "4:3": {"width": 1024, "height": 768, "label": "Classic (4:3)"},
    "3:2": {"width": 1200, "height": 800, "label": "Photo (3:2)"},
    "21:9": {"width": 1280, "height": 544, "label": "Cinematic (21:9)"},
    "4:5": {"width": 1024, "height": 1280, "label": "Portrait (4:5)"},
}


def get_image_default_settings() -> dict:
    return copy.deepcopy(DEFAULT_IMAGE_SETTINGS)

def list_t2i_models() -> dict:
    return {k: v["label"] for k, v in T2I_MODELS.items()}

def list_i2i_models() -> dict:
    return {k: v["label"] for k, v in I2I_MODELS.items()}

def list_image_quality_presets() -> dict:
    return {k: v["label"] for k, v in IMAGE_QUALITY_PRESETS.items()}

def list_image_styles() -> list:
    return IMAGE_STYLE_PRESETS

def list_image_aspect_ratios() -> dict:
    return {k: v["label"] for k, v in IMAGE_ASPECT_RATIOS.items()}

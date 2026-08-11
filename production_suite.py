"""
SoulIllusions Production Suite
Handles series/season/episode/scene management for long-form video production.
Integrates with the GPU backend for batch scene generation.
Based on research from MAViS (3E Principle), Dramaturge (hierarchical review),
PenShot (character consistency), and AI Cine Studio (5-stage workflow).
"""
import os
import json
import time
import uuid
import re
import threading
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# === Narrative Memory Engine ===
try:
    from narrative_memory import MemoryStore, NarrativeStack, UrgencyRouter, LearningEngine
    _memory_store = MemoryStore(DATA_DIR) if 'DATA_DIR' in dir() else None
    _narrative_stack = None
    _urgency_router = None
    _learning_engine = None
    _memory_enabled = True
except Exception as e:
    _memory_enabled = False
    _memory_store = None
    _narrative_stack = None
    _urgency_router = None
    _learning_engine = None

# === Action Logger ===
try:
    from action_logger import get_logger
    _action_logger = get_logger()
except Exception:
    _action_logger = None

router = APIRouter(prefix="/api/production")

# === Paths ===
APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data" / "series"
DATA_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR = APP_DIR / "videos"
VIDEOS_DIR.mkdir(exist_ok=True)

# Initialize memory engine now that DATA_DIR is set
if _memory_enabled:
    _memory_store = MemoryStore(DATA_DIR)
    _narrative_stack = NarrativeStack(_memory_store)
    _urgency_router = UrgencyRouter(_memory_store)
    _learning_engine = LearningEngine(_memory_store)

# === Data Model ===
# Series → Seasons → Episodes → Scenes → Shots
# All stored as JSON files for easy inspection and version control

def _prod_log(action: str, entity_type: str, entity_id: str = None, data: dict = None, result: str = "success"):
    """Log a production suite action."""
    if _action_logger:
        _action_logger.log_production(action, entity_type, entity_id, data, result)

def series_path(series_id: str) -> Path:
    return DATA_DIR / series_id

def season_path(series_id: str, season_num: int) -> Path:
    return series_path(series_id) / f"season_{season_num:02d}"

def episode_path(series_id: str, season_num: int, episode_num: int) -> Path:
    return season_path(series_id, season_num) / f"episode_{episode_num:02d}"

def episode_file(series_id: str, season_num: int, episode_num: int) -> Path:
    p = episode_path(series_id, season_num, episode_num)
    p.mkdir(parents=True, exist_ok=True)
    return p / "episode.json"

def scenes_dir(series_id: str, season_num: int, episode_num: int) -> Path:
    p = episode_path(series_id, season_num, episode_num) / "scenes"
    p.mkdir(parents=True, exist_ok=True)
    return p

def scene_file(series_id: str, season_num: int, episode_num: int, scene_num: int) -> Path:
    return scenes_dir(series_id, season_num, episode_num) / f"scene_{scene_num:03d}.json"

# === Series Management ===

class SeriesCreate(BaseModel):
    title: str
    description: str = ""
    concept: str = ""
    genre: str = "sci-fi"
    target_episode_duration: int = 2700  # 45 minutes in seconds
    seasons_planned: int = 8
    episodes_per_season: int = 16

@router.post("/series/create")
async def create_series(req: SeriesCreate):
    series_id = req.title.lower().replace(" ", "_").replace("-", "_")[:50]
    s_path = series_path(series_id)
    if s_path.exists():
        return JSONResponse({"error": "Series already exists"}, status_code=409)
    s_path.mkdir(parents=True, exist_ok=True)
    
    series_data = {
        "id": series_id,
        "title": req.title,
        "description": req.description,
        "concept": req.concept,
        "genre": req.genre,
        "target_episode_duration": req.target_episode_duration,
        "seasons_planned": req.seasons_planned,
        "episodes_per_season": req.episodes_per_season,
        "created_at": time.time(),
        "seasons": {},
        "characters": {},
        "world_bible": "",
        "style_guide": "",
    }
    
    (s_path / "series_bible.json").write_text(json.dumps(series_data, indent=2))
    
    # Initialize persistent memory for this series
    if _memory_enabled and _memory_store:
        _memory_store.init_series_memory(series_id, series_data)
    
    _prod_log("create", "series", series_id, {"title": req.title, "genre": req.genre})
    return {"status": "created", "series_id": series_id}

@router.get("/series")
async def list_series():
    series_list = []
    for d in DATA_DIR.iterdir():
        if d.is_dir():
            bible = d / "series_bible.json"
            if bible.exists():
                data = json.loads(bible.read_text())
                series_list.append({
                    "id": data["id"],
                    "title": data["title"],
                    "description": data["description"],
                    "genre": data["genre"],
                    "seasons_planned": data["seasons_planned"],
                    "episodes_per_season": data["episodes_per_season"],
                    "seasons_completed": sum(1 for s in data.get("seasons", {}).values() if s.get("status") == "complete"),
                    "episodes_completed": sum(
                        sum(1 for e in s.get("episodes", {}).values() if e.get("status") == "complete")
                        for s in data.get("seasons", {}).values()
                    ),
                })
    return {"series": series_list}

@router.get("/series/{series_id}")
async def get_series(series_id: str):
    bible = series_path(series_id) / "series_bible.json"
    if not bible.exists():
        return JSONResponse({"error": "Series not found"}, status_code=404)
    return json.loads(bible.read_text())

@router.put("/series/{series_id}")
async def update_series(series_id: str, request: Request):
    bible = series_path(series_id) / "series_bible.json"
    if not bible.exists():
        return JSONResponse({"error": "Series not found"}, status_code=404)
    data = json.loads(bible.read_text())
    updates = await request.json()
    data.update(updates)
    bible.write_text(json.dumps(data, indent=2))
    return {"status": "updated", "series_id": series_id}

@router.delete("/series/{series_id}")
async def delete_series(series_id: str):
    s_path = series_path(series_id)
    if s_path.exists():
        import shutil
        shutil.rmtree(s_path)
        return {"status": "deleted"}
    return JSONResponse({"error": "Not found"}, status_code=404)

# === Character Management ===

class CharacterCreate(BaseModel):
    name: str
    description: str = ""
    appearance: str = ""
    personality: str = ""
    background: str = ""
    reference_image: Optional[str] = None
    voice_profile: str = ""

@router.post("/series/{series_id}/characters")
async def add_character(series_id: str, req: CharacterCreate):
    bible = series_path(series_id) / "series_bible.json"
    if not bible.exists():
        return JSONResponse({"error": "Series not found"}, status_code=404)
    data = json.loads(bible.read_text())
    char_id = req.name.lower().replace(" ", "_")[:30]
    data.setdefault("characters", {})[char_id] = {
        "name": req.name,
        "description": req.description,
        "appearance": req.appearance,
        "personality": req.personality,
        "background": req.background,
        "reference_image": req.reference_image,
        "voice_profile": req.voice_profile,
    }
    bible.write_text(json.dumps(data, indent=2))
    return {"status": "added", "character_id": char_id}

@router.get("/series/{series_id}/characters")
async def get_characters(series_id: str):
    bible = series_path(series_id) / "series_bible.json"
    if not bible.exists():
        return JSONResponse({"error": "Series not found"}, status_code=404)
    data = json.loads(bible.read_text())
    return {"characters": data.get("characters", {})}

# === Episode Management ===

class EpisodeCreate(BaseModel):
    title: str = ""
    synopsis: str = ""
    script_raw: str = ""
    target_duration: int = 2700  # 45 minutes

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}")
async def create_episode(series_id: str, season_num: int, episode_num: int, req: EpisodeCreate):
    bible = series_path(series_id) / "series_bible.json"
    if not bible.exists():
        return JSONResponse({"error": "Series not found"}, status_code=404)
    
    data = json.loads(bible.read_text())
    season_key = str(season_num)
    data.setdefault("seasons", {}).setdefault(season_key, {
        "season_number": season_num,
        "status": "planning",
        "episodes": {},
    })
    
    ep_key = str(episode_num)
    title = req.title or f"Episode {episode_num}"
    
    episode_data = {
        "episode_number": episode_num,
        "title": title,
        "synopsis": req.synopsis,
        "script_raw": req.script_raw,
        "script_enhanced": "",
        "target_duration": req.target_duration,
        "status": "draft",  # draft → scripted → broken_down → generating → assembled → reviewed → complete
        "scenes": [],
        "scene_count": 0,
        "generated_scenes": 0,
        "final_video_path": "",
        "review_notes": "",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    
    data["seasons"][season_key]["episodes"][ep_key] = episode_data
    bible.write_text(json.dumps(data, indent=2))
    
    # Also save episode file separately
    ef = episode_file(series_id, season_num, episode_num)
    ef.write_text(json.dumps(episode_data, indent=2))
    
    # Initialize episode memory
    if _memory_enabled and _memory_store:
        _memory_store.init_episode_memory(series_id, season_num, episode_num)
    
    _prod_log("create", "episode", f"{series_id}/S{season_num}E{episode_num}", {"title": req.title})
    return {"status": "created", "episode": episode_data}

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}")
async def get_episode(series_id: str, season_num: int, episode_num: int):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    return json.loads(ef.read_text())

@router.put("/series/{series_id}/season/{season_num}/episode/{episode_num}")
async def update_episode(series_id: str, season_num: int, episode_num: int, request: Request):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    data = json.loads(ef.read_text())
    updates = await request.json()
    data.update(updates)
    data["updated_at"] = time.time()
    ef.write_text(json.dumps(data, indent=2))
    
    # Also update in series bible
    bible = series_path(series_id) / "series_bible.json"
    if bible.exists():
        bible_data = json.loads(bible.read_text())
        season_key = str(season_num)
        ep_key = str(episode_num)
        if season_key in bible_data.get("seasons", {}) and ep_key in bible_data["seasons"][season_key].get("episodes", {}):
            bible_data["seasons"][season_key]["episodes"][ep_key].update(updates)
            bible_data["seasons"][season_key]["episodes"][ep_key]["updated_at"] = time.time()
            bible.write_text(json.dumps(bible_data, indent=2))
    
    return {"status": "updated"}

# === Script Upload (Large Text) ===

class ScriptUpload(BaseModel):
    script_text: str
    title: str = ""
    synopsis: str = ""

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/script/upload")
async def upload_script(series_id: str, season_num: int, episode_num: int, req: ScriptUpload):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    
    data = json.loads(ef.read_text())
    data["script_raw"] = req.script_text
    if req.title:
        data["title"] = req.title
    if req.synopsis:
        data["synopsis"] = req.synopsis
    data["status"] = "scripted"
    data["updated_at"] = time.time()
    ef.write_text(json.dumps(data, indent=2))
    
    word_count = len(req.script_text.split())
    return {"status": "uploaded", "word_count": word_count, "char_count": len(req.script_text)}

# === Script Enhancement (Rewriter) ===
# Based on Dramaturge: Global Review → Scene-level Review → Hierarchical Coordinated Revision
# And MAViS 3E Principle: Explore, Examine, Enhance

class EnhanceRequest(BaseModel):
    enhancement_level: str = "detailed"  # basic, detailed, cinematic, book-level
    focus_areas: str = ""  # e.g. "character development, world-building, dialogue"

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/script/enhance")
async def enhance_script(series_id: str, season_num: int, episode_num: int, req: EnhanceRequest):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    
    data = json.loads(ef.read_text())
    raw_script = data.get("script_raw", "")
    if not raw_script:
        return JSONResponse({"error": "No script to enhance"}, status_code=400)
    
    # Load series bible for context
    bible = series_path(series_id) / "series_bible.json"
    bible_data = json.loads(bible.read_text()) if bible.exists() else {}
    characters = bible_data.get("characters", {})
    world_bible = bible_data.get("world_bible", "")
    concept = bible_data.get("concept", "")
    
    # Build enhancement prompt based on level
    level_prompts = {
        "basic": "Add more sensory details and improve flow.",
        "detailed": "Expand each scene with rich visual descriptions, character motivations, emotional beats, and environmental details. Add subtext and atmosphere.",
        "cinematic": "Rewrite as a full cinematic screenplay with camera directions, lighting cues, sound design notes, and detailed action descriptions. Every scene should paint a vivid picture for a director.",
        "book-level": "Expand into novel-level prose with deep interior monologues, rich world-building, sensory immersion, thematic layers, and literary quality. Every moment should feel lived-in and real. Include detailed descriptions of settings, character micro-expressions, ambient sounds, and emotional subtext.",
    }
    
    enhancement_prompt = level_prompts.get(req.enhancement_level, level_prompts["detailed"])
    
    # Build character context
    char_context = ""
    if characters:
        char_context = "\n\nCHARACTERS:\n"
        for cid, char in characters.items():
            char_context += f"- {char['name']}: {char.get('appearance', '')} | {char.get('personality', '')}\n"
    
    # Build the enhanced script using rule-based expansion
    # (In production, this would call an LLM API)
    enhanced = enhance_script_rule_based(
        raw_script, 
        enhancement_prompt, 
        char_context, 
        world_bible, 
        concept,
        req.focus_areas
    )
    
    data["script_enhanced"] = enhanced
    data["status"] = "scripted"
    data["enhancement_level"] = req.enhancement_level
    data["updated_at"] = time.time()
    ef.write_text(json.dumps(data, indent=2))
    
    _prod_log("enhance", "episode", f"{series_id}/S{season_num}E{episode_num}",
              {"level": req.enhancement_level, "focus": req.focus_areas})
    return {
        "status": "enhanced",
        "level": req.enhancement_level,
        "original_words": len(raw_script.split()),
        "enhanced_words": len(enhanced.split()),
        "expansion_ratio": f"{len(enhanced.split()) / max(1, len(raw_script.split())):.1f}x",
    }

def enhance_script_rule_based(script: str, enhancement_prompt: str, 
                               char_context: str, world_bible: str, 
                               concept: str, focus_areas: str) -> str:
    """
    Rule-based script enhancement. Expands scripts with cinematic detail.
    In production, this would be replaced with an LLM API call.
    """
    lines = script.strip().split("\n")
    enhanced_lines = []
    
    scene_num = 0
    for line in lines:
        line = line.strip()
        if not line:
            enhanced_lines.append("")
            continue
        
        # Detect scene headings (INT., EXT., SCENE, etc.)
        if re.match(r'^(INT\.|EXT\.|SCENE|CHAPTER|---)', line, re.IGNORECASE):
            scene_num += 1
            enhanced_lines.append(f"\n{'='*60}")
            enhanced_lines.append(f"SCENE {scene_num:03d}")
            enhanced_lines.append(f"{'='*60}")
            enhanced_lines.append(line)
            enhanced_lines.append("")
            # Add cinematic direction
            enhanced_lines.append(f"[CAMERA: Establishing shot. {line}]")
            enhanced_lines.append(f"[LIGHTING: Naturalistic, motivated by scene environment]")
            enhanced_lines.append(f"[SOUND: Ambient environmental audio, subtle tension layer]")
            enhanced_lines.append("")
        elif line.startswith("[") or line.startswith("("):
            # Pass through existing direction notes
            enhanced_lines.append(line)
        else:
            # Regular text - expand with detail cues
            enhanced_lines.append(line)
            # Add subtext/direction for dialogue
            if not line.endswith(".") and not line.endswith("!") and not line.endswith("?"):
                enhanced_lines.append(f"  [Direction: Deliver with measured intensity]")
    
    header = f"""
# ENHANCED SCRIPT
# Enhancement Level: {enhancement_prompt}
# Focus Areas: {focus_areas or 'all'}
# Series Concept: {concept}
{char_context}

# World Bible:
{world_bible[:500] if world_bible else 'N/A'}

"""
    
    return header + "\n".join(enhanced_lines)

# === Scene Breakdown ===
# Based on PenShot: Script → shot-level descriptions
# And MAViS: Structure Guide (scene segmentation) + Content Guide (per-shot content)

class BreakdownRequest(BaseModel):
    scene_duration: int = 5  # seconds per scene
    model: str = "ltx"  # which video model to use
    style: str = "cinematic"
    num_frames: int = 97
    fps: int = 24
    steps: int = 30

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/breakdown")
async def breakdown_episode(series_id: str, season_num: int, episode_num: int, req: BreakdownRequest):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    
    data = json.loads(ef.read_text())
    script = data.get("script_enhanced") or data.get("script_raw", "")
    if not script:
        return JSONResponse({"error": "No script to break down"}, status_code=400)
    
    # Load character info for consistency
    bible = series_path(series_id) / "series_bible.json"
    bible_data = json.loads(bible.read_text()) if bible.exists() else {}
    characters = bible_data.get("characters", {})
    
    # Scan for nested stories (flashbacks, dreams, etc.)
    nested_regions = []
    if _memory_enabled and _narrative_stack:
        nested_regions = _narrative_stack.scan_script_for_nested_stories(script)
    
    # Break script into scenes
    scenes = break_script_into_scenes(
        script, 
        req.scene_duration, 
        data.get("target_duration", 2700),
        characters,
        req.model,
        req.style,
        req.num_frames,
        req.fps,
        req.steps,
    )
    
    # Save scenes and initialize scene memory
    s_dir = scenes_dir(series_id, season_num, episode_num)
    for i, scene in enumerate(scenes):
        scene["scene_number"] = i + 1
        scene["status"] = "pending"  # pending → generating → complete → retake
        scene["video_path"] = ""
        scene["job_id"] = ""
        scene["retake_count"] = 0
        scene["created_at"] = time.time()
        sf = s_dir / f"scene_{i+1:03d}.json"
        sf.write_text(json.dumps(scene, indent=2))
        
        # Initialize scene memory with character/location/tone detection
        if _memory_enabled and _memory_store:
            _memory_store.init_scene_memory(series_id, season_num, episode_num, i + 1, scene)
            
            # Check for nested story markers and push/pop narrative stack
            if _narrative_stack:
                segment = scene.get("script_segment", "")
                nested_start = _narrative_stack.detect_nested_story_start(segment)
                if nested_start:
                    _narrative_stack.push_timeline(
                        series_id, season_num, episode_num, i + 1,
                        nested_start["type"],
                        return_trigger="END " + nested_start["type"].upper()
                    )
                nested_end = _narrative_stack.detect_nested_story_end(segment)
                if nested_end:
                    _narrative_stack.pop_timeline(series_id, season_num, episode_num)
    
    # Update episode
    data["scenes"] = [{"scene_number": s["scene_number"], "status": "pending", "prompt": s["prompt"][:100]} for s in scenes]
    data["scene_count"] = len(scenes)
    data["generated_scenes"] = 0
    data["status"] = "broken_down"
    data["breakdown_settings"] = {
        "scene_duration": req.scene_duration,
        "model": req.model,
        "style": req.style,
        "num_frames": req.num_frames,
        "fps": req.fps,
        "steps": req.steps,
    }
    data["nested_stories_detected"] = nested_regions if nested_regions else []
    data["memory_enabled"] = _memory_enabled
    data["updated_at"] = time.time()
    ef.write_text(json.dumps(data, indent=2))
    
    _prod_log("breakdown", "episode", f"{series_id}/S{season_num}E{episode_num}",
              {"scene_count": len(scenes), "model": req.model, "style": req.style})
    return {
        "status": "broken_down",
        "scene_count": len(scenes),
        "estimated_duration": len(scenes) * req.scene_duration,
        "target_duration": data.get("target_duration", 2700),
    }

def break_script_into_scenes(script: str, scene_duration: int, target_duration: int,
                              characters: dict, model: str, style: str,
                              num_frames: int, fps: int, steps: int) -> list:
    """
    Break a script into generation-ready scene prompts.
    Based on PenShot's approach: maintain character/scene consistency across shots.
    """
    # Parse script into segments
    # Look for scene markers, paragraphs, or natural breaks
    segments = []
    
    # Try to split by scene headers
    scene_pattern = re.compile(r'(?:^|\n)(?:SCENE\s+\d+|INT\.|EXT\.|CHAPTER|---|\*\*\*)', re.IGNORECASE)
    scene_splits = scene_pattern.split(script)
    scene_headers = scene_pattern.findall(script)
    
    if len(scene_splits) > 1:
        # Script has scene headers - use them
        for i, segment in enumerate(scene_splits[1:], 0):
            header = scene_headers[i] if i < len(scene_headers) else ""
            segment = (header + segment).strip()
            if segment:
                segments.append(segment)
    else:
        # No scene headers - split by paragraphs
        paragraphs = [p.strip() for p in script.split("\n\n") if p.strip()]
        if len(paragraphs) <= 1:
            # Split by sentences for very short scripts
            sentences = re.split(r'(?<=[.!?])\s+', script)
            # Group sentences into chunks of ~3-5
            chunk_size = 4
            for i in range(0, len(sentences), chunk_size):
                chunk = " ".join(sentences[i:i+chunk_size])
                if chunk.strip():
                    segments.append(chunk)
        else:
            segments = paragraphs
    
    # Calculate how many scenes we need
    target_scenes = max(target_duration // scene_duration, len(segments))
    
    # If we have fewer segments than needed scenes, subdivide
    while len(segments) < target_scenes:
        new_segments = []
        for seg in segments:
            if len(seg) > 200:
                # Split long segments
                mid = len(seg) // 2
                # Find nearest sentence boundary
                for offset in range(50):
                    if seg[mid + offset] in '.!?' and mid + offset < len(seg):
                        mid = mid + offset + 1
                        break
                    if seg[mid - offset] in '.!?' and mid - offset > 0:
                        mid = mid - offset + 1
                        break
                new_segments.append(seg[:mid].strip())
                new_segments.append(seg[mid:].strip())
            else:
                new_segments.append(seg)
        if len(new_segments) == len(segments):
            break  # Can't subdivide further
        segments = new_segments
    
    # Build scene prompts with character consistency
    scenes = []
    char_names = list(characters.keys()) if characters else []
    
    for i, segment in enumerate(segments):
        # Build visual prompt from script segment
        prompt = build_scene_prompt(segment, characters, style, i)
        
        scene = {
            "prompt": prompt,
            "script_segment": segment,
            "duration": scene_duration,
            "model": model,
            "style": style,
            "num_frames": num_frames,
            "fps": fps,
            "steps": steps,
            "seed": None,
            "transition": "cut" if i > 0 else "none",  # cut, fade, dissolve, wipe
            "transition_duration": 0.5,
        }
        scenes.append(scene)
    
    return scenes

def build_scene_prompt(segment: str, characters: dict, style: str, scene_idx: int) -> str:
    """
    Build a text-to-video prompt from a script segment.
    Maintains character consistency by including character descriptions.
    """
    # Style modifiers
    style_modifiers = {
        "cinematic": "cinematic, dramatic lighting, film still, movie quality, 4k, highly detailed",
        "realistic": "photorealistic, ultra realistic, natural lighting, 8k, professional photo",
        "anime": "anime style, cel shaded, vibrant colors, studio quality, detailed background",
        "documentary": "documentary style, natural lighting, realistic, professional photography",
    }
    modifier = style_modifiers.get(style, style_modifiers["cinematic"])
    
    # Shot types for variety
    shot_types = [
        "wide cinematic shot of",
        "dramatic close-up of",
        "medium shot of",
        "tracking shot of",
        "low angle shot of",
        "aerial view of",
        "over-the-shoulder shot of",
        "close-up detail of",
    ]
    shot = shot_types[scene_idx % len(shot_types)]
    
    # Clean up the segment for prompt use
    clean = re.sub(r'[\[\](){}]', '', segment)
    clean = re.sub(r'^SCENE\s+\d+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'^(INT\.|EXT\.)', '', clean)
    clean = clean.strip()
    
    # Truncate if too long
    if len(clean) > 500:
        clean = clean[:497] + "..."
    
    # Add character context if any character names appear in the segment
    char_context = ""
    if characters:
        for cid, char in characters.items():
            if char["name"].lower() in clean.lower():
                appearance = char.get("appearance", "")
                if appearance:
                    char_context += f" {char['name']} ({appearance})."
    
    prompt = f"{shot} {clean}{char_context}, {modifier}"
    return prompt[:1000]  # Keep within model limits

# === Scene Management ===

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes")
async def get_scenes(series_id: str, season_num: int, episode_num: int):
    s_dir = scenes_dir(series_id, season_num, episode_num)
    scenes = []
    for sf in sorted(s_dir.glob("scene_*.json")):
        scenes.append(json.loads(sf.read_text()))
    return {"scenes": scenes, "count": len(scenes)}

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}")
async def get_scene(series_id: str, season_num: int, episode_num: int, scene_num: int):
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    return json.loads(sf.read_text())

class SceneUpdate(BaseModel):
    prompt: Optional[str] = None
    model: Optional[str] = None
    style: Optional[str] = None
    num_frames: Optional[int] = None
    fps: Optional[int] = None
    steps: Optional[int] = None
    seed: Optional[int] = None
    transition: Optional[str] = None
    transition_duration: Optional[float] = None
    # Full settings support
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    guidance_scale: Optional[float] = None
    guidance_rescale: Optional[float] = None
    solver: Optional[str] = None
    flow_shift: Optional[float] = None
    camera_enabled: Optional[bool] = None
    camera_motion: Optional[str] = None
    camera_speed: Optional[float] = None
    camera_preset: Optional[str] = None
    motion_intensity: Optional[float] = None
    upscale: Optional[int] = None
    upscale_model: Optional[str] = None
    interpolate_fps: Optional[int] = None
    color_grading: Optional[dict] = None
    effects: Optional[dict] = None
    codec: Optional[str] = None
    crf: Optional[int] = None
    preset: Optional[str] = None
    tune: Optional[str] = None
    audio: Optional[bool] = None
    native_audio: Optional[bool] = None
    tts_text: Optional[str] = None
    tts_voice: Optional[str] = None
    ambient_prompt: Optional[str] = None
    music_prompt: Optional[str] = None
    settings: Optional[dict] = None

@router.put("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}")
async def update_scene(series_id: str, season_num: int, episode_num: int, scene_num: int, req: SceneUpdate):
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    data = json.loads(sf.read_text())
    for field, value in req.dict(exclude_none=True).items():
        data[field] = value
    sf.write_text(json.dumps(data, indent=2))
    return {"status": "updated"}

# === Batch Generation ===
# Sends scenes to GPU backend for generation

class BatchGenerateRequest(BaseModel):
    gpu_backend_url: str = ""
    start_scene: int = 1
    end_scene: int = 0  # 0 = all
    overwrite: bool = False

# Track generation progress
generation_jobs = {}  # episode_key → {status, current_scene, total_scenes, errors}

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/generate")
async def batch_generate(series_id: str, season_num: int, episode_num: int, req: BatchGenerateRequest):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    
    ep_data = json.loads(ef.read_text())
    s_dir = scenes_dir(series_id, season_num, episode_num)
    
    # Get GPU backend URL
    gpu_url = req.gpu_backend_url
    if not gpu_url:
        # Try to load from config
        config_file = APP_DIR / "config.json"
        if config_file.exists():
            cfg = json.loads(config_file.read_text())
            gpu_url = cfg.get("gpu_backend_url", "")
    
    if not gpu_url:
        return JSONResponse({"error": "No GPU backend URL configured"}, status_code=400)
    
    # Get scenes to generate
    scene_files = sorted(s_dir.glob("scene_*.json"))
    end_scene = req.end_scene if req.end_scene > 0 else len(scene_files)
    
    scenes_to_gen = []
    for i in range(req.start_scene - 1, min(end_scene, len(scene_files))):
        scene_data = json.loads(scene_files[i].read_text())
        if req.overwrite or scene_data.get("status") != "complete":
            scenes_to_gen.append((i + 1, scene_data, scene_files[i]))
    
    if not scenes_to_gen:
        return {"status": "no_work", "message": "All scenes already generated"}
    
    # Start generation in background thread
    episode_key = f"{series_id}_s{season_num}_e{episode_num}"
    generation_jobs[episode_key] = {
        "status": "generating",
        "current_scene": 0,
        "total_scenes": len(scenes_to_gen),
        "completed": 0,
        "failed": 0,
        "errors": [],
        "started_at": time.time(),
    }
    
    # Update episode status
    ep_data["status"] = "generating"
    ef.write_text(json.dumps(ep_data, indent=2))
    
    _prod_log("generate_batch", "episode", f"{series_id}/S{season_num}E{episode_num}",
              {"scene_count": len(scenes_to_gen), "start": req.start_scene, "end": end_scene})
    
    def run_generation():
        for idx, (scene_num, scene_data, sf_path) in enumerate(scenes_to_gen):
            try:
                generation_jobs[episode_key]["current_scene"] = scene_num
                
                # Inject memory context into prompt before generation
                if _memory_enabled and _memory_store:
                    memory_context = _memory_store.build_context_for_scene(
                        series_id, season_num, episode_num, scene_num, scene_data
                    )
                    if memory_context:
                        scene_data["prompt"] = scene_data["prompt"] + f" [{memory_context}]"
                    
                    # Apply learning adjustments
                    if _learning_engine:
                        adjustments = _learning_engine.get_adjustments_for_scene(
                            series_id, season_num, episode_num, scene_num, scene_data
                        )
                        if adjustments:
                            scene_data["prompt"] = _learning_engine.apply_adjustments_to_prompt(
                                scene_data["prompt"], adjustments
                            )
                            # Save adjustments used in scene memory
                            scene_mem = _memory_store.load_scene_memory(
                                series_id, season_num, episode_num, scene_num
                            )
                            if scene_mem:
                                scene_mem["learnings_applied"] = adjustments
                                _memory_store.save_scene_memory(
                                    series_id, season_num, episode_num, scene_num, scene_mem
                                )
                
                # Send to GPU backend
                payload = json.dumps({
                    "prompt": scene_data["prompt"],
                    "model": scene_data.get("model", "ltx"),
                    "style": scene_data.get("style", "cinematic"),
                    "num_frames": scene_data.get("num_frames", 97),
                    "fps": scene_data.get("fps", 24),
                    "steps": scene_data.get("steps", 30),
                    "seed": scene_data.get("seed"),
                }).encode("utf-8")
                
                request = urllib.request.Request(
                    f"{gpu_url}/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
                    method="POST"
                )
                
                with urllib.request.urlopen(request, timeout=30) as resp:
                    result = json.loads(resp.read().decode())
                    job_id = result.get("job_id")
                
                if not job_id:
                    raise Exception("No job_id returned from backend")
                
                # Poll for completion
                video_path = None
                max_wait = 600  # 10 minutes per scene
                start_wait = time.time()
                
                while time.time() - start_wait < max_wait:
                    try:
                        status_req = urllib.request.Request(
                            f"{gpu_url}/api/status/{job_id}",
                            headers={"User-Agent": "SoulIllusions/1.0"}
                        )
                        with urllib.request.urlopen(status_req, timeout=10) as resp:
                            status_data = json.loads(resp.read().decode())
                        
                        if status_data.get("status") == "complete":
                            # Download the video
                            dl_req = urllib.request.Request(
                                f"{gpu_url}/api/download/{job_id}",
                                headers={"User-Agent": "SoulIllusions/1.0"}
                            )
                            with urllib.request.urlopen(dl_req, timeout=120) as resp:
                                video_bytes = resp.read()
                            
                            # Save locally
                            local_path = s_dir / f"scene_{scene_num:03d}.mp4"
                            local_path.write_bytes(video_bytes)
                            video_path = str(local_path)
                            break
                        elif status_data.get("status") == "failed":
                            raise Exception(status_data.get("error", "Generation failed"))
                    except Exception as e:
                        if "timeout" not in str(e).lower():
                            time.sleep(5)
                
                if video_path:
                    scene_data["status"] = "complete"
                    scene_data["video_path"] = video_path
                    scene_data["job_id"] = job_id
                    sf_path.write_text(json.dumps(scene_data, indent=2))
                    generation_jobs[episode_key]["completed"] += 1
                    
                    # Update persistent memory after scene generation
                    if _memory_enabled and _memory_store:
                        _memory_store.update_memory_after_scene(
                            series_id, season_num, episode_num, scene_num,
                            scene_data, video_path
                        )
                        
                        # Run quality assessment and store learnings
                        if _learning_engine:
                            _learning_engine.assess_scene_quality(
                                series_id, season_num, episode_num, scene_num,
                                scene_data, video_path
                            )
                else:
                    scene_data["status"] = "failed"
                    scene_data["error"] = "Timed out waiting for generation"
                    sf_path.write_text(json.dumps(scene_data, indent=2))
                    generation_jobs[episode_key]["failed"] += 1
                    generation_jobs[episode_key]["errors"].append(f"Scene {scene_num}: timeout")
                
            except Exception as e:
                scene_data["status"] = "failed"
                scene_data["error"] = str(e)
                sf_path.write_text(json.dumps(scene_data, indent=2))
                generation_jobs[episode_key]["failed"] += 1
                generation_jobs[episode_key]["errors"].append(f"Scene {scene_num}: {str(e)}")
        
        # Update episode status
        ef2 = episode_file(series_id, season_num, episode_num)
        ep = json.loads(ef2.read_text())
        completed = generation_jobs[episode_key]["completed"]
        total = generation_jobs[episode_key]["total_scenes"]
        
        if completed > 0:
            ep["generated_scenes"] = completed
            ep["status"] = "assembled" if completed == total else "partial"
        else:
            ep["status"] = "failed"
        
        ep["updated_at"] = time.time()
        ef2.write_text(json.dumps(ep, indent=2))
        
        generation_jobs[episode_key]["status"] = "complete"
        generation_jobs[episode_key]["finished_at"] = time.time()
    
    thread = threading.Thread(target=run_generation, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "total_scenes": len(scenes_to_gen),
        "episode_key": episode_key,
    }

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/generate/status")
async def generation_status(series_id: str, season_num: int, episode_num: int):
    episode_key = f"{series_id}_s{season_num}_e{episode_num}"
    if episode_key not in generation_jobs:
        return {"status": "idle", "message": "No generation in progress"}
    return generation_jobs[episode_key]

# === Scene Retake ===

class RetakeRequest(BaseModel):
    gpu_backend_url: str = ""
    prompt_override: Optional[str] = None
    seed: Optional[int] = None

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/retake")
async def retake_scene(series_id: str, season_num: int, episode_num: int, scene_num: int, req: RetakeRequest):
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    
    scene_data = json.loads(sf.read_text())
    
    # Get GPU URL
    gpu_url = req.gpu_backend_url
    if not gpu_url:
        config_file = APP_DIR / "config.json"
        if config_file.exists():
            cfg = json.loads(config_file.read_text())
            gpu_url = cfg.get("gpu_backend_url", "")
    
    if not gpu_url:
        return JSONResponse({"error": "No GPU backend URL"}, status_code=400)
    
    # Update prompt if overridden
    if req.prompt_override:
        scene_data["prompt"] = req.prompt_override
    if req.seed is not None:
        scene_data["seed"] = req.seed
    
    # Inject memory context for retake
    if _memory_enabled and _memory_store:
        memory_context = _memory_store.build_context_for_scene(
            series_id, season_num, episode_num, scene_num, scene_data
        )
        if memory_context and "[MEMORY" not in scene_data["prompt"]:
            scene_data["prompt"] = scene_data["prompt"] + f" [{memory_context}]"
        
        if _learning_engine:
            adjustments = _learning_engine.get_adjustments_for_scene(
                series_id, season_num, episode_num, scene_num, scene_data
            )
            if adjustments:
                scene_data["prompt"] = _learning_engine.apply_adjustments_to_prompt(
                    scene_data["prompt"], adjustments
                )
    
    scene_data["status"] = "generating"
    scene_data["retake_count"] = scene_data.get("retake_count", 0) + 1
    sf.write_text(json.dumps(scene_data, indent=2))
    
    # Generate in background
    def run_retake():
        try:
            payload_dict = {
                "prompt": scene_data["prompt"],
                "model": scene_data.get("model", "ltx"),
                "style": scene_data.get("style", "cinematic"),
                "num_frames": scene_data.get("num_frames", 97),
                "fps": scene_data.get("fps", 24),
                "steps": scene_data.get("steps", 30),
                "seed": scene_data.get("seed"),
            }
            # Include full settings if available
            scene_settings = scene_data.get("settings", {})
            if scene_settings:
                payload_dict.update(scene_settings)
            # Also include top-level advanced fields
            for key in ["negative_prompt", "width", "height", "guidance_scale", "guidance_rescale",
                         "solver", "flow_shift", "camera_enabled", "camera_motion", "camera_speed",
                         "motion_intensity", "upscale", "upscale_model", "interpolate_fps",
                         "color_grading", "effects", "codec", "crf", "preset", "tune",
                         "audio", "native_audio", "tts_text", "tts_voice", "ambient_prompt", "music_prompt"]:
                if key in scene_data and key not in payload_dict:
                    payload_dict[key] = scene_data[key]
            payload = json.dumps(payload_dict).encode("utf-8")
            
            request = urllib.request.Request(
                f"{gpu_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(request, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                job_id = result.get("job_id")
            
            # Poll
            max_wait = 600
            start_wait = time.time()
            while time.time() - start_wait < max_wait:
                try:
                    status_req = urllib.request.Request(
                        f"{gpu_url}/api/status/{job_id}",
                        headers={"User-Agent": "SoulIllusions/1.0"}
                    )
                    with urllib.request.urlopen(status_req, timeout=10) as resp:
                        status_data = json.loads(resp.read().decode())
                    
                    if status_data.get("status") == "complete":
                        dl_req = urllib.request.Request(
                            f"{gpu_url}/api/download/{job_id}",
                            headers={"User-Agent": "SoulIllusions/1.0"}
                        )
                        with urllib.request.urlopen(dl_req, timeout=120) as resp:
                            video_bytes = resp.read()
                        
                        local_path = scenes_dir(series_id, season_num, episode_num) / f"scene_{scene_num:03d}.mp4"
                        local_path.write_bytes(video_bytes)
                        
                        scene_data["status"] = "complete"
                        scene_data["video_path"] = str(local_path)
                        scene_data["job_id"] = job_id
                        sf.write_text(json.dumps(scene_data, indent=2))
                        
                        # Update memory and assess quality after retake
                        if _memory_enabled and _memory_store:
                            _memory_store.update_memory_after_scene(
                                series_id, season_num, episode_num, scene_num,
                                scene_data, str(local_path)
                            )
                            if _learning_engine:
                                _learning_engine.assess_scene_quality(
                                    series_id, season_num, episode_num, scene_num,
                                    scene_data, str(local_path)
                                )
                        return
                    elif status_data.get("status") == "failed":
                        scene_data["status"] = "failed"
                        scene_data["error"] = status_data.get("error", "Failed")
                        sf.write_text(json.dumps(scene_data, indent=2))
                        return
                except:
                    pass
                time.sleep(5)
            
            scene_data["status"] = "failed"
            scene_data["error"] = "Timed out"
            sf.write_text(json.dumps(scene_data, indent=2))
        except Exception as e:
            scene_data["status"] = "failed"
            scene_data["error"] = str(e)
            sf.write_text(json.dumps(scene_data, indent=2))
    
    thread = threading.Thread(target=run_retake, daemon=True)
    thread.start()
    
    _prod_log("retake_scene", "scene", f"{series_id}/S{season_num}E{episode_num}/scene_{scene_num}",
              {"retake_count": scene_data["retake_count"], "prompt_override": bool(req.prompt_override)}, "started")
    
    return {"status": "retake_started", "retake_count": scene_data["retake_count"]}

# === Scene Video Serving ===

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/video")
async def serve_scene_video(series_id: str, season_num: int, episode_num: int, scene_num: int):
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    data = json.loads(sf.read_text())
    video_path = data.get("video_path", "")
    if not video_path or not os.path.exists(video_path):
        return JSONResponse({"error": "Video not generated yet"}, status_code=404)
    return FileResponse(video_path, media_type="video/mp4")

# === Episode Assembly ===
# Stitch all scene videos together with transitions

class AssembleRequest(BaseModel):
    output_format: str = "mp4"
    add_transitions: bool = True
    transition_type: str = "xfade"  # xfade, cut, fade
    add_title_card: bool = True
    title_text: str = ""

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/assemble")
async def assemble_episode(series_id: str, season_num: int, episode_num: int, req: AssembleRequest):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    
    s_dir = scenes_dir(series_id, season_num, episode_num)
    scene_files = sorted(s_dir.glob("scene_*.json"))
    
    # Collect completed scene videos
    video_paths = []
    for sf in scene_files:
        data = json.loads(sf.read_text())
        if data.get("status") == "complete" and data.get("video_path") and os.path.exists(data["video_path"]):
            video_paths.append(data["video_path"])
    
    if not video_paths:
        return JSONResponse({"error": "No completed scenes to assemble"}, status_code=400)
    
    # Create file list for ffmpeg
    list_path = s_dir / "concat_list.txt"
    with open(list_path, "w") as f:
        for vp in video_paths:
            # Escape for ffmpeg
            escaped = vp.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    
    # Output path
    output_path = episode_path(series_id, season_num, episode_num) / f"episode_final.mp4"
    
    # Try ffmpeg concat
    try:
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        
        if result.returncode != 0:
            # Fallback: re-encode
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_path),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac",
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=600)
        
        if result.returncode == 0 and output_path.exists():
            # Update episode
            ep_data = json.loads(ef.read_text())
            ep_data["final_video_path"] = str(output_path)
            ep_data["status"] = "assembled"
            ep_data["assembled_scenes"] = len(video_paths)
            ep_data["updated_at"] = time.time()
            ef.write_text(json.dumps(ep_data, indent=2))
            
            _prod_log("assemble_episode", "episode", f"{series_id}/S{season_num}E{episode_num}",
                      {"scenes": len(video_paths), "output": str(output_path)}, "success")
            
            return {
                "status": "assembled",
                "scenes_assembled": len(video_paths),
                "output_path": str(output_path),
                "file_size_mb": f"{output_path.stat().st_size / 1024 / 1024:.1f} MB",
            }
        else:
            _prod_log("assemble_episode", "episode", f"{series_id}/S{season_num}E{episode_num}",
                      {"error": "ffmpeg failed"}, "failure")
            return JSONResponse({
                "error": "ffmpeg assembly failed",
                "stderr": result.stderr.decode()[:500]
            }, status_code=500)
    except FileNotFoundError:
        return JSONResponse({"error": "ffmpeg not found. Install ffmpeg to assemble episodes."}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/video")
async def serve_episode_video(series_id: str, season_num: int, episode_num: int):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    data = json.loads(ef.read_text())
    video_path = data.get("final_video_path", "")
    if not video_path or not os.path.exists(video_path):
        return JSONResponse({"error": "Episode not assembled yet"}, status_code=404)
    return FileResponse(video_path, media_type="video/mp4")

# === Self-Review System ===
# Based on Dramaturge: Global Review → Scene-level Review → Hierarchical Coordinated Revision
# After a season is complete, analyze it and suggest improvements

class ReviewRequest(BaseModel):
    review_scope: str = "season"  # episode, season
    review_depth: str = "thorough"  # quick, standard, thorough

@router.post("/series/{series_id}/season/{season_num}/review")
async def review_season(series_id: str, season_num: int, req: ReviewRequest):
    bible = series_path(series_id) / "series_bible.json"
    if not bible.exists():
        return JSONResponse({"error": "Series not found"}, status_code=404)
    
    bible_data = json.loads(bible.read_text())
    season_key = str(season_num)
    if season_key not in bible_data.get("seasons", {}):
        return JSONResponse({"error": "Season not found"}, status_code=404)
    
    season = bible_data["seasons"][season_key]
    episodes = season.get("episodes", {})
    
    # Gather all episode data
    episode_reviews = []
    for ep_key, ep_summary in episodes.items():
        ef = episode_file(series_id, season_num, int(ep_key))
        if ef.exists():
            ep_data = json.loads(ef.read_text())
            
            # Analyze scenes
            s_dir = scenes_dir(series_id, season_num, int(ep_key))
            scene_files = sorted(s_dir.glob("scene_*.json"))
            scenes_info = []
            for sf in scene_files:
                scene = json.loads(sf.read_text())
                scenes_info.append({
                    "scene_number": scene["scene_number"],
                    "status": scene.get("status"),
                    "prompt": scene["prompt"][:200],
                    "retake_count": scene.get("retake_count", 0),
                    "has_video": bool(scene.get("video_path") and os.path.exists(scene.get("video_path", ""))),
                })
            
            episode_reviews.append({
                "episode_number": int(ep_key),
                "title": ep_data.get("title", ""),
                "status": ep_data.get("status"),
                "scene_count": ep_data.get("scene_count", 0),
                "generated_scenes": ep_data.get("generated_scenes", 0),
                "scenes": scenes_info,
                "has_final_video": bool(ep_data.get("final_video_path") and os.path.exists(ep_data.get("final_video_path", ""))),
            })
    
    # Generate review notes (rule-based, would use LLM in production)
    review_notes = generate_review_notes(episode_reviews, req.review_depth, bible_data)
    
    # Save review
    review_path = season_path(series_id, season_num) / "season_review.json"
    review_data = {
        "season": season_num,
        "review_scope": req.review_scope,
        "review_depth": req.review_depth,
        "episodes_reviewed": len(episode_reviews),
        "episode_reviews": episode_reviews,
        "review_notes": review_notes,
        "reviewed_at": time.time(),
    }
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(json.dumps(review_data, indent=2))
    
    # Update season status
    bible_data["seasons"][season_key]["status"] = "reviewed"
    bible_data["seasons"][season_key]["review_notes"] = review_notes
    bible.write_text(json.dumps(bible_data, indent=2))
    
    return review_data

def generate_review_notes(episode_reviews: list, depth: str, bible_data: dict) -> dict:
    """Generate review notes based on episode analysis."""
    notes = {
        "overall_assessment": "",
        "strengths": [],
        "weaknesses": [],
        "suggestions": [],
        "scene_quality": [],
        "pacing_notes": [],
        "consistency_issues": [],
    }
    
    total_scenes = sum(ep["scene_count"] for ep in episode_reviews)
    total_generated = sum(ep["generated_scenes"] for ep in episode_reviews)
    total_retakes = sum(
        s["retake_count"] for ep in episode_reviews for s in ep["scenes"]
    )
    
    # Overall
    completion_rate = (total_generated / max(1, total_scenes)) * 100
    notes["overall_assessment"] = (
        f"Season review: {len(episode_reviews)} episodes, {total_scenes} total scenes, "
        f"{total_generated} generated ({completion_rate:.0f}% completion), "
        f"{total_retakes} total retakes."
    )
    
    # Strengths
    if completion_rate > 90:
        notes["strengths"].append("High scene completion rate")
    if total_retakes < total_scenes * 0.1:
        notes["strengths"].append("Low retake rate - scenes generating well on first pass")
    
    # Weaknesses
    failed_scenes = sum(1 for ep in episode_reviews for s in ep["scenes"] if s["status"] == "failed")
    if failed_scenes > 0:
        notes["weaknesses"].append(f"{failed_scenes} scenes failed generation and need retakes")
    
    incomplete_eps = [ep for ep in episode_reviews if ep["status"] != "complete"]
    if incomplete_eps:
        notes["weaknesses"].append(f"{len(incomplete_eps)} episodes not fully complete")
    
    # Suggestions for next season
    notes["suggestions"].append("Review prompts for failed scenes and adjust for clarity")
    notes["suggestions"].append("Consider increasing scene duration for dialogue-heavy episodes")
    notes["suggestions"].append("Add character reference images for better consistency")
    
    if depth == "thorough":
        # Per-episode pacing analysis
        for ep in episode_reviews:
            if ep["scene_count"] > 0:
                avg_retakes = sum(s["retake_count"] for s in ep["scenes"]) / ep["scene_count"]
                if avg_retakes > 1:
                    notes["pacing_notes"].append(
                        f"Episode {ep['episode_number']}: High retake rate ({avg_retakes:.1f}/scene) - "
                        f"prompts may need refinement"
                    )
    
    return notes

# === SoulTube Upload ===
# Upload finished episode to SoulTube via the soulmate API

class SoulTubeUploadRequest(BaseModel):
    soultube_api_url: str = ""  # e.g., https://soulmate.example.com
    api_key: str = ""
    title: str = ""
    description: str = ""
    tags: str = "AI series, In Time Television, sci-fi"
    category: str = "Sci-Fi"

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/upload")
async def upload_to_soultube(series_id: str, season_num: int, episode_num: int, req: SoulTubeUploadRequest):
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    
    ep_data = json.loads(ef.read_text())
    video_path = ep_data.get("final_video_path", "")
    
    if not video_path or not os.path.exists(video_path):
        return JSONResponse({"error": "Episode video not assembled"}, status_code=400)
    
    if not req.soultube_api_url:
        return JSONResponse({"error": "SoulTube API URL required"}, status_code=400)
    
    title = req.title or f"{ep_data.get('title', 'Episode ' + str(episode_num))} - S{season_num}E{episode_num}"
    description = req.description or ep_data.get("synopsis", "")
    
    # Upload via multipart form
    try:
        import mimetypes
        boundary = uuid.uuid4().hex
        filename = os.path.basename(video_path)
        
        with open(video_path, "rb") as f:
            video_bytes = f.read()
        
        # Build multipart form data
        body_parts = []
        # Video file
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
        body_parts.append(b"Content-Type: video/mp4\r\n\r\n")
        body_parts.append(video_bytes)
        body_parts.append(b"\r\n")
        # Title
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="title"\r\n\r\n'.encode())
        body_parts.append(f"{title}\r\n".encode())
        # Description
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="description"\r\n\r\n'.encode())
        body_parts.append(f"{description}\r\n".encode())
        # Tags
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="tags"\r\n\r\n'.encode())
        body_parts.append(f"{req.tags}\r\n".encode())
        # End
        body_parts.append(f"--{boundary}--\r\n".encode())
        
        body = b"".join(body_parts)
        
        upload_req = urllib.request.Request(
            f"{req.soultube_api_url}/v1/soultube/upload",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "SoulIllusions/1.0",
            },
            method="POST"
        )
        
        if req.api_key:
            upload_req.add_header("Authorization", f"Bearer {req.api_key}")
        
        with urllib.request.urlopen(upload_req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
        
        # Update episode with SoulTube ID
        ep_data["soultube_id"] = result.get("id")
        ep_data["soultube_uploaded_at"] = time.time()
        ep_data["status"] = "published"
        ef.write_text(json.dumps(ep_data, indent=2))
        
        return {"status": "uploaded", "soultube_id": result.get("id"), "title": title}
    except Exception as e:
        return JSONResponse({"error": f"Upload failed: {str(e)}"}, status_code=500)

# === Episode Reordering ===

class ReorderRequest(BaseModel):
    new_order: List[int]  # list of scene numbers in new order

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/reorder")
async def reorder_scenes(series_id: str, season_num: int, episode_num: int, req: ReorderRequest):
    s_dir = scenes_dir(series_id, season_num, episode_num)
    
    # Load all scenes
    scenes = {}
    for sf in s_dir.glob("scene_*.json"):
        data = json.loads(sf.read_text())
        scenes[data["scene_number"]] = data
    
    # Reassign scene numbers
    for new_idx, old_num in enumerate(req.new_order, 1):
        if old_num in scenes:
            scenes[old_num]["scene_number"] = new_idx
            # Write to new file
            new_path = s_dir / f"scene_{new_idx:03d}.json"
            new_path.write_text(json.dumps(scenes[old_num], indent=2))
    
    # Delete old files that aren't in new positions
    current_nums = set(req.new_order)
    for sf in s_dir.glob("scene_*.json"):
        num = int(sf.stem.split("_")[1])
        if num > len(req.new_order):
            sf.unlink()
    
    return {"status": "reordered", "new_scene_count": len(req.new_order)}


# ============================================================================
# NARRATIVE MEMORY API ENDPOINTS
# ============================================================================

@router.get("/series/{series_id}/memory")
async def get_series_memory(series_id: str):
    """Get the persistent memory state for a series."""
    if not _memory_enabled or not _memory_store:
        return JSONResponse({"error": "Memory engine not enabled"}, status_code=503)
    return _memory_store.load_series_memory(series_id)

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/memory")
async def get_episode_memory(series_id: str, season_num: int, episode_num: int):
    """Get the memory state for a specific episode."""
    if not _memory_enabled or not _memory_store:
        return JSONResponse({"error": "Memory engine not enabled"}, status_code=503)
    return _memory_store.load_episode_memory(series_id, season_num, episode_num)

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/memory")
async def get_scene_memory(series_id: str, season_num: int, episode_num: int, scene_num: int):
    """Get the memory state for a specific scene."""
    if not _memory_enabled or not _memory_store:
        return JSONResponse({"error": "Memory engine not enabled"}, status_code=503)
    mem = _memory_store.load_scene_memory(series_id, season_num, episode_num, scene_num)
    if not mem:
        return JSONResponse({"error": "Scene memory not found"}, status_code=404)
    return mem

@router.put("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/memory")
async def update_scene_memory(series_id: str, season_num: int, episode_num: int, scene_num: int, request: Request):
    """Manually update scene memory (override character states, location, etc.)."""
    if not _memory_enabled or not _memory_store:
        return JSONResponse({"error": "Memory engine not enabled"}, status_code=503)
    mem = _memory_store.load_scene_memory(series_id, season_num, episode_num, scene_num)
    if not mem:
        return JSONResponse({"error": "Scene memory not found"}, status_code=404)
    updates = await request.json()
    mem.update(updates)
    _memory_store.save_scene_memory(series_id, season_num, episode_num, scene_num, mem)
    return {"status": "updated"}


# === Narrative Stack Endpoints ===

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/narrative-stack")
async def get_narrative_stack(series_id: str, season_num: int, episode_num: int):
    """Get the current narrative stack state for an episode."""
    if not _memory_enabled or not _narrative_stack:
        return JSONResponse({"error": "Narrative stack not enabled"}, status_code=503)
    return _narrative_stack.get_current_timeline(series_id, season_num, episode_num)

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/narrative-stack/push")
async def push_narrative_stack(series_id: str, season_num: int, episode_num: int, request: Request):
    """Push a new timeline onto the narrative stack (enter a nested story)."""
    if not _memory_enabled or not _narrative_stack:
        return JSONResponse({"error": "Narrative stack not enabled"}, status_code=503)
    body = await request.json()
    nested_type = body.get("type", "nested")
    return_trigger = body.get("return_trigger", "")
    scene_num = body.get("scene_number", 0)
    return _narrative_stack.push_timeline(
        series_id, season_num, episode_num, scene_num, nested_type, return_trigger
    )

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/narrative-stack/pop")
async def pop_narrative_stack(series_id: str, season_num: int, episode_num: int):
    """Pop the narrative stack (return from a nested story to the main timeline)."""
    if not _memory_enabled or not _narrative_stack:
        return JSONResponse({"error": "Narrative stack not enabled"}, status_code=503)
    return _narrative_stack.pop_timeline(series_id, season_num, episode_num)

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/narrative-stack/scan")
async def scan_script_for_nested(series_id: str, season_num: int, episode_num: int):
    """Scan an episode's script for nested story regions."""
    if not _memory_enabled or not _narrative_stack:
        return JSONResponse({"error": "Narrative stack not enabled"}, status_code=503)
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    data = json.loads(ef.read_text())
    script = data.get("script_enhanced") or data.get("script_raw", "")
    if not script:
        return JSONResponse({"error": "No script found"}, status_code=400)
    regions = _narrative_stack.scan_script_for_nested_stories(script)
    return {"nested_regions": regions, "count": len(regions)}


# === Urgency Router Endpoints ===

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/urgency")
async def get_urgency_threads(series_id: str, season_num: int, episode_num: int):
    """Get urgency scores for all active timeline threads."""
    if not _memory_enabled or not _urgency_router:
        return JSONResponse({"error": "Urgency router not enabled"}, status_code=503)
    return _urgency_router.get_thread_urgency(series_id, season_num, episode_num)

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/urgency/check-cut")
async def check_urgency_cut(series_id: str, season_num: int, episode_num: int, request: Request):
    """Check if the system should cut to a different timeline thread based on urgency."""
    if not _memory_enabled or not _urgency_router:
        return JSONResponse({"error": "Urgency router not enabled"}, status_code=503)
    body = await request.json()
    next_scene_data = body.get("scene_data", {})
    result = _urgency_router.should_cut(series_id, season_num, episode_num, next_scene_data)
    return result if result else {"should_cut": False}

@router.put("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/urgency")
async def set_scene_urgency(series_id: str, season_num: int, episode_num: int, scene_num: int, request: Request):
    """Manually set the urgency score for a scene."""
    if not _memory_enabled or not _urgency_router:
        return JSONResponse({"error": "Urgency router not enabled"}, status_code=503)
    body = await request.json()
    urgency = body.get("urgency", 0.5)
    _urgency_router.set_scene_urgency(series_id, season_num, episode_num, scene_num, urgency)
    return {"status": "set", "scene_number": scene_num, "urgency": urgency}


# === Learning Engine Endpoints ===

@router.get("/series/{series_id}/learnings")
async def get_learning_summary(series_id: str, season_num: int = 0):
    """Get a summary of learnings for a series (optionally filtered by season)."""
    if not _memory_enabled or not _learning_engine:
        return JSONResponse({"error": "Learning engine not enabled"}, status_code=503)
    sn = season_num if season_num > 0 else None
    return _learning_engine.get_learning_summary(series_id, sn)

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/assessment")
async def get_scene_assessment(series_id: str, season_num: int, episode_num: int, scene_num: int):
    """Get the quality assessment for a specific scene."""
    if not _memory_enabled or not _memory_store:
        return JSONResponse({"error": "Memory engine not enabled"}, status_code=503)
    scene_mem = _memory_store.load_scene_memory(series_id, season_num, episode_num, scene_num)
    if not scene_mem or not scene_mem.get("quality_assessment"):
        return JSONResponse({"error": "No assessment available"}, status_code=404)
    return scene_mem["quality_assessment"]

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/adjustments")
async def get_scene_adjustments(series_id: str, season_num: int, episode_num: int, scene_num: int):
    """Get the learning adjustments that would be applied to a scene."""
    if not _memory_enabled or not _learning_engine:
        return JSONResponse({"error": "Learning engine not enabled"}, status_code=503)
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    scene_data = json.loads(sf.read_text())
    adjustments = _learning_engine.get_adjustments_for_scene(
        series_id, season_num, episode_num, scene_num, scene_data
    )
    return {"adjustments": adjustments, "count": len(adjustments)}

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/assess")
async def assess_scene(series_id: str, season_num: int, episode_num: int, scene_num: int):
    """Manually trigger a quality assessment for a scene."""
    if not _memory_enabled or not _learning_engine:
        return JSONResponse({"error": "Learning engine not enabled"}, status_code=503)
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    scene_data = json.loads(sf.read_text())
    return _learning_engine.assess_scene_quality(
        series_id, season_num, episode_num, scene_num, scene_data, scene_data.get("video_path", "")
    )

@router.get("/memory/status")
async def memory_engine_status():
    """Check if the narrative memory engine is enabled and running."""
    return {
        "enabled": _memory_enabled,
        "memory_store": _memory_store is not None,
        "narrative_stack": _narrative_stack is not None,
        "urgency_router": _urgency_router is not None,
        "learning_engine": _learning_engine is not None,
    }


# === Scene Settings Management ===

class SceneSettingsRequest(BaseModel):
    settings: dict

@router.put("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/settings")
async def set_scene_settings(series_id: str, season_num: int, episode_num: int, scene_num: int, req: SceneSettingsRequest):
    """Set comprehensive settings for a specific scene."""
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    data = json.loads(sf.read_text())
    data["settings"] = req.settings
    sf.write_text(json.dumps(data, indent=2))
    _prod_log("set_scene_settings", "scene", f"{series_id}/S{season_num}E{episode_num}/scene_{scene_num}",
              {"settings_keys": list(req.settings.keys())})
    return {"status": "updated", "scene_num": scene_num}

@router.get("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/settings")
async def get_scene_settings(series_id: str, season_num: int, episode_num: int, scene_num: int):
    """Get settings for a specific scene."""
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    data = json.loads(sf.read_text())
    return {"settings": data.get("settings", {}), "scene_num": scene_num}

class BatchSettingsRequest(BaseModel):
    settings: dict
    start_scene: int = 1
    end_scene: int = 0

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/batch-settings")
async def batch_apply_settings(series_id: str, season_num: int, episode_num: int, req: BatchSettingsRequest):
    """Apply settings to multiple scenes at once."""
    s_dir = scenes_dir(series_id, season_num, episode_num)
    if not s_dir.exists():
        return JSONResponse({"error": "Episode scenes not found"}, status_code=404)
    updated = 0
    for sf in sorted(s_dir.glob("scene_*.json")):
        data = json.loads(sf.read_text())
        scene_num = data.get("scene_number", 0)
        if req.start_scene and scene_num < req.start_scene:
            continue
        if req.end_scene and scene_num > req.end_scene:
            continue
        data["settings"] = req.settings
        sf.write_text(json.dumps(data, indent=2))
        updated += 1
    _prod_log("batch_settings", "episode", f"{series_id}/S{season_num}E{episode_num}",
              {"scenes_updated": updated, "settings_keys": list(req.settings.keys())})
    return {"status": "updated", "scenes_updated": updated}


# === Color Grading Post-Processing ===

class ColorGradeRequest(BaseModel):
    contrast: float = 0.0
    saturation: float = 0.0
    temperature: float = 0.0
    brightness: float = 0.0
    hue: float = 0.0
    gamma: float = 0.0
    vignette_enabled: bool = False
    vignette_intensity: float = 0.3
    film_grain_enabled: bool = False
    film_grain_amount: float = 0.15
    sharpen_enabled: bool = False
    sharpen_amount: float = 0.5

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/color-grade")
async def color_grade_scene(series_id: str, season_num: int, episode_num: int, scene_num: int, req: ColorGradeRequest):
    """Apply color grading to a scene's generated video using FFmpeg."""
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    data = json.loads(sf.read_text())
    video_path = data.get("video_path", "")
    if not video_path or not os.path.exists(video_path):
        return JSONResponse({"error": "Video not generated yet"}, status_code=404)
    
    filters = []
    if req.contrast != 0: filters.append(f"eq=contrast={1.0 + req.contrast}")
    if req.brightness != 0 or req.gamma != 0:
        filters.append(f"eq=brightness={req.brightness:.2f}:gamma={1.0 + req.gamma:.2f}")
    if req.saturation != 0: filters.append(f"eq=saturation={1.0 + req.saturation:.2f}")
    if req.temperature != 0:
        filters.append(f"colorbalance=rs={req.temperature * 0.3}:bs={-req.temperature * 0.3}")
    if req.hue != 0: filters.append(f"hue=h={req.hue * 180}")
    if req.vignette_enabled: filters.append(f"vignette=PI/{5 + req.vignette_intensity * 10}")
    if req.film_grain_enabled: filters.append(f"noise=alls={int(req.film_grain_amount * 100)}:allf=t")
    if req.sharpen_enabled: filters.append(f"unsharp=5:5:{req.sharpen_amount * 1.5}:5:5:{req.sharpen_amount * 1.5}")
    
    if not filters:
        return {"status": "no_changes", "message": "No color grading parameters set"}
    
    output_path = video_path.replace(".mp4", "_graded.mp4")
    filter_str = ",".join(filters)
    
    try:
        import subprocess
        cmd = ["ffmpeg", "-y", "-i", video_path, "-filter:v", filter_str, "-c:a", "copy", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and os.path.exists(output_path):
            data["video_path"] = output_path
            data["color_graded"] = True
            sf.write_text(json.dumps(data, indent=2))
            _prod_log("color_grade", "scene", f"{series_id}/S{season_num}E{episode_num}/scene_{scene_num}",
                      {"filters": filter_str})
            return {"status": "graded", "output_path": output_path}
        return JSONResponse({"error": "ffmpeg failed", "stderr": result.stderr[:500]}, status_code=500)
    except FileNotFoundError:
        return JSONResponse({"error": "ffmpeg not found"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# === Transition Configuration ===

class TransitionConfigRequest(BaseModel):
    transition_type: str = "xfade"
    duration: float = 0.5

@router.put("/series/{series_id}/season/{season_num}/episode/{episode_num}/transitions")
async def set_episode_transitions(series_id: str, season_num: int, episode_num: int, req: TransitionConfigRequest):
    """Set transition type and duration for all scene boundaries in an episode."""
    ef = episode_file(series_id, season_num, episode_num)
    if not ef.exists():
        return JSONResponse({"error": "Episode not found"}, status_code=404)
    ep_data = json.loads(ef.read_text())
    ep_data["transition_config"] = {"type": req.transition_type, "duration": req.duration}
    ef.write_text(json.dumps(ep_data, indent=2))
    _prod_log("set_transitions", "episode", f"{series_id}/S{season_num}E{episode_num}",
              {"type": req.transition_type, "duration": req.duration})
    return {"status": "updated", "transition_type": req.transition_type, "duration": req.duration}


# === Audio Generation/Attachment ===

class AudioRequest(BaseModel):
    tts_text: Optional[str] = None
    tts_voice: str = "narrator_male"
    ambient_prompt: Optional[str] = None
    music_prompt: Optional[str] = None
    music_volume: float = 0.5
    ambient_volume: float = 0.3

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/audio")
async def attach_audio_to_scene(series_id: str, season_num: int, episode_num: int, scene_num: int, req: AudioRequest):
    """Attach audio configuration to a scene (TTS, ambient, music)."""
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    data = json.loads(sf.read_text())
    audio_config = {}
    if req.tts_text:
        audio_config["tts_text"] = req.tts_text
        audio_config["tts_voice"] = req.tts_voice
    if req.ambient_prompt:
        audio_config["ambient_prompt"] = req.ambient_prompt
        audio_config["ambient_volume"] = req.ambient_volume
    if req.music_prompt:
        audio_config["music_prompt"] = req.music_prompt
        audio_config["music_volume"] = req.music_volume
    data["audio_config"] = audio_config
    sf.write_text(json.dumps(data, indent=2))
    _prod_log("attach_audio", "scene", f"{series_id}/S{season_num}E{episode_num}/scene_{scene_num}",
              {"has_tts": bool(req.tts_text), "has_ambient": bool(req.ambient_prompt), "has_music": bool(req.music_prompt)})
    return {"status": "attached", "audio_config": audio_config}


# === Shot Matching ===

class ShotMatchRequest(BaseModel):
    reference_scene: int

@router.post("/series/{series_id}/season/{season_num}/episode/{episode_num}/scenes/{scene_num}/shot-match")
async def shot_match_scene(series_id: str, season_num: int, episode_num: int, scene_num: int, req: ShotMatchRequest):
    """Match color/contrast of a scene to a reference scene using FFmpeg."""
    sf = scene_file(series_id, season_num, episode_num, scene_num)
    if not sf.exists():
        return JSONResponse({"error": "Scene not found"}, status_code=404)
    ref_sf = scene_file(series_id, season_num, episode_num, req.reference_scene)
    if not ref_sf.exists():
        return JSONResponse({"error": "Reference scene not found"}, status_code=404)
    
    data = json.loads(sf.read_text())
    ref_data = json.loads(ref_sf.read_text())
    video_path = data.get("video_path", "")
    ref_path = ref_data.get("video_path", "")
    
    if not video_path or not os.path.exists(video_path):
        return JSONResponse({"error": "Scene video not generated"}, status_code=404)
    if not ref_path or not os.path.exists(ref_path):
        return JSONResponse({"error": "Reference scene video not generated"}, status_code=404)
    
    output_path = video_path.replace(".mp4", "_matched.mp4")
    
    try:
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", ref_path,
            "-filter_complex", "[0:v][1:v]blend=difference",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and os.path.exists(output_path):
            data["video_path"] = output_path
            data["shot_matched"] = True
            data["matched_to_scene"] = req.reference_scene
            sf.write_text(json.dumps(data, indent=2))
            _prod_log("shot_match", "scene", f"{series_id}/S{season_num}E{episode_num}/scene_{scene_num}",
                      {"reference": req.reference_scene})
            return {"status": "matched", "output_path": output_path, "reference_scene": req.reference_scene}
        return JSONResponse({"error": "ffmpeg failed", "stderr": result.stderr[:500]}, status_code=500)
    except FileNotFoundError:
        return JSONResponse({"error": "ffmpeg not found"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# === Settings Schema Info ===

@router.get("/settings/options")
async def get_production_settings_options():
    """Return available setting options for the production suite."""
    try:
        from settings_schema import (
            ASPECT_RATIOS, QUALITY_MODES, CAMERA_PRESETS, SCHEDULERS,
            CODECS, STYLE_PRESETS, TRANSITION_TYPES, UPSCALE_MODELS,
            TTS_VOICES, SETTING_PRESETS, ENCODING_PRESETS, TUNE_OPTIONS
        )
        return {
            "aspect_ratios": {k: v["label"] for k, v in ASPECT_RATIOS.items()},
            "quality_modes": {k: v["label"] for k, v in QUALITY_MODES.items()},
            "camera_presets": {k: v["label"] for k, v in CAMERA_PRESETS.items()},
            "schedulers": SCHEDULERS,
            "codecs": {k: v["label"] for k, v in CODECS.items()},
            "styles": STYLE_PRESETS,
            "transitions": TRANSITION_TYPES,
            "upscale_models": UPSCALE_MODELS,
            "tts_voices": TTS_VOICES,
            "setting_presets": {k: v["label"] for k, v in SETTING_PRESETS.items()},
            "encoding_presets": ENCODING_PRESETS,
            "tune_options": TUNE_OPTIONS,
        }
    except ImportError:
        return {"error": "settings_schema not available"}

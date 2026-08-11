"""
Narrative Memory Engine for SoulIllusions Production Suite

Implements three interconnected systems:
1. Persistent Memory — layered (series/season/episode/scene) world-state tracking
2. Narrative Stack — push/pop timeline states for nested stories (flashbacks, dreams)
3. Recursive Learning — post-generation quality assessment and auto-adjustment

Inspired by:
- Mem0 (layered memory architecture)
- MemGPT (OS-style memory hierarchy with paging)
- CANVAS (world-state modeling: characters/locations/objects)
- VideoMemory (entity-centric Dynamic Memory Bank)
- StoryMem (keyframe memory bank for cross-shot consistency)
- Memento (subject-reconstruction-guided memory)
- CoAgent (Global Context Manager + verify loop)
- VISTA (self-improving generate→critique→rewrite loop)
- CCC (structured critique→coach calibration)
- OneStory (adaptive memory with semantic frame selection)
- DOME (temporal knowledge graphs for conflict detection)
"""
import json
import time
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple


# ============================================================================
# PHASE 1: PERSISTENT MEMORY STORE
# ============================================================================

class MemoryStore:
    """
    Layered persistent memory for narrative consistency.
    
    Layers (longest-lived to shortest-lived):
    - Series: world rules, character definitions, visual style anchors
    - Season: season arc state, relationship evolution, resolved plot threads
    - Episode: per-episode character states, location tracking, emotional arcs
    - Scene: working memory — who's on screen, what just happened, visual state
    
    All stored as JSON files for inspection and version control.
    """
    
    def __init__(self, base_data_dir: Path):
        self.base_dir = base_data_dir
    
    # --- Path helpers ---
    
    def series_memory_path(self, series_id: str) -> Path:
        p = self.base_dir / series_id / "memory"
        p.mkdir(parents=True, exist_ok=True)
        return p / "series_memory.json"
    
    def season_memory_path(self, series_id: str, season_num: int) -> Path:
        p = self.base_dir / series_id / f"season_{season_num:02d}" / "memory"
        p.mkdir(parents=True, exist_ok=True)
        return p / "season_memory.json"
    
    def episode_memory_path(self, series_id: str, season_num: int, episode_num: int) -> Path:
        p = self.base_dir / series_id / f"season_{season_num:02d}" / f"episode_{episode_num:02d}" / "memory"
        p.mkdir(parents=True, exist_ok=True)
        return p / "episode_memory.json"
    
    def scene_memory_path(self, series_id: str, season_num: int, episode_num: int, scene_num: int) -> Path:
        p = self.base_dir / series_id / f"season_{season_num:02d}" / f"episode_{episode_num:02d}" / "memory"
        p.mkdir(parents=True, exist_ok=True)
        return p / f"scene_{scene_num:03d}_memory.json"
    
    # --- Series-level memory (long-term) ---
    
    def init_series_memory(self, series_id: str, series_bible: dict) -> dict:
        """Initialize series memory from the series bible."""
        mem = {
            "series_id": series_id,
            "world_state": {
                "locations": {},
                "objects": {},
                "rules": {},
                "time_of_day_defaults": {},
            },
            "characters": {},
            "visual_anchors": {},
            "plot_threads": [],
            "style_anchors": {
                "cinematography": "cinematic, dramatic lighting",
                "color_palette": "",
                "recurring_visual_motifs": [],
            },
            "narrative_stack": [],
            "learning_log": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        
        # Seed characters from series bible
        for char_id, char_data in series_bible.get("characters", {}).items():
            mem["characters"][char_id] = {
                "name": char_data.get("name", ""),
                "appearance": char_data.get("appearance", ""),
                "personality": char_data.get("personality", ""),
                "background": char_data.get("background", ""),
                "voice_profile": char_data.get("voice_profile", ""),
                "current_state": "introduced",
                "emotional_state": "neutral",
                "location": "unknown",
                "knowledge": [],
                "relationships": {},
                "evolution_log": [],
            }
            mem["visual_anchors"][char_id] = {
                "last_reference_image": None,
                "last_appearance_description": char_data.get("appearance", ""),
                "first_seen_scene": None,
                "last_seen_scene": None,
                "scene_count": 0,
            }
        
        # Seed world state from world bible
        world_bible = series_bible.get("world_bible", "")
        if world_bible:
            locations = self._parse_locations_from_bible(world_bible)
            for loc_id, loc_desc in locations.items():
                mem["world_state"]["locations"][loc_id] = {
                    "name": loc_desc["name"],
                    "description": loc_desc["description"],
                    "visual_description": loc_desc.get("visual", ""),
                    "last_seen_scene": None,
                    "last_reference_frame": None,
                }
        
        self.save_series_memory(series_id, mem)
        return mem
    
    def load_series_memory(self, series_id: str) -> dict:
        p = self.series_memory_path(series_id)
        if not p.exists():
            return self._empty_series_memory(series_id)
        return json.loads(p.read_text())
    
    def save_series_memory(self, series_id: str, mem: dict):
        mem["updated_at"] = time.time()
        self.series_memory_path(series_id).write_text(json.dumps(mem, indent=2))
    
    def _empty_series_memory(self, series_id: str) -> dict:
        return {
            "series_id": series_id,
            "world_state": {"locations": {}, "objects": {}, "rules": {}},
            "characters": {},
            "visual_anchors": {},
            "plot_threads": [],
            "style_anchors": {},
            "narrative_stack": [],
            "learning_log": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
    
    # --- Season-level memory (mid-term) ---
    
    def init_season_memory(self, series_id: str, season_num: int) -> dict:
        mem = {
            "series_id": series_id,
            "season_number": season_num,
            "arc_state": "planning",
            "character_relationships": {},
            "resolved_threads": [],
            "unresolved_threads": [],
            "episode_summaries": {},
            "season_learnings": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.save_season_memory(series_id, season_num, mem)
        return mem
    
    def load_season_memory(self, series_id: str, season_num: int) -> dict:
        p = self.season_memory_path(series_id, season_num)
        if not p.exists():
            return self.init_season_memory(series_id, season_num)
        return json.loads(p.read_text())
    
    def save_season_memory(self, series_id: str, season_num: int, mem: dict):
        mem["updated_at"] = time.time()
        self.season_memory_path(series_id, season_num).write_text(json.dumps(mem, indent=2))
    
    # --- Episode-level memory (short-term) ---
    
    def init_episode_memory(self, series_id: str, season_num: int, episode_num: int) -> dict:
        series_mem = self.load_series_memory(series_id)
        
        mem = {
            "series_id": series_id,
            "season_number": season_num,
            "episode_number": episode_num,
            "character_states": {},
            "location_states": {},
            "active_plot_threads": [],
            "emotional_arc": [],
            "visual_continuity": {
                "time_of_day": "unknown",
                "lighting": "unknown",
                "weather": "unknown",
                "color_tone": "unknown",
            },
            "scene_history": [],
            "last_scene_state": None,
            "narrative_stack": [],
            "active_timeline": "main",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        
        # Copy current character states from series memory
        for char_id, char_data in series_mem.get("characters", {}).items():
            mem["character_states"][char_id] = {
                "name": char_data.get("name", ""),
                "emotional_state": char_data.get("emotional_state", "neutral"),
                "location": char_data.get("location", "unknown"),
                "appearance": char_data.get("last_appearance_description", 
                                            char_data.get("appearance", "")),
                "on_screen": False,
                "last_scene": None,
            }
        
        self.save_episode_memory(series_id, season_num, episode_num, mem)
        return mem
    
    def load_episode_memory(self, series_id: str, season_num: int, episode_num: int) -> dict:
        p = self.episode_memory_path(series_id, season_num, episode_num)
        if not p.exists():
            return self.init_episode_memory(series_id, season_num, episode_num)
        return json.loads(p.read_text())
    
    def save_episode_memory(self, series_id: str, season_num: int, episode_num: int, mem: dict):
        mem["updated_at"] = time.time()
        self.episode_memory_path(series_id, season_num, episode_num).write_text(json.dumps(mem, indent=2))
    
    # --- Scene-level memory (working memory) ---
    
    def init_scene_memory(self, series_id: str, season_num: int, episode_num: int, 
                          scene_num: int, scene_data: dict) -> dict:
        ep_mem = self.load_episode_memory(series_id, season_num, episode_num)
        series_mem = self.load_series_memory(series_id)
        
        mem = {
            "series_id": series_id,
            "season_number": season_num,
            "episode_number": episode_num,
            "scene_number": scene_num,
            "timeline_id": ep_mem.get("active_timeline", "main"),
            "characters_on_screen": [],
            "characters_referenced": [],
            "location": "unknown",
            "time_of_day": ep_mem.get("visual_continuity", {}).get("time_of_day", "unknown"),
            "lighting": ep_mem.get("visual_continuity", {}).get("lighting", "unknown"),
            "emotional_tone": "neutral",
            "urgency_score": 0.5,
            "prompt_context": "",
            "visual_anchors_used": {},
            "learnings_applied": [],
            "quality_assessment": None,
            "created_at": time.time(),
        }
        
        # Detect characters in the scene prompt
        prompt = scene_data.get("prompt", "")
        script_segment = scene_data.get("script_segment", "")
        combined_text = (prompt + " " + script_segment).lower()
        
        for char_id, char_data in series_mem.get("characters", {}).items():
            char_name = char_data.get("name", "").lower()
            if char_name and char_name in combined_text:
                mem["characters_on_screen"].append(char_id)
                mem["visual_anchors_used"][char_id] = {
                    "appearance": char_data.get("appearance", ""),
                    "emotional_state": char_data.get("emotional_state", "neutral"),
                }
        
        # Detect location from script
        location = self._detect_location(script_segment, series_mem)
        if location:
            mem["location"] = location
        
        # Detect time of day
        time_of_day = self._detect_time_of_day(script_segment)
        if time_of_day:
            mem["time_of_day"] = time_of_day
        
        # Detect emotional tone
        mem["emotional_tone"] = self._detect_emotional_tone(script_segment)
        
        # Detect urgency
        mem["urgency_score"] = self._detect_urgency(script_segment)
        
        self.save_scene_memory(series_id, season_num, episode_num, scene_num, mem)
        return mem
    
    def load_scene_memory(self, series_id: str, season_num: int, episode_num: int, scene_num: int) -> dict:
        p = self.scene_memory_path(series_id, season_num, episode_num, scene_num)
        if not p.exists():
            return {}
        return json.loads(p.read_text())
    
    def save_scene_memory(self, series_id: str, season_num: int, episode_num: int, scene_num: int, mem: dict):
        self.scene_memory_path(series_id, season_num, episode_num, scene_num).write_text(json.dumps(mem, indent=2))
    
    # --- Memory context injection ---
    
    def build_context_for_scene(self, series_id: str, season_num: int, episode_num: int, 
                                 scene_num: int, scene_data: dict) -> str:
        """
        Build a memory context string to inject into a scene's generation prompt.
        This is the core function that ensures consistency across scenes.
        """
        series_mem = self.load_series_memory(series_id)
        ep_mem = self.load_episode_memory(series_id, season_num, episode_num)
        scene_mem = self.load_scene_memory(series_id, season_num, episode_num, scene_num)
        
        # If scene memory doesn't exist yet, create it
        if not scene_mem:
            scene_mem = self.init_scene_memory(series_id, season_num, episode_num, scene_num, scene_data)
        
        context_parts = []
        
        # 1. Character visual anchors (who's on screen and what they look like)
        if scene_mem.get("characters_on_screen"):
            char_contexts = []
            for char_id in scene_mem["characters_on_screen"]:
                char = series_mem.get("characters", {}).get(char_id, {})
                anchor = series_mem.get("visual_anchors", {}).get(char_id, {})
                appearance = anchor.get("last_appearance_description") or char.get("appearance", "")
                emotional = char.get("emotional_state", "neutral")
                if appearance:
                    char_contexts.append(f"{char.get('name', char_id)}: {appearance}, feeling {emotional}")
            if char_contexts:
                context_parts.append("CHARACTERS: " + "; ".join(char_contexts))
        
        # 2. Location continuity
        location = scene_mem.get("location", "unknown")
        if location != "unknown":
            loc_data = series_mem.get("world_state", {}).get("locations", {}).get(location, {})
            loc_desc = loc_data.get("visual_description") or loc_data.get("description", "")
            if loc_desc:
                context_parts.append(f"LOCATION: {loc_data.get('name', location)} - {loc_desc}")
        
        # 3. Visual continuity from previous scene
        last_state = ep_mem.get("last_scene_state")
        if last_state:
            cont_parts = []
            if last_state.get("time_of_day") and last_state["time_of_day"] != "unknown":
                cont_parts.append(f"time: {last_state['time_of_day']}")
            if last_state.get("lighting") and last_state["lighting"] != "unknown":
                cont_parts.append(f"lighting: {last_state['lighting']}")
            if last_state.get("emotional_tone") and last_state["emotional_tone"] != "neutral":
                cont_parts.append(f"mood: {last_state['emotional_tone']}")
            if cont_parts:
                context_parts.append("CONTINUITY: " + ", ".join(cont_parts))
        
        # 4. Narrative stack context (if we're in a nested story)
        stack = ep_mem.get("narrative_stack", [])
        if stack:
            current = stack[-1]
            context_parts.append(f"TIMELINE: {current.get('timeline_id', 'nested')} (depth {current.get('depth', 1)})")
            if current.get("emotional_tone"):
                context_parts.append(f"NESTED MOOD: {current['emotional_tone']}")
        
        # 5. Style anchors
        style = series_mem.get("style_anchors", {})
        if style.get("cinematography"):
            context_parts.append(f"STYLE: {style['cinematography']}")
        
        # 6. Learnings (from recursive learning system)
        learnings = self._get_relevant_learnings(series_mem, scene_mem)
        if learnings:
            context_parts.append("ADJUSTMENTS: " + "; ".join(learnings[:3]))
        
        return " | ".join(context_parts) if context_parts else ""
    
    def update_memory_after_scene(self, series_id: str, season_num: int, episode_num: int,
                                   scene_num: int, scene_data: dict, video_path: str = ""):
        """
        Update all memory layers after a scene has been generated.
        This is called after each scene completes in batch generation.
        """
        series_mem = self.load_series_memory(series_id)
        ep_mem = self.load_episode_memory(series_id, season_num, episode_num)
        scene_mem = self.load_scene_memory(series_id, season_num, episode_num, scene_num)
        
        if not scene_mem:
            scene_mem = self.init_scene_memory(series_id, season_num, episode_num, scene_num, scene_data)
        
        # Update character visual anchors
        for char_id in scene_mem.get("characters_on_screen", []):
            anchor = series_mem.get("visual_anchors", {}).get(char_id, {})
            anchor["last_seen_scene"] = f"S{season_num}E{episode_num}C{scene_num}"
            anchor["scene_count"] = anchor.get("scene_count", 0) + 1
            if video_path:
                anchor["last_reference_frame"] = video_path
            series_mem.setdefault("visual_anchors", {})[char_id] = anchor
            
            # Update character state
            char = series_mem.get("characters", {}).get(char_id, {})
            char["last_seen_scene"] = scene_num
            series_mem["characters"][char_id] = char
        
        # Update location tracking
        location = scene_mem.get("location", "unknown")
        if location != "unknown":
            loc = series_mem.get("world_state", {}).get("locations", {}).get(location, {})
            loc["last_seen_scene"] = f"S{season_num}E{episode_num}C{scene_num}"
            if video_path:
                loc["last_reference_frame"] = video_path
            series_mem.setdefault("world_state", {}).setdefault("locations", {})[location] = loc
        
        # Update episode-level last scene state
        ep_mem["last_scene_state"] = {
            "scene_number": scene_num,
            "time_of_day": scene_mem.get("time_of_day", "unknown"),
            "lighting": scene_mem.get("lighting", "unknown"),
            "emotional_tone": scene_mem.get("emotional_tone", "neutral"),
            "location": scene_mem.get("location", "unknown"),
            "characters_on_screen": scene_mem.get("characters_on_screen", []),
            "timeline_id": scene_mem.get("timeline_id", "main"),
        }
        
        ep_mem.setdefault("scene_history", []).append({
            "scene_number": scene_num,
            "timeline_id": scene_mem.get("timeline_id", "main"),
            "location": scene_mem.get("location", "unknown"),
            "emotional_tone": scene_mem.get("emotional_tone", "neutral"),
            "urgency_score": scene_mem.get("urgency_score", 0.5),
            "characters": scene_mem.get("characters_on_screen", []),
            "timestamp": time.time(),
        })
        
        # Update visual continuity
        ep_mem["visual_continuity"] = {
            "time_of_day": scene_mem.get("time_of_day", ep_mem.get("visual_continuity", {}).get("time_of_day", "unknown")),
            "lighting": scene_mem.get("lighting", ep_mem.get("visual_continuity", {}).get("lighting", "unknown")),
            "weather": ep_mem.get("visual_continuity", {}).get("weather", "unknown"),
            "color_tone": ep_mem.get("visual_continuity", {}).get("color_tone", "unknown"),
        }
        
        # Save all layers
        self.save_series_memory(series_id, series_mem)
        self.save_episode_memory(series_id, season_num, episode_num, ep_mem)
        
        # Update scene memory with video path
        scene_mem["video_path"] = video_path
        self.save_scene_memory(series_id, season_num, episode_num, scene_num, scene_mem)
    
    # --- Parsing helpers ---
    
    def _parse_locations_from_bible(self, world_bible: str) -> dict:
        """Extract locations from the world bible text."""
        locations = {}
        # Look for patterns like "**Dayton Zone**" or "Dayton Zone -"
        patterns = [
            r'\*\*([^*]+(?:Zone|zone|district|District|area|Area|city|City))\*\*[-:]\s*([^\n]+)',
            r'^\d+\.\s+\*\*([^*]+)\*\*\s*[-:]\s*([^\n]+)',
            r'(INT\.|EXT\.)\s+([^-]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, world_bible, re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    name = match[-2] if len(match) > 1 else match[0]
                    desc = match[-1] if len(match) > 1 else ""
                else:
                    name = match
                    desc = ""
                loc_id = name.lower().replace(" ", "_").replace("-", "_")[:30]
                if loc_id not in locations:
                    locations[loc_id] = {
                        "name": name.strip(),
                        "description": desc.strip(),
                        "visual": "",
                    }
        
        return locations
    
    def _detect_location(self, text: str, series_mem: dict) -> str:
        """Detect which location a scene takes place in."""
        text_lower = text.lower()
        locations = series_mem.get("world_state", {}).get("locations", {})
        
        # Also check for INT./EXT. markers
        int_ext_match = re.search(r'(?:INT\.|EXT\.)\s+([^-]+?)(?:\s*-|\s+DAY|\s+NIGHT|\s+DAWN|\s+DUSK|\s+EVENING|\s+MORNING|$)', text, re.IGNORECASE)
        if int_ext_match:
            loc_name = int_ext_match.group(1).strip().lower().replace(" ", "_")
            for loc_id, loc_data in locations.items():
                if loc_name in loc_id or loc_id in loc_name:
                    return loc_id
            # Return as new location
            return loc_name[:30]
        
        # Check against known locations
        for loc_id, loc_data in locations.items():
            loc_name = loc_data.get("name", "").lower()
            if loc_name and loc_name in text_lower:
                return loc_id
        
        return "unknown"
    
    def _detect_time_of_day(self, text: str) -> str:
        """Detect time of day from scene text."""
        text_lower = text.lower()
        time_markers = {
            "dawn": ["dawn", "sunrise", "first light"],
            "morning": ["morning", "early morning"],
            "day": ["day", "daytime", "afternoon", "noon", "midday"],
            "evening": ["evening", "dusk", "sunset", "twilight"],
            "night": ["night", "midnight", "dark", "late night"],
        }
        
        for time_id, markers in time_markers.items():
            for marker in markers:
                if marker in text_lower:
                    return time_id
        return "unknown"
    
    def _detect_emotional_tone(self, text: str) -> str:
        """Detect the dominant emotional tone of a scene."""
        text_lower = text.lower()
        tone_scores = {
            "tense": ["tension", "danger", "threat", "escape", "run", "chase", "fear", "panic", "alarm"],
            "sad": ["sad", "cry", "tears", "grief", "loss", "death", "died", "alone", "lonely", "miss"],
            "angry": ["angry", "rage", "furious", "shout", "scream", "fight", "attack"],
            "happy": ["happy", "joy", "laugh", "smile", "celebrate", "love", "warm"],
            "mysterious": ["mystery", "secret", "hidden", "unknown", "shadow", "whisper", "enigmatic"],
            "hopeful": ["hope", "future", "dream", "possibility", "maybe", "could be"],
            "desperate": ["desperate", "last", "final", "only option", "no choice", "running out"],
            "calm": ["calm", "quiet", "peaceful", "still", "serene", "gentle"],
            "intense": ["intense", "critical", "urgent", "now", "immediately", "seconds"],
        }
        
        best_tone = "neutral"
        best_score = 0
        for tone, keywords in tone_scores.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_tone = tone
        
        return best_tone
    
    def _detect_urgency(self, text: str) -> float:
        """
        Detect dramatic urgency of a scene (0.0 = calm, 1.0 = maximum tension).
        Used by the UrgencyRouter for dynamic scene cutting.
        """
        text_lower = text.lower()
        urgency = 0.3  # baseline
        
        # High urgency indicators
        high_urgency_words = ["run", "chase", "escape", "danger", "alarm", "police", "time-keeper", 
                              "caught", "hurry", "now", "seconds", "dying", "death", "fight",
                              "attack", "escape", "flee", "urgent", "critical", "crash", "explode"]
        for word in high_urgency_words:
            if word in text_lower:
                urgency += 0.1
        
        # Low urgency indicators
        low_urgency_words = ["calm", "quiet", "peaceful", "still", "rest", "sleep", "wait",
                             "think", "remember", "reflect", "memory", "dream"]
        for word in low_urgency_words:
            if word in text_lower:
                urgency -= 0.05
        
        # Exclamation marks increase urgency
        urgency += min(text.count("!") * 0.05, 0.2)
        
        # Questions slightly increase tension
        urgency += min(text.count("?") * 0.02, 0.1)
        
        return max(0.0, min(1.0, urgency))
    
    def _get_relevant_learnings(self, series_mem: dict, scene_mem: dict) -> List[str]:
        """Retrieve relevant learnings from the learning log for a scene."""
        learnings = series_mem.get("learning_log", [])
        if not learnings:
            return []
        
        relevant = []
        scene_location = scene_mem.get("location", "unknown")
        scene_tone = scene_mem.get("emotional_tone", "neutral")
        scene_chars = scene_mem.get("characters_on_screen", [])
        
        for entry in learnings[-20:]:  # Last 20 learnings
            # Match by location
            if entry.get("location") == scene_location and entry.get("adjustment"):
                relevant.append(entry["adjustment"])
            # Match by tone
            elif entry.get("emotional_tone") == scene_tone and entry.get("adjustment"):
                relevant.append(entry["adjustment"])
            # Match by character
            elif any(c in entry.get("characters", []) for c in scene_chars) and entry.get("adjustment"):
                relevant.append(entry["adjustment"])
        
        return relevant


# ============================================================================
# PHASE 2: NARRATIVE STACK
# ============================================================================

class NarrativeStack:
    """
    Manages a stack of timeline states for nested stories.
    
    When a flashback/dream/side-story begins:
    1. PUSH current timeline state onto the stack
    2. Create a new timeline context for the nested story
    3. Generate scenes within the nested story
    4. When the nested story ends, POP the stack
    5. Restore the previous timeline state for seamless continuation
    
    The stack supports arbitrary nesting depth (flashback within a flashback).
    """
    
    # Markers that indicate a nested story is beginning
    NESTED_STORY_START_MARKERS = [
        r'(?:FLASHBACK|flashback)\s*(?:BEGIN|start|to)',
        r'(?:DREAM|dream)\s*(?:SEQUENCE|begin|start)',
        r'(?:MEMORY|memory)\s*(?:of|sequence|begins)',
        r'(?:FLASH|flash)\s*[-–]\s*(?:BACK|back)',
        r'(?:INT\.|EXT\.)\s+.*\s*[-–]\s*(?:FLASHBACK|flashback|DREAM|dream|MEMORY|memory)',
        r'(?:YEARS AGO|years ago|LONG AGO|long ago|BEFORE|before)',
        r'(?:REMEMBER|remember|RECALL|recall)\s*[-–:]',
        r'(?:VISION|vision|HALLUCINATION|hallucination)',
        r'(?:STORY WITHIN|story within|SIDE STORY|side story|PARALLEL|parallel)',
    ]
    
    # Markers that indicate a nested story is ending
    NESTED_STORY_END_MARKERS = [
        r'(?:FLASHBACK|flashback)\s*(?:END|over|complete)',
        r'(?:DREAM|dream)\s*(?:ENDS|over|complete)',
        r'(?:MEMORY|memory)\s*(?:ENDS|over|complete)',
        r'(?:RETURN|return|BACK|back)\s*(?:TO|to)\s*(?:PRESENT|present|NOW|now|REALITY|reality)',
        r'(?:END|end)\s*(?:FLASHBACK|flashback|DREAM|dream|MEMORY|memory|VISION|vision)',
        r'(?:BACK|back)\s*(?:TO|to)\s*(?:REALITY|reality|PRESENT|present)',
        r'(?:AWAKE|awake|WAKE|wake)\s*(?:UP|up)',
    ]
    
    def __init__(self, memory_store: MemoryStore):
        self.mem = memory_store
    
    def detect_nested_story_start(self, script_segment: str) -> Optional[dict]:
        """Check if a script segment starts a nested story."""
        for pattern in self.NESTED_STORY_START_MARKERS:
            match = re.search(pattern, script_segment, re.IGNORECASE)
            if match:
                # Determine the type
                matched_text = match.group(0).lower()
                if "flashback" in matched_text or "flash-back" in matched_text:
                    story_type = "flashback"
                elif "dream" in matched_text:
                    story_type = "dream"
                elif "memory" in matched_text or "remember" in matched_text or "recall" in matched_text:
                    story_type = "memory"
                elif "vision" in matched_text or "hallucination" in matched_text:
                    story_type = "vision"
                elif "parallel" in matched_text or "side story" in matched_text:
                    story_type = "parallel"
                else:
                    story_type = "nested"
                
                return {
                    "type": story_type,
                    "marker": match.group(0),
                    "position": match.start(),
                }
        return None
    
    def detect_nested_story_end(self, script_segment: str) -> Optional[dict]:
        """Check if a script segment ends a nested story."""
        for pattern in self.NESTED_STORY_END_MARKERS:
            match = re.search(pattern, script_segment, re.IGNORECASE)
            if match:
                return {
                    "marker": match.group(0),
                    "position": match.start(),
                }
        return None
    
    def push_timeline(self, series_id: str, season_num: int, episode_num: int,
                      scene_num: int, nested_type: str, return_trigger: str = "") -> dict:
        """
        Push the current timeline state onto the narrative stack.
        Called when entering a nested story (flashback, dream, etc.)
        """
        ep_mem = self.mem.load_episode_memory(series_id, season_num, episode_num)
        series_mem = self.mem.load_series_memory(series_id)
        
        # Capture current state
        current_state = {
            "timeline_id": ep_mem.get("active_timeline", "main"),
            "scene_number": scene_num,
            "character_states": dict(ep_mem.get("character_states", {})),
            "visual_state": dict(ep_mem.get("visual_continuity", {})),
            "last_scene_state": dict(ep_mem.get("last_scene_state", {}) or {}),
            "emotional_tone": (ep_mem.get("last_scene_state") or {}).get("emotional_tone", "neutral"),
            "urgency_score": 0.5,
            "return_trigger": return_trigger,
            "depth": len(ep_mem.get("narrative_stack", [])) + 1,
            "pushed_at_scene": scene_num,
            "pushed_at_time": time.time(),
        }
        
        # Push onto episode stack
        ep_mem.setdefault("narrative_stack", []).append(current_state)
        
        # Create new timeline ID
        new_timeline_id = f"{nested_type}_{len(ep_mem['narrative_stack'])}"
        ep_mem["active_timeline"] = new_timeline_id
        
        # Reset visual continuity for the nested story
        ep_mem["visual_continuity"] = {
            "time_of_day": "unknown",
            "lighting": "unknown",
            "weather": "unknown",
            "color_tone": "unknown",
        }
        
        # Also push onto series-level stack for cross-episode tracking
        series_mem.setdefault("narrative_stack", []).append({
            "series_id": series_id,
            "season": season_num,
            "episode": episode_num,
            "scene": scene_num,
            "timeline_id": new_timeline_id,
            "parent_timeline": current_state["timeline_id"],
            "type": nested_type,
            "depth": current_state["depth"],
            "pushed_at": time.time(),
        })
        
        self.mem.save_episode_memory(series_id, season_num, episode_num, ep_mem)
        self.mem.save_series_memory(series_id, series_mem)
        
        return {
            "status": "pushed",
            "new_timeline_id": new_timeline_id,
            "depth": current_state["depth"],
            "parent_timeline": current_state["timeline_id"],
        }
    
    def pop_timeline(self, series_id: str, season_num: int, episode_num: int) -> dict:
        """
        Pop the narrative stack and restore the previous timeline state.
        Called when a nested story ends and we return to the main timeline.
        """
        ep_mem = self.mem.load_episode_memory(series_id, season_num, episode_num)
        series_mem = self.mem.load_series_memory(series_id)
        
        stack = ep_mem.get("narrative_stack", [])
        if not stack:
            return {"status": "empty", "message": "Narrative stack is empty"}
        
        # Pop the top
        restored_state = stack.pop()
        
        # Restore the previous timeline
        ep_mem["active_timeline"] = restored_state["timeline_id"]
        ep_mem["character_states"] = restored_state.get("character_states", {})
        ep_mem["visual_continuity"] = restored_state.get("visual_state", {})
        ep_mem["last_scene_state"] = restored_state.get("last_scene_state", {})
        
        # Pop series-level stack too
        series_stack = series_mem.get("narrative_stack", [])
        if series_stack:
            series_stack.pop()
        
        self.mem.save_episode_memory(series_id, season_num, episode_num, ep_mem)
        self.mem.save_series_memory(series_id, series_mem)
        
        return {
            "status": "popped",
            "restored_timeline": restored_state["timeline_id"],
            "restored_scene": restored_state["scene_number"],
            "depth": len(stack),
            "emotional_tone": restored_state.get("emotional_tone", "neutral"),
        }
    
    def peek_stack(self, series_id: str, season_num: int, episode_num: int) -> List[dict]:
        """Get the current narrative stack without modifying it."""
        ep_mem = self.mem.load_episode_memory(series_id, season_num, episode_num)
        return ep_mem.get("narrative_stack", [])
    
    def get_current_timeline(self, series_id: str, season_num: int, episode_num: int) -> dict:
        """Get info about the currently active timeline."""
        ep_mem = self.mem.load_episode_memory(series_id, season_num, episode_num)
        stack = ep_mem.get("narrative_stack", [])
        active = ep_mem.get("active_timeline", "main")
        
        return {
            "active_timeline": active,
            "depth": len(stack),
            "is_nested": len(stack) > 0,
            "stack": stack,
        }
    
    def scan_script_for_nested_stories(self, script: str) -> List[dict]:
        """
        Scan an entire script and identify all nested story segments.
        Returns a list of nested story regions with start/end positions.
        """
        regions = []
        stack = []
        
        lines = script.split("\n")
        for i, line in enumerate(lines):
            line_num = i + 1
            
            start = self.detect_nested_story_start(line)
            if start:
                stack.append({
                    "start_line": line_num,
                    "type": start["type"],
                    "marker": start["marker"],
                })
            
            end = self.detect_nested_story_end(line)
            if end and stack:
                entry = stack.pop()
                entry["end_line"] = line_num
                entry["end_marker"] = end["marker"]
                regions.append(entry)
        
        # Any unclosed nested stories
        for entry in stack:
            entry["end_line"] = None
            entry["note"] = "Unclosed nested story - will auto-close at scene end"
            regions.append(entry)
        
        return regions


# ============================================================================
# PHASE 3: URGENCY ROUTER
# ============================================================================

class UrgencyRouter:
    """
    Dynamic urgency-based scene cutting between parallel timeline threads.
    
    When multiple timeline threads are active (e.g., main story + flashback),
    the router tracks urgency scores for each and determines when to cut
    between them based on dramatic tension.
    
    Rules:
    - Each timeline thread has an urgency score (0.0 to 1.0)
    - When a thread's urgency exceeds the current thread's urgency by a threshold,
      the system cuts to the higher-urgency thread
    - Cuts can be: hard cut, fade, dissolve (based on urgency delta)
    - Manual overrides are always possible
    """
    
    def __init__(self, memory_store: MemoryStore):
        self.mem = memory_store
        self.cut_threshold = 0.25  # Minimum urgency delta to trigger a cut
        self.min_scene_duration = 2  # Don't cut before this many scenes in a thread
    
    def get_thread_urgency(self, series_id: str, season_num: int, episode_num: int) -> dict:
        """Get urgency scores for all active timeline threads."""
        ep_mem = self.mem.load_episode_memory(series_id, season_num, episode_num)
        scene_history = ep_mem.get("scene_history", [])
        
        # Group scenes by timeline
        threads = {}
        for scene in scene_history:
            tid = scene.get("timeline_id", "main")
            if tid not in threads:
                threads[tid] = {
                    "timeline_id": tid,
                    "scenes": [],
                    "current_urgency": 0.5,
                    "avg_urgency": 0.5,
                    "scene_count": 0,
                }
            threads[tid]["scenes"].append(scene)
            threads[tid]["scene_count"] += 1
        
        # Calculate urgency per thread
        for tid, thread in threads.items():
            if thread["scenes"]:
                urgencies = [s.get("urgency_score", 0.5) for s in thread["scenes"]]
                thread["current_urgency"] = urgencies[-1]  # Most recent
                thread["avg_urgency"] = sum(urgencies) / len(urgencies)
                thread["last_emotional_tone"] = thread["scenes"][-1].get("emotional_tone", "neutral")
                thread["last_scene_number"] = thread["scenes"][-1].get("scene_number", 0)
        
        return {
            "active_timeline": ep_mem.get("active_timeline", "main"),
            "threads": list(threads.values()),
            "stack_depth": len(ep_mem.get("narrative_stack", [])),
        }
    
    def should_cut(self, series_id: str, season_num: int, episode_num: int,
                   next_scene_data: dict) -> Optional[dict]:
        """
        Determine if we should cut to a different timeline thread before
        generating the next scene.
        """
        urgency_info = self.get_thread_urgency(series_id, season_num, episode_num)
        active = urgency_info["active_timeline"]
        threads = urgency_info["threads"]
        
        if len(threads) <= 1:
            return None  # No other threads to cut to
        
        # Find the active thread
        active_thread = None
        for t in threads:
            if t["timeline_id"] == active:
                active_thread = t
                break
        
        if not active_thread:
            return None
        
        # Check if active thread has been going long enough
        if active_thread["scene_count"] < self.min_scene_duration:
            return None  # Too early to cut away
        
        # Find the highest-urgency other thread
        other_threads = [t for t in threads if t["timeline_id"] != active]
        if not other_threads:
            return None
        
        highest = max(other_threads, key=lambda t: t["current_urgency"])
        
        # Check if the urgency delta justifies a cut
        delta = highest["current_urgency"] - active_thread["current_urgency"]
        if delta < self.cut_threshold:
            return None
        
        # Determine cut type based on delta
        if delta > 0.5:
            cut_type = "hard_cut"
        elif delta > 0.35:
            cut_type = "fade"
        else:
            cut_type = "dissolve"
        
        return {
            "should_cut": True,
            "from_timeline": active,
            "to_timeline": highest["timeline_id"],
            "cut_type": cut_type,
            "urgency_delta": round(delta, 2),
            "from_urgency": round(active_thread["current_urgency"], 2),
            "to_urgency": round(highest["current_urgency"], 2),
            "from_tone": active_thread.get("last_emotional_tone", "neutral"),
            "to_tone": highest.get("last_emotional_tone", "neutral"),
        }
    
    def set_scene_urgency(self, series_id: str, season_num: int, episode_num: int,
                          scene_num: int, urgency: float):
        """Manually set the urgency score for a scene."""
        scene_mem = self.mem.load_scene_memory(series_id, season_num, episode_num, scene_num)
        if scene_mem:
            scene_mem["urgency_score"] = max(0.0, min(1.0, urgency))
            self.mem.save_scene_memory(series_id, season_num, episode_num, scene_num, scene_mem)


# ============================================================================
# PHASE 4: RECURSIVE LEARNING ENGINE
# ============================================================================

class LearningEngine:
    """
    Post-generation quality assessment and recursive learning.
    
    After each scene is generated:
    1. Assess quality (consistency, prompt adherence, tone match)
    2. Store assessment in the learning log
    3. Generate adjustment suggestions for future scenes
    
    Before generating the next scene:
    4. Retrieve relevant learnings
    5. Apply adjustments to the scene prompt
    
    This creates a recursive self-improvement loop.
    
    Inspired by:
    - VISTA: generate → critique → rewrite → regenerate
    - CCC: structured critique → coach calibration
    - Self-Forcing: train on own outputs
    - VideoAgent: self-conditioning consistency
    """
    
    def __init__(self, memory_store: MemoryStore):
        self.mem = memory_store
    
    def assess_scene_quality(self, series_id: str, season_num: int, episode_num: int,
                              scene_num: int, scene_data: dict, video_path: str = "") -> dict:
        """
        Assess the quality of a generated scene.
        Rule-based assessment (upgradable to VLM-based in production).
        """
        scene_mem = self.mem.load_scene_memory(series_id, season_num, episode_num, scene_num)
        series_mem = self.mem.load_series_memory(series_id)
        
        assessment = {
            "scene_number": scene_num,
            "timestamp": time.time(),
            "scores": {},
            "issues": [],
            "adjustments": [],
            "characters": scene_mem.get("characters_on_screen", []),
            "location": scene_mem.get("location", "unknown"),
            "emotional_tone": scene_mem.get("emotional_tone", "neutral"),
        }
        
        # 1. Character consistency check
        chars_on_screen = scene_mem.get("characters_on_screen", [])
        if chars_on_screen:
            for char_id in chars_on_screen:
                anchor = series_mem.get("visual_anchors", {}).get(char_id, {})
                appearance = anchor.get("last_appearance_description", "")
                if appearance:
                    # Check if the prompt includes character appearance
                    prompt = scene_data.get("prompt", "")
                    char_name = series_mem.get("characters", {}).get(char_id, {}).get("name", "")
                    if char_name and char_name.lower() in prompt.lower():
                        assessment["scores"]["character_referenced"] = 1.0
                    else:
                        assessment["scores"]["character_referenced"] = 0.5
                        assessment["issues"].append(f"Character {char_name} on screen but not in prompt description")
                        assessment["adjustments"].append(
                            f"Include {char_name}'s appearance description in prompt for consistency"
                        )
        
        # 2. Prompt adherence (basic: check if prompt has key elements)
        prompt = scene_data.get("prompt", "")
        if len(prompt) < 50:
            assessment["scores"]["prompt_detail"] = 0.3
            assessment["issues"].append("Prompt too short - may lack detail for good generation")
            assessment["adjustments"].append("Expand prompt with more visual detail")
        elif len(prompt) < 150:
            assessment["scores"]["prompt_detail"] = 0.6
        else:
            assessment["scores"]["prompt_detail"] = 1.0
        
        # 3. Visual continuity check
        ep_mem = self.mem.load_episode_memory(series_id, season_num, episode_num)
        last_state = ep_mem.get("last_scene_state", {})
        if last_state:
            prev_time = last_state.get("time_of_day", "unknown")
            curr_time = scene_mem.get("time_of_day", "unknown")
            if prev_time != "unknown" and curr_time != "unknown" and prev_time != curr_time:
                # Time of day changed - check if it's a legitimate scene change
                if scene_mem.get("timeline_id") == last_state.get("timeline_id"):
                    assessment["scores"]["time_continuity"] = 0.5
                    assessment["issues"].append(f"Time of day changed from {prev_time} to {curr_time} within same timeline")
                    assessment["adjustments"].append(f"Add time transition cue or match previous {prev_time} lighting")
                else:
                    assessment["scores"]["time_continuity"] = 1.0  # Different timeline, OK
            else:
                assessment["scores"]["time_continuity"] = 1.0
        
        # 4. Emotional tone consistency
        expected_tone = scene_mem.get("emotional_tone", "neutral")
        if expected_tone in ["tense", "desperate", "intense"]:
            if "tension" not in prompt.lower() and "dramatic" not in prompt.lower():
                assessment["scores"]["tone_match"] = 0.5
                assessment["adjustments"].append(f"Add {expected_tone} mood cues to prompt (dramatic lighting, tense atmosphere)")
            else:
                assessment["scores"]["tone_match"] = 1.0
        else:
            assessment["scores"]["tone_match"] = 0.8
        
        # 5. Retake analysis
        retake_count = scene_data.get("retake_count", 0)
        if retake_count > 2:
            assessment["issues"].append(f"Scene required {retake_count} retakes - prompt may need revision")
            assessment["adjustments"].append("Consider rewriting this scene's prompt with more specific visual direction")
            assessment["scores"]["retake_efficiency"] = 0.3
        elif retake_count > 0:
            assessment["scores"]["retake_efficiency"] = 0.7
        else:
            assessment["scores"]["retake_efficiency"] = 1.0
        
        # Calculate overall score
        scores = list(assessment["scores"].values())
        assessment["overall_score"] = sum(scores) / len(scores) if scores else 0.5
        
        # Store in scene memory
        scene_mem["quality_assessment"] = assessment
        self.mem.save_scene_memory(series_id, season_num, episode_num, scene_num, scene_mem)
        
        # Store in learning log (series-level)
        learning_entry = {
            "episode": f"S{season_num}E{episode_num}",
            "scene": scene_num,
            "overall_score": assessment["overall_score"],
            "issues": assessment["issues"],
            "adjustments": assessment["adjustments"],
            "characters": assessment["characters"],
            "location": assessment["location"],
            "emotional_tone": assessment["emotional_tone"],
            "retake_count": retake_count,
            "timestamp": time.time(),
        }
        series_mem.setdefault("learning_log", []).append(learning_entry)
        self.mem.save_series_memory(series_id, series_mem)
        
        # Also store in season-level learnings
        season_mem = self.mem.load_season_memory(series_id, season_num)
        season_mem.setdefault("season_learnings", []).append(learning_entry)
        self.mem.save_season_memory(series_id, season_num, season_mem)
        
        return assessment
    
    def get_adjustments_for_scene(self, series_id: str, season_num: int, episode_num: int,
                                   scene_num: int, scene_data: dict) -> List[str]:
        """
        Get adjustment suggestions for a scene based on past learnings.
        Called before sending a scene to the GPU for generation.
        """
        series_mem = self.mem.load_series_memory(series_id)
        scene_mem = self.mem.load_scene_memory(series_id, season_num, episode_num, scene_num)
        
        if not scene_mem:
            return []
        
        adjustments = self.mem._get_relevant_learnings(series_mem, scene_mem)
        
        # Add urgency-based adjustments
        urgency = scene_mem.get("urgency_score", 0.5)
        if urgency > 0.7:
            adjustments.append("High urgency scene: use dynamic camera movement, fast cuts, intense lighting")
        elif urgency < 0.2:
            adjustments.append("Low urgency scene: use static camera, soft lighting, slow pace")
        
        # Add tone-based adjustments
        tone = scene_mem.get("emotional_tone", "neutral")
        tone_adjustments = {
            "tense": "Add tension cues: shadows, tight framing, shallow depth of field",
            "sad": "Add melancholy cues: muted colors, rain or overcast, slow motion feel",
            "angry": "Add intensity cues: high contrast, handheld camera feel, red color accents",
            "happy": "Add warmth cues: golden hour lighting, bright colors, smooth camera",
            "mysterious": "Add mystery cues: fog, low key lighting, obscured faces, deep shadows",
            "desperate": "Add desperation cues: close-up on eyes, sweat details, rapid breathing visual",
            "calm": "Add serenity cues: soft diffused lighting, wide shots, gentle movement",
        }
        if tone in tone_adjustments:
            adjustments.append(tone_adjustments[tone])
        
        return adjustments
    
    def apply_adjustments_to_prompt(self, prompt: str, adjustments: List[str]) -> str:
        """Apply learning adjustments to a scene's generation prompt."""
        if not adjustments:
            return prompt
        
        # Append adjustments as context
        adjustment_text = ". ".join(adjustments[:4])  # Limit to 4 to avoid prompt bloat
        return f"{prompt}. {adjustment_text}"
    
    def get_learning_summary(self, series_id: str, season_num: int = None) -> dict:
        """Get a summary of learnings for display."""
        series_mem = self.mem.load_series_memory(series_id)
        log = series_mem.get("learning_log", [])
        
        if not log:
            return {"total_learnings": 0, "avg_score": 0, "common_issues": [], "common_adjustments": []}
        
        scores = [e.get("overall_score", 0.5) for e in log]
        all_issues = [issue for e in log for issue in e.get("issues", [])]
        all_adjustments = [adj for e in log for adj in e.get("adjustments", [])]
        
        # Count frequency
        from collections import Counter
        issue_freq = Counter(all_issues).most_common(5)
        adj_freq = Counter(all_adjustments).most_common(5)
        
        return {
            "total_learnings": len(log),
            "avg_score": round(sum(scores) / len(scores), 2),
            "recent_score": round(scores[-1], 2) if scores else 0,
            "score_trend": "improving" if len(scores) > 2 and scores[-1] > scores[0] else "stable",
            "common_issues": [{"issue": i, "count": c} for i, c in issue_freq],
            "common_adjustments": [{"adjustment": a, "count": c} for a, c in adj_freq],
            "total_retakes": sum(e.get("retake_count", 0) for e in log),
        }

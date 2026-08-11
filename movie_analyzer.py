"""
SoulIllusions AI Movie & TV Analyzer Engine
=============================================
An AI-powered engine that sits on top of the video maker platform.

Capabilities:
- Analyze movies from YouTube (trailers, reviews, summaries, full video analysis)
- Analyze movies from Facebook (movie pages, descriptions, discussions)
- Analyze movies from text descriptions / scripts
- Extract: plot structure, characters, world design, visual style, themes, tone
- Dissect multiple movies and combine elements into a new unified movie concept
- Generate plot twists by mixing elements from different sources
- Feed analyzed data to text-to-video pipeline for better video generation
- Feed analyzed data to text-to-game pipeline for world design transfer
- TV series analysis: season structure, episode breakdowns, character arcs

Architecture:
- SQLite database for analyzed movies/series
- YouTube data extraction via search and transcript fetching
- LLM-powered deep analysis using the platform's GPU backend
- Combination engine for merging multiple movie analyses
- Export to text-to-video and text-to-game formats
"""

import os, sys, json, re, asyncio, sqlite3, hashlib, time
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict

SCRIPT_DIR = Path(__file__).parent
MOVIES_DB = SCRIPT_DIR / "movies.db"
MOVIES_DIR = SCRIPT_DIR / "movie_analysis"
MOVIES_DIR.mkdir(exist_ok=True, parents=True)


def init_db():
    conn = sqlite3.connect(str(MOVIES_DB))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS analyzed_movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT DEFAULT 'description',
            source_url TEXT,
            source_platform TEXT DEFAULT 'unknown',
            media_type TEXT DEFAULT 'movie',
            raw_data TEXT,
            analysis TEXT,
            plot_summary TEXT,
            characters TEXT,
            world_design TEXT,
            visual_style TEXT,
            themes TEXT,
            tone TEXT,
            plot_structure TEXT,
            key_scenes TEXT,
            plot_twists TEXT,
            combined_from TEXT,
            status TEXT DEFAULT 'analyzed',
            rating REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS movie_combinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_movie_ids TEXT NOT NULL,
            combined_analysis TEXT,
            new_plot TEXT,
            plot_twist TEXT,
            characters TEXT,
            world_design TEXT,
            visual_style TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE NOT NULL,
            cache_data TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


init_db()


def _get_llm():
    try:
        from soulillusions_agent import LLMInterface, load_config
        cfg = load_config()
        return LLMInterface(cfg)
    except Exception:
        return None


# --- YouTube Data Extraction ---
class YouTubeExtractor:
    """Extracts movie/TV data from YouTube videos."""
    
    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search YouTube for videos related to a movie/TV show."""
        results = []
        try:
            import urllib.request, urllib.parse
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            req = urllib.request.Request(search_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            
            # Extract video IDs and titles from YouTube search results
            video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"\}', html)
            
            seen = set()
            for i, vid in enumerate(video_ids):
                if vid in seen:
                    continue
                seen.add(vid)
                title = titles[i] if i < len(titles) else f"Video {vid}"
                results.append({
                    "video_id": vid,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                })
                if len(results) >= max_results:
                    break
        except Exception as e:
            results.append({"error": f"YouTube search failed: {e}"})
        return results
    
    async def get_transcript(self, video_id: str) -> str:
        """Attempt to get transcript/captions from a YouTube video."""
        try:
            import urllib.request
            url = f"https://www.youtube.com/watch?v={video_id}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            
            # Try to find caption track URLs
            caption_tracks = re.findall(r'"captionTracks":\[(\[.*?\])\]', html)
            if caption_tracks:
                tracks = json.loads("[" + caption_tracks[0].rstrip(']') + "]")
                for track in tracks:
                    if track.get('languageCode', '').startswith('en'):
                        caption_url = track.get('baseUrl', '')
                        if caption_url:
                            cap_req = urllib.request.Request(caption_url, headers={
                                'User-Agent': 'Mozilla/5.0'
                            })
                            with urllib.request.urlopen(cap_req, timeout=15) as cap_resp:
                                caption_xml = cap_resp.read().decode('utf-8', errors='ignore')
                            # Extract text from XML captions
                            texts = re.findall(r'<text[^>]*>(.*?)</text>', caption_xml)
                            transcript = ' '.join(texts)
                            transcript = re.sub(r'&amp;', '&', transcript)
                            transcript = re.sub(r'&#39;', "'", transcript)
                            transcript = re.sub(r'&quot;', '"', transcript)
                            transcript = re.sub(r'&lt;', '<', transcript)
                            transcript = re.sub(r'&gt;', '>', transcript)
                            return transcript[:10000]  # Limit length
            
            # Fallback: extract description and metadata
            desc_match = re.findall(r'"shortDescription":"(.*?)"', html)
            if desc_match:
                return f"[Description]: {desc_match[0][:5000]}"
            
            return "[No transcript available]"
        except Exception as e:
            return f"[Transcript extraction error: {e}]"
    
    async def analyze_youtube_movie(self, movie_title: str) -> Dict:
        """Search YouTube for movie content and extract analysis data."""
        search_queries = [
            f"{movie_title} movie explained",
            f"{movie_title} movie review",
            f"{movie_title} trailer",
            f"{movie_title} plot summary",
        ]
        
        all_videos = []
        all_transcripts = []
        
        for query in search_queries:
            videos = await self.search_videos(query, max_results=3)
            for v in videos:
                if 'error' not in v:
                    all_videos.append(v)
                    transcript = await self.get_transcript(v["video_id"])
                    if not transcript.startswith("[") or "Description" in transcript:
                        all_transcripts.append({
                            "title": v["title"],
                            "url": v["url"],
                            "transcript": transcript
                        })
        
        return {
            "movie_title": movie_title,
            "source": "youtube",
            "videos_found": len(all_videos),
            "transcripts": all_transcripts[:5],
            "combined_text": " ".join([t["transcript"] for t in all_transcripts])[:20000],
        }


# --- Facebook Data Extraction ---
class FacebookExtractor:
    """Extracts movie/TV data from Facebook pages."""
    
    async def search_facebook(self, query: str) -> Dict:
        """Search Facebook for movie/TV show pages."""
        try:
            import urllib.request, urllib.parse
            search_url = f"https://www.facebook.com/search/pages/?q={urllib.parse.quote(query + ' movie')}"
            req = urllib.request.Request(search_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode('utf-8', errors='ignore')
                # Extract page titles and descriptions
                titles = re.findall(r'"name":"([^"]+)"', html)
                descriptions = re.findall(r'"description":"([^"]+)"', html)
                return {
                    "source": "facebook",
                    "pages": titles[:10],
                    "descriptions": descriptions[:5],
                    "combined_text": " ".join(descriptions)[:5000],
                }
            except Exception:
                return {"source": "facebook", "pages": [], "descriptions": [], "combined_text": "",
                        "note": "Facebook requires authentication for full access. Using public data only."}
        except Exception as e:
            return {"source": "facebook", "error": str(e), "combined_text": ""}


# --- Movie Analysis Engine ---
class MovieAnalysisEngine:
    """Deep AI analysis of movies and TV shows."""
    
    def __init__(self):
        self.llm = _get_llm()
        self.youtube = YouTubeExtractor()
        self.facebook = FacebookExtractor()
    
    async def analyze_movie(self, title: str, source: str = "auto",
                            source_url: str = "", description: str = "",
                            media_type: str = "movie") -> Dict:
        """Analyze a movie or TV show from various sources.
        
        Sources:
        - 'youtube': Search YouTube for trailers, reviews, explanations
        - 'facebook': Search Facebook for movie pages
        - 'description': Use provided text description
        - 'url': Use provided URL (YouTube/Facebook)
        - 'auto': Try all available sources
        """
        raw_data = {"title": title, "media_type": media_type}
        
        # Gather data from sources
        if source in ("youtube", "auto") and not description:
            yt_data = await self.youtube.analyze_youtube_movie(title)
            raw_data["youtube"] = yt_data
        
        if source in ("facebook", "auto") and not description:
            fb_data = await self.facebook.search_facebook(title)
            raw_data["facebook"] = fb_data
        
        if source == "url" and source_url:
            if "youtube.com" in source_url or "youtu.be" in source_url:
                vid_id = self._extract_youtube_id(source_url)
                if vid_id:
                    transcript = await self.youtube.get_transcript(vid_id)
                    raw_data["youtube"] = {
                        "videos_found": 1,
                        "transcripts": [{"title": title, "url": source_url, "transcript": transcript}],
                        "combined_text": transcript,
                    }
            elif "facebook.com" in source_url:
                fb_data = await self.facebook.search_facebook(title)
                raw_data["facebook"] = fb_data
        
        if description:
            raw_data["description"] = description
        
        # Combine all available text for analysis
        combined_text = ""
        if "youtube" in raw_data and raw_data["youtube"].get("combined_text"):
            combined_text += raw_data["youtube"]["combined_text"] + "\n\n"
        if "facebook" in raw_data and raw_data["facebook"].get("combined_text"):
            combined_text += raw_data["facebook"]["combined_text"] + "\n\n"
        if description:
            combined_text += description
        
        if not combined_text.strip():
            combined_text = f"Movie title: {title}. No additional data could be retrieved. Analyze based on title and general knowledge."
        
        # Run AI analysis
        analysis = await self._ai_analyze(title, combined_text, media_type)
        
        # Save to database
        movie_id = self._save_analysis(title, source, source_url, raw_data, analysis, media_type)
        
        return {
            "id": movie_id,
            "title": title,
            "source": source,
            "media_type": media_type,
            "analysis": analysis,
            "raw_data_summary": {
                "youtube_videos": len(raw_data.get("youtube", {}).get("transcripts", [])),
                "facebook_pages": len(raw_data.get("facebook", {}).get("pages", [])),
                "has_description": bool(description),
            }
        }
    
    async def _ai_analyze(self, title: str, text: str, media_type: str = "movie") -> Dict:
        """Use LLM to deeply analyze movie content."""
        if not self.llm:
            return self._heuristic_analysis(title, text, media_type)
        
        system_prompt = f"""You are an expert film and TV analyst AI for the SoulIllusions platform.
You analyze movies and TV shows to extract detailed structured data for video and game generation.

Extract and return as JSON:
{{
    "plot_summary": "3-5 sentence summary of the plot",
    "plot_structure": {{
        "acts": [{{"name": "Act 1", "summary": "..."}}, ...],
        "inciting_incident": "...",
        "climax": "...",
        "resolution": "..."
    }},
    "characters": [
        {{"name": "...", "role": "protagonist/antagonist/supporting", "description": "...", "appearance": "...", "personality": "...", "arc": "..."}}
    ],
    "world_design": {{
        "setting": "...",
        "time_period": "...",
        "locations": ["...", ...],
        "atmosphere": "...",
        "technology_level": "...",
        "magic_system": "..." or "none",
        "social_structure": "..."
    }},
    "visual_style": {{
        "color_palette": ["...", ...],
        "lighting": "...",
        "cinematography": "...",
        "special_effects": "...",
        "art_direction": "..."
    }},
    "themes": ["...", ...],
    "tone": "...",
    "key_scenes": [
        {{"scene": "...", "description": "...", "visual_prompt": "...", "emotional_impact": "..."}}
    ],
    "plot_twists": ["...", ...],
    "game_adaptation": {{
        "suggested_genre": "rpg/shooter/platformer/adventure/puzzle/strategy",
        "player_character": "...",
        "antagonist": "...",
        "key_locations": ["...", ...],
        "key_items": ["...", ...],
        "mission_structure": ["...", ...],
        "world_transfer_notes": "How to recreate this world in a game"
    }},
    "video_adaptation": {{
        "key_visual_moments": ["...", ...],
        "character_visual_prompts": [{{"name": "...", "prompt": "..."}}],
        "scene_visual_prompts": ["...", ...],
        "mood_board": "..."
    }}
}}

Analyze this {'movie' if media_type == 'movie' else 'TV series'}: "{title}"

Source material (transcripts, descriptions, reviews):
{text[:15000]}
"""
        
        try:
            response = await self.llm.generate(f"Analyze the {media_type} '{title}'", system_prompt, max_tokens=8000)
            # Try to parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            # Fallback: return raw response
            return {"raw_analysis": response[:5000], "parse_error": "Could not parse JSON"}
        except Exception as e:
            return {"error": f"AI analysis failed: {e}", **self._heuristic_analysis(title, text, media_type)}
    
    def _heuristic_analysis(self, title: str, text: str, media_type: str = "movie") -> Dict:
        """Fallback heuristic analysis when LLM is not available."""
        text_lower = text.lower()
        
        # Extract character names (capitalized words that appear multiple times)
        words = re.findall(r'\b[A-Z][a-z]+\b', text)
        from collections import Counter
        name_counts = Counter(words)
        characters = [{"name": name, "role": "supporting", "description": f"Appears in {title}"}
                      for name, count in name_counts.most_common(10) if count > 2 and name not in 
                      ("The", "This", "That", "Then", "When", "What", "They", "There", "Here", "Movie", "Film")]
        
        # Detect themes
        theme_map = {
            "love": ["love", "romance", "heart", "relationship"],
            "adventure": ["adventure", "journey", "quest", "explore"],
            "conflict": ["war", "battle", "fight", "enemy", "conflict"],
            "mystery": ["mystery", "secret", "hidden", "unknown"],
            "horror": ["horror", "scary", "fear", "terror", "dread"],
            "sci-fi": ["space", "future", "alien", "technology", "robot", "cyber"],
            "fantasy": ["magic", "dragon", "wizard", "kingdom", "spell", "mythical"],
            "crime": ["crime", "detective", "murder", "police", "thief"],
            "comedy": ["funny", "comedy", "humor", "joke", "laugh"],
            "drama": ["drama", "emotional", "family", "struggle", "life"],
        }
        themes = [theme for theme, keywords in theme_map.items()
                  if any(kw in text_lower for kw in keywords)]
        
        # Detect setting
        setting = "modern day"
        if any(kw in text_lower for kw in ["space", "galaxy", "planet", "starship"]):
            setting = "space/sci-fi"
        elif any(kw in text_lower for kw in ["medieval", "kingdom", "castle", "knight", "sword"]):
            setting = "medieval/fantasy"
        elif any(kw in text_lower for kw in ["future", "cyber", "android", "2080", "2100"]):
            setting = "future/cyberpunk"
        elif any(kw in text_lower for kw in ["war", "1940", "1910", "battle"]):
            setting = "historical/war"
        
        # Detect tone
        tone = "neutral"
        if any(kw in text_lower for kw in ["dark", "gritty", "noir", "bleak"]):
            tone = "dark/gritty"
        elif any(kw in text_lower for kw in ["light", "fun", "happy", "bright"]):
            tone = "light/upbeat"
        elif any(kw in text_lower for kw in ["tense", "thriller", "suspense"]):
            tone = "tense/suspenseful"
        elif any(kw in text_lower for kw in ["epic", "grand", "scale"]):
            tone = "epic/grand"
        
        return {
            "plot_summary": f"Analysis of {title} based on available text data. {text[:500]}",
            "plot_structure": {
                "acts": [
                    {"name": "Act 1: Setup", "summary": "Introduction of characters and world"},
                    {"name": "Act 2: Confrontation", "summary": "Rising action and conflict"},
                    {"name": "Act 3: Resolution", "summary": "Climax and conclusion"},
                ],
                "inciting_incident": "To be determined with more data",
                "climax": "To be determined with more data",
                "resolution": "To be determined with more data",
            },
            "characters": characters[:5],
            "world_design": {
                "setting": setting,
                "time_period": "varies",
                "locations": [],
                "atmosphere": tone,
                "technology_level": "modern" if setting == "modern day" else setting,
                "magic_system": "none" if "fantasy" not in themes else "present",
                "social_structure": "varies",
            },
            "visual_style": {
                "color_palette": ["varies"],
                "lighting": "varies",
                "cinematography": "varies",
                "special_effects": "varies",
                "art_direction": "varies",
            },
            "themes": themes,
            "tone": tone,
            "key_scenes": [],
            "plot_twists": [],
            "game_adaptation": {
                "suggested_genre": "adventure",
                "player_character": characters[0]["name"] if characters else "Hero",
                "antagonist": None,
                "key_locations": [],
                "key_items": [],
                "mission_structure": [],
                "world_transfer_notes": f"Transfer the {setting} world of {title} into a game environment",
            },
            "video_adaptation": {
                "key_visual_moments": [],
                "character_visual_prompts": [],
                "scene_visual_prompts": [],
                "mood_board": f"{tone} atmosphere with {setting} setting",
            },
            "analysis_method": "heuristic_fallback",
        }
    
    def _extract_youtube_id(self, url: str) -> str:
        """Extract YouTube video ID from URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return ""
    
    def _save_analysis(self, title: str, source: str, source_url: str,
                       raw_data: dict, analysis: dict, media_type: str) -> int:
        conn = sqlite3.connect(str(MOVIES_DB))
        c = conn.cursor()
        c.execute("""INSERT INTO analyzed_movies 
            (title, source, source_url, source_platform, media_type, raw_data, analysis,
             plot_summary, characters, world_design, visual_style, themes, tone,
             plot_structure, key_scenes, plot_twists)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title, source, source_url,
                "youtube" if "youtube" in source else ("facebook" if "facebook" in source else "mixed"),
                media_type,
                json.dumps(raw_data, default=str),
                json.dumps(analysis, default=str),
                analysis.get("plot_summary", ""),
                json.dumps(analysis.get("characters", []), default=str),
                json.dumps(analysis.get("world_design", {}), default=str),
                json.dumps(analysis.get("visual_style", {}), default=str),
                json.dumps(analysis.get("themes", []), default=str),
                analysis.get("tone", ""),
                json.dumps(analysis.get("plot_structure", {}), default=str),
                json.dumps(analysis.get("key_scenes", []), default=str),
                json.dumps(analysis.get("plot_twists", []), default=str),
            ))
        movie_id = c.lastrowid
        conn.commit()
        conn.close()
        return movie_id
    
    # --- Combine Multiple Movies ---
    async def combine_movies(self, movie_ids: List[int], new_title: str = "",
                              twist_description: str = "") -> Dict:
        """Combine elements from multiple analyzed movies into a new movie concept.
        
        Takes bits, parts, and pieces from each movie — dissecting and reassembling
        them into one unified movie with a unique plot twist.
        """
        movies = []
        for mid in movie_ids:
            m = self.get_movie(mid)
            if m:
                movies.append(m)
        
        if not movies:
            return {"error": "No valid movies found to combine"}
        
        if not new_title:
            new_title = "Combined: " + " + ".join([m["title"] for m in movies[:3]])
        
        # Build combination prompt for AI
        movie_summaries = []
        for i, m in enumerate(movies):
            analysis = m.get("analysis", {})
            movie_summaries.append(f"""
Movie {i+1}: {m['title']}
- Plot: {analysis.get('plot_summary', 'N/A')}
- Themes: {', '.join(analysis.get('themes', []))}
- Tone: {analysis.get('tone', 'N/A')}
- World: {json.dumps(analysis.get('world_design', {}), default=str)[:500]}
- Characters: {json.dumps(analysis.get('characters', []), default=str)[:500]}
- Key scenes: {json.dumps(analysis.get('key_scenes', []), default=str)[:500]}
- Plot twists: {json.dumps(analysis.get('plot_twists', []), default=str)[:300]}
- Visual style: {json.dumps(analysis.get('visual_style', {}), default=str)[:300]}
""")
        
        if self.llm:
            system_prompt = f"""You are a master film writer AI for the SoulIllusions platform.
You are given analyses of {len(movies)} movies. Your job is to dissect each movie, take the best elements
(characters, world design, plot structures, visual styles, themes, key scenes), and combine them
into ONE new original movie concept with a unique plot twist.

The new movie should:
- Take the most compelling character elements from each movie
- Blend the world designs into a cohesive new world
- Mix visual styles into something fresh
- Create a new plot that weaves together elements from all source movies
- Include a SURPRISE plot twist that combines/subverts expectations from the source movies
- Feel like a completely new movie, not a mashup

Return as JSON:
{{
    "title": "{new_title}",
    "combined_plot": "Full plot summary (5-10 sentences)",
    "plot_twist": "The surprise twist that combines elements from the source movies",
    "characters": [{{"name": "...", "origin_movie": "...", "description": "...", "role": "..."}}],
    "world_design": {{...}},
    "visual_style": {{...}},
    "themes": [...],
    "tone": "...",
    "key_scenes": [...],
    "source_elements_used": [{{"movie": "...", "elements_taken": [...], "how_modified": "..."}}],
    "game_adaptation": {{...}},
    "video_adaptation": {{...}}
}}

Movies to combine:
{''.join(movie_summaries)}

Additional twist direction: {twist_description or 'Create a natural surprising twist that combines elements from all movies.'}
"""
            try:
                response = await self.llm.generate(f"Combine these {len(movies)} movies into one", system_prompt, max_tokens=8000)
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        combined = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        combined = {"raw_response": response[:5000]}
                else:
                    combined = {"raw_response": response[:5000]}
            except Exception as e:
                combined = {"error": f"AI combination failed: {e}"}
        else:
            # Heuristic combination
            all_themes = []
            all_characters = []
            all_locations = []
            for m in movies:
                a = m.get("analysis", {})
                all_themes.extend(a.get("themes", []))
                for ch in a.get("characters", []):
                    ch["origin_movie"] = m["title"]
                    all_characters.append(ch)
                wd = a.get("world_design", {})
                all_locations.extend(wd.get("locations", []))
            
            combined = {
                "title": new_title,
                "combined_plot": f"A new story combining elements from {', '.join([m['title'] for m in movies])}. "
                    + " ".join([m.get("analysis", {}).get("plot_summary", "")[:200] for m in movies]),
                "plot_twist": twist_description or "A twist that subverts expectations from all source movies",
                "characters": all_characters[:10],
                "world_design": {
                    "setting": "mixed",
                    "locations": list(set(all_locations))[:10],
                    "atmosphere": "blended",
                },
                "themes": list(set(all_themes)),
                "tone": "mixed",
                "source_elements_used": [{"movie": m["title"], "elements_taken": ["characters", "world", "plot"]} for m in movies],
            }
        
        # Save combination
        conn = sqlite3.connect(str(MOVIES_DB))
        c = conn.cursor()
        c.execute("""INSERT INTO movie_combinations 
            (title, source_movie_ids, combined_analysis, new_plot, plot_twist, characters, world_design, visual_style)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_title,
                json.dumps(movie_ids),
                json.dumps(combined, default=str),
                combined.get("combined_plot", ""),
                combined.get("plot_twist", ""),
                json.dumps(combined.get("characters", []), default=str),
                json.dumps(combined.get("world_design", {}), default=str),
                json.dumps(combined.get("visual_style", {}), default=str),
            ))
        combo_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return {"id": combo_id, "title": new_title, "combined": combined, "source_movies": [m["title"] for m in movies]}
    
    # --- Data Access ---
    def get_movie(self, movie_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(str(MOVIES_DB))
        c = conn.cursor()
        c.execute("SELECT * FROM analyzed_movies WHERE id = ?", (movie_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        cols = ["id", "title", "source", "source_url", "source_platform", "media_type",
                "raw_data", "analysis", "plot_summary", "characters", "world_design",
                "visual_style", "themes", "tone", "plot_structure", "key_scenes",
                "plot_twists", "combined_from", "status", "rating", "created_at", "updated_at"]
        data = dict(zip(cols, row))
        # Parse JSON fields
        for key in ["raw_data", "analysis", "characters", "world_design", "visual_style",
                     "themes", "plot_structure", "key_scenes", "plot_twists"]:
            if data.get(key) and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except:
                    pass
        return data
    
    def list_movies(self, limit: int = 50, media_type: str = "") -> List[Dict]:
        conn = sqlite3.connect(str(MOVIES_DB))
        c = conn.cursor()
        if media_type:
            c.execute("SELECT id, title, source, media_type, status, rating, created_at FROM analyzed_movies WHERE media_type = ? ORDER BY created_at DESC LIMIT ?",
                      (media_type, limit))
        else:
            c.execute("SELECT id, title, source, media_type, status, rating, created_at FROM analyzed_movies ORDER BY created_at DESC LIMIT ?",
                      (limit,))
        rows = c.fetchall()
        conn.close()
        cols = ["id", "title", "source", "media_type", "status", "rating", "created_at"]
        return [dict(zip(cols, r)) for r in rows]
    
    def list_combinations(self, limit: int = 20) -> List[Dict]:
        conn = sqlite3.connect(str(MOVIES_DB))
        c = conn.cursor()
        c.execute("SELECT id, title, source_movie_ids, created_at FROM movie_combinations ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        cols = ["id", "title", "source_movie_ids", "created_at"]
        results = []
        for r in rows:
            d = dict(zip(cols, r))
            try:
                d["source_movie_ids"] = json.loads(d["source_movie_ids"])
            except:
                pass
            results.append(d)
        return results
    
    def get_combination(self, combo_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(str(MOVIES_DB))
        c = conn.cursor()
        c.execute("SELECT * FROM movie_combinations WHERE id = ?", (combo_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        cols = ["id", "title", "source_movie_ids", "combined_analysis", "new_plot",
                "plot_twist", "characters", "world_design", "visual_style", "created_at"]
        data = dict(zip(cols, row))
        for key in ["source_movie_ids", "combined_analysis", "characters", "world_design", "visual_style"]:
            if data.get(key) and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except:
                    pass
        return data
    
    def delete_movie(self, movie_id: int) -> Dict:
        conn = sqlite3.connect(str(MOVIES_DB))
        c = conn.cursor()
        c.execute("DELETE FROM analyzed_movies WHERE id = ?", (movie_id,))
        conn.commit()
        conn.close()
        return {"status": "deleted", "movie_id": movie_id}
    
    # --- Export for Video/Game Pipelines ---
    def get_for_video(self, movie_id: int) -> Dict:
        """Get movie analysis formatted for text-to-video pipeline."""
        movie = self.get_movie(movie_id)
        if not movie:
            return {"error": "Movie not found"}
        analysis = movie.get("analysis", {})
        video_adapt = analysis.get("video_adaptation", {})
        return {
            "movie_id": movie_id,
            "title": movie["title"],
            "plot_summary": analysis.get("plot_summary", movie.get("plot_summary", "")),
            "visual_style": analysis.get("visual_style", movie.get("visual_style", {})),
            "character_visual_prompts": video_adapt.get("character_visual_prompts", []),
            "scene_visual_prompts": video_adapt.get("scene_visual_prompts", []),
            "key_visual_moments": video_adapt.get("key_visual_moments", []),
            "mood_board": video_adapt.get("mood_board", ""),
            "tone": analysis.get("tone", ""),
            "themes": analysis.get("themes", []),
            "key_scenes": analysis.get("key_scenes", []),
        }
    
    def get_for_game(self, movie_id: int) -> Dict:
        """Get movie analysis formatted for text-to-game pipeline — 
        transfers the actual world design of the movie into a game."""
        movie = self.get_movie(movie_id)
        if not movie:
            return {"error": "Movie not found"}
        analysis = movie.get("analysis", {})
        game_adapt = analysis.get("game_adaptation", {})
        world = analysis.get("world_design", movie.get("world_design", {}))
        return {
            "movie_id": movie_id,
            "title": movie["title"],
            "world_design": world,
            "player_character": game_adapt.get("player_character", ""),
            "antagonist": game_adapt.get("antagonist"),
            "suggested_genre": game_adapt.get("suggested_genre", "adventure"),
            "key_locations": game_adapt.get("key_locations", world.get("locations", [])),
            "key_items": game_adapt.get("key_items", []),
            "mission_structure": game_adapt.get("mission_structure", []),
            "world_transfer_notes": game_adapt.get("world_transfer_notes", ""),
            "characters": analysis.get("characters", movie.get("characters", [])),
            "plot_structure": analysis.get("plot_structure", movie.get("plot_structure", {})),
            "themes": analysis.get("themes", []),
            "tone": analysis.get("tone", ""),
            "visual_style": analysis.get("visual_style", movie.get("visual_style", {})),
        }
    
    def get_combination_for_video(self, combo_id: int) -> Dict:
        """Get combined movie data for text-to-video."""
        combo = self.get_combination(combo_id)
        if not combo:
            return {"error": "Combination not found"}
        combined = combo.get("combined_analysis", {})
        return {
            "combo_id": combo_id,
            "title": combo["title"],
            "plot": combo.get("new_plot", combined.get("combined_plot", "")),
            "plot_twist": combo.get("plot_twist", ""),
            "characters": combo.get("characters", combined.get("characters", [])),
            "world_design": combo.get("world_design", combined.get("world_design", {})),
            "visual_style": combo.get("visual_style", combined.get("visual_style", {})),
            "themes": combined.get("themes", []),
            "tone": combined.get("tone", ""),
            "key_scenes": combined.get("key_scenes", []),
            "source_elements_used": combined.get("source_elements_used", []),
        }
    
    def get_combination_for_game(self, combo_id: int) -> Dict:
        """Get combined movie data for text-to-game."""
        combo = self.get_combination(combo_id)
        if not combo:
            return {"error": "Combination not found"}
        combined = combo.get("combined_analysis", {})
        game_adapt = combined.get("game_adaptation", {})
        return {
            "combo_id": combo_id,
            "title": combo["title"],
            "world_design": combo.get("world_design", combined.get("world_design", {})),
            "player_character": game_adapt.get("player_character", ""),
            "antagonist": game_adapt.get("antagonist"),
            "suggested_genre": game_adapt.get("suggested_genre", "adventure"),
            "key_locations": game_adapt.get("key_locations", []),
            "key_items": game_adapt.get("key_items", []),
            "mission_structure": game_adapt.get("mission_structure", []),
            "characters": combo.get("characters", combined.get("characters", [])),
            "plot": combo.get("new_plot", combined.get("combined_plot", "")),
            "plot_twist": combo.get("plot_twist", ""),
            "visual_style": combo.get("visual_style", combined.get("visual_style", {})),
        }


# --- Singleton ---
_engine: Optional[MovieAnalysisEngine] = None

def get_movie_engine() -> MovieAnalysisEngine:
    global _engine
    if _engine is None:
        _engine = MovieAnalysisEngine()
    return _engine


# --- CLI ---
def cli():
    print("=" * 55)
    print("  SoulIllusions Movie & TV Analyzer Engine")
    print("=" * 55)
    
    if len(sys.argv) < 2:
        print("Commands:")
        print("  analyze <title> [--source youtube|facebook|description|auto] [--type movie|tv] [--desc TEXT] [--url URL]")
        print("  list [--type movie|tv]")
        print("  get <id>")
        print("  combine <id1,id2,...> [--title X] [--twist TEXT]")
        print("  for-video <id>")
        print("  for-game <id>")
        print("  combo-for-video <combo_id>")
        print("  combo-for-game <combo_id>")
        print("  combinations")
        print("  delete <id>")
        return
    
    cmd = sys.argv[1]
    engine = get_movie_engine()
    
    if cmd == "analyze":
        title = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
        source = "auto"
        media_type = "movie"
        desc = ""
        url = ""
        for i, arg in enumerate(sys.argv):
            if arg == "--source" and i + 1 < len(sys.argv): source = sys.argv[i + 1]
            elif arg == "--type" and i + 1 < len(sys.argv): media_type = sys.argv[i + 1]
            elif arg == "--desc" and i + 1 < len(sys.argv): desc = sys.argv[i + 1]
            elif arg == "--url" and i + 1 < len(sys.argv): url = sys.argv[i + 1]
        result = asyncio.run(engine.analyze_movie(title, source, url, desc, media_type))
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "list":
        mt = ""
        if "--type" in sys.argv:
            mt = sys.argv[sys.argv.index("--type") + 1]
        movies = engine.list_movies(media_type=mt)
        print(json.dumps(movies, indent=2))
    
    elif cmd == "get":
        mid = int(sys.argv[2])
        movie = engine.get_movie(mid)
        print(json.dumps(movie, indent=2, default=str) if movie else "Not found")
    
    elif cmd == "combine":
        ids = [int(x) for x in sys.argv[2].split(",")]
        title = ""
        twist = ""
        for i, arg in enumerate(sys.argv):
            if arg == "--title" and i + 1 < len(sys.argv): title = sys.argv[i + 1]
            elif arg == "--twist" and i + 1 < len(sys.argv): twist = sys.argv[i + 1]
        result = asyncio.run(engine.combine_movies(ids, title, twist))
        print(json.dumps(result, indent=2, default=str))
    
    elif cmd == "for-video":
        mid = int(sys.argv[2])
        print(json.dumps(engine.get_for_video(mid), indent=2, default=str))
    
    elif cmd == "for-game":
        mid = int(sys.argv[2])
        print(json.dumps(engine.get_for_game(mid), indent=2, default=str))
    
    elif cmd == "combo-for-video":
        cid = int(sys.argv[2])
        print(json.dumps(engine.get_combination_for_video(cid), indent=2, default=str))
    
    elif cmd == "combo-for-game":
        cid = int(sys.argv[2])
        print(json.dumps(engine.get_combination_for_game(cid), indent=2, default=str))
    
    elif cmd == "combinations":
        print(json.dumps(engine.list_combinations(), indent=2, default=str))
    
    elif cmd == "delete":
        mid = int(sys.argv[2])
        print(json.dumps(engine.delete_movie(mid), indent=2))
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli()

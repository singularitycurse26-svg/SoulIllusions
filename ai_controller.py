"""
SoulIllusions AI Controller — Full Programmatic Control API

Exposes every SoulIllusions function as a structured API that an external AI
(such as Cascade/Claude) can call to control the application programmatically.

Based on MCP design patterns:
- Tools: Executable functions the AI can call (actions)
- Resources: Read-only state inspection (queries)
- Structured JSON responses with success/error/result

The AI can:
- Create/manage series, seasons, episodes, scenes
- Generate videos with any model and parameters
- Enhance scripts and break down episodes into scenes
- Manage characters and world bible
- Inspect all application state
- Control the narrative memory engine
- Read action logs and upgrade notes
- Trigger post-processing

Usage:
    from ai_controller import AIController
    controller = AIController(production_suite, server_config)
    result = controller.execute("create_series", {"title": "My Show", ...})
"""

import json
import os
import time
import uuid
import traceback
from typing import Any, Optional


class AIController:
    """Programmatic control interface for SoulIllusions.

    Every method is exposed as a 'tool' that an AI can call.
    State inspection methods are 'resources'.
    """

    def __init__(self, production_suite=None, server_app=None, action_logger=None):
        self.production_suite = production_suite
        self.server_app = server_app
        self.action_logger = action_logger
        self._tools = {}
        self._resources = {}
        self._register_all()

    def _register_all(self):
        """Register all available tools and resources."""
        # === Production Suite Tools ===
        self._tool("list_series", "List all series in the production suite", self._list_series)
        self._tool("create_series", "Create a new series. Required: title, concept. Optional: genre, description, seasons_planned, episodes_per_season", self._create_series)
        self._tool("get_series", "Get full details of a series by ID. Required: series_id", self._get_series)
        self._tool("update_series", "Update series fields. Required: series_id. Optional: title, genre, concept, description, world_bible", self._update_series)
        self._tool("delete_series", "Delete a series and all its data. Required: series_id", self._delete_series)

        self._tool("list_seasons", "List seasons for a series. Required: series_id", self._list_seasons)
        self._tool("get_season", "Get season details. Required: series_id, season_number", self._get_season)

        self._tool("list_episodes", "List episodes in a season. Required: series_id, season_number", self._list_episodes)
        self._tool("create_episode", "Create a new episode. Required: series_id, season_number, title. Optional: script, synopsis", self._create_episode)
        self._tool("get_episode", "Get episode details including scenes. Required: series_id, season_number, episode_number", self._get_episode)
        self._tool("update_episode", "Update episode fields. Required: series_id, season_number, episode_number. Optional: title, script, synopsis, enhanced_script", self._update_episode)
        self._tool("delete_episode", "Delete an episode. Required: series_id, season_number, episode_number", self._delete_episode)

        self._tool("enhance_script", "Enhance a script using the built-in enhancer. Required: series_id, season_number, episode_number", self._enhance_script)
        self._tool("breakdown_episode", "Break an episode script into scenes. Required: series_id, season_number, episode_number", self._breakdown_episode)

        self._tool("list_scenes", "List scenes in an episode. Required: series_id, season_number, episode_number", self._list_scenes)
        self._tool("get_scene", "Get scene details. Required: series_id, season_number, episode_number, scene_number", self._get_scene)
        self._tool("update_scene", "Update a scene's prompt or settings. Required: series_id, season_number, episode_number, scene_number. Optional: prompt, style, model, status", self._update_scene)
        self._tool("generate_scene", "Generate video for a scene. Required: series_id, season_number, episode_number, scene_number", self._generate_scene)
        self._tool("retake_scene", "Regenerate a scene's video. Required: series_id, season_number, episode_number, scene_number", self._retake_scene)

        self._tool("list_characters", "List characters in a series. Required: series_id", self._list_characters)
        self._tool("add_character", "Add a character to a series. Required: series_id, name. Optional: role, description, appearance, personality", self._add_character)
        self._tool("update_character", "Update a character. Required: series_id, character_id. Optional: name, role, description, appearance, personality", self._update_character)
        self._tool("delete_character", "Delete a character. Required: series_id, character_id", self._delete_character)

        self._tool("save_world_bible", "Save the world bible for a series. Required: series_id, content", self._save_world_bible)

        # === Video Generation Tools ===
        self._tool("generate_video", "Generate a video with full advanced pipeline. Required: prompt. Optional: model, style, num_frames, fps, steps, seed, enhance, negative_prompt, width, height, guidance_scale, guidance_rescale, solver, flow_shift, use_karras_sigmas, use_dynamic_shifting, decode_timestep, decode_noise_scale, camera_enabled, camera_motion, camera_direction, camera_speed, camera_intensity, camera_fov, motion_intensity, temporal_smoothing, flicker_elimination, upscale, upscale_model, interpolate_fps, interpolate_motion_blur, color_grading, effects, codec, crf, preset, tune, profile, pixel_format, audio, native_audio, tts_text, tts_voice, ambient_prompt, music_prompt", self._generate_video)
        self._tool("check_generation_status", "Check status of a generation job. Required: job_id", self._check_generation)
        self._tool("download_video", "Download a generated video. Required: job_id", self._download_video)

        # === Narrative Memory Tools ===
        self._tool("get_memory_state", "Get narrative memory state for a scene. Required: series_id, season_number, episode_number, scene_number", self._get_memory_state)
        self._tool("assess_scene", "Run quality assessment on a scene. Required: series_id, season_number, episode_number, scene_number. Optional: notes", self._assess_scene)
        self._tool("push_nested_story", "Push a nested story onto the narrative stack. Required: series_id, season_number, episode_number, scene_number, story_title, story_prompt", self._push_nested_story)
        self._tool("pop_nested_story", "Pop the current nested story from the stack. Required: series_id, season_number, episode_number, scene_number", self._pop_nested_story)
        self._tool("get_narrative_stack", "Get the current narrative stack for a scene. Required: series_id, season_number, episode_number, scene_number", self._get_narrative_stack)
        self._tool("get_learning_state", "Get the learning engine state and rules", self._get_learning_state)

        # === Action Log Tools ===
        self._tool("get_recent_actions", "Get recent user actions from the log. Optional: count, category, source", self._get_recent_actions)
        self._tool("get_action_stats", "Get statistics about logged actions", self._get_action_stats)
        self._tool("search_actions", "Search action log for specific events. Optional: action_contains, source, result, limit", self._search_actions)
        self._tool("add_upgrade_note", "Add an upgrade note for later review. Required: idea. Optional: context, severity", self._add_upgrade_note)
        self._tool("get_upgrade_notes", "Read all upgrade notes", self._get_upgrade_notes)

        # === System Tools ===
        self._tool("get_system_status", "Get full system status including GPU backend, models, and features", self._get_system_status)
        self._tool("get_available_models", "List all available video generation models with capabilities", self._get_models)
        self._tool("get_available_styles", "List all available video styles", self._get_styles)
        self._tool("get_settings_options", "Get all available setting options (aspect ratios, quality modes, camera presets, schedulers, codecs, transitions, upscale models, TTS voices, setting presets)", self._get_settings_options)
        self._tool("apply_setting_preset", "Apply a named setting preset. Required: preset_name (cinematic_short, social_media_vertical, anime_sequence, documentary_clip, fast_preview, music_video, horror_atmosphere)", self._apply_setting_preset)

        # === Scene Settings Tools ===
        self._tool("set_scene_settings", "Set comprehensive settings for a scene. Required: series_id, season_number, episode_number, scene_number, settings (dict)", self._set_scene_settings)
        self._tool("get_scene_settings", "Get settings for a scene. Required: series_id, season_number, episode_number, scene_number", self._get_scene_settings)
        self._tool("batch_apply_settings", "Apply settings to multiple scenes at once. Required: series_id, season_number, episode_number, settings (dict). Optional: start_scene, end_scene", self._batch_apply_settings)
        self._tool("color_grade_scene", "Apply color grading to a scene's video. Required: series_id, season_number, episode_number, scene_number. Optional: contrast, saturation, temperature, brightness, hue, gamma, vignette_enabled, vignette_intensity, film_grain_enabled, film_grain_amount, sharpen_enabled, sharpen_amount", self._color_grade_scene)
        self._tool("set_episode_transitions", "Set transition type and duration for an episode. Required: series_id, season_number, episode_number. Optional: transition_type (cut, xfade, fade, dissolve, wipe_left, wipe_right, slide, zoom, flash), duration", self._set_episode_transitions)
        self._tool("attach_audio", "Attach audio config to a scene. Required: series_id, season_number, episode_number, scene_number. Optional: tts_text, tts_voice, ambient_prompt, music_prompt, music_volume, ambient_volume", self._attach_audio)
        self._tool("shot_match_scene", "Match color/contrast of a scene to a reference scene. Required: series_id, season_number, episode_number, scene_number, reference_scene", self._shot_match_scene)
        self._tool("set_config", "Set a configuration value. Required: key, value", self._set_config)
        self._tool("get_config", "Get configuration. Optional: key (returns all if omitted)", self._get_config)

        # === Image Studio Tools ===
        self._tool("generate_image", "Generate an image. Required: prompt (for T2I). Optional: model (flux, sdxl, sd15, nano_banana, seedream, gpt_image for T2I; kontext, seedream_edit, nano_banana_edit, seededit_v3, upscaler, bg_remover, face_swap, image_extender for I2I), negative_prompt, aspect_ratio (1:1, 16:9, 9:16, 4:3, 3:2, 21:9, 4:5), quality (draft, standard, high, ultra), seed, batch_count, style_preset, width, height, guidance_scale, steps, lora_model, lora_weight, reference_strength, image_mode (t2i or i2i), reference_images", self._generate_image)
        self._tool("check_image_status", "Check image generation status. Required: job_id", self._check_image_status)
        self._tool("get_image_models", "List all available image generation models (T2I and I2I)", self._get_image_models)
        self._tool("get_image_options", "Get all image generation options (aspect ratios, quality presets, styles, enhance tags, quick prompts)", self._get_image_options)
        self._tool("list_images", "List all locally saved images", self._list_images)
        self._tool("image_to_video", "Send a generated image to the video generation pipeline as a first frame. Required: image_url or job_id. Optional: prompt, model, style, num_frames, fps, steps", self._image_to_video)

        # === Asset Library Tools ===
        self._tool("create_asset", "Create a new reusable asset in the library. Required: name, category (character, location, vehicle, object, building, effect). Optional: subtype, description, tags, image_refs, prompt, model", self._create_asset)
        self._tool("list_assets", "List assets in the library. Optional: category, subtype, tag, series_id, search, limit", self._list_assets)
        self._tool("get_asset", "Get a single asset by ID. Required: asset_id", self._get_asset)
        self._tool("update_asset", "Update asset properties. Required: asset_id. Optional: name, description, tags, subtype, locked, metadata", self._update_asset)
        self._tool("add_asset_version", "Add a new version to an asset. Required: asset_id, image_refs. Optional: description, prompt, model, notes", self._add_asset_version)
        self._tool("rollback_asset", "Rollback asset to a previous version. Required: asset_id, version_num", self._rollback_asset)
        self._tool("get_asset_archive", "Get full version history for an asset. Required: asset_id", self._get_asset_archive)
        self._tool("bind_asset_to_series", "Bind an asset to a series for consistency tracking. Required: asset_id, series_id. Optional: seasons, episodes", self._bind_asset_to_series)
        self._tool("get_consistency_refs", "Get consistency reference images and descriptions for all locked assets in a series. Required: series_id. Optional: scene_prompt", self._get_consistency_refs)
        self._tool("parse_script", "Parse a movie script to extract characters, locations, vehicles, objects, creatures. Required: script_text. Optional: title", self._parse_script)
        self._tool("get_asset_categories", "List all asset categories with subtypes and icons", self._get_asset_categories)

        # === Resources (read-only state inspection) ===
        self._resource("system.state", "Current system state and status", self._get_system_status)
        self._resource("production.series", "All series in the production suite", self._list_series)
        self._resource("action_log.recent", "Recent action log events", lambda: self._get_recent_actions({"count": 50}))
        self._resource("action_log.stats", "Action log statistics", self._get_action_stats)
        self._resource("upgrade_notes", "All upgrade notes", self._get_upgrade_notes)
        self._resource("settings.options", "All available setting options", self._get_settings_options)
        self._resource("image.models", "All available image generation models", self._get_image_models)
        self._resource("image.options", "All available image generation options", self._get_image_options)

    def _tool(self, name: str, description: str, handler):
        """Register a tool (callable action)."""
        self._tools[name] = {"description": description, "handler": handler}

    def _resource(self, name: str, description: str, handler):
        """Register a resource (read-only state)."""
        self._resources[name] = {"description": description, "handler": handler}

    def list_tools(self) -> list:
        """List all available tools with descriptions."""
        return [{"name": k, "description": v["description"]} for k, v in self._tools.items()]

    def list_resources(self) -> list:
        """List all available resources with descriptions."""
        return [{"name": k, "description": v["description"]} for k, v in self._resources.items()]

    def execute(self, tool_name: str, params: dict = None) -> dict:
        """Execute a tool by name with given parameters.

        Returns:
            {"success": bool, "result": ..., "error": ..., "tool": tool_name, "params": params}
        """
        if tool_name not in self._tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}", "available": list(self._tools.keys())}

        if self.action_logger:
            self.action_logger.log(f"ai.tool.{tool_name}", {"params": params}, source="ai")

        try:
            result = self._tools[tool_name]["handler"](params or {})
            return {"success": True, "result": result, "tool": tool_name}
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tool": tool_name,
                "params": params,
            }

    def read_resource(self, resource_name: str) -> dict:
        """Read a resource by name."""
        if resource_name not in self._resources:
            return {"success": False, "error": f"Unknown resource: {resource_name}"}
        try:
            result = self._resources[resource_name]["handler"]()
            return {"success": True, "result": result, "resource": resource_name}
        except Exception as e:
            return {"success": False, "error": str(e), "resource": resource_name}

    # === Tool Handlers ===

    def _list_series(self, params):
        if not self.production_suite:
            return {"error": "Production suite not available"}
        return self.production_suite._call_endpoint("GET", "/api/series")

    def _create_series(self, params):
        if not self.production_suite:
            return {"error": "Production suite not available"}
        return self.production_suite._call_endpoint("POST", "/api/series", body=params)

    def _get_series(self, params):
        sid = params.get("series_id")
        if not sid:
            return {"error": "series_id required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}")

    def _update_series(self, params):
        sid = params.get("series_id")
        if not sid:
            return {"error": "series_id required"}
        body = {k: v for k, v in params.items() if k != "series_id"}
        return self.production_suite._call_endpoint("PUT", f"/api/series/{sid}", body=body)

    def _delete_series(self, params):
        sid = params.get("series_id")
        if not sid:
            return {"error": "series_id required"}
        return self.production_suite._call_endpoint("DELETE", f"/api/series/{sid}")

    def _list_seasons(self, params):
        sid = params.get("series_id")
        if not sid:
            return {"error": "series_id required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}/seasons")

    def _get_season(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        if not sid or sn is None:
            return {"error": "series_id and season_number required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}/seasons/{sn}")

    def _list_episodes(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        if not sid or sn is None:
            return {"error": "series_id and season_number required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}/seasons/{sn}/episodes")

    def _create_episode(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        if not sid or sn is None:
            return {"error": "series_id and season_number required"}
        body = {k: v for k, v in params.items() if k not in ("series_id", "season_number")}
        return self.production_suite._call_endpoint("POST", f"/api/series/{sid}/seasons/{sn}/episodes", body=body)

    def _get_episode(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not sid or sn is None or en is None:
            return {"error": "series_id, season_number, episode_number required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}/seasons/{sn}/episodes/{en}")

    def _update_episode(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not sid or sn is None or en is None:
            return {"error": "series_id, season_number, episode_number required"}
        body = {k: v for k, v in params.items() if k not in ("series_id", "season_number", "episode_number")}
        return self.production_suite._call_endpoint("PUT", f"/api/series/{sid}/seasons/{sn}/episodes/{en}", body=body)

    def _delete_episode(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not sid or sn is None or en is None:
            return {"error": "series_id, season_number, episode_number required"}
        return self.production_suite._call_endpoint("DELETE", f"/api/series/{sid}/seasons/{sn}/episodes/{en}")

    def _enhance_script(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not sid or sn is None or en is None:
            return {"error": "series_id, season_number, episode_number required"}
        return self.production_suite._call_endpoint("POST", f"/api/series/{sid}/seasons/{sn}/episodes/{en}/enhance")

    def _breakdown_episode(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not sid or sn is None or en is None:
            return {"error": "series_id, season_number, episode_number required"}
        return self.production_suite._call_endpoint("POST", f"/api/series/{sid}/seasons/{sn}/episodes/{en}/breakdown")

    def _list_scenes(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not sid or sn is None or en is None:
            return {"error": "series_id, season_number, episode_number required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes")

    def _get_scene(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not sid or sn is None or en is None or sc is None:
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}")

    def _update_scene(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not sid or sn is None or en is None or sc is None:
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        body = {k: v for k, v in params.items() if k not in ("series_id", "season_number", "episode_number", "scene_number")}
        return self.production_suite._call_endpoint("PUT", f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}", body=body)

    def _generate_scene(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not sid or sn is None or en is None or sc is None:
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        return self.production_suite._call_endpoint("POST", f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/generate")

    def _retake_scene(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not sid or sn is None or en is None or sc is None:
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        return self.production_suite._call_endpoint("POST", f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/retake")

    def _list_characters(self, params):
        sid = params.get("series_id")
        if not sid:
            return {"error": "series_id required"}
        return self.production_suite._call_endpoint("GET", f"/api/series/{sid}/characters")

    def _add_character(self, params):
        sid = params.get("series_id")
        if not sid:
            return {"error": "series_id required"}
        body = {k: v for k, v in params.items() if k != "series_id"}
        return self.production_suite._call_endpoint("POST", f"/api/series/{sid}/characters", body=body)

    def _update_character(self, params):
        sid = params.get("series_id")
        cid = params.get("character_id")
        if not sid or not cid:
            return {"error": "series_id and character_id required"}
        body = {k: v for k, v in params.items() if k not in ("series_id", "character_id")}
        return self.production_suite._call_endpoint("PUT", f"/api/series/{sid}/characters/{cid}", body=body)

    def _delete_character(self, params):
        sid = params.get("series_id")
        cid = params.get("character_id")
        if not sid or not cid:
            return {"error": "series_id and character_id required"}
        return self.production_suite._call_endpoint("DELETE", f"/api/series/{sid}/characters/{cid}")

    def _save_world_bible(self, params):
        sid = params.get("series_id")
        if not sid:
            return {"error": "series_id required"}
        body = {"content": params.get("content", "")}
        return self.production_suite._call_endpoint("PUT", f"/api/series/{sid}/world-bible", body=body)

    # === Video Generation ===

    def _generate_video(self, params):
        import urllib.request
        url = self.server_app.config.get("gpu_backend_url", "") if self.server_app else ""
        if not url:
            return {"error": "No GPU backend configured"}
        try:
            payload = json.dumps(params).encode("utf-8")
            req = urllib.request.Request(
                f"{url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions-AI/1.0"},
                method="POST"
            )
            import urllib.request as ur
            with ur.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def _check_generation(self, params):
        job_id = params.get("job_id")
        if not job_id:
            return {"error": "job_id required"}
        import urllib.request
        url = self.server_app.config.get("gpu_backend_url", "") if self.server_app else ""
        if not url:
            return {"error": "No GPU backend configured"}
        try:
            req = urllib.request.Request(f"{url}/api/status/{job_id}",
                                         headers={"User-Agent": "SoulIllusions-AI/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def _download_video(self, params):
        job_id = params.get("job_id")
        if not job_id:
            return {"error": "job_id required"}
        return {"url": f"/api/download/{job_id}", "note": "Use GET request to download the video file"}

    # === Narrative Memory ===

    def _get_memory_state(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        return self.production_suite._call_endpoint("GET",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/memory")

    def _assess_scene(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        body = {"notes": params.get("notes", "")}
        return self.production_suite._call_endpoint("POST",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/assess", body=body)

    def _push_nested_story(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        body = {
            "story_title": params.get("story_title", ""),
            "story_prompt": params.get("story_prompt", ""),
        }
        return self.production_suite._call_endpoint("POST",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/push-story", body=body)

    def _pop_nested_story(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        return self.production_suite._call_endpoint("POST",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/pop-story")

    def _get_narrative_stack(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        return self.production_suite._call_endpoint("GET",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/narrative-stack")

    def _get_learning_state(self, params):
        return self.production_suite._call_endpoint("GET", "/api/learning/state")

    # === Action Log ===

    def _get_recent_actions(self, params):
        if not self.action_logger:
            return {"error": "Action logger not available"}
        return self.action_logger.get_recent_events(
            count=params.get("count", 50),
            category=params.get("category"),
            source=params.get("source"),
        )

    def _get_action_stats(self, params):
        if not self.action_logger:
            return {"error": "Action logger not available"}
        return self.action_logger.get_stats()

    def _search_actions(self, params):
        if not self.action_logger:
            return {"error": "Action logger not available"}
        return self.action_logger.search_events(
            action_contains=params.get("action_contains"),
            source=params.get("source"),
            result=params.get("result"),
            limit=params.get("limit", 50),
        )

    def _add_upgrade_note(self, params):
        if not self.action_logger:
            return {"error": "Action logger not available"}
        self.action_logger.note_upgrade_idea(
            idea=params.get("idea", ""),
            context=params.get("context"),
            severity=params.get("severity", "info"),
        )
        return {"status": "note added"}

    def _get_upgrade_notes(self, params):
        if not self.action_logger:
            return {"error": "Action logger not available"}
        path = self.action_logger.upgrade_notes_path
        if not os.path.exists(path):
            return {"notes": ""}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return {"notes": f.read()}
        except Exception as e:
            return {"error": str(e)}

    # === System ===

    def _get_system_status(self, params):
        status = {
            "production_suite": "available" if self.production_suite else "unavailable",
            "action_logger": "available" if self.action_logger else "unavailable",
            "tools_count": len(self._tools),
            "resources_count": len(self._resources),
        }
        if self.server_app:
            import urllib.request
            url = self.server_app.config.get("gpu_backend_url", "")
            status["gpu_backend_url"] = url
            if url:
                try:
                    req = urllib.request.Request(f"{url}/api/status",
                                                 headers={"User-Agent": "SoulIllusions-AI/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        status["gpu_backend"] = json.loads(resp.read().decode())
                except Exception as e:
                    status["gpu_backend"] = {"status": "offline", "error": str(e)}
            else:
                status["gpu_backend"] = {"status": "not_configured"}
        if self.action_logger:
            status["action_log"] = self.action_logger.get_stats()
        return status

    def _get_models(self, params):
        return {
            "models": [
                {"id": "auto", "name": "Auto", "desc": "Automatically select best model"},
                {"id": "ltx", "name": "LTX-Video", "desc": "Fastest (768x512, 24fps)", "resolution": "768x512"},
                {"id": "wan22", "name": "Wan 2.2 TI2V-5B", "desc": "Best quality 720P (1280x704, 24fps)", "resolution": "1280x704"},
                {"id": "motif", "name": "Motif-Video 2B", "desc": "Balanced 720P GGUF (1280x736, 24fps)", "resolution": "1280x736"},
                {"id": "helios", "name": "Helios-Distilled", "desc": "Real-time minute-scale (832x480, 24fps)", "resolution": "832x480"},
                {"id": "holocine", "name": "HoloCine", "desc": "Multi-shot narrative (1280x704, 24fps)", "resolution": "1280x704"},
            ]
        }

    def _get_styles(self, params):
        return {
            "styles": ["cinematic", "realistic", "anime", "documentary", "music video", "social media",
                       "noir", "vintage", "cyberpunk", "fantasy", "horror", "romance", "action",
                       "dreamy", "3d_render", "watercolor", "comic_book", "claymation"]
        }

    def _get_settings_options(self, params):
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

    def _apply_setting_preset(self, params):
        preset_name = params.get("preset_name")
        if not preset_name:
            return {"error": "preset_name required"}
        try:
            from settings_schema import SETTING_PRESETS, apply_preset
            if preset_name not in SETTING_PRESETS:
                return {"error": f"Unknown preset: {preset_name}", "available": list(SETTING_PRESETS.keys())}
            settings = apply_preset(preset_name)
            return {"status": "applied", "preset": preset_name, "settings": settings}
        except ImportError:
            return {"error": "settings_schema not available"}

    # === Scene Settings Handlers ===

    def _set_scene_settings(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        body = {"settings": params.get("settings", {})}
        return self.production_suite._call_endpoint("PUT",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/settings", body=body)

    def _get_scene_settings(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        return self.production_suite._call_endpoint("GET",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/settings")

    def _batch_apply_settings(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not all([sid, sn is not None, en is not None]):
            return {"error": "series_id, season_number, episode_number required"}
        body = {
            "settings": params.get("settings", {}),
            "start_scene": params.get("start_scene", 1),
            "end_scene": params.get("end_scene", 0),
        }
        return self.production_suite._call_endpoint("POST",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/batch-settings", body=body)

    def _color_grade_scene(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        body = {k: v for k, v in params.items() if k not in ("series_id", "season_number", "episode_number", "scene_number")}
        return self.production_suite._call_endpoint("POST",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/color-grade", body=body)

    def _set_episode_transitions(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        if not all([sid, sn is not None, en is not None]):
            return {"error": "series_id, season_number, episode_number required"}
        body = {k: v for k, v in params.items() if k not in ("series_id", "season_number", "episode_number")}
        return self.production_suite._call_endpoint("PUT",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/transitions", body=body)

    def _attach_audio(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        if not all([sid, sn is not None, en is not None, sc is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number required"}
        body = {k: v for k, v in params.items() if k not in ("series_id", "season_number", "episode_number", "scene_number")}
        return self.production_suite._call_endpoint("POST",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/audio", body=body)

    def _shot_match_scene(self, params):
        sid = params.get("series_id")
        sn = params.get("season_number")
        en = params.get("episode_number")
        sc = params.get("scene_number")
        ref = params.get("reference_scene")
        if not all([sid, sn is not None, en is not None, sc is not None, ref is not None]):
            return {"error": "series_id, season_number, episode_number, scene_number, reference_scene required"}
        body = {"reference_scene": ref}
        return self.production_suite._call_endpoint("POST",
            f"/api/series/{sid}/seasons/{sn}/episodes/{en}/scenes/{sc}/shot-match", body=body)

    def _set_config(self, params):
        key = params.get("key")
        value = params.get("value")
        if not key:
            return {"error": "key required"}
        if self.server_app:
            self.server_app.config[key] = value
            return {"status": "ok", "key": key, "value": value}
        return {"error": "Server not available"}

    def _get_config(self, params):
        if not self.server_app:
            return {"error": "Server not available"}
        key = params.get("key")
        if key:
            return {key: self.server_app.config.get(key)}
        return self.server_app.config

    # === Image Studio Handlers ===

    def _generate_image(self, params):
        import urllib.request
        url = self.server_app.config.get("gpu_backend_url", "") if self.server_app else ""
        if not url:
            return {"error": "No GPU backend configured"}
        try:
            payload = json.dumps(params).encode("utf-8")
            request = urllib.request.Request(
                f"{url}/api/image/generate",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SoulIllusions/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(request, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def _check_image_status(self, params):
        import urllib.request
        job_id = params.get("job_id")
        if not job_id:
            return {"error": "job_id required"}
        url = self.server_app.config.get("gpu_backend_url", "") if self.server_app else ""
        if not url:
            return {"error": "No GPU backend configured"}
        try:
            request = urllib.request.Request(
                f"{url}/api/image/status/{job_id}",
                headers={"User-Agent": "SoulIllusions/1.0"}
            )
            with urllib.request.urlopen(request, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def _get_image_models(self, params=None):
        try:
            from settings_schema import T2I_MODELS, I2I_MODELS
            return {
                "t2i": {k: {"label": v["label"], "desc": v["desc"], "resolutions": v["resolutions"], "aspect_ratios": v["aspect_ratios"]} for k, v in T2I_MODELS.items()},
                "i2i": {k: {"label": v["label"], "desc": v["desc"], "max_images": v["max_images"], "resolutions": v["resolutions"], "aspect_ratios": v["aspect_ratios"]} for k, v in I2I_MODELS.items()},
            }
        except ImportError:
            return {"error": "settings_schema not available"}

    def _get_image_options(self, params=None):
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
                "t2i_models": list(T2I_MODELS.keys()),
                "i2i_models": list(I2I_MODELS.keys()),
            }
        except ImportError:
            return {"error": "settings_schema not available"}

    def _list_images(self, params=None):
        import urllib.request
        base_url = f"http://localhost:{self.server_app.config.get('port', 7860)}" if self.server_app else ""
        if not base_url:
            return {"error": "Server not available"}
        try:
            request = urllib.request.Request(
                f"{base_url}/api/images",
                headers={"User-Agent": "SoulIllusions/1.0"}
            )
            with urllib.request.urlopen(request, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def _image_to_video(self, params):
        """Bridge: use a generated image as first frame for video generation."""
        image_url = params.get("image_url")
        job_id = params.get("job_id")
        if not image_url and job_id:
            image_url = f"/api/image/download/{job_id}"
        if not image_url:
            return {"error": "image_url or job_id required"}
        # Build video generation payload with image as first frame
        video_params = {
            "prompt": params.get("prompt", ""),
            "model": params.get("model", "auto"),
            "style": params.get("style", "cinematic"),
            "num_frames": params.get("num_frames", 97),
            "fps": params.get("fps", 24),
            "steps": params.get("steps", 30),
            "first_frame_image": image_url,
        }
        return self._generate_video(video_params)

    # === Asset Library Handlers ===
    def _get_asset_library(self):
        try:
            from asset_library import AssetLibrary
            from pathlib import Path
            lib = AssetLibrary(str(Path(__file__).parent / "asset_data"))
            return lib
        except ImportError:
            return None

    def _create_asset(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        try:
            asset = lib.create_asset(
                name=params["name"], category=params["category"],
                subtype=params.get("subtype", ""), description=params.get("description", ""),
                tags=params.get("tags", []), image_refs=params.get("image_refs", []),
                prompt=params.get("prompt", ""), model=params.get("model", ""),
            )
            return {"asset": asset.to_dict(), "status": "created"}
        except Exception as e:
            return {"error": str(e)}

    def _list_assets(self, params=None):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        p = params or {}
        return {"assets": lib.list_assets(category=p.get("category"), subtype=p.get("subtype"),
                tag=p.get("tag"), series_id=p.get("series_id"), search=p.get("search"),
                limit=p.get("limit", 100))}

    def _get_asset(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        a = lib.get_asset(params.get("asset_id", ""))
        if not a:
            return {"error": "Asset not found"}
        return {"asset": a.to_dict()}

    def _update_asset(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        a = lib.update_asset(params.get("asset_id", ""),
            name=params.get("name"), description=params.get("description"),
            tags=params.get("tags"), subtype=params.get("subtype"),
            locked=params.get("locked"), metadata=params.get("metadata"))
        if not a:
            return {"error": "Asset not found"}
        return {"asset": a.to_dict(), "status": "updated"}

    def _add_asset_version(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        v = lib.add_version(params.get("asset_id", ""),
            image_refs=params.get("image_refs", []),
            description=params.get("description"),
            prompt=params.get("prompt", ""), model=params.get("model", ""),
            notes=params.get("notes", ""))
        if not v:
            return {"error": "Asset not found"}
        return {"version": v.to_dict(), "status": "added"}

    def _rollback_asset(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        ok = lib.rollback(params.get("asset_id", ""), params.get("version_num", 0))
        return {"status": "rolled_back" if ok else "failed"}

    def _get_asset_archive(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        return lib.get_archive(params.get("asset_id", ""))

    def _bind_asset_to_series(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        ok = lib.bind_to_series(params.get("asset_id", ""), params.get("series_id", ""),
            params.get("seasons", []), params.get("episodes", []))
        return {"status": "bound" if ok else "failed"}

    def _get_consistency_refs(self, params):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        refs = lib.get_consistency_refs(params.get("series_id", ""), params.get("scene_prompt", ""))
        enhanced = lib.build_generation_prompt(params.get("series_id", ""), params.get("scene_prompt", ""))
        return {"refs": refs, "enhanced_prompt": enhanced}

    def _parse_script(self, params):
        try:
            from script_parser import ScriptParser
            parser = ScriptParser()
            return parser.parse_and_extract(params.get("script_text", ""), params.get("title", ""))
        except ImportError:
            return {"error": "Script parser not available"}

    def _get_asset_categories(self, params=None):
        lib = self._get_asset_library()
        if not lib:
            return {"error": "Asset library not available"}
        return {"categories": lib.get_categories()}

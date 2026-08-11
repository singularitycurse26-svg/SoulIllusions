"""
SoulIllusions Script Parser
=============================
Parses movie/TV scripts to extract characters, locations, vehicles, objects,
creatures, and other assets. Generates image prompts for each entity.

Inspired by:
- DSPy script-to-storyboard pipeline (Asset Extract -> Scene Segment -> Consolidation -> Prompt Generation)
- Story Claw (script parsing -> structured JSON with characters, locations, emotions, actions)
- Vidtory Drama Studio (script decomposition into scenes, shots, characters, locations)
- MiniStory AI (script planning -> character/location extraction -> image generation)

Supports:
- Standard screenplay format (Courier, ALL CAPS character names, INT./EXT. scene headings)
- Fountain format (lightweight markdown-like screenplay format)
- Plain text narratives
"""

import re
import json
import time
from typing import Optional


# === Patterns for screenplay parsing ===
SCENE_HEADING_RE = re.compile(
    r'^(?:INT\.|EXT\.|INT\/EXT\.|EST\.|I\/E\.)\s*(.+?)(?:\s*[-\u2014]\s*(.+))?$',
    re.IGNORECASE | re.MULTILINE
)
CHARACTER_RE = re.compile(
    r'^\s{10,}([A-Z][A-Z0-9\s\'.\-]+?)(?:\s*\([^)]+\))?\s*$',
    re.MULTILINE
)
PARENTHETICAL_RE = re.compile(r'\([^)]*\)')
TRANSITION_RE = re.compile(
    r'^(CUT TO:|FADE OUT\.|FADE IN:|DISSOLVE TO:|SMASH CUT:|MATCH CUT:|JUMP CUT:|FADE TO BLACK)',
    re.IGNORECASE | re.MULTILINE
)

# Entity extraction patterns from action/description lines
VEHICLE_KEYWORDS = [
    "car", "truck", "van", "bus", "motorcycle", "helicopter", "plane", "airplane",
    "jet", "fighter", "spaceship", "shuttle", "rocket", "boat", "ship", "submarine",
    "yacht", "destroyer", "cruiser", "carrier", "train", "subway", "tram",
    "tank", "mech", "robot", "walker", "speeder", "pod",
]
OBJECT_KEYWORDS = [
    "sword", "gun", "rifle", "pistol", "knife", "blade", "axe", "bow", "arrow",
    "shield", "armor", "helmet", "staff", "wand", "crystal", "amulet", "ring",
    "crown", "scepter", "book", "scroll", "map", "device", "gadget", "computer",
    "phone", "radio", "camera", "binoculars", "telescope", "microscope",
    "key", "lock", "chest", "box", "crate", "barrel", "bottle", "vial",
    "potion", "artifact", "relic", "totem", "idol", "statue", "painting",
]
CREATURE_KEYWORDS = [
    "dragon", "wolf", "tiger", "lion", "bear", "eagle", "hawk", "falcon",
    "snake", "serpent", "spider", "scorpion", "shark", "whale", "kraken",
    "phoenix", "griffin", "unicorn", "centaur", "minotaur", "golem",
    "zombie", "vampire", "werewolf", "ghost", "demon", "angel", "alien",
    "mutant", "cyborg", "android", "robot", "giant", "troll", "ogre",
    "goblin", "elf", "dwarf", "fairy", "sprite", "elemental",
]


class ExtractedEntity:
    """An entity extracted from a script (character, location, vehicle, etc.)."""
    def __init__(self, name: str, entity_type: str, subtype: str = "",
                 description: str = "", first_appearance: str = "",
                 appearances: list = None, suggested_prompt: str = "",
                 confidence: float = 1.0):
        self.name = name
        self.entity_type = entity_type
        self.subtype = subtype
        self.description = description
        self.first_appearance = first_appearance
        self.appearances = appearances or []
        self.suggested_prompt = suggested_prompt
        self.confidence = confidence
        self.tags = []

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "subtype": self.subtype,
            "description": self.description,
            "first_appearance": self.first_appearance,
            "appearances": self.appearances,
            "suggested_prompt": self.suggested_prompt,
            "confidence": self.confidence,
            "tags": self.tags,
        }


class ParsedScene:
    """A scene parsed from a script."""
    def __init__(self, scene_num: int, heading: str, location: str = "",
                 time_of_day: str = "", description: str = "",
                 characters: list = None, action_lines: list = None,
                 dialogue_count: int = 0):
        self.scene_num = scene_num
        self.heading = heading
        self.location = location
        self.time_of_day = time_of_day
        self.description = description
        self.characters = characters or []
        self.action_lines = action_lines or []
        self.dialogue_count = dialogue_count

    def to_dict(self) -> dict:
        return {
            "scene_num": self.scene_num,
            "heading": self.heading,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "description": self.description,
            "characters": self.characters,
            "action_lines": self.action_lines[:5],
            "dialogue_count": self.dialogue_count,
        }


class ScriptParseResult:
    """Complete result of parsing a script."""
    def __init__(self, title: str = "", raw_text: str = ""):
        self.title = title
        self.raw_text = raw_text
        self.entities: list = []
        self.scenes: list = []
        self.metadata = {
            "total_scenes": 0,
            "total_characters": 0,
            "total_locations": 0,
            "total_vehicles": 0,
            "total_objects": 0,
            "total_creatures": 0,
            "parsed_at": time.time(),
        }
        self.errors = []

    def add_entity(self, entity: ExtractedEntity):
        existing = next((e for e in self.entities
                        if e.name.lower() == entity.name.lower()
                        and e.entity_type == entity.entity_type), None)
        if existing:
            existing.appearances.extend(entity.appearances)
            if not existing.description and entity.description:
                existing.description = entity.description
        else:
            self.entities.append(entity)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "metadata": self.metadata,
            "entities": [e.to_dict() for e in self.entities],
            "scenes": [s.to_dict() for s in self.scenes],
            "errors": self.errors,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class ScriptParser:
    """
    Parses scripts to extract entities and scenes.
    Generates image prompts for each entity for use in the Image Studio.
    """

    def parse(self, script_text: str, title: str = "") -> ScriptParseResult:
        result = ScriptParseResult(title=title or self._guess_title(script_text),
                                   raw_text=script_text)
        lines = script_text.split("\n")
        self._parse_scenes(lines, result)
        self._parse_characters(script_text, result)
        self._parse_locations_from_scenes(result)
        self._parse_action_entities(script_text, result)
        self._generate_prompts(result)
        self._update_metadata(result)
        return result

    def _guess_title(self, text: str) -> str:
        first_line = text.strip().split("\n")[0].strip()
        if first_line.startswith("Title:"):
            return first_line.replace("Title:", "").strip()
        if first_line.startswith("# "):
            return first_line.replace("# ", "").strip()
        if len(first_line) < 80 and not first_line.isupper():
            return first_line
        return "Untitled Script"

    def _parse_scenes(self, lines: list, result: ScriptParseResult):
        scene_num = 0
        current_scene = None
        action_buffer = []

        for i, line in enumerate(lines):
            heading_match = SCENE_HEADING_RE.match(line.strip())
            if heading_match:
                if current_scene:
                    current_scene.action_lines = action_buffer
                    result.scenes.append(current_scene)
                scene_num += 1
                heading = line.strip()
                location = heading_match.group(1).strip()
                time_of_day = heading_match.group(2).strip() if heading_match.group(2) else ""
                current_scene = ParsedScene(
                    scene_num=scene_num, heading=heading,
                    location=location, time_of_day=time_of_day,
                    description="",
                )
                action_buffer = []
            elif current_scene:
                stripped = line.strip()
                if stripped and not CHARACTER_RE.match(line) and not TRANSITION_RE.match(stripped):
                    if not PARENTHETICAL_RE.fullmatch(stripped):
                        action_buffer.append(stripped)
                        if not current_scene.description:
                            current_scene.description = stripped

        if current_scene:
            current_scene.action_lines = action_buffer
            result.scenes.append(current_scene)

    def _parse_characters(self, text: str, result: ScriptParseResult):
        seen = set()
        for m in CHARACTER_RE.finditer(text):
            name = m.group(1).strip()
            if len(name) < 2 or name.startswith("(") or name.islower():
                continue
            if name.upper() in ("CONTINUOUS", "CUT TO", "FADE OUT", "FADE IN", "DISSOLVE",
                                "THE END", "FIN", "END OF", "SCENE", "ACT"):
                continue
            clean_name = PARENTHETICAL_RE.sub("", name).strip()
            if clean_name.lower() in seen:
                continue
            seen.add(clean_name.lower())

            first_appearance = ""
            for scene in result.scenes:
                if clean_name.upper() in scene.heading.upper() or any(
                    clean_name.upper() in al.upper() for al in scene.action_lines
                ):
                    first_appearance = scene.heading
                    scene.characters.append(clean_name)
                    break

            entity = ExtractedEntity(
                name=clean_name,
                entity_type="character",
                description="",
                first_appearance=first_appearance,
                appearances=[first_appearance] if first_appearance else [],
            )
            result.add_entity(entity)

    def _parse_locations_from_scenes(self, result: ScriptParseResult):
        seen = set()
        for scene in result.scenes:
            loc = scene.location
            if not loc or loc.lower() in seen:
                continue
            seen.add(loc.lower())
            entity = ExtractedEntity(
                name=loc,
                entity_type="location",
                description=scene.description[:200] if scene.description else "",
                first_appearance=scene.heading,
                appearances=[scene.heading],
            )
            result.add_entity(entity)

    def _parse_action_entities(self, text: str, result: ScriptParseResult):
        lines = text.split("\n")
        action_text = " ".join(
            line.strip() for line in lines
            if line.strip() and not CHARACTER_RE.match(line)
            and not SCENE_HEADING_RE.match(line.strip())
            and not TRANSITION_RE.match(line.strip())
        )

        for kw in VEHICLE_KEYWORDS:
            pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+' + kw + r'\b', re.IGNORECASE)
            for m in pattern.finditer(action_text):
                name = f"{m.group(1)} {kw}".strip()
                if not any(e.name.lower() == name.lower() for e in result.entities):
                    entity = ExtractedEntity(
                        name=name, entity_type="vehicle", subtype=kw,
                        description=f"A {kw} mentioned in the script",
                        confidence=0.7,
                    )
                    result.add_entity(entity)

        for kw in CREATURE_KEYWORDS:
            pattern = re.compile(r'\b(' + kw + r')\b', re.IGNORECASE)
            for m in pattern.finditer(action_text):
                name = kw.capitalize()
                if not any(e.name.lower() == name.lower() for e in result.entities):
                    entity = ExtractedEntity(
                        name=name, entity_type="creature", subtype=kw,
                        description=f"A {kw} appearing in the script",
                        confidence=0.6,
                    )
                    result.add_entity(entity)

        for kw in OBJECT_KEYWORDS:
            pattern = re.compile(r'\b([A-Z][a-z]+)?\s*' + kw + r'\b', re.IGNORECASE)
            for m in pattern.finditer(action_text):
                prefix = m.group(1)
                name = f"{prefix} {kw}".strip() if prefix else kw.capitalize()
                if not any(e.name.lower() == name.lower() for e in result.entities):
                    entity = ExtractedEntity(
                        name=name, entity_type="object", subtype=kw,
                        description=f"A {kw} referenced in the script",
                        confidence=0.5,
                    )
                    result.add_entity(entity)

    def _generate_prompts(self, result: ScriptParseResult):
        for entity in result.entities:
            entity.suggested_prompt = self._build_prompt(entity, result)

    def _build_prompt(self, entity: ExtractedEntity, result: ScriptParseResult) -> str:
        etype = entity.entity_type
        name = entity.name
        desc = entity.description

        if etype == "character":
            prompt = f"Full body character design of {name}"
            if desc:
                prompt += f", {desc}"
            prompt += (", professional concept art, highly detailed, clean background, "
                       "character reference sheet, front view, neutral pose, "
                       "suitable for animation reference")
        elif etype == "location":
            prompt = f"{name} environment establishing shot"
            if desc:
                prompt += f", {desc}"
            prompt += (", wide angle, cinematic lighting, highly detailed, "
                       "concept art environment, atmospheric, depth of field")
        elif etype == "vehicle":
            prompt = f"{name} vehicle design"
            if desc:
                prompt += f", {desc}"
            prompt += (", multiple angle reference, side profile and front view, "
                       "clean background, highly detailed concept art, "
                       "industrial design render")
        elif etype == "creature":
            prompt = f"{name} creature design"
            if desc:
                prompt += f", {desc}"
            prompt += (", full body, dynamic pose, concept art, highly detailed, "
                       "mythical creature reference, clean background")
        elif etype == "object":
            prompt = f"{name} prop design"
            if desc:
                prompt += f", {desc}"
            prompt += (", product photography style, clean background, "
                       "highly detailed, studio lighting, multiple angles")
        else:
            prompt = f"{name}, highly detailed, concept art"

        if entity.first_appearance:
            prompt += f" (from scene: {entity.first_appearance})"

        return prompt

    def _update_metadata(self, result: ScriptParseResult):
        cats = {}
        for e in result.entities:
            cats[e.entity_type] = cats.get(e.entity_type, 0) + 1
        result.metadata = {
            "total_scenes": len(result.scenes),
            "total_characters": cats.get("character", 0),
            "total_locations": cats.get("location", 0),
            "total_vehicles": cats.get("vehicle", 0),
            "total_objects": cats.get("object", 0),
            "total_creatures": cats.get("creature", 0),
            "total_entities": len(result.entities),
            "parsed_at": time.time(),
        }

    def generate_batch_prompts(self, parse_result: ScriptParseResult,
                               category: str = None) -> list:
        """Generate a list of {name, prompt, category} for batch image generation."""
        prompts = []
        for entity in parse_result.entities:
            if category and entity.entity_type != category:
                continue
            prompts.append({
                "name": entity.name,
                "prompt": entity.suggested_prompt,
                "category": entity.entity_type,
                "subtype": entity.subtype,
                "description": entity.description,
            })
        return prompts

    def parse_and_extract(self, script_text: str, title: str = "") -> dict:
        """Convenience: parse and return dict ready for API response."""
        result = self.parse(script_text, title)
        return result.to_dict()

"""
SoulIllusions Asset Library System
===================================
Manages reusable image assets (characters, locations, vehicles, objects, creatures, etc.)
with versioning, categorization, series binding, and consistency tracking.

Inspired by:
- Kling Elements 3.0 (multi-angle reference images, subject binding)
- Runway Gen-4 References (@tag system)
- Pika Scene Ingredients (separate character/outfit/prop images)
- DSPy script-to-storyboard pipeline (asset extraction → linking → prompting)
- Pixo asset library (character/scene/general types with @tagging)
"""

import json
import os
import time
import copy
import hashlib
from pathlib import Path
from typing import Optional


# === Asset Categories ===
ASSET_CATEGORIES = {
    "character": {
        "label": "Character",
        "icon": "🎭",
        "subtypes": ["person", "ai_robot", "alien", "animal", "creature", "cell_biology", "mythical_being"],
        "default_angles": ["front", "side", "back", "detail"],
        "desc": "People, robots, aliens, animals, creatures — anything that moves and acts",
    },
    "location": {
        "label": "Location",
        "icon": "🏔️",
        "subtypes": ["city", "landscape", "interior", "exterior", "space", "underwater", "fantasy_realm"],
        "default_angles": ["wide", "close", "aerial", "detail"],
        "desc": "Cities, landscapes, interiors, buildings, worlds",
    },
    "vehicle": {
        "label": "Vehicle",
        "icon": "🚗",
        "subtypes": ["car", "truck", "aircraft", "spacecraft", "boat", "train", "motorcycle", "mech"],
        "default_angles": ["front", "side", "back", "detail"],
        "desc": "Cars, ships, planes, mechs, spacecraft",
    },
    "object": {
        "label": "Object / Prop",
        "icon": "📦",
        "subtypes": ["weapon", "tool", "device", "furniture", "artifact", "food", "document"],
        "default_angles": ["front", "side", "detail", "context"],
        "desc": "Props, weapons, devices, artifacts — things characters interact with",
    },
    "building": {
        "label": "Building / Structure",
        "icon": "🏛️",
        "subtypes": ["skyscraper", "house", "temple", "fortress", "ruin", "station", "monument"],
        "default_angles": ["wide", "side", "aerial", "detail"],
        "desc": "Buildings, structures, architecture",
    },
    "effect": {
        "label": "Effect / FX",
        "icon": "✨",
        "subtypes": ["explosion", "magic", "weather", "energy", "particle", "lighting"],
        "default_angles": ["main", "variation", "detail", "context"],
        "desc": "Visual effects, magic, explosions, weather",
    },
}


class AssetVersion:
    """A single version of an asset — stores image refs, description, and metadata."""
    def __init__(self, version_num: int, image_refs: list, description: str,
                 prompt: str = "", negative_prompt: str = "", model: str = "",
                 settings: dict = None, notes: str = "", created_by: str = "user"):
        self.version_num = version_num
        self.image_refs = image_refs  # list of URLs/paths
        self.description = description
        self.prompt = prompt
        self.negative_prompt = negative_prompt or ""
        self.model = model
        self.settings = settings or {}
        self.notes = notes
        self.created_by = created_by
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "version": self.version_num,
            "image_refs": self.image_refs,
            "description": self.description,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "model": self.model,
            "settings": self.settings,
            "notes": self.notes,
            "created_by": self.created_by,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict):
        v = cls(
            version_num=d.get("version", 1),
            image_refs=d.get("image_refs", []),
            description=d.get("description", ""),
            prompt=d.get("prompt", ""),
            negative_prompt=d.get("negative_prompt", ""),
            model=d.get("model", ""),
            settings=d.get("settings", {}),
            notes=d.get("notes", ""),
            created_by=d.get("created_by", "user"),
        )
        v.timestamp = d.get("timestamp", time.time())
        return v


class Asset:
    """A reusable asset with version history and series bindings."""
    def __init__(self, asset_id: str, name: str, category: str,
                 subtype: str = "", description: str = "",
                 tags: list = None, series_bindings: list = None):
        self.asset_id = asset_id
        self.name = name
        self.category = category
        self.subtype = subtype
        self.description = description
        self.tags = tags or []
        self.series_bindings = series_bindings or []  # list of {series_id, seasons: [], episodes: []}
        self.versions: list[AssetVersion] = []
        self.current_version: int = 0
        self.locked: bool = False  # locked = consistency enforced
        self.created = time.time()
        self.updated = time.time()
        self.metadata = {}  # extra fields: voice_profile, color_palette, etc.

    @property
    def latest(self) -> Optional[AssetVersion]:
        if not self.versions:
            return None
        sorted_v = sorted(self.versions, key=lambda v: v.version_num)
        return sorted_v[-1]

    @property
    def active_version(self) -> Optional[AssetVersion]:
        for v in self.versions:
            if v.version_num == self.current_version:
                return v
        return self.latest

    def add_version(self, image_refs: list, description: str = None,
                    prompt: str = "", negative_prompt: str = "", model: str = "",
                    settings: dict = None, notes: str = "") -> AssetVersion:
        next_num = (max(v.version_num for v in self.versions) + 1) if self.versions else 1
        v = AssetVersion(
            version_num=next_num,
            image_refs=image_refs,
            description=description or self.description,
            prompt=prompt, negative_prompt=negative_prompt, model=model,
            settings=settings, notes=notes,
        )
        self.versions.append(v)
        self.current_version = next_num
        self.updated = time.time()
        if description:
            self.description = description
        return v

    def rollback(self, version_num: int) -> bool:
        for v in self.versions:
            if v.version_num == version_num:
                self.current_version = version_num
                self.updated = time.time()
                return True
        return False

    def compare_versions(self, v1: int, v2: int) -> dict:
        ver1 = next((v for v in self.versions if v.version_num == v1), None)
        ver2 = next((v for v in self.versions if v.version_num == v2), None)
        if not ver1 or not ver2:
            return {"error": "Version not found"}
        return {
            "v1": ver1.to_dict(), "v2": ver2.to_dict(),
            "diffs": {
                "description_changed": ver1.description != ver2.description,
                "images_changed": ver1.image_refs != ver2.image_refs,
                "prompt_changed": ver1.prompt != ver2.prompt,
                "model_changed": ver1.model != ver2.model,
            }
        }

    def bind_to_series(self, series_id: str, seasons: list = None, episodes: list = None):
        existing = next((b for b in self.series_bindings if b["series_id"] == series_id), None)
        if existing:
            if seasons:
                for s in seasons:
                    if s not in existing["seasons"]:
                        existing["seasons"].append(s)
            if episodes:
                for e in episodes:
                    if e not in existing["episodes"]:
                        existing["episodes"].append(e)
        else:
            self.series_bindings.append({
                "series_id": series_id,
                "seasons": seasons or [],
                "episodes": episodes or [],
            })
        self.updated = time.time()

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "category": self.category,
            "subtype": self.subtype,
            "description": self.description,
            "tags": self.tags,
            "series_bindings": self.series_bindings,
            "versions": [v.to_dict() for v in self.versions],
            "current_version": self.current_version,
            "locked": self.locked,
            "created": self.created,
            "updated": self.updated,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict):
        a = cls(
            asset_id=d["asset_id"],
            name=d["name"],
            category=d["category"],
            subtype=d.get("subtype", ""),
            description=d.get("description", ""),
            tags=d.get("tags", []),
            series_bindings=d.get("series_bindings", []),
        )
        a.versions = [AssetVersion.from_dict(v) for v in d.get("versions", [])]
        a.current_version = d.get("current_version", 0)
        a.locked = d.get("locked", False)
        a.created = d.get("created", time.time())
        a.updated = d.get("updated", time.time())
        a.metadata = d.get("metadata", {})
        return a


class AssetLibrary:
    """
    Central asset library — stores, retrieves, versions, and manages
    all reusable image assets for SoulIllusions productions.
    """
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path("asset_data")
        self.data_dir.mkdir(exist_ok=True)
        self.assets: dict[str, Asset] = {}
        self._load()

    def _library_path(self) -> Path:
        return self.data_dir / "asset_library.json"

    def _load(self):
        p = self._library_path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for aid, ad in data.get("assets", {}).items():
                    self.assets[aid] = Asset.from_dict(ad)
            except Exception as e:
                print(f"[AssetLibrary] Warning: could not load library: {e}")

    def _save(self):
        p = self._library_path()
        data = {"assets": {aid: a.to_dict() for aid, a in self.assets.items()}}
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _gen_id(self, name: str, category: str) -> str:
        base = f"{category}_{name}".lower().replace(" ", "_").replace("/", "_")[:40]
        h = hashlib.md5(f"{base}_{time.time()}".encode()).hexdigest()[:8]
        return f"{base}_{h}"

    def create_asset(self, name: str, category: str, subtype: str = "",
                     description: str = "", tags: list = None,
                     image_refs: list = None, prompt: str = "",
                     negative_prompt: str = "", model: str = "",
                     settings: dict = None, notes: str = "") -> Asset:
        if category not in ASSET_CATEGORIES:
            raise ValueError(f"Unknown category: {category}. Available: {list(ASSET_CATEGORIES.keys())}")
        asset_id = self._gen_id(name, category)
        asset = Asset(asset_id=asset_id, name=name, category=category,
                      subtype=subtype, description=description, tags=tags or [])
        if image_refs:
            asset.add_version(image_refs=image_refs, description=description,
                              prompt=prompt, negative_prompt=negative_prompt,
                              model=model, settings=settings, notes=notes)
        self.assets[asset_id] = asset
        self._save()
        return asset

    def get_asset(self, asset_id: str) -> Optional[Asset]:
        return self.assets.get(asset_id)

    def update_asset(self, asset_id: str, name: str = None, description: str = None,
                     tags: list = None, subtype: str = None, locked: bool = None,
                     metadata: dict = None) -> Optional[Asset]:
        a = self.assets.get(asset_id)
        if not a:
            return None
        if name is not None: a.name = name
        if description is not None: a.description = description
        if tags is not None: a.tags = tags
        if subtype is not None: a.subtype = subtype
        if locked is not None: a.locked = locked
        if metadata is not None: a.metadata = {**a.metadata, **metadata}
        a.updated = time.time()
        self._save()
        return a

    def add_version(self, asset_id: str, image_refs: list, description: str = None,
                    prompt: str = "", negative_prompt: str = "", model: str = "",
                    settings: dict = None, notes: str = "") -> Optional[AssetVersion]:
        a = self.assets.get(asset_id)
        if not a:
            return None
        v = a.add_version(image_refs=image_refs, description=description,
                          prompt=prompt, negative_prompt=negative_prompt,
                          model=model, settings=settings, notes=notes)
        self._save()
        return v

    def rollback(self, asset_id: str, version_num: int) -> bool:
        a = self.assets.get(asset_id)
        if not a:
            return False
        result = a.rollback(version_num)
        if result:
            self._save()
        return result

    def compare_versions(self, asset_id: str, v1: int, v2: int) -> dict:
        a = self.assets.get(asset_id)
        if not a:
            return {"error": "Asset not found"}
        return a.compare_versions(v1, v2)

    def delete_asset(self, asset_id: str) -> bool:
        if asset_id in self.assets:
            del self.assets[asset_id]
            self._save()
            return True
        return False

    def list_assets(self, category: str = None, subtype: str = None,
                    tag: str = None, series_id: str = None,
                    search: str = None, limit: int = 100) -> list:
        results = []
        for a in self.assets.values():
            if category and a.category != category:
                continue
            if subtype and a.subtype != subtype:
                continue
            if tag and tag not in a.tags:
                continue
            if series_id and not any(b["series_id"] == series_id for b in a.series_bindings):
                continue
            if search:
                s = search.lower()
                if s not in a.name.lower() and s not in a.description.lower() and s not in " ".join(a.tags).lower():
                    continue
            results.append(a.to_dict())
        results.sort(key=lambda x: x.get("updated", 0), reverse=True)
        return results[:limit]

    def bind_to_series(self, asset_id: str, series_id: str,
                       seasons: list = None, episodes: list = None) -> bool:
        a = self.assets.get(asset_id)
        if not a:
            return False
        a.bind_to_series(series_id, seasons, episodes)
        self._save()
        return True

    def get_series_assets(self, series_id: str) -> dict:
        """Get all assets bound to a series, grouped by category."""
        grouped = {cat: [] for cat in ASSET_CATEGORIES}
        for a in self.assets.values():
            if any(b["series_id"] == series_id for b in a.series_bindings):
                grouped.setdefault(a.category, []).append(a.to_dict())
        return grouped

    def get_consistency_refs(self, series_id: str, scene_prompt: str = "") -> dict:
        """
        Given a series and optional scene prompt, return reference images
        and descriptions for all locked assets bound to that series.
        This is what gets injected into video generation for consistency.
        """
        refs = {"characters": [], "locations": [], "vehicles": [], "objects": [], "buildings": [], "effects": []}
        for a in self.assets.values():
            if not a.locked:
                continue
            if not any(b["series_id"] == series_id for b in a.series_bindings):
                continue
            v = a.active_version
            if not v:
                continue
            entry = {
                "asset_id": a.asset_id,
                "name": a.name,
                "description": v.description,
                "image_refs": v.image_refs,
                "prompt": v.prompt,
                "tag": f"@{a.name.lower().replace(' ', '_')}",
            }
            cat_key = a.category + "s" if a.category in refs else "objects"
            refs.setdefault(cat_key, []).append(entry)
        return refs

    def build_generation_prompt(self, series_id: str, scene_prompt: str) -> str:
        """
        Build an enhanced prompt that includes consistency references
        for all locked assets bound to the series.
        """
        refs = self.get_consistency_refs(series_id, scene_prompt)
        parts = [scene_prompt]
        for cat, items in refs.items():
            for item in items:
                parts.append(f"[{item['tag']}: {item['description']}]")
        return " ".join(parts)

    def get_archive(self, asset_id: str) -> dict:
        """Return full version history for an asset (the image archive)."""
        a = self.assets.get(asset_id)
        if not a:
            return {"error": "Asset not found"}
        return {
            "asset_id": asset_id,
            "name": a.name,
            "current_version": a.current_version,
            "versions": [v.to_dict() for v in sorted(a.versions, key=lambda v: v.version_num)],
        }

    def get_categories(self) -> dict:
        return {k: {"label": v["label"], "icon": v["icon"], "desc": v["desc"],
                     "subtypes": v["subtypes"], "default_angles": v["default_angles"]}
                for k, v in ASSET_CATEGORIES.items()}

    def stats(self) -> dict:
        by_cat = {}
        for a in self.assets.values():
            by_cat[a.category] = by_cat.get(a.category, 0) + 1
        total_versions = sum(len(a.versions) for a in self.assets.values())
        return {
            "total_assets": len(self.assets),
            "by_category": by_cat,
            "total_versions": total_versions,
            "locked_assets": sum(1 for a in self.assets.values() if a.locked),
        }

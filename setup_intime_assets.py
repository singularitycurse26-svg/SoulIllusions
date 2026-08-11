"""Parse the In Time Episode 1 script through the asset library and create assets."""
import json
import urllib.request
from pathlib import Path

SERVER = "http://localhost:7860"

def api_post(path, data):
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        SERVER + path, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def api_get(path):
    req = urllib.request.Request(SERVER + path)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def main():
    # 1. Retry scene breakdown
    print("[1] Breaking down Episode 1 into scenes...")
    try:
        result = api_post("/api/production/series/in_time_television/season/1/episode/1/breakdown", {
            "scene_duration": 5,
            "model": "ltx",
            "style": "cinematic",
            "num_frames": 97,
            "fps": 24,
            "steps": 30,
        })
        if result.get("status") == "broken_down":
            print(f"  {result['scene_count']} scenes created!")
            print(f"  Estimated duration: {result['estimated_duration']}s")
        else:
            print(f"  Result: {result}")
    except Exception as e:
        print(f"  Breakdown error: {e}")

    # 2. Parse script through asset library
    print("\n[2] Parsing script through asset library...")
    script_text = Path("scripts/in_time_ep1.txt").read_text(encoding="utf-8")
    try:
        result = api_post("/api/script/parse", {
            "script_text": script_text,
            "title": "In Time - Episode 1: The Clock Starts"
        })
        meta = result.get("metadata", {})
        print(f"  Scenes: {meta.get('total_scenes', 0)}")
        print(f"  Characters: {meta.get('total_characters', 0)}")
        print(f"  Locations: {meta.get('total_locations', 0)}")
        print(f"  Vehicles: {meta.get('total_vehicles', 0)}")
        print(f"  Objects: {meta.get('total_objects', 0)}")
        print(f"  Creatures: {meta.get('total_creatures', 0)}")
        entities = result.get("entities", [])
        print(f"  Total entities: {len(entities)}")
        for e in entities:
            print(f"    - {e['name']} ({e['entity_type']})")
    except Exception as e:
        print(f"  Parse error: {e}")
        return

    # 3. Create assets from parsed entities
    print(f"\n[3] Creating {len(entities)} assets from script...")
    created = 0
    for e in entities:
        cat = e["entity_type"]
        if cat == "creature":
            cat = "character"
        try:
            resp = api_post("/api/assets/create", {
                "name": e["name"],
                "category": cat,
                "subtype": e.get("subtype", ""),
                "description": e.get("description", ""),
                "tags": [e["entity_type"], "in_time", "ep1"],
                "prompt": e.get("suggested_prompt", ""),
            })
            if not resp.get("error"):
                created += 1
                print(f"  + {e['name']} ({cat})")
        except Exception as ex:
            print(f"  ! {e['name']}: {ex}")
    print(f"  Created {created} assets.")

    # 4. Bind all assets to the series
    print("\n[4] Binding assets to series 'in_time_television'...")
    assets = api_get("/api/assets?tag=in_time").get("assets", [])
    bound = 0
    for a in assets:
        try:
            resp = api_post(f"/api/assets/{a['asset_id']}/bind", {
                "series_id": "in_time_television",
                "seasons": [1],
                "episodes": [1]
            })
            if resp.get("status") == "bound":
                bound += 1
        except Exception:
            pass
    print(f"  Bound {bound} assets to series.")

    # 5. Lock character assets for consistency
    print("\n[5] Locking character assets for consistency...")
    locked = 0
    for a in assets:
        if a["category"] == "character":
            try:
                payload = json.dumps({"locked": True}).encode("utf-8")
                req = urllib.request.Request(
                    f"{SERVER}/api/assets/{a['asset_id']}",
                    data=payload, headers={"Content-Type": "application/json"},
                    method="PUT"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    r = json.loads(resp.read().decode())
                    if r.get("status") == "updated":
                        locked += 1
                        print(f"  Locked: {a['name']}")
            except Exception:
                pass
    print(f"  Locked {locked} character assets.")

    # 6. Show final stats
    print("\n[6] Final asset library stats:")
    stats = api_get("/api/assets/stats")
    print(f"  Total assets: {stats.get('total_assets', 0)}")
    print(f"  Total versions: {stats.get('total_versions', 0)}")
    print(f"  Locked assets: {stats.get('locked_assets', 0)}")
    print(f"  By category: {stats.get('by_category', {})}")

    print("\n" + "=" * 60)
    print("  IN TIME EPISODE 1 - SETUP COMPLETE!")
    print("=" * 60)
    print(f"\n  Series: In Time Television (in_time_television)")
    print(f"  Episode: S1E1 'Tick' - script uploaded, enhanced, broken into scenes")
    print(f"  Assets: {created} created from script, {bound} bound to series, {locked} locked")
    print(f"\n  Open http://localhost:7860 in your browser to see:")
    print(f"  - Production Suite tab: Series, Episode 1, scene breakdowns")
    print(f"  - Asset Library tab: All In Time characters, locations, vehicles, props")
    print(f"\n  Next: Generate images for each asset in Image Studio,")
    print(f"  then generate video scenes with consistency refs.")

if __name__ == "__main__":
    main()

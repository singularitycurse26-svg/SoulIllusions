"""
Setup script to initialize the In Time Television series in the SoulIllusions Production Suite.
Run this script to create the series, add characters, and upload the Episode 1 script.
"""
import json
import urllib.request
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from intime_series_bible import SERIES_BIBLE, EPISODE_1_SCRIPT

SERVER_URL = "http://localhost:7860"
PROD_API = SERVER_URL + "/api/production"


def api_post(path, data):
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        PROD_API + path,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"error": str(e)}


def api_get(path):
    req = urllib.request.Request(PROD_API + path)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"error": str(e)}


def main():
    print("=" * 60)
    print("  In Time Television - Production Suite Setup")
    print("=" * 60)

    # Check server is running
    print("\n[1] Checking server connection...")
    try:
        urllib.request.urlopen(SERVER_URL, timeout=5)
        print("  Server is running.")
    except Exception:
        print("  ERROR: Cannot connect to server at", SERVER_URL)
        print("  Make sure SoulIllusions server is running (launch.bat)")
        return

    # Create series
    print("\n[2] Creating series: In Time Television...")
    result = api_post("/series/create", {
        "title": SERIES_BIBLE["title"],
        "description": SERIES_BIBLE["description"],
        "concept": SERIES_BIBLE["concept"],
        "genre": SERIES_BIBLE["genre"],
        "target_episode_duration": SERIES_BIBLE["target_episode_duration"],
        "seasons_planned": SERIES_BIBLE["seasons_planned"],
        "episodes_per_season": SERIES_BIBLE["episodes_per_season"],
    })

    if result.get("status") == "created":
        series_id = result["series_id"]
        print(f"  Created! Series ID: {series_id}")
    elif "already exists" in result.get("error", ""):
        series_id = "in_time_television"
        print(f"  Series already exists. Using ID: {series_id}")
    else:
        print(f"  Failed: {result}")
        return

    # Update world bible
    print("\n[3] Uploading world bible...")
    bible_data = api_get("/series/" + series_id)
    if "world_bible" not in bible_data:
        bible_data["world_bible"] = SERIES_BIBLE["world_bible"]

    payload = json.dumps({"world_bible": SERIES_BIBLE["world_bible"]}).encode("utf-8")
    req = urllib.request.Request(
        PROD_API + "/series/" + series_id,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("  World bible uploaded.")
    except Exception as e:
        print(f"  Warning: {e}")

    # Add characters
    print(f"\n[4] Adding {len(SERIES_BIBLE['characters'])} characters...")
    for cid, char in SERIES_BIBLE["characters"].items():
        result = api_post(f"/series/{series_id}/characters", {
            "name": char["name"],
            "description": char["description"],
            "appearance": char["appearance"],
            "personality": char["personality"],
            "background": char.get("background", ""),
            "voice_profile": char.get("voice_profile", ""),
        })
        if result.get("status") == "added":
            print(f"  + {char['name']}")
        elif "already" in result.get("error", "").lower():
            print(f"  ~ {char['name']} (already exists)")
        else:
            print(f"  ! {char['name']}: {result}")

    # Create Episode 1
    print("\n[5] Creating Season 1, Episode 1: 'Tick'...")
    result = api_post(f"/series/{series_id}/season/1/episode/1", {
        "title": "Tick",
        "synopsis": (
            "In Dayton Zone, Kai Morrow lives day-to-day, literally. When a stranger "
            "gives him a century of time before timing out, Kai's life is transformed. "
            "But the Time Authority wants that time back, and a time-keeper named Sable "
            "Cross is assigned to find him."
        ),
        "script_raw": EPISODE_1_SCRIPT,
        "target_duration": 2700,
    })

    if result.get("status") == "created":
        print("  Episode 1 created!")
    elif "already" in str(result.get("error", "")).lower():
        print("  Episode 1 already exists. Updating script...")
        # Upload script to existing episode
        result = api_post(f"/series/{series_id}/season/1/episode/1/script/upload", {
            "script_text": EPISODE_1_SCRIPT,
            "title": "Tick",
        })
        if result.get("status") == "uploaded":
            print(f"  Script uploaded! ({result['word_count']} words)")
    else:
        print(f"  Failed: {result}")
        return

    # Upload script
    print("\n[6] Uploading Episode 1 script...")
    result = api_post(f"/series/{series_id}/season/1/episode/1/script/upload", {
        "script_text": EPISODE_1_SCRIPT,
        "title": "Tick",
    })
    if result.get("status") == "uploaded":
        print(f"  Script uploaded! {result['word_count']} words, {result['char_count']} chars")
    else:
        print(f"  Warning: {result}")

    # Enhance script
    print("\n[7] Enhancing script (cinematic level)...")
    result = api_post(f"/series/{series_id}/season/1/episode/1/script/enhance", {
        "enhancement_level": "cinematic",
        "focus_areas": "visual detail, character emotion, atmosphere, camera work",
    })
    if result.get("status") == "enhanced":
        print(f"  Enhanced! {result['original_words']} → {result['enhanced_words']} words ({result['expansion_ratio']} expansion)")
    else:
        print(f"  Warning: {result}")

    # Break down into scenes
    print("\n[8] Breaking down Episode 1 into scenes...")
    result = api_post(f"/series/{series_id}/season/1/episode/1/breakdown", {
        "scene_duration": 5,
        "model": "ltx",
        "style": "cinematic",
        "num_frames": 97,
        "fps": 24,
        "steps": 30,
    })
    if result.get("status") == "broken_down":
        print(f"  {result['scene_count']} scenes created!")
        print(f"  Estimated duration: {result['estimated_duration']}s (target: {result['target_duration']}s)")
    else:
        print(f"  Warning: {result}")

    print("\n" + "=" * 60)
    print("  SETUP COMPLETE!")
    print("=" * 60)
    print(f"\n  Series: {SERIES_BIBLE['title']}")
    print(f"  Series ID: {series_id}")
    print(f"  Characters: {len(SERIES_BIBLE['characters'])}")
    print(f"  Episode 1: 'Tick' - script uploaded and enhanced")
    print(f"\n  Next steps:")
    print(f"  1. Open {SERVER_URL} in your browser")
    print(f"  2. Go to the 'Production Suite' tab")
    print(f"  3. Open the In Time Television series")
    print(f"  4. Navigate to Season 1 → Episode 1")
    print(f"  5. Review the timeline and scene breakdowns")
    print(f"  6. Connect your GPU backend (Colab notebook)")
    print(f"  7. Click 'Generate All Scenes' to start video generation")
    print(f"  8. After generation, click 'Assemble Episode'")
    print(f"  9. Click 'Upload to SoulTube' to publish")
    print()


if __name__ == "__main__":
    main()

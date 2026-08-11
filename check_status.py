import urllib.request, json
resp = urllib.request.urlopen("http://localhost:7860/api/assets?limit=50")
data = json.loads(resp.read().decode())
assets = data.get("assets", [])
print(f"Total assets: {len(assets)}")
for a in assets:
    name = a.get("name", "?")
    cat = a.get("category", "?")
    locked = a.get("locked", False)
    bound = bool(a.get("series_bindings"))
    print(f"  {name} ({cat}) locked={locked} bound={bound}")

# Check episode breakdown
resp2 = urllib.request.urlopen("http://localhost:7860/api/production/series/in_time_television/season/1/episode/1")
ep = json.loads(resp2.read().decode())
scenes = ep.get("scenes", [])
print(f"\nEpisode 1 scenes: {len(scenes)}")
for s in scenes:
    print(f"  Scene {s.get('scene_number', '?')}: {s.get('prompt', '')[:60]}...")

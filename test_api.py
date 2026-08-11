import urllib.request, json
# Test stats endpoint (was 404 before fix)
resp = urllib.request.urlopen("http://localhost:7860/api/assets/stats")
stats = json.loads(resp.read().decode())
print("Stats endpoint:", json.dumps(stats, indent=2))

# Test categories endpoint
resp2 = urllib.request.urlopen("http://localhost:7860/api/assets/categories")
cats = json.loads(resp2.read().decode())
print("\nCategories:", list(cats.get("categories", {}).keys()))

# Test asset list
resp3 = urllib.request.urlopen("http://localhost:7860/api/assets?limit=5")
data = json.loads(resp3.read().decode())
print(f"\nAssets loaded: {len(data.get('assets', []))}")
for a in data.get("assets", [])[:5]:
    print(f"  {a['name']} ({a['category']})")

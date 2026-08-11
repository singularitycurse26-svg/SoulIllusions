import urllib.request
resp = urllib.request.urlopen("http://localhost:7860")
html = resp.read().decode('utf-8')
# Save to file for inspection
with open('served_page.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Page size: {len(html)} chars")

# Check for switchTab in the served page
if 'function switchTab' in html:
    idx = html.index('function switchTab')
    print(f"\nswitchTab found at char {idx}:")
    print(html[idx:idx+300])
else:
    print("switchTab NOT FOUND in served page!")

# Check for the tab buttons
if 'onclick="switchTab' in html:
    idx = html.index('onclick="switchTab')
    print(f"\nTab button found:")
    print(html[idx-50:idx+80])
else:
    print("Tab onclick NOT FOUND!")

# Check for JS errors - look for unescaped quotes or broken syntax
# Check the init() call
if 'init();' in html:
    idx = html.index('init();')
    print(f"\ninit() call found at char {idx}:")
    print(html[idx-100:idx+50])

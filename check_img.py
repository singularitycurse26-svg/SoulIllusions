import urllib.request

req = urllib.request.Request('http://localhost:7860/api/image/file/img_intime_poster', headers={'User-Agent': 'Mozilla/5.0'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read()
    ct = resp.headers.get('content-type')
    print(f'Status: OK')
    print(f'Content-Type: {ct}')
    print(f'Size: {len(data)/1024:.0f} KB')
except Exception as e:
    print(f'Error: {e}')

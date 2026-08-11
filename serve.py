"""Simple HTTP server to play SoulIllusions in your browser."""
import http.server
import socketserver
import re

PORT = 8080

with open('mega_city_template.py', 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r"MEGA_CITY_TEMPLATE = r'''(.*?)'''", content, re.DOTALL)
if not match:
    print("ERROR: Could not extract HTML template from mega_city_template.py")
    exit(1)

html = match.group(1).replace('{{TITLE}}', 'SoulIllusions')

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args):
        pass

print(f"SoulIllusions running at http://localhost:{PORT}")
print("Press Ctrl+C to stop.")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()

"""SoulIllusions CLI - launch the game in your browser."""
import http.server
import socketserver
import re
import os
import sys
import webbrowser
import threading

PORT = 8080


def _load_template():
    template_path = os.path.join(os.path.dirname(__file__), "mega_city_template.py")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"MEGA_CITY_TEMPLATE = r'''(.*?)'''", content, re.DOTALL)
    if not match:
        print("ERROR: Could not extract HTML template from mega_city_template.py")
        sys.exit(1)
    return match.group(1).replace("{{TITLE}}", "SoulIllusions")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        html = _load_template()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    """Launch SoulIllusions in your browser."""
    print("=" * 50)
    print("  SoulIllusions - An Incentives Inc. Production")
    print("  Time is Life. Earn it. Spend it. Survive.")
    print("=" * 50)
    print()
    print(f"  Starting server on http://localhost:{PORT}")
    print("  Opening your browser...")
    print("  Press Ctrl+C to stop.")
    print()

    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    with socketserver.TCPServer(("", PORT), _Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  SoulIllusions stopped. Thanks for playing!")
            sys.exit(0)


if __name__ == "__main__":
    main()

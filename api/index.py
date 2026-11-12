"""Vercel Serverless Handler for HSI & KRX Sentiment Intelligence Dashboard."""

from http.server import BaseHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HTML_FILE = BASE_DIR / "public" / "index.html"
if not HTML_FILE.exists():
    HTML_FILE = BASE_DIR / "index.html"
if not HTML_FILE.exists():
    HTML_FILE = BASE_DIR / "report" / "dashboard.html"


class handler(BaseHTTPRequestHandler):
    """Vercel native BaseHTTPRequestHandler."""

    def do_GET(self):
        if HTML_FILE.exists():
            content = HTML_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(content)
        else:
            msg = b"Dashboard file not found."
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(msg)


def app(environ, start_response):
    """WSGI callable fallback."""
    if HTML_FILE.exists():
        content = HTML_FILE.read_bytes()
        status = "200 OK"
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(content))),
            ("Cache-Control", "public, max-age=3600"),
        ]
    else:
        content = b"Dashboard file not found."
        status = "404 Not Found"
        headers = [("Content-Type", "text/plain")]

    start_response(status, headers)
    return [content]

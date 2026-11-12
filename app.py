"""WSGI Entrypoint for Vercel Serverless Deployment.

Serves the interactive HSI & KRX Sentiment Intelligence Dashboard.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "index.html"
if not HTML_FILE.exists():
    HTML_FILE = BASE_DIR / "report" / "dashboard.html"


def app(environ, start_response):
    """Standard WSGI entrypoint for Vercel Python runtime."""
    if HTML_FILE.exists():
        content = HTML_FILE.read_bytes()
        status = "200 OK"
        response_headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(content))),
            ("Cache-Control", "public, max-age=3600"),
        ]
    else:
        content = b"Dashboard not found. Please run report/generate_dashboard.py first."
        status = "404 Not Found"
        response_headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(content))),
        ]

    start_response(status, response_headers)
    return [content]

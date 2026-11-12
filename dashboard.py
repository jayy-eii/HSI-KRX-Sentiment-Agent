#!/usr/bin/env python3
"""Local Interactive Web Server for HSI & KRX Sentiment Intelligence Dashboard.

Usage:
    python dashboard.py
    or:
    ./venv/bin/python dashboard.py

Serves the modern interactive dashboard at http://localhost:8000/ and opens it in your browser.
"""

import http.server
import os
import socketserver
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_DIR = PROJECT_ROOT / "report"
HTML_PATH = REPORT_DIR / "dashboard.html"
PORT = 8000


class DashboardHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler serving the interactive dashboard at root."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self):
        # Route root '/' to report/dashboard.html
        if self.path in ("/", "/index.html", "/dashboard"):
            self.path = "/report/dashboard.html"
        return super().do_GET()

    def log_message(self, format, *args):
        # Clean terminal logging
        sys.stderr.write(f"[DASHBOARD SERVER] {self.address_string()} - {format % args}\n")


def ensure_dashboard_built():
    """Build report/dashboard.html if it doesn't already exist."""
    if not HTML_PATH.exists():
        print("[INFO] Building report/dashboard.html from data/processed/all_posts.csv...")
        from report.generate_dashboard import generate_html_dashboard
        generate_html_dashboard()


def main():
    ensure_dashboard_built()

    # Change directory to project root
    os.chdir(PROJECT_ROOT)

    handler = DashboardHTTPRequestHandler
    # Allow port reuse so restarting is instant
    socketserver.TCPServer.allow_reuse_address = True

    try:
        with socketserver.TCPServer(("", PORT), handler) as httpd:
            url = f"http://localhost:{PORT}"
            print("\n" + "=" * 80)
            print("  HSI & KRX Sentiment Agent — Intelligence Dashboard")
            print("=" * 80)
            print(f"  * Local Server running at:  {url}")
            print(f"  * Master Dataset:           data/processed/all_posts.csv (488 posts)")
            print(f"  * Offline HTML File:        report/dashboard.html")
            print("-" * 80)
            print("  Press Ctrl+C to stop the server.")
            print("=" * 80 + "\n")

            # Auto-open browser
            try:
                webbrowser.open(url)
            except Exception:
                pass

            httpd.serve_forever()

    except OSError as e:
        if "Address already in use" in str(e):
            print(f"[ERROR] Port {PORT} is currently in use. You can access the existing instance at http://localhost:{PORT} or open report/dashboard.html directly in your browser.")
        else:
            raise e
    except KeyboardInterrupt:
        print("\n[INFO] Dashboard server stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()

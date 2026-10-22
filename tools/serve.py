#!/usr/bin/env python3
"""Preview public/ locally with Cloudflare Pages URL rules.

Usage:
    python3 tools/serve.py [port]

Serves /blog/ai/foo from foo.html and falls back to 404.html, matching how
Cloudflare Pages resolves extensionless URLs.
"""

import http.server
import os
import sys
from functools import partial
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "public"


class PagesHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        resolved = super().translate_path(path)
        if not os.path.exists(resolved) and os.path.exists(resolved + ".html"):
            return resolved + ".html"
        return resolved

    def send_error(self, code, message=None, explain=None):
        page = PUBLIC / "404.html"
        if code != 404 or not page.exists():
            return super().send_error(code, message, explain)
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(PagesHandler, directory=str(PUBLIC))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Serving {PUBLIC} at http://localhost:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()

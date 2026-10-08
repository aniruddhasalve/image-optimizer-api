
"""Small dependency-free REST utility service."""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def response(status: int, payload, content_type: str = "application/json"):
    if content_type == "application/json":
        data = json.dumps(payload, ensure_ascii=False).encode()
    elif isinstance(payload, str):
        data = payload.encode()
    else:
        data = payload
    return status, {"Content-Type": content_type, "Content-Length": str(len(data))}, data


def error(message: str, status: int = 400):
    return response(status, {"error": message})


class Handler(BaseHTTPRequestHandler):
    def _serve(self, method: str):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = None
        status, headers, body = handle(method, self.path.split("?", 1)[0], payload)
        self.send_response(status)
        for key, value in headers.items(): self.send_header(key, value)
        self.end_headers(); self.wfile.write(body)
    do_GET = lambda self: self._serve("GET")
    do_POST = lambda self: self._serve("POST")
    do_PUT = lambda self: self._serve("PUT")
    do_DELETE = lambda self: self._serve("DELETE")
    def log_message(self, *_): pass


import base64, os, subprocess, tempfile

def handle(method, path, payload):
    if method == "GET" and path == "/health": return response(200, {"ok": True, "service": "image-optimizer-api"})
    if method != "POST" or path != "/optimize": return error("route not found", 404)
    if not isinstance(payload, dict) or not payload.get("data"): return error("data is required")
    try: raw = base64.b64decode(payload["data"], validate=True)
    except Exception: return error("data must be base64")
    tool = os.environ.get("IMAGE_TOOL", "convert")
    try:
        with tempfile.TemporaryDirectory() as d:
            src, out = os.path.join(d, "in.bin"), os.path.join(d, "out.bin")
            open(src, "wb").write(raw); subprocess.run([tool, src, "-strip", out], check=True, timeout=30, capture_output=True)
            optimized = open(out, "rb").read()
            return response(200, {"data": base64.b64encode(optimized).decode(), "bytes": len(optimized), "saved_bytes": len(raw)-len(optimized)})
    except (OSError, subprocess.SubprocessError) as exc: return error(f"image optimization failed: {exc}", 503)


def serve(host="0.0.0.0", port=8080):
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve()

"""Kodr API — stdlib-only HTTP server exposing the engine as JSON endpoints.

Run:            python api.py [port]
Endpoints:
  GET  /v1/engines            -> list of engines + capabilities
  POST /v1/generate           -> {"description": str}      -> code
  POST /v1/map                -> {"description": str}      -> map JSON (kodr-map-v1)
  POST /v1/vision             -> multipart form "file"    -> scene report
Uses the same engine as the Space: HF router LLM when HF_TOKEN is present,
guaranteed local fallback otherwise.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import codegen, theme, three_d, vision  # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))

engines = {
    "v1/generate": "text -> playable game code (wall-clock ~2-15s; needs HF_TOKEN for the smart path)",
    "v1/map": "text -> kodr-map-v1 JSON (theme, grid, mechanics) for build pipelines",
    "v1/vision": "image/video -> scene report (palette, mood, structure) image or video",
    "v1/3d": "text/image -> OBJ/GLB/STL mesh (local voxel generator, always works)",
}


def _json(handler, obj, status=200):
    body = json.dumps(obj).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception:
        return {}


def _extract_multipart(raw, ctype):
    """Pull the first file payload out of a multipart/form-data body."""
    try:
        ct = ctype.split(";")
        boundary = next((p.split("=", 1)[1].strip('"') for p in ct if p.strip().startswith("boundary=")), None)
        if not boundary:
            return raw
        sep = ("--" + boundary).encode()
        parts = raw.split(sep)
        for part in parts:
            if b"\r\n\r\n" in part and b"filename=" in part[:512].lower() or b"filename=" in part:
                head, _, body = part.partition(b"\r\n\r\n")
                payload = body.rsplit(b"\r\n--", 1)[0]
                if payload:
                    return payload
        return raw
    except Exception:
        return raw


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.split("?")[0].rstrip("/") == "/v1/engines":
            return _json(self, {"engines": engines, "count": len(engines),
                                "llm_available": bool(os.environ.get("HF_TOKEN"))})
        return _json(self, {"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        try:
            if path == "/v1/generate":
                data = _read_json(self)
                res = codegen.generate(data.get("description", ""))
                return _json(self, {
                    "title": res["title"],
                    "engine": res["engine"],
                    "theme": res["meta"]["theme"],
                    "mechanics": res["meta"]["mechanics"],
                    "code": res["code"],
                })
            if path == "/v1/map":
                data = _read_json(self)
                key = theme.detect_theme(data.get("description", ""))
                pal = theme.PALETTES[key]
                grid = three_d.synthesize_grid(pal, key, size=int(data.get("size", 20)))
                return _json(self, {
                    "schema": "kodr-map-v1",
                    "theme": key,
                    "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in pal["colors"]],
                    "mechanics": theme.detect_mechanics(data.get("description", "")),
                    "tile_legend": [".", "#", "T", "R", "W", "L", "P", "S", "B", "G"],
                    "grid": grid,
                })
            if path == "/v1/vision":
                ctype = self.headers.get("Content-Type") or ""
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                media = _extract_multipart(raw, ctype) if ctype.startswith("multipart/") else raw
                tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_upload")
                os.makedirs(tmp, exist_ok=True)
                fp = os.path.join(tmp, "media.bin")
                with open(fp, "wb") as f:
                    f.write(media)
                rep = vision.analyze_image(fp)
                return _json(self, rep or {"ok": False, "error": "no media"})
            if path.startswith("/v1/3d"):
                data = _read_json(self)
                res = three_d.generate(text=data.get("description", ""),
                                       image_path=data.get("image_path"),
                                       size=int(data.get("size", 20)))
                import base64
                wrap = {}
                for k in ("obj", "glb", "stl"):
                    p = res.get(k)
                    if p and os.path.exists(p):
                        with open(p, "rb") as f:
                            wrap[k] = base64.b64encode(f.read()).decode()
                return _json(self, {"theme": res["theme"], "cloud": res.get("cloud"),
                                    "voxels": res["meta"]["voxels"], "files_b64": wrap})
        except Exception as e:
            return _json(self, {"error": str(e)}, 500)
        return _json(self, {"error": "not found"}, 404)


srv = ThreadingHTTPServer(("0.0.0.0", PORT), _H)


if __name__ == "__main__":
    print(f"Kodr API on :{PORT}")
    if not os.environ.get("HF_TOKEN"):
        print("No HF_TOKEN — using the guaranteed local fallback engine.")
    srv.serve_forever()
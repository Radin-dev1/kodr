"""Kodr API server — self-hosted auth, API keys, usage + the three models.

Run:  python server.py            (serves the site + API on :7860, override with KODR_PORT)
Stdlib only (sqlite3 + http.server); engine/ needs Pillow + numpy.

Auth is self-contained: PBKDF2-hashed passwords in SQLite, HMAC-signed session
cookies. No Supabase, no external services. Each model (nova1 / rex3d / prism1)
gets its own API key and per-key usage tracking.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    from engine import nova as nova_engine
    from engine import prism as prism_engine
    from engine import three_d as three_d_engine
    MODELS_OK = True
except Exception as e:  # pragma: no cover
    nova_engine = prism_engine = three_d_engine = None
    MODELS_ERROR = str(e)
    MODELS_OK = False

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "kodr.db")
SECRET_PATH = os.path.join(ROOT, "kodr_secret.txt")

MODELS = {
    "nova1": {"label": "Nova-1", "kind": "coding", "endpoint": "/api/v1/nova1/generate"},
    "rex3d": {"label": "rex3d", "kind": "3d", "endpoint": "/api/v1/rex3d/generate"},
    "prism1": {"label": "Prism-1", "kind": "2d", "endpoint": "/api/v1/prism1/generate"},
}
MAX_KEYS_PER_MODEL = 5


def _secret():
    if os.path.exists(SECRET_PATH):
        return open(SECRET_PATH, "rb").read().strip()
    s = secrets.token_bytes(32)
    with open(SECRET_PATH, "wb") as f:
        f.write(s)
    return s


SECRET = _secret()
_lock = threading.RLock()


def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            masked TEXT NOT NULL,
            revoked INTEGER DEFAULT 0,
            calls INTEGER DEFAULT 0,
            bytes INTEGER DEFAULT 0,
            last_used TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage_daily (
            key_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            calls INTEGER DEFAULT 0,
            UNIQUE(key_id, day)
        );
        """
    )
    con.commit()
    con.close()


def hash_password(pw):
    salt = secrets.token_hex(12)
    d = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 210_000)
    return "pbkdf2$210000$%s$%s" % (salt, d.hex())


def verify_password(pw, stored):
    try:
        _, iters, salt, expected = stored.split("$")
        d = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(d.hex(), expected)
    except Exception:
        return False


def cookie_for(uid):
    exp = int(time.time()) + 60 * 60 * 24 * 30
    body = "%d.%d" % (uid, exp)
    mac = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
    return "%s.%s" % (body, mac)


def read_cookie(val):
    try:
        body, mac = val.rsplit(".", 1)
        expect = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expect):
            return None
        uid, exp = map(int, body.split("."))
        if time.time() > exp:
            return None
        return uid
    except Exception:
        return None


def make_key(model):
    tok = "%s_%s" % (model, secrets.token_hex(16))
    digest = hashlib.sha256(tok.encode()).hexdigest()
    masked = tok[:14] + "..." + tok[-4:]
    return tok, digest, masked


def create_user(username, email, pw):
    con = db()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cur = con.execute(
        "INSERT INTO users (username, email, pw_hash, created_at) VALUES (?,?,?,?)",
        (username, email.lower(), hash_password(pw), ts),
    )
    uid = cur.lastrowid
    created = []
    for model in MODELS:
        tok, digest, masked = make_key(model)
        con.execute(
            "INSERT INTO api_keys (user_id, model, key_hash, masked, created_at) VALUES (?,?,?,?,?)",
            (uid, model, digest, masked, ts),
        )
        created.append({"model": model, "key": tok, "masked": masked})
    con.commit()
    con.close()
    return uid, created


def user_keys(uid):
    con = db()
    rows = con.execute(
        "SELECT id, model, masked, revoked, calls, bytes, last_used, created_at "
        "FROM api_keys WHERE user_id=? ORDER BY created_at",
        (uid,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def usage_for(user_id):
    con = db()
    agg = con.execute(
        "SELECT model, SUM(calls) calls, SUM(bytes) bytes FROM api_keys "
        "WHERE user_id=? AND revoked=0 GROUP BY model",
        (user_id,),
    ).fetchall()
    daily = con.execute(
        "SELECT d.day, d.calls, k.model FROM usage_daily d "
        "JOIN api_keys k ON k.id = d.key_id WHERE k.user_id=? ORDER BY d.day",
        (user_id,),
    ).fetchall()
    con.close()
    return dict(agg=[dict(r) for r in agg]), [dict(r) for r in daily]


def record_usage(key_id, nbytes):
    con = db()
    day = time.strftime("%Y-%m-%d")
    con.execute("UPDATE api_keys SET calls=calls+1, bytes=bytes+?, last_used=? WHERE id=?",
                (nbytes, time.strftime("%Y-%m-%d %H:%M:%S"), key_id))
    con.execute(
        "INSERT INTO usage_daily (key_id, day, calls) VALUES (?,?,1) "
        "ON CONFLICT(key_id, day) DO UPDATE SET calls=calls+1",
        (key_id, day),
    )
    con.commit()
    con.close()


def key_by_token(token):
    digest = hashlib.sha256((token or "").encode()).hexdigest()
    con = db()
    row = con.execute(
        "SELECT k.*, u.username FROM api_keys k JOIN users u ON u.id=k.user_id "
        "WHERE k.key_hash=? LIMIT 1",
        (digest,),
    ).fetchone()
    con.close()
    return row


class API(BaseHTTPRequestHandler):
    server_version = "KodrAPI/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.environ.get("KODR_QUIET"):
            return
        super().log_message(fmt, *args)

    # ---- helpers ----------------------------------------------------------
    def _send(self, code, obj, extra=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_binary(self, code, data, ctype, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        ln = int(self.headers.get("Content-Length", 0) or 0)
        if not ln:
            return {}
        raw = self.rfile.read(ln)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _session_user(self):
        c = self.headers.get("Cookie") or ""
        for part in c.split("; "):
            if part.startswith("kodr_sess="):
                return read_cookie(part[len("kodr_sess="):])
        return None

    def _bearer(self):
        a = self.headers.get("Authorization") or ""
        if a.lower().startswith("bearer "):
            return a[7:].strip()
        return None

    # ---- routing ----------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/auth/me":
            return self.serve_me()
        if path == "/api/keys":
            return self.serve_keys()
        if path == "/api/usage":
            return self.serve_usage()
        if path == "/api/config":
            return self._send(200, {"ok": True, "models": MODELS, "offline_engines": MODELS_OK,
                                   "error": "" if MODELS_OK else globals().get("MODELS_ERROR", "")})
        if path == "/healthz":
            return self._send(200, {"ok": True, "ts": time.time()})
        return self.serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        route = {
            "/api/auth/signup": self.signup,
            "/api/auth/login": self.login,
            "/api/auth/logout": self.logout,
            "/api/keys": self.create_key,
            "/api/keys/revoke": self.revoke_key,
            "/api/keys/regenerate": self.regenerate_key,
            "/api/v1/nova1/generate": self.nova1,
            "/api/v1/rex3d/generate": self.rex3d,
            "/api/v1/prism1/generate": self.prism1,
        }.get(path)
        if not route:
            return self._send(404, {"error": "not found"})
        return route()

    # ---- auth -------------------------------------------------------------
    def signup(self):
        b = self._read_json()
        username = (b.get("username") or "").strip()
        email = (b.get("email") or "").strip()
        pw = b.get("password") or ""
        if len(username) < 3 or "@" not in email or len(pw) < 8:
            return self._send(400, {"error": "username ≥3 chars, valid email, password ≥8 chars"})
        try:
            uid, _keys = create_user(username, email, pw)
        except sqlite3.IntegrityError:
            return self._send(409, {"error": "username or email already taken"})
        return self._send(200, {"ok": True, "user": username, "message": "Signed up; keys created for all three models."},
                          self._session_cookie(uid))

    def login(self):
        b = self._read_json()
        ident = (b.get("username") or b.get("email") or "").strip()
        pw = b.get("password") or ""
        con = db()
        row = con.execute("SELECT * FROM users WHERE username=? OR email=? LIMIT 1",
                          (ident, ident.lower())).fetchone()
        con.close()
        if not row or not verify_password(pw, row["pw_hash"]):
            return self._send(401, {"error": "invalid credentials"})
        return self._send(200, {"ok": True, "user": row["username"]},
                          self._session_cookie(row["id"]))

    def logout(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "2")
        self.send_header("Set-Cookie", "kodr_sess=; Max-Age=0; Path=/; HttpOnly")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b"{}")

    def _session_cookie(self, uid):
        return {"Set-Cookie":
                "kodr_sess=%s; Path=/; HttpOnly; Max-Age=2592000; SameSite=Lax" % cookie_for(uid)}

    def serve_me(self):
        uid = self._session_user()
        if not uid:
            return self._send(401, {"error": "not logged in"})
        con = db()
        u = con.execute("SELECT username, email FROM users WHERE id=?", (uid,)).fetchone()
        con.close()
        if not u:
            return self._send(401, {"error": "not logged in"})
        agg, daily = usage_for(uid)
        return self._send(200, {
            "ok": True, "user": u["username"], "email": u["email"],
            "keys": user_keys(uid), "usage": agg, "daily": daily,
        })

    def serve_keys(self):
        uid = self._session_user()
        if not uid:
            return self._send(401, {"error": "not logged in"})
        return self._send(200, {"ok": True, "keys": user_keys(uid)})

    def serve_usage(self):
        uid = self._session_user()
        if not uid:
            return self._send(401, {"error": "not logged in"})
        agg, daily = usage_for(uid)
        return self._send(200, {"ok": True, "usage": agg, "daily": daily})

    def create_key(self):
        uid = self._session_user()
        if not uid:
            return self._send(401, {"error": "not logged in"})
        b = self._read_json()
        model = b.get("model") or ""
        if model not in MODELS:
            return self._send(400, {"error": "unknown model"})
        con = db()
        n = con.execute("SELECT COUNT(*) c FROM api_keys WHERE user_id=? AND model=? AND revoked=0",
                        (uid, model)).fetchone()["c"]
        if n >= MAX_KEYS_PER_MODEL:
            con.close()
            return self._send(429, {"error": "limit %d keys per model" % MAX_KEYS_PER_MODEL})
        tok, digest, masked = make_key(model)
        con.execute("INSERT INTO api_keys (user_id, model, key_hash, masked, created_at) VALUES (?,?,?,?,?)",
                    (uid, model, digest, masked, time.strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
        con.close()
        return self._send(200, {"ok": True, "model": model, "key": tok, "masked": masked,
                                "message": "Save this key now — it is shown only once."})

    def revoke_key(self):
        uid = self._session_user()
        if not uid:
            return self._send(401, {"error": "not logged in"})
        b = self._read_json()
        con = db()
        con.execute("UPDATE api_keys SET revoked=1 WHERE id=? AND user_id=?", (b.get("id"), uid))
        con.commit()
        con.close()
        return self._send(200, {"ok": True})

    def regenerate_key(self):
        uid = self._session_user()
        if not uid:
            return self._send(401, {"error": "not logged in"})
        b = self._read_json()
        con = db()
        row = con.execute("SELECT model FROM api_keys WHERE id=? AND user_id=?", (b.get("id"), uid)).fetchone()
        if not row:
            con.close()
            return self._send(404, {"error": "key not found"})
        con.execute("UPDATE api_keys SET revoked=1 WHERE id=? AND user_id=?", (b.get("id"), uid))
        tok, digest, masked = make_key(row["model"])
        con.execute("INSERT INTO api_keys (user_id, model, key_hash, masked, created_at) VALUES (?,?,?,?,?)",
                    (uid, row["model"], digest, masked, time.strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
        con.close()
        return self._send(200, {"ok": True, "model": row["model"], "key": tok, "masked": masked})

    def _authorize(self, model):
        token = self._bearer()
        row = key_by_token(token)
        if not row or row["revoked"]:
            return None, None
        if row["model"] != model:
            return None, "key belongs to '%s', not '%s'" % (row["model"], model)
        return row, None

    # ---- models -----------------------------------------------------------
    def nova1(self):
        key, err = self._authorize("nova1")
        if err or not key:
            return self._send(401, {"error": err or "invalid or missing nova1 API key"})
        b = self._read_json()
        prompt = (b.get("prompt") or "a lava dungeon".strip())
        engine = (b.get("engine") or "python").lower()
        r = nova_engine.compose(prompt, engine=engine)
        payload = r["code"]
        size = len(payload.encode("utf-8"))
        record_usage(key["id"], size)
        return self._send(200, {
            "ok": True, "model": "nova1", "engine": engine,
            "main_file": r["main_file"], "files": r["files"],
            "code": payload, "theme": r["theme"], "seed": r["seed"],
            "arch": r["arch"], "preview_ascii": r["preview_ascii"],
            "usage": {"calls": key["calls"] + 1, "bytes": key["bytes"] + size},
        })

    def prism1(self):
        key, err = self._authorize("prism1")
        if err or not key:
            return self._send(401, {"error": err or "invalid or missing prism1 API key"})
        b = self._read_json()
        prompt = (b.get("prompt") or "a mountain range at dawn").strip()
        style = b.get("style")
        if style in (None, "", "auto"):
            style = None
        size = b.get("size", 640)
        size = (int(size) if isinstance(size, (int, float)) else 640, 640)
        r = prism_engine.generate(prompt, style=style, size=size)
        with open(r["path"], "rb") as f:
            data = base64.b64encode(f.read()).decode()
        size_bytes = int(len(data) * 0.75)
        record_usage(key["id"], size_bytes)
        return self._send(200, {
            "ok": True, "model": "prism1", "image_b64": data,
            "mime": "image/png", "style": r["style"], "seed": r["seed"],
            "theme": r["theme"], "palette_hex": r["palette_hex"],
            "size": r["size"], "usage": {"calls": key["calls"] + 1, "bytes": key["bytes"] + size_bytes},
        })

    def rex3d(self):
        key, err = self._authorize("rex3d")
        if err or not key:
            return self._send(401, {"error": err or "invalid or missing rex3d API key"})
        b = self._read_json()
        prompt = (b.get("prompt") or "a small medieval castle").strip()
        size = int(b.get("size") or 20)
        img = b.get("image_data")
        image_path = None
        if img:
            try:
                raw = base64.b64decode(img.split(",", 1)[-1])
                image_path = os.path.join(tempfile.mkdtemp(prefix="rex3d_"), "ref.png")
                with open(image_path, "wb") as f:
                    f.write(raw)
            except Exception:
                image_path = None
        result = three_d_engine.generate(text=prompt, image_path=image_path, size=size)
        out = {}
        for ext in ("obj", "mtl", "stl", "glb"):
            pth = result.get(ext)
            if pth and os.path.exists(pth):
                with open(pth, "rb") as f:
                    out[ext] = base64.b64encode(f.read()).decode()
        with open(result["preview"], "rb") as f:
            out["preview_b64"] = base64.b64encode(f.read()).decode()
        size_bytes = sum(len(v) for v in out.values())
        record_usage(key["id"], size_bytes)
        return self._send(200, {
            "ok": True, "model": "rex3d", "mesh": out,
            "theme": result["theme"], "meta": result["meta"],
            "size": size, "usage": {"calls": key["calls"] + 1, "bytes": key["bytes"] + size_bytes},
        })

    # ---- static -----------------------------------------------------------
    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        rel = path.lstrip("/").replace("\\", "/")
        if ".." in rel.split("/"):
            return self._send(403, {"error": "forbidden"})
        fp = os.path.join(ROOT, rel)
        if not os.path.isfile(fp):
            return self._send(404, {"error": "not found"})
        if rel.endswith(".js"):
            ctype = "text/javascript; charset=utf-8"
        elif rel.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif rel.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        else:
            ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        with open(fp, "rb") as f:
            data = f.read()
        self._send_binary(200, data, ctype)


def main():
    init_db()
    port = int(os.environ.get("KODR_PORT", "7860"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), API)
    print("Kodr server on http://localhost:%d  (auth + API keys + usage + models)" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
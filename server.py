from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import time
import sqlite3
import os
import base64

HOST = "0.0.0.0"
PORT = 8000
DB_PATH = "warehouse_server.db"
PHOTOS_DIR = "photos"

MAX_PHOTO_BYTES = 20 * 1024 * 1024  # 20MB

def db_connect():
    return sqlite3.connect(DB_PATH)

def ensure_column(con, table, col, coldef):
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef}")
        con.commit()

def db_init():
    os.makedirs(PHOTOS_DIR, exist_ok=True)

    con = db_connect()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products(
            barcode TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            qty INTEGER NOT NULL,
            photoUri TEXT,
            isDeleted INTEGER NOT NULL DEFAULT 0,
            updatedAt INTEGER NOT NULL DEFAULT 0
        )
    """)
    con.commit()
    ensure_column(con, "products", "photoRemoteUrl", "TEXT")
    con.close()

def row_to_dict(row):
    return {
        "barcode": row[0],
        "name": row[1],
        "price": row[2],
        "qty": row[3],
        "photoUri": row[4],
        "isDeleted": row[5],
        "updatedAt": row[6],
        "photoRemoteUrl": row[7],
    }

def guess_content_type(path: str) -> str:
    low = path.lower()
    if low.endswith(".png"): return "image/png"
    if low.endswith(".webp"): return "image/webp"
    return "image/jpeg"

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, code, content_type, data: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/ping":
            self._send_json(200, {"ok": True, "ts": int(time.time())})
            return

        # Нове: перевірка існування штрихкоду на сервері
        if parsed.path == "/exists":
            qs = parse_qs(parsed.query)
            barcode = (qs.get("barcode", [""])[0] or "").strip()
            if not barcode:
                self._send_json(400, {"ok": False, "error": "barcode required"})
                return

            con = db_connect()
            ensure_column(con, "products", "photoRemoteUrl", "TEXT")
            cur = con.cursor()
            cur.execute("SELECT 1 FROM products WHERE barcode = ? LIMIT 1", (barcode,))
            exists = cur.fetchone() is not None
            con.close()

            self._send_json(200, {"ok": True, "exists": exists})
            return

        if parsed.path.startswith("/photos/"):
            filename = os.path.basename(parsed.path[len("/photos/"):])
            full = os.path.join(PHOTOS_DIR, filename)
            if not os.path.isfile(full):
                self._send_json(404, {"ok": False, "error": "photo not found"})
                return
            with open(full, "rb") as f:
                data = f.read()
            self._send_bytes(200, guess_content_type(full), data)
            return

        if parsed.path == "/pull":
            qs = parse_qs(parsed.query)
            try:
                since = int(qs.get("since", ["0"])[0])
            except:
                since = 0

            con = db_connect()
            ensure_column(con, "products", "photoRemoteUrl", "TEXT")
            cur = con.cursor()
            cur.execute(
                "SELECT barcode, name, price, qty, photoUri, isDeleted, updatedAt, photoRemoteUrl "
                "FROM products WHERE updatedAt > ? ORDER BY updatedAt ASC",
                (since,)
            )
            rows = cur.fetchall()
            con.close()

            items = [row_to_dict(r) for r in rows]
            self._send_json(200, {"ok": True, "count": len(items), "items": items, "serverTime": int(time.time() * 1000)})
            return

        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/upload_photo":
            try:
                data = self._read_json()
                if not data:
                    self._send_json(400, {"ok": False, "error": "empty body"})
                    return

                barcode = str(data.get("barcode", "")).strip()
                b64 = data.get("dataBase64", "")
                ext = str(data.get("ext", "jpg")).lower()

                if not barcode or not b64:
                    self._send_json(400, {"ok": False, "error": "barcode/dataBase64 required"})
                    return

                if ext not in ("jpg", "jpeg", "png", "webp"):
                    ext = "jpg"

                raw = base64.b64decode(b64.encode("utf-8"))
                if len(raw) > MAX_PHOTO_BYTES:
                    self._send_json(413, {"ok": False, "error": f"photo too large (>{MAX_PHOTO_BYTES} bytes)"})
                    return

                filename = f"{barcode}.{ext}".replace("/", "_").replace("\\", "_")
                full = os.path.join(PHOTOS_DIR, filename)

                with open(full, "wb") as f:
                    f.write(raw)

                url = f"/photos/{filename}"
                self._send_json(200, {"ok": True, "photoRemoteUrl": url})
            except Exception as e:
                self._send_json(500, {"ok": False, "error": str(e)})
            return

        if parsed.path == "/push":
            try:
                data = self._read_json()
                if not data or "items" not in data or not isinstance(data["items"], list):
                    self._send_json(400, {"ok": False, "error": "bad json, expected {items:[...]}"})
                    return

                items = data["items"]

                con = db_connect()
                ensure_column(con, "products", "photoRemoteUrl", "TEXT")
                cur = con.cursor()

                applied = 0
                ignored = 0

                for it in items:
                    barcode = str(it.get("barcode", "")).strip()
                    if not barcode:
                        ignored += 1
                        continue

                    name = str(it.get("name", "")).strip()
                    price = float(it.get("price", 0.0))
                    qty = int(it.get("qty", 0))
                    photoUri = it.get("photoUri", None)
                    isDeleted = int(it.get("isDeleted", 0))
                    updatedAt = int(it.get("updatedAt", 0))
                    photoRemoteUrl = it.get("photoRemoteUrl", None)

                    cur.execute("SELECT updatedAt FROM products WHERE barcode = ?", (barcode,))
                    row = cur.fetchone()
                    if row is not None and int(row[0]) >= updatedAt:
                        ignored += 1
                        continue

                    cur.execute("""
                        INSERT INTO products(barcode, name, price, qty, photoUri, isDeleted, updatedAt, photoRemoteUrl)
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(barcode) DO UPDATE SET
                            name=excluded.name,
                            price=excluded.price,
                            qty=excluded.qty,
                            photoUri=excluded.photoUri,
                            isDeleted=excluded.isDeleted,
                            updatedAt=excluded.updatedAt,
                            photoRemoteUrl=excluded.photoRemoteUrl
                    """, (barcode, name, price, qty, photoUri, isDeleted, updatedAt, photoRemoteUrl))
                    applied += 1

                con.commit()
                con.close()

                self._send_json(200, {"ok": True, "applied": applied, "ignored": ignored, "serverTime": int(time.time() * 1000)})
            except Exception as e:
                self._send_json(500, {"ok": False, "error": str(e)})
            return

        self._send_json(404, {"ok": False, "error": "not found"})

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    db_init()
    print(f"Server running on http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()

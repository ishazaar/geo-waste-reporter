"""
Durable storage for serverless hosting (Vercel).

Vercel's disk is temporary: every cold start gives the app an empty disk, so the SQLite file was recreated and
re-seeded (losing new reports and admin updates) and uploaded photos vanished. This module keeps both somewhere
permanent. Pick ONE backend with environment variables:

  Redis (easiest on Vercel: Storage tab -> Create Database -> Upstash Redis -> Connect to project)
      KV_REST_API_URL + KV_REST_API_TOKEN  (or UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN), added automatically

  GitHub (no new account needed)
      GITHUB_TOKEN       fine-grained token with "Contents: Read and write" on ONE private repo
      GITHUB_DATA_REPO   "your-username/geo-waste-data"
      GITHUB_DATA_BRANCH optional, default "main"
      -> database saved as db/geo_waste.db, photos as photos/<name> (the app serves them at /uploads/<name>)

  Supabase Storage
      SUPABASE_URL, SUPABASE_SERVICE_KEY  (+ optional SUPABASE_PHOTO_BUCKET / SUPABASE_DB_BUCKET)

With neither set, everything behaves exactly as before (local disk). Nothing here raises into a request:
failures are logged and skipped.
"""
import base64
import json
import mimetypes
import os
import re
import sqlite3
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib

TIMEOUT_S = 12
CHECK_EVERY_S = 3
_state = {"version": None, "checked": 0.0, "error": None}
_WRITE_PATH = re.compile(r"^/api/(reports(/[^/]+/(status|upvote))?|seed)/?$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-]{1,120}$")


# =================================================================== GitHub backend
class GitHubBackend:
    name = "github"

    def __init__(self):
        self.token = os.environ["GITHUB_TOKEN"].strip()
        self.repo = os.environ["GITHUB_DATA_REPO"].strip().strip("/")
        self.branch = (os.environ.get("GITHUB_DATA_BRANCH") or "main").strip()
        self.db_path = "db/geo_waste.db"

    def _req(self, method, path, body=None, raw=False):
        url = f"https://api.github.com/repos/{self.repo}/contents/{urllib.parse.quote(path)}"
        if method == "GET":
            url += "?ref=" + urllib.parse.quote(self.branch)
        headers = {"Authorization": "Bearer " + self.token, "User-Agent": "geo-waste-reporter",
                   "X-GitHub-Api-Version": "2022-11-28",
                   "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.read()

    def _meta(self, path):
        try:
            return json.loads(self._req("GET", path))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def version(self):
        m = self._meta(self.db_path)
        return m["sha"] if m else None

    def get_db(self):
        try:
            return self._req("GET", self.db_path, raw=True)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def _put(self, path, data, message, sha=None):
        body = {"message": message, "content": base64.b64encode(data).decode(), "branch": self.branch}
        if sha:
            body["sha"] = sha
        return json.loads(self._req("PUT", path, body))

    def put_db(self, data):
        m = self._meta(self.db_path)
        for attempt in range(2):
            try:
                res = self._put(self.db_path, data, "Update database", m["sha"] if m else None)
                return res["content"]["sha"]
            except urllib.error.HTTPError as e:
                if e.code in (409, 422) and attempt == 0:     # file changed under us: refetch its sha, retry once
                    m = self._meta(self.db_path)
                    continue
                raise

    def put_photo(self, name, data, mime):
        self._put("photos/" + name, data, "Add photo " + name)
        return "/uploads/" + name            # served by the app itself (the repo is private)

    def get_photo(self, name):
        try:
            return self._req("GET", "photos/" + name, raw=True)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise


# =================================================================== Redis backend (Upstash / Vercel Storage)
class RedisBackend:
    """Database (compressed) and photos live as keys in a Redis database reached over HTTPS."""
    name = "redis"

    def __init__(self):
        e = os.environ
        self.url = (e.get("KV_REST_API_URL") or e.get("UPSTASH_REDIS_REST_URL") or "").strip().rstrip("/")
        self.token = (e.get("KV_REST_API_TOKEN") or e.get("UPSTASH_REDIS_REST_TOKEN") or "").strip()

    def _cmd(self, *args):
        req = urllib.request.Request(self.url, data=json.dumps(list(args)).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            res = json.loads(r.read())
        if res.get("error"):
            raise RuntimeError(str(res["error"])[:120])
        return res.get("result")

    def version(self):
        return self._cmd("GET", "gwr:db:ver")

    def get_db(self):
        v = self._cmd("GET", "gwr:db")
        return zlib.decompress(base64.b64decode(v)) if v else None

    def put_db(self, data):
        self._cmd("SET", "gwr:db", base64.b64encode(zlib.compress(data, 6)).decode())
        ver = uuid.uuid4().hex
        self._cmd("SET", "gwr:db:ver", ver)
        return ver

    def put_photo(self, name, data, mime):
        self._cmd("SET", "gwr:photo:" + name, base64.b64encode(data).decode())
        return "/uploads/" + name            # served by the app itself

    def get_photo(self, name):
        v = self._cmd("GET", "gwr:photo:" + name)
        return base64.b64decode(v) if v else None


# =================================================================== Supabase backend
class SupabaseBackend:
    name = "supabase"

    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].strip().rstrip("/")
        self.key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")).strip()
        self.photo_bucket = os.environ.get("SUPABASE_PHOTO_BUCKET", "gwr-photos")
        self.db_bucket = os.environ.get("SUPABASE_DB_BUCKET", "gwr-private")

    def _call(self, method, bucket, path, data=None, ctype=None, upsert=False):
        headers = {"Authorization": "Bearer " + self.key, "apikey": self.key}
        if ctype:
            headers["Content-Type"] = ctype
        if upsert:
            headers["x-upsert"] = "true"
        req = urllib.request.Request(f"{self.url}/storage/v1/object/{bucket}/{urllib.parse.quote(path)}",
                                     data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=TIMEOUT_S)

    def _get(self, bucket, name):
        try:
            with self._call("GET", bucket, name) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            raise

    def version(self):
        raw = self._get(self.db_bucket, "version.txt")
        return raw.decode().strip() if raw else None

    def get_db(self):
        return self._get(self.db_bucket, "geo_waste.db")

    def put_db(self, data):
        with self._call("POST", self.db_bucket, "geo_waste.db", data, "application/octet-stream", True):
            pass
        ver = uuid.uuid4().hex
        with self._call("POST", self.db_bucket, "version.txt", ver.encode(), "text/plain", True):
            pass
        return ver

    def put_photo(self, name, data, mime):
        with self._call("POST", self.photo_bucket, name, data, mime, True):
            pass
        return f"{self.url}/storage/v1/object/public/{self.photo_bucket}/{urllib.parse.quote(name)}"

    def get_photo(self, name):
        return None                           # photos are served directly from the public bucket


def _backend():
    e = os.environ
    if e.get("GITHUB_TOKEN") and e.get("GITHUB_DATA_REPO"):
        return GitHubBackend()
    if (e.get("KV_REST_API_URL") and e.get("KV_REST_API_TOKEN")) or (e.get("UPSTASH_REDIS_REST_URL") and e.get("UPSTASH_REDIS_REST_TOKEN")):
        return RedisBackend()
    if e.get("SUPABASE_URL") and (e.get("SUPABASE_SERVICE_KEY") or e.get("SUPABASE_SERVICE_ROLE_KEY")):
        return SupabaseBackend()
    return None


def enabled() -> bool:
    return _backend() is not None


def status() -> dict:
    b = _backend()
    return {"durable_storage": b is not None, "storage_backend": b.name if b else None,
            "db_version_loaded": bool(_state["version"]), "last_error": _state["error"]}


def is_write_path(path: str) -> bool:
    return bool(_WRITE_PATH.match(path or ""))


# =================================================================== photos
def upload_photo(name: str, data: bytes, mime: str) -> str:
    """Stores a photo permanently and returns the URL to save with the report. Raises on failure."""
    return _backend().put_photo(name, data, mime)


def get_photo(name: str):
    """Returns (bytes, mime) for a stored photo, or None."""
    b = _backend()
    if not b or not _SAFE_NAME.match(name or ""):
        return None
    try:
        data = b.get_photo(name)
    except Exception as e:
        print("[persist] photo fetch failed:", type(e).__name__, str(e)[:100])
        return None
    return (data, mimetypes.guess_type(name)[0] or "application/octet-stream") if data else None


# =================================================================== database file
def _db_path() -> str:
    try:
        import database
        for attr in ("DB_PATH", "DB_FILE", "DATABASE", "DATABASE_PATH"):
            v = getattr(database, attr, None)
            if isinstance(v, str) and v:
                return v
        return os.path.join(database.DATA_DIR, "geo_waste.db")
    except Exception:
        return os.path.join(tempfile.gettempdir(), "geo_waste.db")


def pull(force: bool = False) -> str:
    """Loads the shared database if it is newer than ours: 'loaded', 'current', 'missing' or 'error'."""
    b = _backend()
    if not b:
        return "missing"
    try:
        ver = b.version()
        if ver is None:
            return "missing"
        if ver == _state["version"] and not force:
            return "current"
        data = b.get_db()
        if not data:
            return "missing"
        path = _db_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".incoming"
        with open(tmp, "wb") as f:
            f.write(data)
        chk = sqlite3.connect(tmp)
        chk.execute("SELECT count(*) FROM sqlite_master").fetchone()   # refuse a corrupt download
        chk.close()
        for ext in ("-wal", "-shm", "-journal"):
            try:
                os.remove(path + ext)
            except OSError:
                pass
        os.replace(tmp, path)
        _state["version"], _state["error"] = ver, None
        return "loaded"
    except Exception as e:
        _state["error"] = f"pull: {type(e).__name__}: {str(e)[:100]}"
        print("[persist]", _state["error"])
        return "error"


def push() -> bool:
    """Uploads a consistent snapshot of the local database."""
    b = _backend()
    path = _db_path()
    if not b or not os.path.exists(path):
        return False
    snap = path + ".snapshot"
    try:
        src, dst = sqlite3.connect(path), sqlite3.connect(snap)
        src.backup(dst)
        src.close()
        dst.close()
        with open(snap, "rb") as f:
            data = f.read()
        _state["version"], _state["error"] = b.put_db(data), None
        return True
    except Exception as e:
        _state["error"] = f"push: {type(e).__name__}: {str(e)[:100]}"
        print("[persist]", _state["error"])
        return False
    finally:
        try:
            os.remove(snap)
        except OSError:
            pass


def pull_on_startup() -> str:
    """Call BEFORE init_db(): 'loaded', 'missing' (safe to seed and push) or 'error' (do NOT push)."""
    res = pull(force=True)
    if res == "error":
        res = pull(force=True)
    return res


def refresh_if_stale():
    """Cheap check before each API request: if another instance changed the database, load it."""
    if not enabled() or time.time() - _state["checked"] < CHECK_EVERY_S:
        return
    _state["checked"] = time.time()
    pull()

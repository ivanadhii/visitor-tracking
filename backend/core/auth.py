import os
import secrets
import time
import yaml
import threading
import jwt
from typing import Dict, Optional

USERS_FILE = os.environ.get("USERS_FILE", "/app/data/userlist.yaml")
SECRET_FILE = os.environ.get("JWT_SECRET_FILE", "/app/data/.jwt_secret")
TOKEN_TTL = 8 * 3600  # 8 hours


def _load_or_create_secret() -> str:
    """Load JWT secret from file, or generate and persist a new one."""
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE) as f:
            secret = f.read().strip()
            if secret:
                return secret
    os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
    secret = secrets.token_hex(32)
    with open(SECRET_FILE, "w") as f:
        f.write(secret)
    return secret


_JWT_SECRET = _load_or_create_secret()


class AuthManager:
    def __init__(self):
        self._users: Dict[str, str] = {}
        self._file_mtime: float = 0
        self._lock = threading.Lock()
        self._load()
        self._start_watcher()

    # ─── file I/O ─────────────────────────────────────────────────────────────

    def _read_yaml(self) -> list:
        if not os.path.exists(USERS_FILE):
            return []
        try:
            with open(USERS_FILE) as f:
                data = yaml.safe_load(f) or []
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[AuthManager] Failed to read userlist: {e}")
            return []

    def _load(self):
        entries = self._read_yaml()
        users = {}
        for entry in entries:
            username = str(entry.get("username", "")).strip()
            password = str(entry.get("password", "")).strip()
            if username and password:
                users[username] = password
        with self._lock:
            self._users = users
        if os.path.exists(USERS_FILE):
            self._file_mtime = os.path.getmtime(USERS_FILE)
        print(f"[AuthManager] Loaded {len(users)} user(s)")

    # ─── file watcher ─────────────────────────────────────────────────────────

    def _start_watcher(self):
        t = threading.Thread(target=self._watch_loop, daemon=True, name="auth-watcher")
        t.start()

    def _watch_loop(self):
        while True:
            time.sleep(5)
            try:
                if not os.path.exists(USERS_FILE):
                    continue
                mtime = os.path.getmtime(USERS_FILE)
                if mtime > self._file_mtime:
                    self._file_mtime = mtime
                    self._load()
                    print("[AuthManager] Userlist reloaded")
            except Exception as e:
                print(f"[AuthManager] Watcher error: {e}")

    # ─── public ───────────────────────────────────────────────────────────────

    @property
    def auth_required(self) -> bool:
        with self._lock:
            return len(self._users) > 0

    def login(self, username: str, password: str) -> Optional[str]:
        with self._lock:
            if self._users.get(username) != password:
                return None
        payload = {
            "sub": username,
            "exp": int(time.time()) + TOKEN_TTL,
        }
        return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")

    def verify(self, token: str) -> Optional[str]:
        """Returns username if token is valid, None otherwise."""
        try:
            payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
            username = payload.get("sub")
            # Reject if user was removed from userlist
            with self._lock:
                if self._users and username not in self._users:
                    return None
            return username
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

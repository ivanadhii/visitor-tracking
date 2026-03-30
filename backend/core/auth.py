import os
import uuid
import time
import yaml
import threading
from typing import Dict, Optional

USERS_FILE = os.environ.get("USERS_FILE", "/app/data/userlist.yaml")
SESSION_TTL = 8 * 3600  # 8 hours


class AuthManager:
    def __init__(self):
        self._users: Dict[str, str] = {}       # username -> password
        self._sessions: Dict[str, dict] = {}   # token -> {username, expires_at}
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
            # Invalidate sessions for removed users
            self._sessions = {
                t: s for t, s in self._sessions.items()
                if s["username"] in users
            }
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
        """Auth is only required if userlist.yaml exists and has users."""
        with self._lock:
            return len(self._users) > 0

    def login(self, username: str, password: str) -> Optional[str]:
        with self._lock:
            if self._users.get(username) != password:
                return None
            token = str(uuid.uuid4())
            self._sessions[token] = {
                "username": username,
                "expires_at": time.time() + SESSION_TTL,
            }
        return token

    def logout(self, token: str):
        with self._lock:
            self._sessions.pop(token, None)

    def verify(self, token: str) -> Optional[str]:
        """Returns username if token is valid, None otherwise."""
        with self._lock:
            session = self._sessions.get(token)
            if not session:
                return None
            if time.time() > session["expires_at"]:
                del self._sessions[token]
                return None
            return session["username"]

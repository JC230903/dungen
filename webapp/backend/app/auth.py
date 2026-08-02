"""Multi-user accounts: password hashing, signed bearer tokens, user CRUD.

Stdlib-only for hashing/tokens on purpose (no `bcrypt`/`passlib`/`pyjwt`
dependency) — password hashing is PBKDF2-HMAC-SHA256 via `hashlib`
(NIST-recommended, no C extension to build on a bare Windows box for the
home deploy), tokens are a plain HMAC-signed payload via `hmac`/`secrets`,
not a full JWT (no need for JWT's algorithm-negotiation surface here — this
token is only ever read by this same backend).

Shares the same DB as `projects.py` (one `users` table alongside
`projects`) — see `app/db.py` for which storage backend that resolves to.

Signing secret: on Cloud Run, `AUTH_SECRET_KEY` (env var, e.g. from Secret
Manager) MUST be set — Cloud Run's local disk is ephemeral and not shared
across instances, so a file-based secret would differ per instance and
every other instance would reject tokens it didn't sign. The home deploy
(one process, durable disk) keeps the file-based secret for simplicity —
no secret-management step needed to get it running.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from typing import Optional

from . import db
from .projects import _conn as _projects_conn  # same DB, shared connection helper

SECRET_PATH = Path(__file__).resolve().parent.parent / "data" / "secret.key"
TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 days
PBKDF2_ITERATIONS = 200_000

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


def _conn():
    conn = _projects_conn()  # ensures projects table + parent dir/DB exist too
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL
        )"""
    )
    return conn


def _get_secret() -> bytes:
    env_secret = os.environ.get("AUTH_SECRET_KEY")
    if env_secret:
        return bytes.fromhex(env_secret) if _looks_like_hex(env_secret) else env_secret.encode("utf-8")
    if db.BACKEND == "postgres":
        raise RuntimeError(
            "AUTH_SECRET_KEY env var is required when running against Postgres/Cloud Run "
            "(local disk isn't shared across instances or restarts) — see webapp/deploy-gcp/README.md"
        )
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_hex(32))
    return bytes.fromhex(SECRET_PATH.read_text().strip())


def _looks_like_hex(s: str) -> bool:
    try:
        bytes.fromhex(s)
        return True
    except ValueError:
        return False


# ---------- passwords ----------
def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    _, digest_hex = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest_hex, expected_hash_hex)


# ---------- tokens (HMAC-signed, not encrypted — payload is just id/username/expiry) ----------
def make_token(user_id: str, username: str) -> str:
    expiry = int(time.time()) + TOKEN_TTL_SECONDS
    payload = f"{user_id}:{username}:{expiry}"
    payload_b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    sig = hmac.new(_get_secret(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> Optional[dict]:
    try:
        payload_b64, sig = token.split(".", 1)
    except ValueError:
        return None
    expected_sig = hmac.new(_get_secret(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        payload = base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
        user_id, username, expiry = payload.split(":", 2)
        expiry = int(expiry)
    except (ValueError, UnicodeDecodeError):
        return None
    if time.time() > expiry:
        return None
    return {"user_id": user_id, "username": username}


# ---------- user CRUD ----------
def validate_username(username: str) -> Optional[str]:
    if not USERNAME_RE.match(username):
        return "Username must be 3-32 characters: letters, numbers, underscore, dot, or dash."
    return None


def validate_password(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 256:
        return "Password is too long."
    return None


def create_user(username: str, password: str) -> dict:
    salt_hex, hash_hex = hash_password(password)
    uid = uuid.uuid4().hex
    now = time.time()
    with _conn() as conn:
        try:
            conn.execute(
                "INSERT INTO users (id, username, salt, pw_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (uid, username, salt_hex, hash_hex, now),
            )
        except Exception as exc:
            if db.is_integrity_error(exc):
                raise ValueError(f"Username '{username}' is already taken") from None
            raise
    return {"id": uid, "username": username}


def get_user_by_username(username: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, username, salt, pw_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "username": row[1], "salt": row[2], "pw_hash": row[3]}


def get_user_by_id(user_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return {"id": row[0], "username": row[1]}

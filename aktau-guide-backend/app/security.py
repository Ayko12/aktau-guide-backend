"""Хеширование паролей (PBKDF2-SHA256, стандартная библиотека) и JWT (PyJWT)."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import secrets

import jwt

PBKDF2_ITERATIONS = 390_000
ALGORITHM = "HS256"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iters))
        return hmac.compare_digest(dk, _unb64(digest))
    except (ValueError, TypeError):
        return False


def create_token(user_id: str, secret: str, ttl_minutes: int) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + dt.timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> str | None:
    """id пользователя или None, если токен недействителен/истёк."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None

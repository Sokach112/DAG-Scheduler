"""Password hashing, cookie sessions, and request authentication."""

import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import HTTPException, Request, Response

from . import store


SESSION_COOKIE = "dags_session"
SESSION_DAYS = 7
PBKDF2_ITERATIONS = 120_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def normalize_username(value: str) -> str:
    username = (value or "").strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="username must be 3-64 characters: letters, digits, _ . -")
    return username


def validate_password(value: str) -> str:
    if not value or len(value) < 8:
        raise HTTPException(
            status_code=400, detail="password must be at least 8 characters")
    if len(value) > 200:
        raise HTTPException(status_code=400, detail="password is too long")
    return value


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=SESSION_DAYS)


def start_session(response: Response, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    store.create_session(
        user_id, session_token_hash(token), session_expiry())
    secure = os.environ.get("DAG_COOKIE_SECURE", "").lower() in {
        "1", "true", "yes"}
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def end_session(request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        store.delete_session(session_token_hash(token))
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(request: Request) -> Optional[Dict]:
    user = getattr(request.state, "user", None)
    if user is not None:
        return user
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user = store.get_user_by_session(session_token_hash(token))
    if user is not None:
        request.state.user = user
    return user


def require_user(request: Request) -> Dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_admin(request: Request) -> Dict:
    user = require_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="admin access required")
    return user


def user_payload(user: Dict) -> Dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_admin": bool(user["is_admin"]),
    }

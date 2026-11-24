import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password


def hash_password(raw_password: str) -> str:
    return make_password(raw_password)


def verify_password(raw_password: str, encoded_hash: str) -> bool:
    return check_password(raw_password, encoded_hash)


def generate_user_code() -> str:
    return f"usr_{uuid.uuid4().hex[:8]}"


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(user) -> tuple[str, int]:
    ttl = settings.ACCESS_TOKEN_TTL_SECONDS
    now = datetime.now(UTC)
    payload = {
        "sub": user.user_code,
        "uid": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    token = jwt.encode(
        payload, settings.JWT_SIGNING_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return token, ttl


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token, settings.JWT_SIGNING_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )


def create_refresh_token_value() -> tuple[str, str, datetime]:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    return raw_token, token_hash, expires_at


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "User", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])

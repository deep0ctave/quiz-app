import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()
DUMMY_PIN_HASH = password_hash.hash("schoolmela-invalid-pin")


def hash_pin(pin: str) -> str:
    return password_hash.hash(pin)


def verify_pin(pin: str, encoded: str) -> bool:
    if encoded.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(pin.encode(), encoded.encode())
        except ValueError:
            return False
    return password_hash.verify(pin, encoded)


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_access_token(user_id: int, role: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "roles": [role], "iss": settings.jwt_issuer,
         "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)
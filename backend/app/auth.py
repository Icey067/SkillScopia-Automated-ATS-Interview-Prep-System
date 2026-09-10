from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def create_token(subject: str, expires_delta: timedelta, token_type: str, token_id: str | None = None) -> str:
    payload = {
        "sub": subject,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    if token_id:
        payload["jti"] = token_id
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return create_token(
        str(user_id),
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    token_id = uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return create_token(
        str(user_id),
        timedelta(days=settings.refresh_token_expire_days), "refresh", token_id
    ), token_id, expires_at


def decode_token(token: str, expected_type: str) -> tuple[int, dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != expected_type:
            raise JWTError("Wrong token type")
        sub = payload.get("sub")
        if sub is None:
            raise JWTError("Missing subject")
        return int(sub), payload
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid token") from exc

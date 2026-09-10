from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.auth import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import ConflictError, UnauthorizedError
from app.models import RefreshToken, User
from app.rate_limit import limiter
from app.schemas import LogoutRequest, RefreshRequest, TokenPair, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user: User, db: Session) -> TokenPair:
    refresh, token_id, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_id=token_id, expires_at=expires_at))
    db.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=refresh)


def _is_expired(timestamp: datetime) -> bool:
    """SQLite returns naive datetimes; Postgres returns timezone-aware values."""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp <= datetime.now(timezone.utc)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise ConflictError("Email already registered")
    user = User(email=payload.email.lower(), hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("Invalid credentials")
    return _token_pair(user, db)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        user_id, claims = decode_token(payload.refresh_token, "refresh")
    except ValueError:
        raise UnauthorizedError("Invalid refresh token")
    user = db.get(User, user_id)
    token_id = claims.get("jti")
    stored = db.query(RefreshToken).filter(RefreshToken.token_id == token_id).first() if token_id else None
    if (
        user is None
        or stored is None
        or stored.user_id != user.id
        or stored.revoked_at
        or _is_expired(stored.expires_at)
    ):
        raise UnauthorizedError("User not found")
    stored.revoked_at = datetime.now(timezone.utc)
    return _token_pair(user, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    try:
        _, claims = decode_token(payload.refresh_token, "refresh")
    except ValueError:
        return
    token_id = claims.get("jti")
    if token_id:
        stored = db.query(RefreshToken).filter(RefreshToken.token_id == token_id).first()
        if stored and not stored.revoked_at:
            stored.revoked_at = datetime.now(timezone.utc)
            db.commit()


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current

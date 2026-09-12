from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_timestamp_expired,
    verify_password,
)
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import ConflictError, UnauthorizedError
from app.models import RefreshToken, User
from app.rate_limit import limiter
from app.schemas import LogoutRequest, RefreshRequest, TokenPair, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


async def _create_and_store_token_pair(user: User, db: AsyncSession) -> TokenPair:
    refresh_token_str, token_id, expires_at = create_refresh_token(user.id)
    token_record = RefreshToken(
        user_id=user.id,
        token_id=token_id,
        expires_at=expires_at,
    )
    db.add(token_record)
    await db.commit()
    access_token_str = create_access_token(user.id)
    return TokenPair(access_token=access_token_str, refresh_token=refresh_token_str)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictError("Email already registered")

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
async def login(
    payload: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("Invalid credentials")

    return await _create_and_store_token_pair(user, db)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    try:
        user_id, claims = decode_token(payload.refresh_token, "refresh")
    except ValueError:
        raise UnauthorizedError("Invalid refresh token")

    token_id = claims.get("jti")
    if not token_id:
        raise UnauthorizedError("Invalid refresh token")

    user = await db.get(User, user_id)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_id == token_id))
    stored = result.scalar_one_or_none()

    if (
        user is None
        or stored is None
        or stored.user_id != user.id
        or stored.revoked_at is not None
        or is_timestamp_expired(stored.expires_at)
    ):
        raise UnauthorizedError("Refresh token has expired or been revoked")

    # Rotate refresh token: revoke current token and issue a fresh pair
    stored.revoked_at = datetime.now(timezone.utc)
    return await _create_and_store_token_pair(user, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        _, claims = decode_token(payload.refresh_token, "refresh")
    except ValueError:
        return

    token_id = claims.get("jti")
    if token_id:
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_id == token_id))
        stored = result.scalar_one_or_none()
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(timezone.utc)
            await db.commit()


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)) -> User:
    return current

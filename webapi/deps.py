"""Shared FastAPI dependencies: DB session, current user, admin permissions."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.database import async_session
from bot_package.models import Admin, User

from .security import AuthError, decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session():
    async with async_session() as session:
        yield session


def _credentials_error(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_bearer(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise _credentials_error()
    try:
        return decode_token(credentials.credentials)
    except AuthError:
        raise _credentials_error("Invalid or expired token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    payload = _decode_bearer(credentials)
    if payload.get("role") != "user":
        raise _credentials_error("User token required")
    telegram_id = int(payload["sub"])
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        raise _credentials_error("Unknown user")
    if user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")
    return user


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Admin:
    payload = _decode_bearer(credentials)
    if payload.get("role") != "admin":
        raise _credentials_error("Admin token required")
    telegram_id = int(payload["sub"])
    admin = (
        await session.execute(
            select(Admin).where(Admin.telegram_id == telegram_id, Admin.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if admin is None:
        raise _credentials_error("Unknown or deactivated admin")
    return admin


def require_permission(permission: str):
    async def checker(admin: Admin = Depends(get_current_admin)) -> Admin:
        perms = {p.strip() for p in (admin.permissions or "").split(",") if p.strip()}
        if admin.is_owner or "all" in perms or permission in perms:
            return admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission}",
        )

    return checker

import hmac

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin

from ..config import BotConfig
from ..deps import get_session
from ..schemas import AdminLoginRequest, AdminTokenResponse
from ..security import issue_admin_token

router = APIRouter(prefix="/admin/auth", tags=["admin"])


@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(body: AdminLoginRequest, session: AsyncSession = Depends(get_session)):
    if not BotConfig.ADMIN_PASSWORD or not hmac.compare_digest(
        body.password, BotConfig.ADMIN_PASSWORD
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    admin = (
        await session.execute(
            select(Admin).where(Admin.telegram_id == body.telegram_id, Admin.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return AdminTokenResponse(
        access_token=issue_admin_token(admin.telegram_id, admin.permissions or "", admin.is_owner),
        permissions=admin.permissions or "",
        is_owner=admin.is_owner,
    )

"""Admin: broadcast and admin-account management (owner-only)."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin
from bot_package.services.admin_service import AdminService
from bot_package.services.broadcast_service import BroadcastService

from ..deps import get_session, require_owner, require_permission

router = APIRouter(prefix="/admin", tags=["admin"])

# Keep references to in-flight broadcast tasks so they aren't garbage-collected.
_broadcast_tasks: set[asyncio.Task] = set()


# --- Broadcast ---------------------------------------------------------------

class BroadcastRequest(BaseModel):
    text: str = Field(min_length=1)
    parse_mode: str | None = None  # "Markdown" | "HTML" | None


@router.post("/broadcast")
async def broadcast(
    body: BroadcastRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    recipients = await BroadcastService.recipient_ids(session)
    # Send in the background — delivering to many users takes a while.
    task = asyncio.create_task(
        BroadcastService.send_text(recipients, text=body.text, parse_mode=body.parse_mode)
    )
    _broadcast_tasks.add(task)
    task.add_done_callback(_broadcast_tasks.discard)
    return {"queued": len(recipients)}


# --- Admin management (owner only) -------------------------------------------

def _admin_out(a: Admin) -> dict:
    return {
        "telegram_id": a.telegram_id,
        "permissions": a.permissions,
        "is_owner": a.is_owner,
        "is_active": a.is_active,
    }


class AdminUpsertRequest(BaseModel):
    telegram_id: int
    permissions: str  # CSV of permission keys, or "all"


class PermissionsRequest(BaseModel):
    permissions: str


@router.get("/admins")
async def list_admins(
    session: AsyncSession = Depends(get_session),
    _owner: Admin = Depends(require_owner),
):
    return [_admin_out(a) for a in await AdminService.list_admins(session)]


@router.post("/admins")
async def add_admin(
    body: AdminUpsertRequest,
    session: AsyncSession = Depends(get_session),
    owner: Admin = Depends(require_owner),
):
    admin = await AdminService.add_or_update_admin(
        session, body.telegram_id, body.permissions, created_by=owner.telegram_id
    )
    await session.commit()
    return _admin_out(admin)


@router.put("/admins/{telegram_id}/permissions")
async def set_permissions(
    telegram_id: int,
    body: PermissionsRequest,
    session: AsyncSession = Depends(get_session),
    owner: Admin = Depends(require_owner),
):
    admin = await AdminService.add_or_update_admin(
        session, telegram_id, body.permissions, created_by=owner.telegram_id
    )
    await session.commit()
    return _admin_out(admin)


@router.delete("/admins/{telegram_id}")
async def remove_admin(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
    _owner: Admin = Depends(require_owner),
):
    ok = await AdminService.remove_admin(session, telegram_id)
    await session.commit()
    if not ok:
        raise HTTPException(status_code=409, detail="Admin not found or is an owner")
    return {"removed": True}

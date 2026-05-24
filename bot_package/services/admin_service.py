from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config_loader import BotConfig
from ..models import Admin


ALL_PERMISSIONS = ("inventory", "prices", "users", "reports", "coupons")


def normalize_permissions(raw_permissions: str | list[str] | tuple[str, ...] | set[str]) -> str:
    if isinstance(raw_permissions, str):
        parts = [part.strip().lower() for part in raw_permissions.replace(",", " ").split()]
    else:
        parts = [str(part).strip().lower() for part in raw_permissions]

    if "all" in parts:
        parts = list(ALL_PERMISSIONS)

    valid = []
    for part in parts:
        if part in ALL_PERMISSIONS and part not in valid:
            valid.append(part)
    return ",".join(valid)


def permissions_to_set(raw_permissions: str) -> set[str]:
    return {part.strip() for part in raw_permissions.split(",") if part.strip()}


class AdminService:
    @staticmethod
    async def sync_configured_admins(session: AsyncSession) -> None:
        for owner_id in BotConfig.OWNER_USER_IDS:
            await AdminService.add_or_update_admin(
                session,
                telegram_id=owner_id,
                permissions="all",
                created_by=None,
                is_owner=True,
            )

        configured_admins = set(BotConfig.ADMIN_USER_IDS) - set(BotConfig.OWNER_USER_IDS)
        for admin_id in configured_admins:
            await AdminService.add_or_update_admin(
                session,
                telegram_id=admin_id,
                permissions="all",
                created_by=None,
                is_owner=False,
            )
        await session.commit()

    @staticmethod
    async def get_admin(session: AsyncSession, telegram_id: int) -> Admin | None:
        result = await session.execute(
            select(Admin).where(Admin.telegram_id == telegram_id, Admin.is_active == True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def can_access(session: AsyncSession, telegram_id: int, permission: str | None = None) -> bool:
        admin = await AdminService.get_admin(session, telegram_id)
        if not admin:
            return False
        if admin.is_owner or permission is None:
            return True
        return permission in permissions_to_set(admin.permissions)

    @staticmethod
    async def is_owner(session: AsyncSession, telegram_id: int) -> bool:
        admin = await AdminService.get_admin(session, telegram_id)
        return bool(admin and admin.is_owner)

    @staticmethod
    async def add_or_update_admin(
        session: AsyncSession,
        telegram_id: int,
        permissions: str,
        created_by: int | None,
        is_owner: bool = False,
    ) -> Admin:
        result = await session.execute(select(Admin).where(Admin.telegram_id == telegram_id))
        admin = result.scalar_one_or_none()
        normalized_permissions = normalize_permissions(permissions)
        if not normalized_permissions:
            normalized_permissions = "reports"

        if admin:
            admin.permissions = normalized_permissions
            admin.is_owner = admin.is_owner or is_owner
            admin.is_active = True
            admin.updated_at = datetime.now(timezone.utc)
            return admin

        admin = Admin(
            telegram_id=telegram_id,
            permissions=normalized_permissions,
            is_owner=is_owner,
            is_active=True,
            created_by=created_by,
        )
        session.add(admin)
        return admin

    @staticmethod
    async def remove_admin(session: AsyncSession, telegram_id: int) -> bool:
        result = await session.execute(select(Admin).where(Admin.telegram_id == telegram_id))
        admin = result.scalar_one_or_none()
        if not admin or admin.is_owner:
            return False
        admin.is_active = False
        admin.updated_at = datetime.now(timezone.utc)
        return True

    @staticmethod
    async def list_admins(session: AsyncSession) -> list[Admin]:
        result = await session.execute(select(Admin).where(Admin.is_active == True).order_by(Admin.is_owner.desc(), Admin.telegram_id))
        return list(result.scalars().all())

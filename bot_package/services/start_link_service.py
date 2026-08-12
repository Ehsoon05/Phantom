import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config_loader import BotConfig
from ..models import StartLink, StartLinkVisit, User


START_LINK_PAYLOAD_PREFIX = "sl_"


def _normalize_code(value: str) -> str:
    code = re.sub(r"[^A-Za-z0-9_-]+", "", (value or "").strip())
    return code[:48]


class StartLinkService:
    @staticmethod
    def payload_for(code: str) -> str:
        return f"{START_LINK_PAYLOAD_PREFIX}{code}"

    @staticmethod
    def url_for(code: str) -> str:
        return f"https://t.me/{BotConfig.MAIN_BOT_USERNAME}?start={StartLinkService.payload_for(code)}"

    @staticmethod
    async def create_link(
        session: AsyncSession,
        name: str,
        *,
        created_by: int | None = None,
        code: str | None = None,
    ) -> StartLink:
        name = " ".join((name or "").strip().split())
        if not name:
            raise ValueError("name_required")
        normalized_code = _normalize_code(code or "")
        for _ in range(10):
            candidate = normalized_code or secrets.token_urlsafe(5).replace("-", "").replace("_", "")[:8]
            exists = (
                await session.execute(select(StartLink.id).where(func.lower(StartLink.code) == candidate.lower()))
            ).scalar_one_or_none()
            if exists is None:
                link = StartLink(name=name, code=candidate, created_by=created_by)
                session.add(link)
                await session.commit()
                await session.refresh(link)
                return link
            normalized_code = ""
        raise ValueError("code_collision")

    @staticmethod
    async def list_links(session: AsyncSession) -> list[tuple[StartLink, int]]:
        stmt = (
            select(StartLink, func.count(StartLinkVisit.id))
            .outerjoin(StartLinkVisit, StartLinkVisit.start_link_id == StartLink.id)
            .group_by(StartLink.id)
            .order_by(StartLink.created_at.desc(), StartLink.id.desc())
        )
        return list((await session.execute(stmt)).all())

    @staticmethod
    async def get_link(session: AsyncSession, link_id: int) -> StartLink | None:
        return (
            await session.execute(select(StartLink).where(StartLink.id == link_id))
        ).scalar_one_or_none()

    @staticmethod
    async def find_by_code(session: AsyncSession, code: str) -> StartLink | None:
        normalized = _normalize_code(code)
        if not normalized:
            return None
        return (
            await session.execute(select(StartLink).where(func.lower(StartLink.code) == normalized.lower()))
        ).scalar_one_or_none()

    @staticmethod
    async def toggle_link(session: AsyncSession, link_id: int) -> StartLink | None:
        link = await StartLinkService.get_link(session, link_id)
        if not link:
            return None
        link.is_active = not link.is_active
        link.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(link)
        return link

    @staticmethod
    async def delete_link(session: AsyncSession, link_id: int) -> bool:
        link = await StartLinkService.get_link(session, link_id)
        if not link:
            return False
        await session.delete(link)
        await session.commit()
        return True

    @staticmethod
    async def record_start(session: AsyncSession, user: User, payload: str | None) -> StartLink | None:
        if not payload or not payload.startswith(START_LINK_PAYLOAD_PREFIX):
            return None
        code = payload.removeprefix(START_LINK_PAYLOAD_PREFIX)
        link = await StartLinkService.find_by_code(session, code)
        if not link or not link.is_active:
            return link
        now = datetime.now(timezone.utc)
        visit = (
            await session.execute(
                select(StartLinkVisit).where(
                    StartLinkVisit.start_link_id == link.id,
                    StartLinkVisit.user_id == user.telegram_id,
                )
            )
        ).scalar_one_or_none()
        if visit:
            visit.hit_count = int(visit.hit_count or 0) + 1
            visit.last_seen_at = now
        else:
            session.add(
                StartLinkVisit(
                    start_link_id=link.id,
                    user_id=user.telegram_id,
                    first_seen_at=now,
                    last_seen_at=now,
                    hit_count=1,
                )
            )
        await session.flush()
        return link

    @staticmethod
    async def visits_for_link(session: AsyncSession, link_id: int, *, limit: int = 30) -> list[StartLinkVisit]:
        result = await session.execute(
            select(StartLinkVisit)
            .options(selectinload(StartLinkVisit.user))
            .where(StartLinkVisit.start_link_id == link_id)
            .order_by(StartLinkVisit.first_seen_at.desc(), StartLinkVisit.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def visit_count(session: AsyncSession, link_id: int) -> int:
        return int(
            (
                await session.execute(
                    select(func.count(StartLinkVisit.id)).where(StartLinkVisit.start_link_id == link_id)
                )
            ).scalar_one()
            or 0
        )

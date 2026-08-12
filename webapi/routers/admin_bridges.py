import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import (
    Admin,
    PanelBridgeAssignment,
    PanelBridgeRule,
    ProvisionPanel,
    ShopPlan,
    ShopPlanCategory,
)
from bot_package.services.panel_bridge_service import PanelBridgeService
from bot_package.services.provisioning_service import ProvisioningError, ProvisioningService

from ..deps import get_session, require_permission


router = APIRouter(prefix="/admin/panel-bridges", tags=["admin"])


class BridgeRuleBody(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    source_panel_keys: list[str] = Field(default_factory=list)
    source_category_keys: list[str] = Field(default_factory=list)
    source_plan_ids: list[int] = Field(default_factory=list)
    target_panel_key: str
    target_inbounds: dict[str, list[str]]
    cleanup_on_delete: bool = True
    apply_now: bool = True


def _loads(value: str | None, fallback):
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _rule_out(rule: PanelBridgeRule, assignments: int = 0) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "source_panel_keys": _loads(rule.source_panel_keys_json, []),
        "source_category_keys": _loads(rule.source_category_keys_json, []),
        "source_plan_ids": _loads(rule.source_plan_ids_json, []),
        "target_panel_key": rule.target_panel_key,
        "target_inbounds": _loads(rule.target_inbounds_json, {}),
        "target_ports": _loads(rule.target_ports_json, []),
        "cleanup_on_delete": rule.cleanup_on_delete,
        "is_enabled": rule.is_enabled,
        "sync_status": rule.sync_status,
        "total_matches": rule.total_matches,
        "synced_count": rule.synced_count,
        "skipped_count": rule.skipped_count,
        "failed_count": rule.failed_count,
        "last_error": rule.last_error,
        "last_synced_at": rule.last_synced_at,
        "assignments": assignments,
    }


async def _validated_rule_values(session: AsyncSession, body: BridgeRuleBody) -> tuple[dict, list[int]]:
    if not (body.source_panel_keys or body.source_category_keys or body.source_plan_ids):
        raise HTTPException(status_code=422, detail="حداقل یک پنل، دسته یا پلن مبدا انتخاب کنید.")
    target = await ProvisioningService.get_panel(session, body.target_panel_key)
    if target is None:
        raise HTTPException(status_code=404, detail="پنل مقصد پیدا نشد یا غیرفعال است.")
    options = await ProvisioningService.fetch_inbound_options(target)
    available = {(item["protocol"], item["tag"]): item for item in options}
    normalized: dict[str, list[str]] = {}
    ports: set[int] = set()
    for protocol, tags in body.target_inbounds.items():
        selected = []
        for tag in tags:
            option = available.get((protocol, tag))
            if option is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"اینباند {protocol} / {tag} دیگر در پنل مقصد وجود ندارد.",
                )
            selected.append(tag)
            if int(option.get("port") or 0) > 0:
                ports.add(int(option["port"]))
        if selected:
            normalized[protocol] = selected
    if not normalized or not ports:
        raise HTTPException(status_code=422, detail="حداقل یک اینباند دارای پورت انتخاب کنید.")
    return normalized, sorted(ports)


def _schedule(background_tasks: BackgroundTasks, coroutine, *args) -> None:
    background_tasks.add_task(coroutine, *args)


@router.get("")
async def list_rules(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    rows = (await session.execute(select(PanelBridgeRule).order_by(PanelBridgeRule.id.desc()))).scalars().all()
    counts = dict(
        (
            await session.execute(
                select(PanelBridgeAssignment.rule_id, func.count(PanelBridgeAssignment.id))
                .group_by(PanelBridgeAssignment.rule_id)
            )
        ).all()
    )
    return [_rule_out(rule, int(counts.get(rule.id, 0))) for rule in rows]


@router.get("/context")
async def bridge_context(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    await ProvisioningService.ensure_env_panels(session)
    panels = (await session.execute(select(ProvisionPanel).order_by(ProvisionPanel.id))).scalars().all()
    categories = (await session.execute(select(ShopPlanCategory).order_by(ShopPlanCategory.display_order))).scalars().all()
    plans = (await session.execute(select(ShopPlan).order_by(ShopPlan.category_key, ShopPlan.display_order))).scalars().all()
    return {
        "panels": [{"key": row.key, "title": row.title, "enabled": row.is_enabled} for row in panels],
        "categories": [{"key": row.key, "title": row.title} for row in categories],
        "plans": [
            {"id": row.id, "title": row.title, "category_key": row.category_key, "active": row.is_active}
            for row in plans
        ],
    }


@router.get("/panels/{panel_key}/inbounds")
async def live_inbounds(
    panel_key: str,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    panel = await ProvisioningService.get_panel(session, panel_key)
    if panel is None:
        raise HTTPException(status_code=404, detail="پنل پیدا نشد یا غیرفعال است.")
    try:
        return await ProvisioningService.fetch_inbound_options(panel)
    except ProvisioningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("")
async def create_rule(
    body: BridgeRuleBody,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    inbounds, ports = await _validated_rule_values(session, body)
    rule = PanelBridgeRule(
        name=body.name.strip(),
        source_panel_keys_json=json.dumps(sorted(set(body.source_panel_keys))),
        source_category_keys_json=json.dumps(sorted(set(body.source_category_keys))),
        source_plan_ids_json=json.dumps(sorted(set(body.source_plan_ids))),
        target_panel_key=body.target_panel_key,
        target_inbounds_json=json.dumps(inbounds, ensure_ascii=False),
        target_ports_json=json.dumps(ports),
        cleanup_on_delete=body.cleanup_on_delete,
        is_enabled=True,
        sync_status="queued" if body.apply_now else "idle",
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    if body.apply_now:
        _schedule(background_tasks, PanelBridgeService.run_rule, rule.id)
    return _rule_out(rule)


@router.put("/{rule_id}")
async def update_rule(
    rule_id: int,
    body: BridgeRuleBody,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    rule = await session.get(PanelBridgeRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="قانون پیدا نشد.")
    assignment_count = int(
        await session.scalar(
            select(func.count(PanelBridgeAssignment.id)).where(
                PanelBridgeAssignment.rule_id == rule.id
            )
        )
        or 0
    )
    if assignment_count and body.target_panel_key != rule.target_panel_key:
        raise HTTPException(
            status_code=409,
            detail="برای تغییر پنل مقصد، ابتدا این قانون را با پاک‌سازی حذف و قانون جدید بسازید.",
        )
    inbounds, ports = await _validated_rule_values(session, body)
    rule.name = body.name.strip()
    rule.source_panel_keys_json = json.dumps(sorted(set(body.source_panel_keys)))
    rule.source_category_keys_json = json.dumps(sorted(set(body.source_category_keys)))
    rule.source_plan_ids_json = json.dumps(sorted(set(body.source_plan_ids)))
    rule.target_panel_key = body.target_panel_key
    rule.target_inbounds_json = json.dumps(inbounds, ensure_ascii=False)
    rule.target_ports_json = json.dumps(ports)
    rule.cleanup_on_delete = body.cleanup_on_delete
    rule.is_enabled = True
    rule.sync_status = "queued" if body.apply_now else "idle"
    rule.updated_at = datetime.now(timezone.utc)
    await session.commit()
    if body.apply_now:
        _schedule(background_tasks, PanelBridgeService.run_rule, rule.id)
    return _rule_out(rule)


@router.post("/{rule_id}/sync")
async def sync_rule(
    rule_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    rule = await session.get(PanelBridgeRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="قانون پیدا نشد.")
    if rule.sync_status == "running":
        return {"queued": False, "detail": "همگام‌سازی در حال اجراست."}
    rule.is_enabled = True
    rule.sync_status = "queued"
    await session.commit()
    _schedule(background_tasks, PanelBridgeService.run_rule, rule.id)
    return {"queued": True}


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    rule = await session.get(PanelBridgeRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="قانون پیدا نشد.")
    rule.is_enabled = False
    rule.sync_status = "cleaning"
    await session.commit()
    _schedule(background_tasks, PanelBridgeService.remove_rule, rule.id)
    return {"cleaning": True}

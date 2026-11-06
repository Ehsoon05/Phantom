"""Admin: coupons and referral reward rules."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, Coupon, CouponTarget, ReferralRewardRule, User
from bot_package.services.coupon_service import CouponError, CouponService
from bot_package.services.referral_service import ReferralService
from bot_package.services.settings_service import SettingsService

from ..deps import get_session, require_permission

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Coupons -----------------------------------------------------------------

async def _coupon_out(session: AsyncSession, c: Coupon) -> dict:
    target_count = (
        await session.execute(
            select(func.count(CouponTarget.id)).where(CouponTarget.coupon_id == c.id)
        )
    ).scalar_one()
    return {
        "id": c.id,
        "code": c.code,
        "discount_type": c.discount_type,
        "amount": c.amount,
        "applies_to_all": c.applies_to_all,
        "is_active": c.is_active,
        "target_user_count": target_count,
    }


class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    discount_type: str  # "percent" | "fixed"
    amount: int = Field(gt=0)
    target_user_ids: list[int] | None = None


class CouponUpdateRequest(BaseModel):
    discount_type: str
    amount: int = Field(gt=0)
    target_user_ids: list[int] | None = None


@router.get("/coupons")
async def list_coupons(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("coupons")),
):
    coupons = await CouponService.list_coupons(session)
    return [await _coupon_out(session, c) for c in coupons]


@router.post("/coupons")
async def create_coupon(
    body: CouponCreateRequest,
    session: AsyncSession = Depends(get_session),
    admin: Admin = Depends(require_permission("coupons")),
):
    try:
        coupon = await CouponService.create_coupon(
            session,
            code=body.code,
            discount_type=body.discount_type,
            amount=body.amount,
            created_by=admin.telegram_id,
            target_user_ids=body.target_user_ids,
        )
        await session.commit()
    except CouponError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await _coupon_out(session, coupon)


@router.put("/coupons/{code}")
async def update_coupon(
    code: str,
    body: CouponUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("coupons")),
):
    try:
        coupon = await CouponService.update_coupon(
            session,
            code=code,
            discount_type=body.discount_type,
            amount=body.amount,
            target_user_ids=body.target_user_ids,
        )
        await session.commit()
    except CouponError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return await _coupon_out(session, coupon)


@router.post("/coupons/{code}/deactivate")
async def deactivate_coupon(
    code: str,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("coupons")),
):
    coupon = await CouponService.deactivate_coupon(session, code)
    await session.commit()
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return await _coupon_out(session, coupon)


@router.delete("/coupons/{code}")
async def delete_coupon(
    code: str,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("coupons")),
):
    coupon = await CouponService.delete_coupon(session, code)
    await session.commit()
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"deleted": True}


# --- Referral reward rules ---------------------------------------------------

class ReferralCommissionRequest(BaseModel):
    enabled: bool
    percent: int = Field(ge=0, le=100)


@router.get("/referrals/commission")
async def get_referral_commission(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    return await ReferralService.commission_settings(session)


@router.put("/referrals/commission")
async def update_referral_commission(
    body: ReferralCommissionRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    await SettingsService.set_referral_commission_enabled(session, body.enabled)
    await SettingsService.set_referral_commission_percent(session, body.percent)
    return await ReferralService.commission_settings(session)


def _rule_out(r: ReferralRewardRule) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "qualification_type": r.qualification_type,
        "required_count": r.required_count,
        "is_repeatable": r.is_repeatable,
        "reward_type": r.reward_type,
        "wallet_amount": r.wallet_amount,
        "shop_plan_id": r.shop_plan_id,
        "is_active": r.is_active,
    }


class RuleCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    qualification_type: str  # joined | wallet_charged | purchased | purchased_and_charged
    required_count: int = Field(gt=0)
    is_repeatable: bool = False
    reward_type: str  # wallet | service
    wallet_amount: int | None = None
    shop_plan_id: int | None = None


@router.get("/referrals/rules")
async def list_rules(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    return [_rule_out(r) for r in await ReferralService.list_rules(session)]


@router.post("/referrals/rules")
async def create_rule(
    body: RuleCreateRequest,
    session: AsyncSession = Depends(get_session),
    admin: Admin = Depends(require_permission("users")),
):
    try:
        rule = await ReferralService.create_rule(
            session,
            title=body.title,
            qualification_type=body.qualification_type,
            required_count=body.required_count,
            is_repeatable=body.is_repeatable,
            reward_type=body.reward_type,
            created_by=admin.telegram_id,
            wallet_amount=body.wallet_amount,
            shop_plan_id=body.shop_plan_id,
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _rule_out(rule)


@router.post("/referrals/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    rule = await ReferralService.toggle_rule(session, rule_id)
    await session.commit()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _rule_out(rule)


@router.delete("/referrals/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    ok = await ReferralService.delete_rule(session, rule_id)
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": True}


@router.post("/referrals/recalculate")
async def recalculate_referrals(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    grants = await ReferralService.evaluate_all_referrers(session)
    await session.commit()
    return {"grants": len(grants)}


@router.get("/referrals/report")
async def referral_report(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    rows = await ReferralService.referral_map(session)
    return [
        {"referred_user_id": ref, "referrer_user_id": by, "referred_at": at}
        for ref, by, at in rows
    ]

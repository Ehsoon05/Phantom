"""Exchange-rate engine for crypto top-ups.

Returns the effective *toman per 1 coin unit* rate, honouring the admin's
chosen mode (online API vs manual) and margin %. Online rates are cached and
refreshed on a schedule (see the 10-minute JobQueue job) so user-facing
conversions never block on a network call.

Online sources (no API key required):
  - USDT -> toman:  Nobitex order book (USDTIRT, price in rials -> /10 = toman)
  - TON  -> USD:    CoinGecko simple price; TON -> toman = TON_usd * USDT_toman
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .settings_service import SettingsService

logger = logging.getLogger(__name__)

NOBITEX_USDT_IRT = "https://api.nobitex.ir/v2/orderbook/USDTIRT"
COINGECKO_TON_USD = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd"

# Display precision (decimal places) per coin for the amount the user must send.
COIN_DECIMALS = {"USDT": 2, "TON": 4}

# In-process cache of online rates: coin -> (toman_per_unit: Decimal, fetched_at)
_online_cache: dict[str, tuple[Decimal, datetime]] = {}


class RateError(Exception):
    pass


async def _fetch_usdt_toman(client: httpx.AsyncClient) -> Optional[Decimal]:
    try:
        resp = await client.get(NOBITEX_USDT_IRT, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        last_rial = Decimal(str(data["lastTradePrice"]))
        return last_rial / Decimal(10)  # rial -> toman
    except Exception as exc:  # noqa: BLE001 - network/parse failures are non-fatal
        logger.warning("Failed to fetch USDT->toman: %s", exc)
        return None


async def _fetch_ton_toman(client: httpx.AsyncClient, usdt_toman: Optional[Decimal]) -> Optional[Decimal]:
    if usdt_toman is None:
        return None
    try:
        resp = await client.get(COINGECKO_TON_USD, timeout=10)
        resp.raise_for_status()
        ton_usd = Decimal(str(resp.json()["the-open-network"]["usd"]))
        return ton_usd * usdt_toman
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch TON->toman: %s", exc)
        return None


class RateService:
    @staticmethod
    async def refresh_online_rates() -> dict[str, Decimal]:
        """Fetch live rates into the cache. Keeps stale values on failure."""
        now = datetime.now(timezone.utc)
        async with httpx.AsyncClient() as client:
            usdt = await _fetch_usdt_toman(client)
            ton = await _fetch_ton_toman(client, usdt)
        if usdt is not None:
            _online_cache["USDT"] = (usdt, now)
        if ton is not None:
            _online_cache["TON"] = (ton, now)
        return {coin: value for coin, (value, _) in _online_cache.items()}

    @staticmethod
    def cached_online_rate(coin: str) -> Optional[Decimal]:
        entry = _online_cache.get(coin.upper())
        return entry[0] if entry else None

    @staticmethod
    def cache_age_seconds(coin: str) -> Optional[float]:
        entry = _online_cache.get(coin.upper())
        if not entry:
            return None
        return (datetime.now(timezone.utc) - entry[1]).total_seconds()

    @staticmethod
    async def _base_rate(session: AsyncSession, coin: str) -> tuple[Decimal, str]:
        """Return (toman_per_unit_before_margin, source)."""
        coin = coin.upper()
        mode = await SettingsService.get_rate_mode(session)
        if mode == "manual":
            manual = await SettingsService.get_manual_rate(session, coin)
            if manual <= 0:
                raise RateError(f"Manual rate for {coin} is not set.")
            return Decimal(manual), "manual"

        # online
        rate = RateService.cached_online_rate(coin)
        if rate is None:
            await RateService.refresh_online_rates()
            rate = RateService.cached_online_rate(coin)
        if rate is None or rate <= 0:
            # Fall back to manual if available, so the shop keeps working offline.
            manual = await SettingsService.get_manual_rate(session, coin)
            if manual > 0:
                return Decimal(manual), "manual_fallback"
            raise RateError(f"No online rate available for {coin} and no manual fallback set.")
        return rate, "online"

    @staticmethod
    async def get_effective_rate(session: AsyncSession, coin: str) -> tuple[Decimal, str]:
        """Toman per 1 coin unit after applying margin. Returns (rate, source).

        Margin lowers the toman-per-coin rate so the user sends slightly more
        crypto for the same toman credit (the shop's markup).
        """
        base, source = await RateService._base_rate(session, coin)
        margin = Decimal(str(await SettingsService.get_margin(session)))
        effective = base * (Decimal(100) - margin) / Decimal(100)
        if effective <= 0:
            raise RateError("Effective rate computed as non-positive; check margin.")
        return effective, source

    @staticmethod
    async def toman_to_crypto(session: AsyncSession, coin: str, toman: int) -> tuple[Decimal, Decimal, str]:
        """Convert a toman amount to the crypto amount the user must send.

        Returns (crypto_amount, effective_rate, source). The crypto amount is
        rounded UP to the coin's display precision so the shop never under-charges.
        """
        coin = coin.upper()
        rate, source = await RateService.get_effective_rate(session, coin)
        raw = Decimal(toman) / rate
        places = COIN_DECIMALS.get(coin, 2)
        quantum = Decimal(1).scaleb(-places)  # e.g. 0.01
        # Round up so the converted crypto is always >= exact value.
        crypto = raw.quantize(quantum, rounding=ROUND_DOWN)
        if crypto < raw:
            crypto += quantum
        return crypto, rate, source

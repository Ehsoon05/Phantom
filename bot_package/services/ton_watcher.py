"""TON deposit support via a single receiving address + per-invoice memo.

Attribution is by the text comment (memo) the user includes in the transfer,
so no per-invoice address derivation is needed. The server holds no keys.

  - Native TON: matched via Toncenter v2 ``getTransactions`` (in_msg comment).
  - USDT jetton on TON: matched via Toncenter v3 ``jetton/transfers`` comment.

Note: senders must use a wallet that lets them attach a text comment; a few
exchange withdrawal forms do not, which is surfaced to users in the UI.
"""
import logging
from decimal import Decimal
from typing import Optional

import httpx

from ..config_loader import BotConfig

logger = logging.getLogger(__name__)

TONCENTER_V2 = "https://toncenter.com/api/v2"
TONCENTER_V3 = "https://toncenter.com/api/v3"
TON_DECIMALS = 9          # nanoton
TON_USDT_DECIMALS = 6     # USDT jetton on TON


class TonWatcherError(Exception):
    pass


def _headers() -> dict:
    return {"X-API-Key": BotConfig.TON_API_KEY} if BotConfig.TON_API_KEY else {}


async def fetch_incoming_ton(memo: str, min_amount: Optional[Decimal] = None) -> list[dict]:
    """Return confirmed native-TON transfers whose comment equals ``memo``.

    Each item: {tx_hash, from, amount (Decimal TON), confirmations}.
    """
    if not BotConfig.TON_DEPOSIT_ADDRESS:
        return []
    url = f"{TONCENTER_V2}/getTransactions"
    params = {"address": BotConfig.TON_DEPOSIT_ADDRESS, "limit": 50, "archival": "true"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=_headers(), timeout=15)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Toncenter v2 fetch failed: %s", exc)
        return []

    results: list[dict] = []
    for tx in payload.get("result", []):
        in_msg = tx.get("in_msg") or {}
        comment = (in_msg.get("message") or "").strip()
        if comment != memo:
            continue
        raw_value = in_msg.get("value")
        if raw_value is None:
            continue
        amount = Decimal(str(raw_value)) / (Decimal(10) ** TON_DECIMALS)
        if min_amount is not None and amount < min_amount:
            continue
        tx_id = tx.get("transaction_id") or {}
        results.append(
            {
                "tx_hash": tx_id.get("hash"),
                "from": in_msg.get("source"),
                "amount": amount,
                "confirmations": BotConfig.CRYPTO_MIN_CONFIRMATIONS,
            }
        )
    return results


async def fetch_incoming_usdt_ton(memo: str, min_amount: Optional[Decimal] = None) -> list[dict]:
    """Return USDT-jetton transfers to the deposit address whose comment == memo.

    Requires TON_USDT_JETTON_MASTER to be configured; otherwise returns [].
    """
    if not (BotConfig.TON_DEPOSIT_ADDRESS and BotConfig.TON_USDT_JETTON_MASTER):
        return []
    url = f"{TONCENTER_V3}/jetton/transfers"
    params = {
        "dest": BotConfig.TON_DEPOSIT_ADDRESS,
        "jetton_master": BotConfig.TON_USDT_JETTON_MASTER,
        "limit": 50,
        "direction": "in",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=_headers(), timeout=15)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Toncenter v3 jetton fetch failed: %s", exc)
        return []

    results: list[dict] = []
    for tr in payload.get("jetton_transfers", []):
        comment = (tr.get("comment") or "").strip()
        if comment != memo:
            continue
        raw_value = tr.get("amount")
        if raw_value is None:
            continue
        amount = Decimal(str(raw_value)) / (Decimal(10) ** TON_USDT_DECIMALS)
        if min_amount is not None and amount < min_amount:
            continue
        results.append(
            {
                "tx_hash": tr.get("transaction_hash") or tr.get("trace_id"),
                "from": tr.get("source"),
                "amount": amount,
                "confirmations": BotConfig.CRYPTO_MIN_CONFIRMATIONS,
            }
        )
    return results

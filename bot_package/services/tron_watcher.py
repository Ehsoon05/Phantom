"""Tron (TRC-20 USDT) watch-only deposit support.

Addresses are derived from an account-level *extended public key* (xpub) via
BIP44 (coin type 195). The server therefore never holds spend keys: it can
generate receive addresses and watch them, but cannot move funds. Sweep the
collected balances offline using the seed.

Payment detection polls TronGrid's TRC-20 transfer endpoint for each address.
"""
import logging
from decimal import Decimal
from typing import Optional

import httpx

from ..config_loader import BotConfig

logger = logging.getLogger(__name__)

TRONGRID_BASE = "https://api.trongrid.io"
USDT_DECIMALS = 6  # TRC-20 USDT uses 6 decimals (sun-equivalent)


class TronWatcherError(Exception):
    pass


def _account_pubkey():
    """Build a watch-only BIP44 account public key from the configured xpub.

    Imported lazily so the dependency is only required when crypto is enabled.
    """
    if not BotConfig.TRON_XPUB:
        raise TronWatcherError("TRON_XPUB is not configured.")
    from bip_utils import Bip44, Bip44Coins, Bip44Changes  # noqa: WPS433

    # The xpub is an account-level key; derive external chain (change=0) leaves.
    acct = Bip44.FromExtendedKey(BotConfig.TRON_XPUB, Bip44Coins.TRON)
    return acct.Change(Bip44Changes.CHAIN_EXT)


def derive_address(index: int) -> str:
    """Return the Tron base58 address for the given derivation index."""
    change = _account_pubkey()
    return change.AddressIndex(index).PublicKey().ToAddress()


def _headers() -> dict:
    return {"TRON-PRO-API-KEY": BotConfig.TRON_API_KEY} if BotConfig.TRON_API_KEY else {}


async def fetch_incoming_usdt(address: str, min_amount: Optional[Decimal] = None) -> list[dict]:
    """Return confirmed incoming USDT transfers to ``address``.

    Each item: {tx_hash, from, amount (Decimal USDT), confirmations}. Only
    transfers of the configured USDT contract are returned.
    """
    url = f"{TRONGRID_BASE}/v1/accounts/{address}/transactions/trc20"
    params = {
        "only_confirmed": "true",
        "only_to": "true",
        "contract_address": BotConfig.TRON_USDT_CONTRACT,
        "limit": 50,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=_headers(), timeout=15)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("TronGrid fetch failed for %s: %s", address, exc)
        return []

    results: list[dict] = []
    for item in payload.get("data", []):
        if item.get("to", "").strip() != address:
            continue
        raw_value = item.get("value")
        if raw_value is None:
            continue
        amount = Decimal(str(raw_value)) / (Decimal(10) ** USDT_DECIMALS)
        if min_amount is not None and amount < min_amount:
            continue
        results.append(
            {
                "tx_hash": item.get("transaction_id"),
                "from": item.get("from"),
                "amount": amount,
                # TronGrid only_confirmed already filters to confirmed txs.
                "confirmations": BotConfig.CRYPTO_MIN_CONFIRMATIONS,
            }
        )
    return results

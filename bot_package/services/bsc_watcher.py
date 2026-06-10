"""BNB Smart Chain (BEP-20 USDC) watch-only deposit support.

Mirrors the Tron design: a unique deposit address per invoice, derived from an
account-level EVM extended public key (BIP44 coin type 60). The server holds no
spend keys. Payment detection polls the BscScan token-transfer API.

Note: Binance-Peg USDC on BSC uses 18 decimals (unlike Ethereum USDC's 6); the
per-transfer ``tokenDecimal`` from the API is used when present, with a config
fallback.
"""
import logging
from decimal import Decimal
from typing import Optional

import httpx

from ..config_loader import BotConfig

logger = logging.getLogger(__name__)

BSCSCAN_API = "https://api.bscscan.com/api"


class BscWatcherError(Exception):
    pass


def _account_pubkey():
    """Watch-only EVM account public key derived from the configured xpub.

    Imported lazily so bip_utils is only required when crypto is enabled.
    """
    if not BotConfig.BSC_XPUB:
        raise BscWatcherError("BSC_XPUB is not configured.")
    from bip_utils import Bip44, Bip44Coins, Bip44Changes  # noqa: WPS433

    # BSC shares Ethereum's address scheme; the xpub is an account-level key.
    acct = Bip44.FromExtendedKey(BotConfig.BSC_XPUB, Bip44Coins.ETHEREUM)
    return acct.Change(Bip44Changes.CHAIN_EXT)


def derive_address(index: int) -> str:
    """Return the (checksummed) EVM address for the given derivation index."""
    change = _account_pubkey()
    return change.AddressIndex(index).PublicKey().ToAddress()


async def fetch_incoming_usdc(address: str, min_amount: Optional[Decimal] = None) -> list[dict]:
    """Return incoming BEP-20 USDC transfers to ``address``.

    Each item: {tx_hash, from, amount (Decimal USDC), confirmations}.
    """
    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": BotConfig.BSC_USDC_CONTRACT,
        "address": address,
        "sort": "desc",
        "page": 1,
        "offset": 50,
    }
    if BotConfig.BSCSCAN_API_KEY:
        params["apikey"] = BotConfig.BSCSCAN_API_KEY
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(BSCSCAN_API, params=params, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("BscScan fetch failed for %s: %s", address, exc)
        return []

    # BscScan returns status "1" with a result list, or "0"/message on no txs.
    if not isinstance(payload.get("result"), list):
        return []

    target = address.lower()
    results: list[dict] = []
    for item in payload["result"]:
        if (item.get("to") or "").lower() != target:
            continue
        if (item.get("contractAddress") or "").lower() != BotConfig.BSC_USDC_CONTRACT.lower():
            continue
        raw_value = item.get("value")
        if raw_value is None:
            continue
        try:
            decimals = int(item.get("tokenDecimal") or BotConfig.BSC_USDC_DECIMALS)
        except (TypeError, ValueError):
            decimals = BotConfig.BSC_USDC_DECIMALS
        amount = Decimal(str(raw_value)) / (Decimal(10) ** decimals)
        if min_amount is not None and amount < min_amount:
            continue
        try:
            confirmations = int(item.get("confirmations") or 0)
        except (TypeError, ValueError):
            confirmations = 0
        results.append(
            {
                "tx_hash": item.get("hash"),
                "from": item.get("from"),
                "amount": amount,
                "confirmations": confirmations,
            }
        )
    return results

#!/usr/bin/env python3
"""Move manually-managed SVN subscription rows to MMD with a rollback manifest."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot_package.config_loader import BotConfig
from bot_package.database import async_session, engine
from bot_package.models import Config, ProvisionPanel, ShopPlan
from bot_package.services.provisioning_service import (
    ProvisioningError,
    ProvisioningService,
    _subscription_url,
)
from bot_package.services.schema_service import SchemaService


CONFIRMATION = "MIGRATE-MANUAL-SVN-TO-MMD"
SVN_HOSTS = {"sub.svnteam-max.com:2053", "youpanel.temas-arvha.ir:2053"}
PANEL_FIELDS = (
    "id",
    "public_sub_token",
    "sub_link",
    "volume_gb",
    "category_key",
    "is_sold",
    "service_name",
    "panel_username",
    "telegram_user_id",
    "profile_title",
    "device_limit",
    "show_config_preview",
    "show_header",
    "channel_handle",
    "info_proxies_enabled",
    "address_rewrites_json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-key", default="svn")
    parser.add_argument("--target-key", default="mmd")
    parser.add_argument("--source-api-url", default="http://127.0.0.1:18443")
    parser.add_argument(
        "--panel-db",
        default="/tmp/phantom-panel-manual-migration.db",
    )
    parser.add_argument(
        "--pre-migration-panel-db",
        default="/tmp/phantom-panel-pre-mmd.db",
    )
    parser.add_argument(
        "--main-backup-db",
        default="/opt/phantom/backups/vpn_shop.db.pre-mmd-migration-20260729",
    )
    parser.add_argument(
        "--manifest",
        default="/opt/phantom/backups/mmd-migration-rollback-20260729.json",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    return parser.parse_args()


def _token_from_url(value: str) -> str:
    parts = [part for part in urlparse(value or "").path.split("/") if part]
    return parts[-1] if parts else ""


def _row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _address_rewrites_text(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return ""
    if not isinstance(value, dict):
        return ""
    return "\n".join(
        f"{source}={target}"
        for source, target in sorted(value.items())
        if str(source).strip() and str(target).strip()
    )


def _sync_payload(
    row: dict,
    *,
    upstream_url: str,
    panel_username: str | None,
    usage_offset_bytes: int,
    display_total_bytes: int,
    info_proxies_enabled: bool,
    address_rewrites: str,
) -> dict:
    return {
        "token": row["public_sub_token"],
        "upstream_url": upstream_url,
        "volume_gb": max(0, int(row.get("volume_gb") or 0)),
        "category_key": row.get("category_key") or "default",
        "is_sold": bool(row.get("is_sold")),
        "service_name": row.get("service_name"),
        "panel_username": panel_username,
        "profile_title": row.get("profile_title"),
        "telegram_user_id": row.get("telegram_user_id"),
        "usage_offset_bytes": max(0, int(usage_offset_bytes)),
        "display_total_bytes": max(0, int(display_total_bytes)),
        "device_limit": (
            max(0, int(row["device_limit"]))
            if row.get("device_limit") is not None
            else None
        ),
        "show_config_preview": (
            bool(row["show_config_preview"])
            if row.get("show_config_preview") is not None
            else None
        ),
        "info_proxies_enabled": bool(info_proxies_enabled),
        "show_header": (
            bool(row["show_header"])
            if row.get("show_header") is not None
            else None
        ),
        "channel_handle": row.get("channel_handle"),
        "address_rewrites": address_rewrites,
    }


async def _token(
    client: httpx.AsyncClient,
    panel: ProvisionPanel,
) -> str:
    response = await client.post(
        "/api/admin/token",
        data={"username": panel.username, "password": panel.password},
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise ProvisioningError("Source panel did not return an access token.")
    return str(token)


async def _all_users(
    client: httpx.AsyncClient,
    headers: dict[str, str],
) -> list[dict]:
    users: list[dict] = []
    offset = 0
    while True:
        response = await client.get(
            "/api/users",
            params={"offset": offset, "limit": 100},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        page = payload.get("users", payload if isinstance(payload, list) else [])
        if not isinstance(page, list):
            raise ProvisioningError("Source panel returned an invalid users list.")
        users.extend(user for user in page if isinstance(user, dict))
        if len(page) < 100:
            return users
        offset += len(page)


def _source_status(source: dict) -> tuple[str, str]:
    status = str(source.get("status") or "active").strip().lower()
    create_status = "on_hold" if status == "on_hold" else "active"
    rollback_status = "on_hold" if status == "on_hold" else "active"
    return create_status, rollback_status


def _target_payload(
    source: dict,
    username: str,
    access_fields: dict,
) -> tuple[dict, int, int]:
    total = max(0, int(source.get("data_limit") or 0))
    used = max(0, int(source.get("used_traffic") or 0))
    remaining = max(total - used, 0) if total else 0
    create_status, _ = _source_status(source)
    on_hold_duration = max(0, int(source.get("on_hold_expire_duration") or 0))
    payload = {
        "username": username,
        "data_limit": remaining or (1 if total else 0),
        "data_limit_reset_strategy": "no_reset",
        "status": create_status,
        "expire": (
            0
            if create_status == "on_hold"
            else max(0, int(source.get("expire") or 0))
        ),
        "on_hold_expire_duration": (
            on_hold_duration or None if create_status == "on_hold" else None
        ),
        **access_fields,
    }
    return payload, used, total


def _load_panel_rows(path: str) -> list[dict]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    columns = ", ".join(PANEL_FIELDS)
    rows = [
        dict(row)
        for row in connection.execute(
            f"SELECT {columns} FROM subscription_configs ORDER BY id"
        ).fetchall()
    ]
    connection.close()
    return [
        row
        for row in rows
        if urlparse(row["sub_link"]).netloc.lower() in SVN_HOSTS
    ]


def _load_rows_by_token(path: str) -> dict[str, dict]:
    if not Path(path).exists():
        return {}
    return {
        row["public_sub_token"]: row
        for row in _load_panel_rows(path)
        if row.get("public_sub_token")
    }


def _main_rollback_entries(
    current: sqlite3.Connection,
    backup: sqlite3.Connection,
    original_panel_rows: dict[str, dict],
    source_users: dict[str, dict],
    target_users: dict[str, dict],
) -> tuple[list[dict], list[int]]:
    current.row_factory = sqlite3.Row
    backup.row_factory = sqlite3.Row
    configs = current.execute(
        """
        SELECT id, panel_username, public_sub_token, sub_link,
               usage_offset_bytes, display_total_bytes
        FROM configs
        WHERE panel_key = 'mmd'
          AND category_key = 'express'
          AND is_sold = 1
          AND panel_deleted_at IS NULL
        ORDER BY id
        """
    ).fetchall()
    entries = []
    missing = []
    for config in configs:
        old = backup.execute(
            """
            SELECT id, sub_link, panel_key, panel_username,
                   usage_offset_bytes, display_total_bytes
            FROM configs
            WHERE id = ?
            """,
            (config["id"],),
        ).fetchone()
        source = source_users.get(config["panel_username"])
        target = target_users.get(config["panel_username"])
        original_panel = original_panel_rows.get(config["public_sub_token"])
        if not old or not source or not target or not original_panel:
            missing.append(config["id"])
            continue
        _, rollback_status = _source_status(target)
        entries.append(
            {
                "kind": "main",
                "config_id": config["id"],
                "username": config["panel_username"],
                "public_sub_token": config["public_sub_token"],
                "rollback_status": rollback_status,
                "source_expire": max(0, int(source.get("expire") or 0)),
                "source_on_hold_duration": max(
                    0, int(source.get("on_hold_expire_duration") or 0)
                ),
                "original_config": dict(old),
                "target_sub_link": config["sub_link"],
                "original_panel_row": original_panel,
            }
        )
    return entries, missing


def _write_manifest(path: str, manifest: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    os.chmod(temporary, 0o600)
    temporary.replace(target)


async def run(args: argparse.Namespace) -> int:
    if args.apply and args.confirm != CONFIRMATION:
        print(f"Refusing apply: pass --confirm {CONFIRMATION}")
        return 2

    await SchemaService.ensure_schema(engine)
    panel_rows = _load_panel_rows(args.panel_db)
    original_panel_rows = _load_rows_by_token(args.pre_migration_panel_db)
    summary: Counter[str] = Counter()

    async with async_session() as session:
        source_panel = await ProvisioningService.get_panel(session, args.source_key)
        target_panel = await ProvisioningService.get_panel(session, args.target_key)
        if source_panel is None or target_panel is None:
            raise ProvisioningError("Source or target panel is missing/disabled.")

        async with httpx.AsyncClient(
            base_url=args.source_api_url.rstrip("/"),
            verify=False,
            timeout=30,
        ) as source_client:
            source_token = await _token(source_client, source_panel)
            source_headers = {"Authorization": f"Bearer {source_token}"}
            source_users_list = await _all_users(source_client, source_headers)
            source_by_username = {
                str(user.get("username")): user
                for user in source_users_list
                if user.get("username")
            }
            source_by_token = {
                _token_from_url(str(user.get("subscription_url") or "")): user
                for user in source_users_list
                if _token_from_url(str(user.get("subscription_url") or ""))
            }

            async with ProvisioningService._api_client(target_panel) as (
                target_client,
                target_token,
            ):
                target_headers = {"Authorization": f"Bearer {target_token}"}
                target_users_list = await _all_users(
                    target_client,
                    target_headers,
                )
                target_by_username = {
                    str(user.get("username")): user
                    for user in target_users_list
                    if user.get("username")
                }
                access_fields = await ProvisioningService._access_fields(
                    target_client,
                    target_panel,
                    target_headers,
                )

                current_db = sqlite3.connect("/opt/phantom/vpn_shop.db")
                backup_db = sqlite3.connect(args.main_backup_db)
                main_entries, main_missing = _main_rollback_entries(
                    current_db,
                    backup_db,
                    original_panel_rows,
                    source_by_username,
                    target_by_username,
                )
                current_db.close()
                backup_db.close()
                if main_missing:
                    raise ProvisioningError(
                        f"Cannot build rollback data for configs: {main_missing}"
                    )

                manifest = {
                    "version": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source_key": args.source_key,
                    "target_key": args.target_key,
                    "source_api_url": args.source_api_url,
                    "main_backup_db": args.main_backup_db,
                    "main_entries": main_entries,
                    "manual_entries": [],
                    "skipped_entries": [],
                }
                if args.apply:
                    _write_manifest(args.manifest, manifest)

                async with httpx.AsyncClient(timeout=30) as sync_client:
                    for row in panel_rows:
                        source = source_by_token.get(
                            _token_from_url(row["sub_link"])
                        )
                        if not source and row.get("panel_username"):
                            source = source_by_username.get(row["panel_username"])
                        if source is None:
                            summary["dead_source"] += 1
                            manifest["skipped_entries"].append(
                                {
                                    "panel_row_id": row["id"],
                                    "public_sub_token": row["public_sub_token"],
                                    "reason": "source_user_not_found",
                                    "original_panel_row": row,
                                }
                            )
                            continue

                        username = str(source["username"])
                        payload, used, total = _target_payload(
                            source,
                            username,
                            access_fields,
                        )
                        existing = await target_client.get(
                            f"/api/user/{username}",
                            headers=target_headers,
                        )
                        action = "create" if existing.status_code == 404 else "update"
                        if existing.status_code != 404 and existing.is_error:
                            summary[f"target_lookup_{existing.status_code}"] += 1
                            continue

                        entry = {
                            "kind": "manual",
                            "panel_row_id": row["id"],
                            "username": username,
                            "public_sub_token": row["public_sub_token"],
                            "rollback_status": _source_status(source)[1],
                            "source_expire": max(0, int(source.get("expire") or 0)),
                            "source_on_hold_duration": max(
                                0,
                                int(source.get("on_hold_expire_duration") or 0),
                            ),
                            "source_data_limit": total,
                            "source_used_traffic": used,
                            "original_panel_row": row,
                            "target_action": action,
                        }
                        if not args.apply:
                            summary[f"would_{action}"] += 1
                            continue

                        if action == "create":
                            response = await target_client.post(
                                "/api/user",
                                headers=target_headers,
                                json=payload,
                            )
                        else:
                            response = await target_client.put(
                                f"/api/user/{username}",
                                headers=target_headers,
                                json={
                                    key: value
                                    for key, value in payload.items()
                                    if key != "username"
                                },
                            )
                        if response.is_error:
                            summary[f"target_write_{response.status_code}"] += 1
                            continue

                        target_response = await target_client.get(
                            f"/api/user/{username}",
                            headers=target_headers,
                        )
                        if target_response.is_error:
                            summary[
                                f"target_verify_{target_response.status_code}"
                            ] += 1
                            continue
                        target_user = target_response.json()
                        target_sub_link = _subscription_url(
                            target_panel.base_url,
                            target_user,
                        )
                        entry["target_sub_link"] = target_sub_link

                        sync_payload = _sync_payload(
                            row,
                            upstream_url=target_sub_link,
                            panel_username=username,
                            usage_offset_bytes=used,
                            display_total_bytes=total,
                            info_proxies_enabled=True,
                            address_rewrites="",
                        )
                        sync_response = await sync_client.post(
                            BotConfig.SUBSCRIPTION_PANEL_SYNC_URL,
                            json=sync_payload,
                            headers={
                                "Authorization": (
                                    f"Bearer "
                                    f"{BotConfig.SUBSCRIPTION_PANEL_SYNC_TOKEN}"
                                )
                            },
                        )
                        if sync_response.is_error:
                            summary[
                                f"subscription_sync_{sync_response.status_code}"
                            ] += 1
                            continue

                        disable = await source_client.put(
                            f"/api/user/{username}",
                            headers=source_headers,
                            json={"status": "disabled"},
                        )
                        if disable.is_error:
                            summary[
                                f"source_disable_{disable.status_code}"
                            ] += 1
                            continue

                        manifest["manual_entries"].append(entry)
                        _write_manifest(args.manifest, manifest)
                        summary[f"migrated_{action}"] += 1

                if args.apply:
                    _write_manifest(args.manifest, manifest)

    print(f"mode={'apply' if args.apply else 'dry-run'}")
    print(f"summary={dict(summary)}")
    if args.apply:
        print(f"manifest={args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))

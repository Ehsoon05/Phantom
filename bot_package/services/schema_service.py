from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from ..models import Base


class SchemaService:
    @staticmethod
    async def ensure_schema(engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
            if "users" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "users",
                    {
                        "referral_code": "VARCHAR",
                        "referred_by_user_id": "BIGINT",
                        "referred_at": "DATETIME",
                        "accepted_rules_at": "DATETIME",
                        "trial_claimed_at": "DATETIME",
                        "trial_panel_username": "VARCHAR",
                        "verified_phone_number": "VARCHAR",
                        "phone_verified_at": "DATETIME",
                    },
                )
            if "configs" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "configs",
                    {
                        "category_key": "VARCHAR DEFAULT 'default' NOT NULL",
                        "public_sub_token": "VARCHAR",
                    },
                )
            if "purchases" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "purchases",
                    {
                        "category_key": "VARCHAR DEFAULT 'default' NOT NULL",
                        "original_price": "INTEGER",
                        "discount_amount": "INTEGER DEFAULT 0 NOT NULL",
                        "coupon_id": "INTEGER",
                        "coupon_code": "VARCHAR",
                        "service_name": "VARCHAR",
                    },
                )
            if "shop_messages" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "shop_messages",
                    {
                        "premium_emoji_id": "VARCHAR",
                        "premium_emoji_position": "VARCHAR DEFAULT 'none' NOT NULL",
                        "response_button_type": "VARCHAR DEFAULT 'text' NOT NULL",
                        "response_button_text": "VARCHAR",
                        "response_button_url": "VARCHAR",
                        "response_button_style": "VARCHAR",
                        "response_button_premium_emoji_id": "VARCHAR",
                        "response_button_source_id": "INTEGER",
                    },
                )
            if "shop_buttons" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "shop_buttons",
                    {
                        "emoji_position": "VARCHAR DEFAULT 'left' NOT NULL",
                        "premium_emoji_position": "VARCHAR DEFAULT 'left' NOT NULL",
                    },
                )
            if "shop_plans" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "shop_plans",
                    {
                        "category_key": "VARCHAR DEFAULT 'default' NOT NULL",
                        "price": "INTEGER",
                        "emoji_position": "VARCHAR DEFAULT 'left' NOT NULL",
                        "premium_emoji_position": "VARCHAR DEFAULT 'left' NOT NULL",
                    },
                )
                await SchemaService._drop_sqlite_shop_plan_volume_unique(conn)
            if "rial_payment_requests" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "rial_payment_requests",
                    {
                        "phone_number": "VARCHAR",
                        "support_handle": "VARCHAR DEFAULT '@PhantomHubsSupport' NOT NULL",
                        "request_text": "TEXT DEFAULT '' NOT NULL",
                        "status": "VARCHAR DEFAULT 'pending' NOT NULL",
                        "updated_at": "DATETIME",
                    },
                )

    @staticmethod
    async def _add_missing_columns(conn, table_name: str, columns: dict[str, str]) -> None:
        existing = await conn.run_sync(
            lambda sync_conn: {column["name"] for column in inspect(sync_conn).get_columns(table_name)}
        )
        for name, ddl in columns.items():
            if name not in existing:
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl}"))

    @staticmethod
    async def _drop_sqlite_shop_plan_volume_unique(conn) -> None:
        dialect = conn.engine.dialect.name
        if dialect != "sqlite":
            return

        indexes = await conn.execute(text("PRAGMA index_list(shop_plans)"))
        has_unique_volume = False
        for row in indexes.fetchall():
            index_name = row[1]
            is_unique = bool(row[2])
            if not is_unique:
                continue
            columns = await conn.execute(text(f"PRAGMA index_info('{index_name}')"))
            column_names = [column_row[2] for column_row in columns.fetchall()]
            if column_names == ["volume_gb"]:
                has_unique_volume = True
                break

        if not has_unique_volume:
            return

        await conn.execute(text("ALTER TABLE shop_plans RENAME TO shop_plans_old_unique_volume"))
        await conn.execute(text("""
            CREATE TABLE shop_plans (
                id INTEGER NOT NULL PRIMARY KEY,
                volume_gb INTEGER NOT NULL,
                category_key VARCHAR NOT NULL DEFAULT 'default',
                title VARCHAR NOT NULL,
                price INTEGER,
                emoji VARCHAR,
                premium_emoji_id VARCHAR,
                premium_emoji_position VARCHAR NOT NULL DEFAULT 'left',
                emoji_position VARCHAR NOT NULL DEFAULT 'left',
                style VARCHAR DEFAULT 'success',
                display_order INTEGER NOT NULL DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                updated_at DATETIME
            )
        """))
        await conn.execute(text("""
            INSERT INTO shop_plans (
                id, volume_gb, category_key, title, price, emoji, premium_emoji_id,
                premium_emoji_position, emoji_position, style, display_order, is_active, updated_at
            )
            SELECT
                id,
                volume_gb,
                COALESCE(category_key, 'default'),
                title,
                price,
                emoji,
                premium_emoji_id,
                COALESCE(premium_emoji_position, 'left'),
                COALESCE(emoji_position, 'left'),
                style,
                display_order,
                is_active,
                updated_at
            FROM shop_plans_old_unique_volume
        """))
        await conn.execute(text("DROP TABLE shop_plans_old_unique_volume"))

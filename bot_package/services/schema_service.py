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
                    },
                )
            if "purchases" in tables:
                await SchemaService._add_missing_columns(
                    conn,
                    "purchases",
                    {
                        "original_price": "INTEGER",
                        "discount_amount": "INTEGER DEFAULT 0 NOT NULL",
                        "coupon_id": "INTEGER",
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

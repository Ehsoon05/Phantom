from __future__ import annotations

import html

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import select

from .config_loader import BotConfig
from .database import async_session, engine
from .models import Config
from .services.schema_service import SchemaService


app = FastAPI(title="Phantom Subscription Gateway")


@app.on_event("startup")
async def startup() -> None:
    await SchemaService.ensure_schema(engine)


@app.get("/")
async def index() -> RedirectResponse:
    return RedirectResponse(f"https://t.me/{BotConfig.SUBSCRIPTION_CHANNEL_HANDLE.lstrip('@')}")


@app.get("/sub/{token}")
async def sub_alias(token: str, request: Request) -> Response:
    return await subscription(token, request)


@app.get("/token/{token}")
async def subscription(token: str, request: Request) -> Response:
    config = await _config_for_token(token)
    if not config:
        raise HTTPException(status_code=404, detail="Subscription not found")

    upstream = await _fetch_upstream(config.sub_link, request)
    if _wants_html(request):
        return HTMLResponse(_render_subscription_page(config, upstream))

    return Response(
        content=upstream["body"],
        media_type=upstream["content_type"] or "text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
async def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


async def _config_for_token(token: str) -> Config | None:
    async with async_session() as session:
        result = await session.execute(select(Config).where(Config.public_sub_token == token))
        return result.scalar_one_or_none()


async def _fetch_upstream(url: str, request: Request) -> dict[str, str]:
    headers = {
        "User-Agent": request.headers.get("user-agent", "PhantomSubscriptionGateway/1.0"),
        "Accept": request.headers.get("accept", "*/*"),
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, verify=False) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream subscription is unavailable: {exc}") from exc

    return {
        "body": response.text,
        "content_type": response.headers.get("content-type", "text/plain; charset=utf-8"),
    }


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    user_agent = request.headers.get("user-agent", "").lower()
    if "text/html" not in accept.lower():
        return False
    vpn_clients = ("v2ray", "clash", "sing-box", "hiddify", "streisand", "shadowrocket", "nekobox", "v2rayng")
    return not any(client in user_agent for client in vpn_clients)


def _render_subscription_page(config: Config, upstream: dict[str, str]) -> str:
    primary = BotConfig.SUBSCRIPTION_TEMPLATE_PRIMARY or "#426df8"
    channel = BotConfig.SUBSCRIPTION_CHANNEL_HANDLE or "@PhantomHubs"
    channel_url = f"https://t.me/{channel.lstrip('@')}"
    configs = _subscription_lines(upstream["body"])
    title = f"Phantom {config.volume_gb}GB"
    escaped_title = html.escape(title)
    escaped_channel = html.escape(channel)
    config_count = len(configs)
    preview_rows = "\n".join(
        f"<li><code>{html.escape(line[:120])}{'...' if len(line) > 120 else ''}</code></li>"
        for line in configs[:8]
    )
    if not preview_rows:
        preview_rows = "<li>داده‌ای برای نمایش مرورگری پیدا نشد؛ لینک را داخل اپلیکیشن کلاینت وارد کنید.</li>"

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{ --primary: {primary}; --ink: #172033; --muted: #667085; --bg: #f6f8ff; --card: #ffffff; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Tahoma, Arial, sans-serif; background: var(--bg); color: var(--ink); }}
    .shell {{ max-width: 940px; margin: 0 auto; padding: 28px 16px 44px; }}
    .hero {{ padding: 28px; border-radius: 8px; background: linear-gradient(135deg, var(--primary), #2446b8); color: white; }}
    .hero h1 {{ margin: 0 0 12px; font-size: 28px; letter-spacing: 0; }}
    .hero p {{ margin: 0; line-height: 1.9; opacity: .94; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }}
    .btn {{ display: inline-flex; align-items: center; justify-content: center; min-height: 42px; padding: 0 16px; border-radius: 8px; text-decoration: none; font-weight: 700; }}
    .btn.primary {{ background: white; color: var(--primary); }}
    .btn.ghost {{ color: white; border: 1px solid rgba(255,255,255,.45); }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }}
    .card {{ background: var(--card); border: 1px solid #e5e9f5; border-radius: 8px; padding: 16px; box-shadow: 0 10px 28px rgba(23,32,51,.06); }}
    .metric {{ font-size: 24px; font-weight: 800; color: var(--primary); margin-bottom: 6px; }}
    .label {{ color: var(--muted); font-size: 13px; }}
    .section h2 {{ font-size: 18px; margin: 0 0 12px; }}
    ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }}
    li {{ background: #f8faff; border: 1px solid #edf1ff; border-radius: 8px; padding: 10px; overflow-wrap: anywhere; direction: ltr; text-align: left; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; color: #28344f; }}
    @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} .hero h1 {{ font-size: 23px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>{escaped_title}</h1>
      <p>اشتراک شما آماده است. برای دریافت کانفیگ‌ها، همین لینک را داخل اپلیکیشن کلاینت خود وارد کنید.</p>
      <div class="actions">
        <a class="btn primary" href="{html.escape(channel_url)}">عضویت در {escaped_channel}</a>
        <a class="btn ghost" href="javascript:navigator.clipboard.writeText(location.href)">کپی لینک اشتراک</a>
      </div>
    </section>
    <section class="grid">
      <div class="card"><div class="metric">{config.volume_gb}</div><div class="label">حجم سرویس / گیگ</div></div>
      <div class="card"><div class="metric">{config_count}</div><div class="label">تعداد کانفیگ‌های دریافت‌شده</div></div>
      <div class="card"><div class="metric">فعال</div><div class="label">وضعیت لینک اشتراک</div></div>
    </section>
    <section class="card section">
      <h2>پیش‌نمایش کانفیگ‌ها</h2>
      <ul>{preview_rows}</ul>
    </section>
  </main>
</body>
</html>"""


def _subscription_lines(body: str) -> list[str]:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if len(lines) <= 1 and body.strip():
        return [body.strip()]
    return lines

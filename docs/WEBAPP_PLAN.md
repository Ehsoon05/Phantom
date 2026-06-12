# Phantom Web Platform — Architecture & Implementation Plan

> Telegram Mini App (user shop) + Admin Web Panel, connected to the existing Phantom bot database and services.

---

## 1. Big Picture

```
                        ┌─────────────────────────────────────────────┐
                        │                  SERVER                     │
                        │                                             │
 Telegram clients ───►  │  ┌───────────────┐     ┌─────────────────┐  │
 (Mini App webview)     │  │  Next.js      │     │   FastAPI       │  │
                        │  │  Mini App     │────►│   API Layer     │  │
                        │  │  (user shop)  │     │  (new, Python)  │  │
                        │  └───────────────┘     │                 │  │
                        │                        │  reuses         │  │
 Admin browser ──────►  │  ┌───────────────┐     │  bot_package/   │  │
                        │  │  React (Vite) │────►│  services + ORM │  │
                        │  │  Admin SPA    │     └────────┬────────┘  │
                        │  └───────────────┘              │           │
                        │                        ┌────────▼────────┐  │
                        │  ┌───────────────┐     │   SQLite /      │  │
                        │  │  Telegram     │────►│   PostgreSQL    │  │
                        │  │  Bots (PTB)   │     │  (shared DB)    │  │
                        │  └───────────────┘     └─────────────────┘  │
                        └─────────────────────────────────────────────┘
```

**Core decision: a FastAPI backend is the bridge.** The bot is Python + async SQLAlchemy; FastAPI shares the same event loop ecosystem, the same `models.py`, and — critically — the same **service layer** (`InventoryService.sell_config()`, `CouponService`, `ReferralService.evaluate_referred_user()`, `CryptoPaymentService`, etc.). The web apps never touch the DB directly; they call the API, which calls the exact same battle-tested services the bot uses. No duplicated business logic, no purchase-race bugs between bot and webapp.

Repo layout (monorepo, same Git repo):

```
Phantom/
  bot_package/          # existing — untouched except small extractions
  api/                  # NEW — FastAPI app
    main.py
    deps.py             # DB session, auth dependencies
    auth/               # initData validation, admin JWT
    routers/
      user/             # shop, wallet, purchases, referrals, payments
      admin/            # stats, users, inventory, coupons, settings...
    schemas/            # Pydantic response/request models
  webapp/               # NEW — Next.js Telegram Mini App (user-facing)
  admin-panel/          # NEW — React (Vite) + shadcn admin SPA
  deploy/               # systemd units + nginx/Caddy config
```

---

## 2. Authentication Design

### 2.1 Mini App (users)
Telegram Mini Apps send a signed `initData` string in every launch. The flow:

1. Frontend reads `window.Telegram.WebApp.initData`.
2. Sends it to `POST /api/v1/auth/telegram`.
3. Backend validates the HMAC-SHA256 signature against `BOT_TOKEN` (per Telegram spec), checks `auth_date` freshness (< 1h).
4. Backend issues a short-lived **JWT** (e.g. 24h) containing `telegram_id`; runs the same `get_or_create_user()` + referral payload logic as `/start`.
5. Frontend stores the JWT in memory and sends it as `Authorization: Bearer` on every call.

`start_param` from the Mini App deep link carries the referral code — so `t.me/YourBot/shop?startapp=ref_xxx` works exactly like `/start ref_xxx`.

### 2.2 Admin Panel
The current bot uses a single shared password — **upgrade this for the web**:

- Login = Telegram ID must exist in `admin` table (`is_active=True`) **+ password** + optional **TOTP (2FA)** for owners.
- Better UX option: **Telegram Login Widget** on the login page (cryptographically proves the Telegram ID), then password as the second factor.
- Backend issues a JWT with the admin's `permissions` CSV baked into claims; every admin route enforces permissions server-side (`require_permission("inventory")` dependency).
- Refresh tokens in httpOnly cookies, access token 15 min. Rate-limit login attempts.

---

## 3. The API Layer (FastAPI) — Phase 1

### User endpoints (`/api/v1/...`)
| Endpoint | Maps to existing service |
|---|---|
| `POST /auth/telegram` | initData validation + `get_or_create_user` + `ReferralService.apply_start_payload` |
| `GET /me` | user profile, wallet balance, trial status |
| `GET /shop/plans` | `ShopPlan`/`ShopPlanCategory` + `CouponService.prices_with_active_discount()` |
| `GET /shop/stock` | per-plan availability counts |
| `POST /purchases` | `InventoryService.sell_config()` + coupon + referral evaluation (idempotency key required) |
| `GET /purchases` | purchase history + subscription links (`SubscriptionLinkService.public_link_for_config`) |
| `POST /coupons/apply` | `CouponService.get_coupon_by_code()` validation |
| `POST /payments/crypto` | `CryptoPaymentService` — create invoice, return address/memo/QR/expiry |
| `GET /payments/crypto/{id}` | poll invoice status (pending → paid → credited) |
| `POST /payments/rial` | `RialPaymentRequest` creation (amount → phone → card steps collapse into one form) |
| `GET /referrals` | referral link, qualified counts, earned rewards |
| `POST /trial` | `MarzbanTrialService.create_or_get()` |
| `GET /channels/required` | required-channel gating check |
| `GET /settings/shop` | customized messages/branding from `ShopMessage`/`bot_setting` |

### Admin endpoints (`/api/v1/admin/...`)
Grouped by the existing permission keys:

- **reports**: dashboard stats (users total/new, revenue by period, GB sold, wallet liabilities), sales time-series, crypto invoice ledger, rial request queue, referral leaderboard.
- **users**: search, detail (purchases, transactions, referrals), charge wallet, set balance, block/unblock.
- **inventory**: stock by category/volume, bulk add config links, low-stock view.
- **prices / shop**: CRUD for `ShopPlan`, `ShopPlanCategory`, `ShopMessage`, `ShopButton`; crypto rate mode/margin/manual rates; rial settings; trial settings; required channels.
- **coupons**: CRUD + redemption stats.
- **broadcast**: compose + send via `BroadcastService` (runs as background task with progress polling).
- **referral rules**: CRUD + recalculate grants.
- **audit**: every admin mutation logged to a new `admin_audit_log` table (NEW — who did what, when, old/new value). The bot's admin actions can adopt it later too.

### Cross-cutting
- All sessions via the existing `async_sessionmaker` from `bot_package/database.py`.
- **Idempotency keys** on purchase/charge endpoints (header `Idempotency-Key`) to survive webview retries.
- Rate limiting (slowapi) on auth + purchase routes.
- CORS locked to the two frontend origins.
- OpenAPI docs auto-generated → frontends generate typed clients from the schema.

---

## 4. User Mini App — Next.js + shadcn (Phase 2)

**Stack:** Next.js 16 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query, `@telegram-apps/sdk-react`, `next-intl` (fa default, RTL).

### Non-negotiables given this project
- **RTL + Persian first.** The entire bot is Farsi. Root layout `dir="rtl"`, `Vazirmatn` font, Persian numeral formatting helpers (the bot already parses Persian numerals — mirror that).
- **Mobile-first.** Design at 360–430 px; the Mini App webview *is* a phone. Bottom tab bar navigation, large touch targets, safe-area insets.
- **Telegram-native feel.** Map Telegram's `themeParams` (bg, text, hint, button colors) onto shadcn CSS variables → the app automatically matches the user's Telegram theme, light *and* dark. Use `MainButton`/`BackButton` from the Telegram SDK for checkout confirmation, and `HapticFeedback` on purchase success.

### Screens
1. **Home** — wallet balance card, quick actions (Buy / Top-up / Trial), active subscriptions summary, required-channel gate (blocking sheet if not joined).
2. **Shop** — category tabs → plan cards (emoji, title, GB, price, struck-through original price when coupon active, stock badge). Tap → bottom-sheet checkout: coupon field, final price, pay with wallet. Insufficient balance → inline top-up CTA.
3. **Wallet & Top-up** —
   - *Crypto:* coin picker (TON ⭐ recommended, USDT-TRC20, USDT-TON, USDC-BEP20) → amount in toman → live converted amount → invoice screen with QR, tap-to-copy address + memo, countdown to expiry, and **live status polling** (pending → detected → confirmed → credited) with a celebratory state on credit.
   - *Rial:* one form (amount, phone via Telegram `requestContact`, card number with Luhn validation) → tracking code + copyable support message.
   - Transaction history list.
4. **My Services** — purchased configs with tap-to-copy subscription link, QR, "add to v2ray app" deep links, purchase date/volume. Trial claim button if eligible.
5. **Referrals** — shareable Mini App deep link (`?startapp=ref_x`) with Telegram native share, progress bars toward each active reward rule ("3/5 invited friends purchased"), earned rewards list.
6. **Profile/Help** — rules, support link, customized shop messages from the admin.

### My added ideas (user side)
- **Stock-aware UI**: grey out / "sold out" badge on plans with zero inventory instead of failing at purchase time.
- **Invoice resume**: if a user closes the webview mid-crypto-payment, Home shows a "pending payment" banner that reopens the invoice.
- **Skeleton loaders + optimistic wallet updates** for the in-Telegram instant feel.
- Keep the bot fully functional in parallel — the Mini App is opened via a persistent **menu button** (`setChatMenuButton`) and inline "🛍 Open Shop" buttons; both channels share the same DB so state is always consistent.

---

## 5. Admin Panel — React (Vite) + shadcn (Phase 3)

**Stack:** Vite + React 19 + TypeScript, shadcn/ui, Tailwind, TanStack Query + Router, Recharts, TanStack Table, react-hook-form + zod. Served as static files by nginx/Caddy on the server (e.g. `admin.yourdomain.com`), talking to the same FastAPI. Desktop-first but responsive (the sidebar collapses; you can approve a rial payment from your phone).

### Pages
1. **Dashboard** — KPI cards (revenue today/week/month, new users, active wallet liability total, GB sold), revenue & signups time-series charts, payment-method split donut, low-stock alerts, live feed of recent purchases/top-ups.
2. **Users** — searchable/sortable table (ID, username, balance, purchases, referred-by, blocked). Detail drawer: full transaction + purchase history, referral tree, actions (charge wallet, set balance, block) — each behind a confirm dialog and written to the audit log.
3. **Inventory** — stock matrix (category × volume, color-coded by level), bulk paste-import of config links with per-line validation preview before commit, sold-config browser.
4. **Plans & Pricing** — drag-to-reorder plan list, inline price editing, category management, emoji/style pickers matching the bot's options.
5. **Payments** —
   - *Rial queue:* pending requests with one-click **Approve (charges wallet) / Reject**, tracking-code search. This replaces the clunkiest bot-admin flow.
   - *Crypto ledger:* all invoices filterable by status/coin, tx-hash links to block explorers, underpaid-invoice resolution (manual credit with note).
6. **Coupons** — CRUD, target-user picker, redemption stats per coupon.
7. **Referral Rules** — rule builder form (qualification type, count, repeatable, reward), grants ledger, recalculate button.
8. **Broadcast** — compose with live Telegram-style preview (parse mode), optional audience filter (all / purchasers / balance > X — *new capability*), send with real-time progress bar (sent/blocked/failed) via polling.
9. **Settings** — crypto rate mode/margin/manual rates, rial minimum & phone toggle, trial enable/volume/duration, required channels CRUD, shop message/button customization with preview.
10. **Audit Log** — filterable history of all admin actions.

Permission-aware UI: nav items and actions hide/disable based on the JWT's permission claims (server still enforces).

### My added ideas (admin side)
- **DB explorer (owner-only, read-only)**: a guarded page to run read-only SQL (enforced via `EXPLAIN`-check + statement whitelist) and browse any table — satisfies "essentially access the db" without handing out write access; destructive ops stay behind purpose-built, audited endpoints.
- **Telegram alerts bridge**: API pings the admin bot when a rial request arrives or stock drops below threshold — web and bot stay complementary.
- **CSV export** on every table (users, purchases, invoices) for accounting.

---

## 6. Step-by-Step Implementation Roadmap

### Phase 0 — Foundations (½ week)
1. Add `api/` package; wire FastAPI + uvicorn to `bot_package.database` sessionmaker and `config_loader`.
2. Decide hosting domains: `app.yourdomain.com` (mini app), `admin.yourdomain.com` (panel), `api.yourdomain.com` (or `/api` path on one domain). HTTPS is **mandatory** for Mini Apps.
3. **Recommended now:** migrate prod DB to PostgreSQL (the code is already written for it) — two processes (bot + API) writing to one SQLite file works but Postgres removes the lock-contention risk. Add Alembic for migrations going forward (needed for `admin_audit_log` and future schema changes).

### Phase 1 — API (1.5–2 weeks)
4. initData validation + user JWT auth.
5. User endpoints: shop, purchase (with idempotency), wallet, crypto invoice create/status, rial request, referrals, trial, channels.
6. Admin auth (Telegram Login Widget + password, JWT with permission claims).
7. Admin endpoints: stats/reports first, then users, inventory, payments queue, coupons, settings, broadcast.
8. `admin_audit_log` table + middleware.
9. Tests: reuse the existing pytest setup; the service layer is already tested, so focus on auth, permission enforcement, and idempotency.

### Phase 2 — User Mini App (2 weeks)
10. Scaffold Next.js 16 + Tailwind + shadcn + RTL/Persian setup + Telegram SDK; theme-param → CSS variable bridge.
11. Auth bootstrap + required-channel gate.
12. Shop → checkout → purchase flow (the revenue path — build and test first).
13. Wallet: crypto invoice flow with live status polling; rial form.
14. My Services, Referrals, Profile.
15. Register the Mini App with BotFather (`/newapp`), set menu button, add inline "Open Shop" buttons in the bot.
16. Test inside real Telegram (iOS + Android webviews differ) via a tunneled HTTPS dev URL.

### Phase 3 — Admin Panel (2 weeks)
17. Scaffold Vite + React + shadcn, login, permission-aware shell (sidebar/topbar).
18. Dashboard with charts.
19. Users + Payments queue (highest admin value — ship these first).
20. Inventory, Plans/Pricing, Coupons, Referral rules.
21. Broadcast, Settings, Audit log, read-only DB explorer.

### Phase 4 — Deployment & Hardening (½–1 week)
22. systemd unit for the API (`phantom-api.service`, uvicorn workers) alongside the existing bot service; Next.js as `phantom-webapp.service` (or static-export it if no SSR needed); admin panel as static files.
23. nginx/Caddy reverse proxy + TLS; CORS/CSP headers; rate limits.
24. Extend the existing auto-update script to rebuild frontends on deploy.
25. Load-test the purchase endpoint for race conditions (two buyers, one config); backup cron for the DB.

**Total: roughly 6–7 weeks of focused work, with usable milestones at the end of every phase.**

---

## 7. Key Risks & Decisions to Confirm

| Decision | Recommendation |
|---|---|
| SQLite vs Postgres with two writer processes | Move to **Postgres** at Phase 0; SQLite WAL works short-term but is the main scaling risk |
| Where business logic lives | **Only in `bot_package/services`** — API is a thin layer; never reimplement purchase/credit logic in TS |
| Admin web auth | Telegram Login Widget + password (+ TOTP for owners); do **not** reuse the bot's in-memory shared-password session |
| Mini App vs bot coexistence | Both stay live; shared DB keeps them consistent; bot becomes the notification channel |
| Live payment status | Simple 3–5s polling first; upgrade to SSE/WebSocket only if needed |
| Next.js SSR vs static | Start with SSR off (static export) — the app is fully client-side behind auth; simplifies hosting |

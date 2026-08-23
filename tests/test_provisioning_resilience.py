from __future__ import annotations

import unittest

import httpx

from bot_package.config_loader import BotConfig
from bot_package.models import ProvisionPanel
from bot_package.services.provisioning_service import (
    ProvisioningError,
    ProvisioningService,
    _panel_api_base_url,
    _panel_api_base_urls,
    _panel_http_headers,
    _subscription_url,
)


class _StaticClient:
    def __init__(self, response: httpx.Response):
        self.response = response

    async def post(self, *_args, **_kwargs) -> httpx.Response:
        return self.response


def _panel() -> ProvisionPanel:
    return ProvisionPanel(
        key="svn",
        title="SVN",
        panel_type="marzban",
        base_url="https://public-panel.example",
        username="admin",
        password="secret",
        is_enabled=True,
    )


class ProvisioningResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_cloudflare_challenge_becomes_provisioning_error(self) -> None:
        request = httpx.Request("POST", "https://public-panel.example/api/admin/token")
        response = httpx.Response(
            403,
            request=request,
            headers={"cf-mitigated": "challenge", "content-type": "text/html"},
            text="<title>Just a moment...</title>",
        )

        with self.assertRaisesRegex(ProvisioningError, "Cloudflare"):
            await ProvisioningService._token(_StaticClient(response), _panel())

    async def test_invalid_credentials_become_provisioning_error(self) -> None:
        request = httpx.Request("POST", "https://public-panel.example/api/admin/token")
        response = httpx.Response(401, request=request, json={"detail": "Incorrect credentials"})

        with self.assertRaisesRegex(ProvisioningError, "رمز پنل"):
            await ProvisioningService._token(_StaticClient(response), _panel())

    def test_svn_public_panel_is_preferred_over_management_fallback(self) -> None:
        previous = BotConfig.SVN_PANEL_API_URL
        try:
            BotConfig.SVN_PANEL_API_URL = "https://direct-api.example/"
            self.assertEqual(_panel_api_base_url(_panel()), "https://public-panel.example")
        finally:
            BotConfig.SVN_PANEL_API_URL = previous

    def test_svn_private_management_url_is_fallback(self) -> None:
        previous = BotConfig.SVN_PANEL_API_URL
        try:
            BotConfig.SVN_PANEL_API_URL = "http://127.0.0.1:18443/"
            self.assertEqual(
                _panel_api_base_urls(_panel()),
                ["https://public-panel.example", "http://127.0.0.1:18443"],
            )
        finally:
            BotConfig.SVN_PANEL_API_URL = previous

    def test_svn_direct_requests_use_cloudflare_compatible_user_agent(self) -> None:
        headers = _panel_http_headers(_panel())
        self.assertIn("Mozilla/5.0", headers["User-Agent"])
        self.assertIn("application/json", headers["Accept"])

    def test_subscription_url_always_uses_public_panel_base(self) -> None:
        self.assertEqual(
            _subscription_url(
                "https://youpanel.example.com:2053",
                {
                    "subscription_url": (
                        "http://127.0.0.1:18443/sub/example?client=sing-box"
                    )
                },
            ),
            "https://youpanel.example.com:2053/sub/example?client=sing-box",
        )

    def test_subscription_url_rewrites_legacy_mexico_hosts(self) -> None:
        self.assertEqual(
            _subscription_url(
                "https://my.mexicosenter.ir:8000",
                {
                    "subscription_url": (
                        "https://my.litegames.ir:8000/sub/djMsNjQ5MjgsMTc4NzQ5NjQ2Ng.example"
                    )
                },
            ),
            "https://my.mexicosenter.ir:8000/sub/djMsNjQ5MjgsMTc4NzQ5NjQ2Ng.example",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import httpx

from bot_package.config_loader import BotConfig
from bot_package.models import ProvisionPanel
from bot_package.services.provisioning_service import (
    ProvisioningError,
    ProvisioningService,
    _panel_api_base_url,
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

    def test_svn_can_use_separate_management_api_url(self) -> None:
        previous = BotConfig.SVN_PANEL_API_URL
        try:
            BotConfig.SVN_PANEL_API_URL = "https://direct-api.example/"
            self.assertEqual(_panel_api_base_url(_panel()), "https://direct-api.example")
        finally:
            BotConfig.SVN_PANEL_API_URL = previous


if __name__ == "__main__":
    unittest.main()

from types import SimpleNamespace

from tests import _api_test_env  # noqa: F401

from bot_package.handlers.admin_handlers import _admin_user_preview


def test_admin_user_preview_escapes_markdown_user_fields():
    user = SimpleNamespace(
        telegram_id=123,
        first_name="Test_Name",
        username="user_name",
        wallet_balance=1000,
        is_blocked=False,
    )

    preview = _admin_user_preview(user)

    assert "Test\\_Name" in preview
    assert "@user\\_name" in preview

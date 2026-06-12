"""Shared test environment for API tests.

Must be imported BEFORE ``api.main`` / ``bot_package.database``: the engine is
created at import time from DB_URL. A file-backed SQLite DB is used instead of
``:memory:`` because each pooled aiosqlite connection to ``:memory:`` gets its
own private database, which breaks any test exercising concurrent requests.
"""

import os
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / ".pytest-api.db"

os.environ["_PHANTOM_DOTENV_LOADED"] = "1"
os.environ.setdefault("API_JWT_SECRET", "test-secret-test-secret-test-secret-1234")
os.environ.setdefault("MAIN_BOT_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("DB_URL", f"sqlite+aiosqlite:///{_DB_PATH.as_posix()}")

# Start every pytest process from a clean slate. Safe: the engine has not
# connected yet at import time.
if "_PHANTOM_API_TEST_DB_CLEANED" not in os.environ:
    os.environ["_PHANTOM_API_TEST_DB_CLEANED"] = "1"
    _DB_PATH.unlink(missing_ok=True)

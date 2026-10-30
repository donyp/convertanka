"""Test database setup: must be imported before server modules.

Forces a local in-memory SQLite so tests never touch the production database.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# File-based SQLite: database.py's create_engine uses QueuePool args
# (pool_size/max_overflow) which are rejected by the in-memory SingletonThreadPool.
_APP_DB = os.path.join(tempfile.gettempdir(), "mutasiconvert_test_app_engine.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_APP_DB}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ.pop("SMTP_HOST", None)
os.environ.pop("SMTP_USER", None)
os.environ.pop("SMTP_PASS", None)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

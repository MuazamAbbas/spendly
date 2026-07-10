import os
import tempfile

# Point the app at an isolated temp DB *before* app.py is imported anywhere in
# this process, because app.py runs init_db()/seed_db() at module import time.
_fd, _TEST_DB_PATH = tempfile.mkstemp(prefix="spendly_test_", suffix=".db")
os.close(_fd)
os.environ["SPENDLY_DB_PATH"] = _TEST_DB_PATH

import pytest  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import app as _flask_app  # noqa: E402
from database.db import get_db  # noqa: E402


@pytest.fixture
def app():
    _flask_app.config.update(TESTING=True)
    yield _flask_app


@pytest.fixture
def seed_user_id():
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    conn.close()
    return row["id"]


@pytest.fixture
def login(client):
    def _login(user_id):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
        return client
    return _login


@pytest.fixture
def fresh_user():
    conn = get_db()
    email = f"fresh-{os.urandom(4).hex()}@spendly.com"
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Fresh User", email, generate_password_hash("password123")),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id, email

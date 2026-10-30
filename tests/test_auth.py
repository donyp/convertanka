import asyncio
import calendar
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from server.auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, get_admin_user, SECRET_KEY, ALGORITHM,
)
from tests.db import TestSessionLocal
from tests.helpers import make_user


def test_password_hash_and_verify():
    h = get_password_hash("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrongpass", h)


def test_password_hashes_are_salted():
    assert get_password_hash("secret123") != get_password_hash("secret123")


def test_access_token_roundtrip():
    from jose import jwt
    token = create_access_token({"sub": "a@gmail.com"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "a@gmail.com"
    assert "exp" in payload
    now_epoch = calendar.timegm(datetime.utcnow().utctimetuple())
    assert payload["exp"] > now_epoch


def test_access_token_custom_expiry():
    from jose import jwt
    token = create_access_token({"sub": "x"}, expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    expected = calendar.timegm((datetime.utcnow() + timedelta(minutes=5)).utctimetuple())
    assert abs(payload["exp"] - expected) < 5


def test_get_current_user_invalid_token():
    with pytest.raises(HTTPException) as ei:
        asyncio.run(get_current_user(token="not-a-jwt", db=None))
    assert ei.value.status_code == 401


def test_get_current_user_unknown_email():
    token = create_access_token({"sub": "ghost@gmail.com"})
    db = TestSessionLocal()
    with pytest.raises(HTTPException) as ei:
        asyncio.run(get_current_user(token=token, db=db))
    db.close()
    assert ei.value.status_code == 401


def test_get_current_user_success():
    u = make_user()
    token = create_access_token({"sub": u.email})
    db = TestSessionLocal()
    result = asyncio.run(get_current_user(token=token, db=db))
    db.close()
    assert result.email == u.email


def test_get_admin_user_denied_for_regular_user():
    u = make_user()
    with pytest.raises(HTTPException) as ei:
        asyncio.run(get_admin_user(current_user=u))
    assert ei.value.status_code == 403


def test_get_admin_user_allows_admin():
    a = make_user(is_admin=True)
    result = asyncio.run(get_admin_user(current_user=a))
    assert result.is_admin is True

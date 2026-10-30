"""Security regression tests for Critical/High audit findings (C1-C3, H1-H5)."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

import server.main as main
from server.models import CoinPurchase, ConversionRecord
from server.rate_limit import enforce_rate_limit, get_client_ip
from tests.conftest import auth_headers_for
from tests.db import TestSessionLocal
from tests.helpers import (build_pdf, db_query, get_user, make_package,
                           make_purchase, make_user)

ROOT = Path(__file__).resolve().parent.parent


def pdf_file(name="mutasi.pdf", num_pages=1):
    return {"file": (name, build_pdf(num_pages), "application/pdf")}


def get_purchase(purchase_id):
    db = TestSessionLocal()
    p = db.query(CoinPurchase).filter(CoinPurchase.id == purchase_id).first()
    db.close()
    return p


# --- C2: XSS payloads rejected at registration ---------------------------------

@pytest.mark.parametrize("bad_email", [
    '"><script>alert(1)</script>@gmail.com',
    "<img src=x onerror=alert(1)>@gmail.com",
    "a<b>c@gmail.com",
])
def test_register_rejects_xss_email(client, bad_email):
    r = client.post("/api/auth/register", data={
        "email": bad_email, "password": "password123",
    })
    assert r.status_code == 400
    assert "Format email" in r.json()["detail"]


# --- H4: inactive accounts blocked ---------------------------------------------

def test_inactive_user_token_rejected(client):
    u = make_user(is_active=False)
    r = client.get("/api/auth/me", headers=auth_headers_for(u))
    assert r.status_code == 403
    assert "dinonaktifkan" in r.json()["detail"]


def test_inactive_user_cannot_login(client):
    u = make_user(is_active=False)
    r = client.post("/api/auth/login",
                    data={"username": u.email, "password": "password123"})
    assert r.status_code == 403
    assert "dinonaktifkan" in r.json()["detail"]


# --- H1: coins credited exactly once -------------------------------------------

def test_no_double_credit_berhasil_ditolak_berhasil(client, admin, admin_headers):
    pkg = make_package(coin_amount=100)
    u = make_user(coins=10)
    p = make_purchase(u.id, pkg)

    for status in ("berhasil", "ditolak", "berhasil"):
        r = client.put(f"/api/admin/purchases/{p.id}/status",
                       data={"new_status": status}, headers=admin_headers)
        assert r.status_code == 200

    assert get_user(u.email).coins == 110  # credited exactly once


def test_credited_purchase_is_flagged(client, admin, admin_headers):
    pkg = make_package(coin_amount=100)
    u = make_user(coins=10)
    p = make_purchase(u.id, pkg)

    client.put(f"/api/admin/purchases/{p.id}/status",
               data={"new_status": "berhasil"}, headers=admin_headers)
    assert get_purchase(p.id).coins_credited is True


# --- H2: failed conversion never costs the user --------------------------------

def test_failed_convert_unknown_bank_no_deduction(client, user, user_headers):
    r = client.post("/api/convert", files=pdf_file(),
                    data={"bank": "mandiri"}, headers=user_headers)
    assert r.status_code == 400
    assert get_user(user.email).coins == 50
    assert db_query(ConversionRecord, user_id=user.id) == []


def test_failed_convert_empty_data_no_deduction(client, user, user_headers, monkeypatch):
    monkeypatch.setattr(main, "parse_bca", lambda path: ([], {"bank": "BCA"}))
    r = client.post("/api/convert", files=pdf_file(),
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 400
    assert get_user(user.email).coins == 50
    assert db_query(ConversionRecord, user_id=user.id) == []


def test_failed_convert_parse_error_no_deduction(client, user, user_headers, monkeypatch):
    def boom(path):
        raise ValueError("parse error")

    monkeypatch.setattr(main, "parse_bca", boom)
    r = client.post("/api/convert", files=pdf_file(),
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 500
    assert get_user(user.email).coins == 50
    assert db_query(ConversionRecord, user_id=user.id) == []


# --- H3: DB-backed rate limiting -----------------------------------------------

def test_register_rate_limited_after_5(client):
    for i in range(5):
        r = client.post("/api/auth/register", data={
            "email": f"user{i}@gmail.com", "password": "password123",
        })
        assert r.status_code == 200

    r = client.post("/api/auth/register", data={
        "email": "overflow@gmail.com", "password": "password123",
    })
    assert r.status_code == 429


def test_login_rate_limited_by_email(client):
    u = make_user()
    for _ in range(5):
        r = client.post("/api/auth/login",
                        data={"username": u.email, "password": "wrong"})
        assert r.status_code == 401

    r = client.post("/api/auth/login",
                    data={"username": u.email, "password": "wrong"})
    assert r.status_code == 429


def test_forgot_password_rate_limited(client):
    for _ in range(3):
        r = client.post("/api/auth/forgot-password",
                        data={"email": "ghost@gmail.com"})
        assert r.status_code == 200

    r = client.post("/api/auth/forgot-password",
                    data={"email": "ghost@gmail.com"})
    assert r.status_code == 429


def test_enforce_rate_limit_blocks_after_limit():
    db = TestSessionLocal()
    try:
        for _ in range(2):
            enforce_rate_limit(db, "unit_key", 2, 60)
        with pytest.raises(HTTPException) as exc:
            enforce_rate_limit(db, "unit_key", 2, 60)
        assert exc.value.status_code == 429
    finally:
        db.close()


def test_client_ip_prefers_leftmost_xff():
    class FakeClient:
        host = "9.9.9.9"

    class FakeReq:
        def __init__(self, headers):
            self.headers = headers
            self.client = FakeClient()

    assert get_client_ip(FakeReq({"x-forwarded-for": "1.2.3.4, 10.0.0.1"})) == "1.2.3.4"
    assert get_client_ip(FakeReq({})) == "9.9.9.9"


# --- C3: SECRET_KEY fail-hard in production ------------------------------------

def _clean_env():
    env = {k: v for k, v in os.environ.items()
           if k not in ("SECRET_KEY", "ENV", "VERCEL")}
    db_file = Path(tempfile.gettempdir()) / "mutasiconvert_subproc.db"
    env["DATABASE_URL"] = f"sqlite:///{db_file}"
    return env


def _import_auth(env):
    return subprocess.run(
        [sys.executable, "-c", "import server.auth"],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )


def test_secret_key_required_in_production():
    env = _clean_env()
    env["ENV"] = "production"
    r = _import_auth(env)
    assert r.returncode != 0
    assert "SECRET_KEY" in (r.stdout + r.stderr)


def test_secret_key_required_on_vercel():
    env = _clean_env()
    env["VERCEL"] = "1"
    r = _import_auth(env)
    assert r.returncode != 0
    assert "SECRET_KEY" in (r.stdout + r.stderr)


def test_secret_key_dev_fallback_ok():
    r = _import_auth(_clean_env())
    assert r.returncode == 0

from datetime import datetime, timedelta

from server.models import User
from tests.db import TestSessionLocal
from tests.helpers import make_user, get_user
from tests.conftest import auth_headers_for


# --- Register ------------------------------------------------------------------

def test_register_success(client):
    r = client.post("/api/auth/register", data={
        "email": "new@gmail.com", "password": "secret123",
        "device_fingerprint": "fp-abc",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["unique_code"].startswith("MC-")
    u = get_user("new@gmail.com")
    assert u.coins == 2
    assert u.email_verified is False
    assert u.ip_address == "testclient"
    assert u.device_fingerprint == "fp-abc"


def test_register_rejects_non_gmail(client):
    r = client.post("/api/auth/register", data={
        "email": "x@yahoo.com", "password": "secret123",
    })
    assert r.status_code == 400
    assert "gmail.com" in r.json()["detail"]


def test_register_rejects_duplicate_email(client):
    make_user(email="dup@gmail.com")
    r = client.post("/api/auth/register", data={
        "email": "dup@gmail.com", "password": "secret123",
    })
    assert r.status_code == 400
    assert "sudah terdaftar" in r.json()["detail"]


# --- Login ---------------------------------------------------------------------

def test_login_success(client):
    make_user(email="login@gmail.com", password="secret123")
    r = client.post("/api/auth/login", data={
        "username": "login@gmail.com", "password": "secret123",
    })
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.json()["token_type"] == "bearer"


def test_login_wrong_password(client):
    make_user(email="login@gmail.com", password="secret123")
    r = client.post("/api/auth/login", data={
        "username": "login@gmail.com", "password": "wrong",
    })
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", data={
        "username": "ghost@gmail.com", "password": "x",
    })
    assert r.status_code == 401


def test_login_inactive_account(client):
    make_user(email="off@gmail.com", is_active=False)
    r = client.post("/api/auth/login", data={
        "username": "off@gmail.com", "password": "password123",
    })
    assert r.status_code == 403
    assert "dinonaktifkan" in r.json()["detail"]


# --- Me ------------------------------------------------------------------------

def test_me_returns_user_info(client, user, user_headers):
    r = client.get("/api/auth/me", headers=user_headers)
    assert r.status_code == 200
    b = r.json()
    assert b["email"] == user.email
    assert b["coins"] == 50
    assert b["is_admin"] is False
    assert b["is_active"] is True
    assert b["email_verified"] is True
    assert b["low_balance_warning"] is False


def test_me_low_balance_warning(client):
    u = make_user(coins=2)
    r = client.get("/api/auth/me", headers=auth_headers_for(u))
    assert r.json()["low_balance_warning"] is True


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer bogus"})
    assert r.status_code == 401


# --- Email verification --------------------------------------------------------

def test_email_verification_flow(client):
    u = make_user(email="verify@gmail.com", email_verified=False, coins=5)
    h = auth_headers_for(u)

    r = client.post("/api/auth/request-verification", headers=h)
    assert r.status_code == 200

    otp = get_user("verify@gmail.com").verification_otp
    assert otp and len(otp) == 6

    # wrong OTP
    r = client.post("/api/auth/verify-email", data={"otp": "000000"}, headers=h)
    assert r.status_code == 400

    # correct OTP
    r = client.post("/api/auth/verify-email", data={"otp": otp}, headers=h)
    assert r.status_code == 200
    fresh = get_user("verify@gmail.com")
    assert fresh.email_verified is True
    assert fresh.coins == 15
    assert fresh.verification_otp is None


def test_request_verification_already_verified(client, user, user_headers):
    r = client.post("/api/auth/request-verification", headers=user_headers)
    assert r.status_code == 400


def test_verify_email_expired_otp(client):
    u = make_user(email="exp@gmail.com", email_verified=False)
    db = TestSessionLocal()
    fu = db.query(User).filter(User.email == u.email).first()
    fu.verification_otp = "123456"
    fu.verification_otp_expiry = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    db.close()

    r = client.post("/api/auth/verify-email", data={"otp": "123456"},
                    headers=auth_headers_for(u))
    assert r.status_code == 400
    assert "kedaluwarsa" in r.json()["detail"]


# --- Forgot / reset password ---------------------------------------------------

def test_forgot_password_flow(client):
    u = make_user(email="reset@gmail.com", password="oldpass123")

    r = client.post("/api/auth/forgot-password", data={"email": u.email})
    assert r.status_code == 200

    otp = get_user(u.email).reset_otp
    assert otp and len(otp) == 6

    r = client.post("/api/auth/verify-otp", data={"email": u.email, "otp": otp})
    assert r.status_code == 200

    r = client.post("/api/auth/reset-password", data={
        "email": u.email, "otp": otp, "new_password": "newpass456",
    })
    assert r.status_code == 200

    r = client.post("/api/auth/login", data={
        "username": u.email, "password": "newpass456",
    })
    assert r.status_code == 200

    fresh = get_user(u.email)
    assert fresh.reset_otp is None
    assert fresh.reset_otp_expiry is None


def test_forgot_password_unknown_email_no_enumeration(client):
    r = client.post("/api/auth/forgot-password", data={"email": "ghost@gmail.com"})
    assert r.status_code == 200
    assert "Jika email terdaftar" in r.json()["message"]


def test_verify_otp_wrong_code(client):
    u = make_user()
    db = TestSessionLocal()
    fu = db.query(User).filter(User.email == u.email).first()
    fu.reset_otp = "111111"
    fu.reset_otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    db.close()

    r = client.post("/api/auth/verify-otp", data={"email": u.email, "otp": "999999"})
    assert r.status_code == 400


def test_reset_password_expired_otp(client):
    u = make_user()
    db = TestSessionLocal()
    fu = db.query(User).filter(User.email == u.email).first()
    fu.reset_otp = "111111"
    fu.reset_otp_expiry = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    db.close()

    r = client.post("/api/auth/reset-password", data={
        "email": u.email, "otp": "111111", "new_password": "whatever123",
    })
    assert r.status_code == 400


# --- Profile update ------------------------------------------------------------

def test_update_profile_full_name(client, user, user_headers):
    r = client.post("/api/user/update-profile", data={"full_name": "Budi"},
                    headers=user_headers)
    assert r.status_code == 200
    assert get_user(user.email).full_name == "Budi"


def test_update_password_requires_current(client, user, user_headers):
    r = client.post("/api/user/update-profile", data={"new_password": "x"},
                    headers=user_headers)
    assert r.status_code == 400
    assert "Password lama diperlukan" in r.json()["detail"]


def test_update_password_wrong_current(client, user, user_headers):
    r = client.post("/api/user/update-profile", data={
        "current_password": "salah", "new_password": "newpass789",
    }, headers=user_headers)
    assert r.status_code == 400
    assert "Password lama salah" in r.json()["detail"]


def test_update_password_success(client):
    u = make_user(password="oldpass123")
    r = client.post("/api/user/update-profile", data={
        "current_password": "oldpass123", "new_password": "newpass789",
    }, headers=auth_headers_for(u))
    assert r.status_code == 200

    r = client.post("/api/auth/login", data={
        "username": u.email, "password": "newpass789",
    })
    assert r.status_code == 200


def test_update_profile_requires_auth(client):
    r = client.post("/api/user/update-profile", data={"full_name": "X"})
    assert r.status_code == 401

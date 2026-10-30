from server.models import ConversionRecord
from tests.db import TestSessionLocal
from tests.helpers import make_user
from tests.conftest import auth_headers_for


# --- Balance -------------------------------------------------------------------

def test_balance(client, user, user_headers):
    r = client.get("/api/balance", headers=user_headers)
    assert r.status_code == 200
    assert r.json() == {"balance": 50}


def test_balance_requires_auth(client):
    assert client.get("/api/balance").status_code == 401


# --- History -------------------------------------------------------------------

def test_history_returns_own_records_only(client):
    u1 = make_user(email="u1@gmail.com")
    u2 = make_user(email="u2@gmail.com")
    db = TestSessionLocal()
    db.add(ConversionRecord(user_id=u1.id, bank="bca", filename="a.pdf",
                            page_count=2, coin_cost=1))
    db.add(ConversionRecord(user_id=u2.id, bank="bsi", filename="b.pdf",
                            page_count=4, coin_cost=2))
    db.commit()
    db.close()

    r = client.get("/api/user/history", headers=auth_headers_for(u1))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["bank"] == "BCA"
    assert rows[0]["filename"] == "a.pdf"
    assert rows[0]["page_count"] == 2
    assert rows[0]["coin_cost"] == 1
    assert rows[0]["created_at"].endswith("Z")


def test_history_empty(client, user, user_headers):
    r = client.get("/api/user/history", headers=user_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_history_requires_auth(client):
    assert client.get("/api/user/history").status_code == 401


# --- Root pages ----------------------------------------------------------------

def test_landing_page(client):
    assert client.get("/").status_code == 200


def test_app_page(client):
    assert client.get("/app").status_code == 200


def test_admin_page(client):
    assert client.get("/admin").status_code == 200


def test_buy_coin_page(client):
    assert client.get("/buy-coin").status_code == 200

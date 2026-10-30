from datetime import datetime, timedelta

from server.models import BroadcastNotification, ConversionRecord, User
from tests.db import TestSessionLocal
from tests.helpers import make_user, get_user, make_package
from tests.conftest import auth_headers_for


# --- Access control ------------------------------------------------------------

def test_admin_endpoint_requires_auth(client):
    assert client.get("/api/admin/users").status_code == 401


def test_admin_endpoint_forbidden_for_regular_user(client, user_headers):
    assert client.get("/api/admin/users", headers=user_headers).status_code == 403


# --- Admin management ----------------------------------------------------------

def test_create_admin(client, admin, admin_headers):
    r = client.post("/api/admin/create-admin", data={
        "email": "newadmin@gmail.com", "password": "pw12345",
        "full_name": "Admin Baru",
    }, headers=admin_headers)
    assert r.status_code == 200
    nu = get_user("newadmin@gmail.com")
    assert nu.is_admin is True
    assert nu.coins == 1000
    assert nu.full_name == "Admin Baru"


def test_create_admin_duplicate_email(client, admin, admin_headers):
    make_user(email="exists@gmail.com")
    r = client.post("/api/admin/create-admin", data={
        "email": "exists@gmail.com", "password": "pw12345",
    }, headers=admin_headers)
    assert r.status_code == 400


def test_list_users(client, admin, admin_headers):
    make_user(email="satu@gmail.com", coins=10)
    make_user(email="dua@gmail.com", coins=20)
    r = client.get("/api/admin/users", headers=admin_headers)
    assert r.status_code == 200
    users = r.json()
    emails = {u["email"] for u in users}
    assert {"satu@gmail.com", "dua@gmail.com", admin.email} <= emails
    for u in users:
        assert "unique_code" in u and "is_active" in u


# --- Add coins -----------------------------------------------------------------

def test_add_coins(client, admin, admin_headers):
    u = make_user(coins=10)
    r = client.post("/api/admin/add-coins", data={
        "unique_code": u.unique_code, "amount": 25,
    }, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["new_balance"] == 35
    assert get_user(u.email).coins == 35


def test_add_coins_unknown_code(client, admin, admin_headers):
    r = client.post("/api/admin/add-coins", data={
        "unique_code": "MC-NOTFOUND", "amount": 10,
    }, headers=admin_headers)
    assert r.status_code == 404


# --- Stats ---------------------------------------------------------------------

def test_stats(client, admin, admin_headers):
    make_user(email="aktif@gmail.com", coins=10)
    make_user(email="nonaktif@gmail.com", coins=20, is_active=False)
    db = TestSessionLocal()
    db.add(ConversionRecord(user_id=admin.id, bank="bca", filename="a.pdf",
                            page_count=2, coin_cost=1))
    db.commit()
    db.close()

    r = client.get("/api/admin/stats", headers=admin_headers)
    assert r.status_code == 200
    b = r.json()
    assert b["total_users"] == 2
    assert b["total_admins"] == 1
    assert b["total_conversions"] == 1
    assert b["conversions_today"] == 1
    assert b["conversions_month"] == 1
    assert b["total_coins_circulating"] == 30
    assert b["popular_bank"] == "BCA"
    assert b["active_users"] == 1
    assert b["inactive_users"] == 1
    assert b["bank_stats"] == [{"bank": "BCA", "count": 1}]


def test_stats_empty(client, admin, admin_headers):
    b = client.get("/api/admin/stats", headers=admin_headers).json()
    assert b["total_users"] == 0
    assert b["popular_bank"] == "-"
    assert b["total_coins_circulating"] == 0


# --- Logs ----------------------------------------------------------------------

def test_admin_logs_recorded(client, admin, admin_headers):
    u = make_user(coins=10)
    client.post("/api/admin/add-coins", data={
        "unique_code": u.unique_code, "amount": 5,
    }, headers=admin_headers)

    r = client.get("/api/admin/logs", headers=admin_headers)
    assert r.status_code == 200
    logs = r.json()
    assert any(
        l["admin_email"] == admin.email
        and l["action"] == "Tambah 5 koin"
        and l["target_info"] == u.email
        for l in logs
    )


# --- Toggle user ---------------------------------------------------------------

def test_toggle_user_deactivates_and_reactivates(client, admin, admin_headers):
    u = make_user()
    r = client.post(f"/api/admin/toggle-user/{u.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert get_user(u.email).is_active is False

    r = client.post(f"/api/admin/toggle-user/{u.id}", headers=admin_headers)
    assert r.json()["is_active"] is True


def test_toggle_user_rejects_admin_target(client, admin, admin_headers):
    other_admin = make_user(email="admin2@gmail.com", is_admin=True)
    r = client.post(f"/api/admin/toggle-user/{other_admin.id}", headers=admin_headers)
    assert r.status_code == 400


def test_toggle_user_not_found(client, admin, admin_headers):
    r = client.post("/api/admin/toggle-user/9999", headers=admin_headers)
    assert r.status_code == 404


# --- Delete user ---------------------------------------------------------------

def test_delete_user_removes_records(client, admin, admin_headers):
    u = make_user(email="korban@gmail.com")
    db = TestSessionLocal()
    db.add(ConversionRecord(user_id=u.id, bank="bca", filename="a.pdf",
                            page_count=1, coin_cost=1))
    db.commit()
    db.close()

    r = client.delete(f"/api/admin/delete-user/{u.id}", headers=admin_headers)
    assert r.status_code == 200
    assert get_user(u.email) is None

    db = TestSessionLocal()
    remaining = db.query(ConversionRecord).filter(
        ConversionRecord.user_id == u.id).count()
    db.close()
    assert remaining == 0


def test_delete_user_self_forbidden(client, admin, admin_headers):
    r = client.delete(f"/api/admin/delete-user/{admin.id}", headers=admin_headers)
    assert r.status_code == 400


def test_delete_user_not_found(client, admin, admin_headers):
    r = client.delete("/api/admin/delete-user/9999", headers=admin_headers)
    assert r.status_code == 404


# --- Toggle admin --------------------------------------------------------------

def test_toggle_admin(client, admin, admin_headers):
    u = make_user()
    r = client.post(f"/api/admin/toggle-admin/{u.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True
    assert get_user(u.email).is_admin is True

    # promoted user can now access admin endpoints
    r = client.get("/api/admin/users", headers=auth_headers_for(u))
    assert r.status_code == 200

    # demote back
    client.post(f"/api/admin/toggle-admin/{u.id}", headers=admin_headers)
    assert get_user(u.email).is_admin is False


def test_toggle_admin_self_forbidden(client, admin, admin_headers):
    r = client.post(f"/api/admin/toggle-admin/{admin.id}", headers=admin_headers)
    assert r.status_code == 400


# --- Packages ------------------------------------------------------------------

def test_packages_crud(client, admin, admin_headers):
    r = client.post("/api/admin/packages", data={
        "name": "Paket A", "coin_amount": 100, "price": 50000,
    }, headers=admin_headers)
    assert r.status_code == 200

    pkgs = client.get("/api/packages").json()
    found = [p for p in pkgs if p["name"] == "Paket A"]
    assert len(found) == 1
    assert found[0]["coin_amount"] == 100
    assert found[0]["price"] == 50000

    r = client.delete(f"/api/admin/packages/{found[0]['id']}", headers=admin_headers)
    assert r.status_code == 200

    pkgs = client.get("/api/packages").json()
    assert all(p["name"] != "Paket A" for p in pkgs)


def test_packages_list_requires_no_auth(client):
    make_package()
    r = client.get("/api/packages")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_delete_package_not_found(client, admin, admin_headers):
    r = client.delete("/api/admin/packages/9999", headers=admin_headers)
    assert r.status_code == 404


# --- Broadcast -----------------------------------------------------------------

def test_broadcast_and_notifications(client, admin, admin_headers):
    r = client.post("/api/admin/broadcast", data={
        "title": "Maintenance", "message": "Server down nanti malam",
    }, headers=admin_headers)
    assert r.status_code == 200

    r = client.get("/api/admin/broadcasts", headers=admin_headers)
    assert r.status_code == 200
    assert any(n["title"] == "Maintenance" for n in r.json())

    u = make_user()
    r = client.get("/api/notifications", headers=auth_headers_for(u))
    assert r.status_code == 200
    assert any(n["title"] == "Maintenance" for n in r.json())


def test_notifications_exclude_old_broadcasts(client, admin):
    u = make_user()
    db = TestSessionLocal()
    db.add(BroadcastNotification(
        admin_id=admin.id, title="Lama", message="x",
        created_at=datetime.utcnow() - timedelta(days=8),
    ))
    db.commit()
    db.close()

    r = client.get("/api/notifications", headers=auth_headers_for(u))
    assert all(n["title"] != "Lama" for n in r.json())


def test_broadcast_requires_admin(client, user_headers):
    r = client.post("/api/admin/broadcast", data={
        "title": "X", "message": "Y",
    }, headers=user_headers)
    assert r.status_code == 403

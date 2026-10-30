from server.models import CoinPurchase
from tests.db import TestSessionLocal
from tests.helpers import make_user, get_user, make_package, make_purchase
from tests.conftest import auth_headers_for
import server.main as main


def get_purchase(purchase_id):
    db = TestSessionLocal()
    p = db.query(CoinPurchase).filter(CoinPurchase.id == purchase_id).first()
    db.close()
    return p


# --- Create purchase -----------------------------------------------------------

def test_create_purchase(client, user, user_headers):
    pkg = make_package()
    r = client.post("/api/purchases", data={
        "package_id": pkg.id, "buyer_name": "Budi",
        "buyer_phone": "0812345678", "payment_method": "GoPay",
    }, headers=user_headers)
    assert r.status_code == 200
    b = r.json()
    assert b["order_number"].startswith("INV-")
    assert b["price"] == 50000
    assert b["payment_method"] == "GoPay"

    p = get_purchase(b["purchase_id"])
    assert p.status == "pending"
    assert p.user_id == user.id
    assert p.coin_amount == 100


def test_create_purchase_inactive_package(client, user, user_headers):
    pkg = make_package(is_active=False)
    r = client.post("/api/purchases", data={
        "package_id": pkg.id, "buyer_name": "Budi",
        "buyer_phone": "0812345678", "payment_method": "GoPay",
    }, headers=user_headers)
    assert r.status_code == 404


def test_create_purchase_missing_package(client, user, user_headers):
    r = client.post("/api/purchases", data={
        "package_id": 9999, "buyer_name": "Budi",
        "buyer_phone": "0812345678", "payment_method": "GoPay",
    }, headers=user_headers)
    assert r.status_code == 404


def test_create_purchase_requires_auth(client):
    pkg = make_package()
    r = client.post("/api/purchases", data={
        "package_id": pkg.id, "buyer_name": "Budi",
        "buyer_phone": "08", "payment_method": "GoPay",
    })
    assert r.status_code == 401


# --- Upload proof --------------------------------------------------------------

def test_upload_proof(client, user, user_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", str(tmp_path))
    pkg = make_package()
    p = make_purchase(user.id, pkg)
    img = b"\x89PNG fake-image-bytes"

    r = client.post(f"/api/purchases/{p.id}/upload-proof",
                    files={"file": ("proof.png", img, "image/png")},
                    headers=user_headers)
    assert r.status_code == 200

    fresh = get_purchase(p.id)
    assert fresh.status == "menunggu"
    assert fresh.proof_filename.endswith(".png")
    saved = tmp_path / fresh.proof_filename
    assert saved.exists()
    assert saved.read_bytes() == img


def test_upload_proof_rejects_invalid_extension(client, user, user_headers):
    pkg = make_package()
    p = make_purchase(user.id, pkg)
    r = client.post(f"/api/purchases/{p.id}/upload-proof",
                    files={"file": ("proof.gif", b"GIF89a", "image/gif")},
                    headers=user_headers)
    assert r.status_code == 400
    assert "Format file tidak didukung" in r.json()["detail"]


def test_upload_proof_wrong_owner(client, user, user_headers):
    other = make_user(email="other@gmail.com")
    pkg = make_package()
    p = make_purchase(other.id, pkg)
    r = client.post(f"/api/purchases/{p.id}/upload-proof",
                    files={"file": ("proof.png", b"x", "image/png")},
                    headers=user_headers)
    assert r.status_code == 404


def test_upload_proof_not_found(client, user, user_headers):
    r = client.post("/api/purchases/9999/upload-proof",
                    files={"file": ("proof.png", b"x", "image/png")},
                    headers=user_headers)
    assert r.status_code == 404


def test_upload_proof_rejected_when_processed(client, user, user_headers):
    pkg = make_package()
    p = make_purchase(user.id, pkg, status="berhasil")
    r = client.post(f"/api/purchases/{p.id}/upload-proof",
                    files={"file": ("proof.png", b"x", "image/png")},
                    headers=user_headers)
    assert r.status_code == 400


# --- List purchases ------------------------------------------------------------

def test_user_purchases_list(client, user, user_headers):
    pkg = make_package()
    make_purchase(user.id, pkg)
    make_purchase(user.id, pkg)

    r = client.get("/api/user/purchases", headers=user_headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    for row in rows:
        assert row["package_name"] == "Paket 100"
        assert row["status"] == "pending"
        assert row["created_at"].endswith("Z")


def test_admin_purchases_with_status_filter(client, admin, admin_headers):
    pkg = make_package()
    u = make_user()
    make_purchase(u.id, pkg, status="pending")
    make_purchase(u.id, pkg, status="menunggu")

    r = client.get("/api/admin/purchases", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert all("user_email" in p for p in r.json())

    r = client.get("/api/admin/purchases", params={"status": "pending"},
                   headers=admin_headers)
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "pending"

    r = client.get("/api/admin/purchases", params={"status": "ditolak"},
                   headers=admin_headers)
    assert r.json() == []


# --- Update purchase status ----------------------------------------------------

def test_update_status_berhasil_credits_coins(client, admin, admin_headers):
    pkg = make_package(coin_amount=100)
    u = make_user(coins=10)
    p = make_purchase(u.id, pkg)

    r = client.put(f"/api/admin/purchases/{p.id}/status",
                   data={"new_status": "berhasil"}, headers=admin_headers)
    assert r.status_code == 200
    assert "koin ditambahkan" in r.json()["message"]
    assert get_user(u.email).coins == 110
    assert get_purchase(p.id).status == "berhasil"


def test_update_status_berhasil_no_double_credit(client, admin, admin_headers):
    pkg = make_package(coin_amount=100)
    u = make_user(coins=10)
    p = make_purchase(u.id, pkg)

    client.put(f"/api/admin/purchases/{p.id}/status",
               data={"new_status": "berhasil"}, headers=admin_headers)
    client.put(f"/api/admin/purchases/{p.id}/status",
               data={"new_status": "berhasil"}, headers=admin_headers)
    assert get_user(u.email).coins == 110


def test_update_status_ditolak_no_coins(client, admin, admin_headers):
    pkg = make_package(coin_amount=100)
    u = make_user(coins=10)
    p = make_purchase(u.id, pkg)

    r = client.put(f"/api/admin/purchases/{p.id}/status",
                   data={"new_status": "ditolak"}, headers=admin_headers)
    assert r.status_code == 200
    assert get_user(u.email).coins == 10
    assert get_purchase(p.id).status == "ditolak"


def test_update_status_invalid(client, admin, admin_headers):
    pkg = make_package()
    u = make_user()
    p = make_purchase(u.id, pkg)
    r = client.put(f"/api/admin/purchases/{p.id}/status",
                   data={"new_status": "lunas"}, headers=admin_headers)
    assert r.status_code == 400
    assert "Status tidak valid" in r.json()["detail"]


def test_update_status_not_found(client, admin, admin_headers):
    r = client.put("/api/admin/purchases/9999/status",
                   data={"new_status": "berhasil"}, headers=admin_headers)
    assert r.status_code == 404

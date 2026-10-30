from server.models import User, ConversionRecord, CoinPurchase, CoinPackage, AdminLog
from tests.db import TestSessionLocal


def test_user_auto_generates_unique_code():
    db = TestSessionLocal()
    u = User(email="a@gmail.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    assert u.unique_code.startswith("MC-")
    assert len(u.unique_code) == 11  # MC- + 8 hex


def test_user_respects_custom_unique_code():
    u = User(email="b@gmail.com", hashed_password="x", unique_code="CUSTOM-1")
    assert u.unique_code == "CUSTOM-1"


def test_user_column_defaults():
    db = TestSessionLocal()
    u = User(email="c@gmail.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    assert u.coins == 30
    assert u.is_admin is False
    assert u.is_active is True
    assert u.email_verified is False
    assert u.created_at is not None


def test_conversion_record_defaults():
    db = TestSessionLocal()
    u = User(email="d@gmail.com", hashed_password="x")
    db.add(u)
    db.commit()
    r = ConversionRecord(user_id=u.id, bank="bca", filename="a.pdf",
                         page_count=2, coin_cost=1)
    db.add(r)
    db.commit()
    db.refresh(r)
    db.close()
    assert r.created_at is not None


def test_purchase_defaults():
    db = TestSessionLocal()
    pkg = CoinPackage(name="P", coin_amount=10, price=1000)
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    u = User(email="e@gmail.com", hashed_password="x")
    db.add(u)
    db.commit()
    p = CoinPurchase(order_number="INV-1", user_id=u.id, package_id=pkg.id,
                     buyer_name="B", buyer_phone="08", payment_method="GoPay",
                     package_name=pkg.name, coin_amount=pkg.coin_amount, price=pkg.price)
    db.add(p)
    db.commit()
    db.refresh(p)
    db.close()
    assert p.status == "pending"
    assert p.created_at is not None
    assert p.updated_at is not None


def test_admin_log_defaults():
    db = TestSessionLocal()
    u = User(email="f@gmail.com", hashed_password="x")
    db.add(u)
    db.commit()
    log = AdminLog(admin_id=u.id, action="Test")
    db.add(log)
    db.commit()
    db.refresh(log)
    db.close()
    assert log.created_at is not None

"""Shared test helpers: minimal PDF builder, fake pdfplumber objects, DB helpers."""

import uuid

from server.models import CoinPackage, CoinPurchase, User
from server.auth import get_password_hash
from tests.db import TestSessionLocal


# --- Minimal valid PDF builder -------------------------------------------------

def build_pdf(num_pages=1):
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i} 0 R" for i in range(num_pages))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {num_pages} >>".encode())
    for _ in range(num_pages):
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    count = len(objs) + 1
    out += f"xref\n0 {count}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# --- Fake pdfplumber objects ---------------------------------------------------

def W(text, x0, top, bottom=None):
    return {"text": text, "x0": x0, "top": top,
            "bottom": bottom if bottom is not None else top + 8}


class FakePage:
    def __init__(self, width=612.0, text="", words=None, tables=None):
        self.width = width
        self._text = text
        self._words = words or []
        self._tables = tables or []

    def extract_text(self):
        return self._text

    def extract_words(self):
        return [dict(w) for w in self._words]

    def extract_tables(self):
        return [list(t) for t in self._tables]


class FakePDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


# --- Database helpers ----------------------------------------------------------


def make_user(email="user@test.com", password="password123", coins=50,
              is_admin=False, is_active=True, email_verified=True, **kwargs):
    db = TestSessionLocal()
    u = User(email=email, hashed_password=get_password_hash(password),
             coins=coins, is_admin=is_admin, is_active=is_active,
             email_verified=email_verified, **kwargs)
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return u


def get_user(email):
    db = TestSessionLocal()
    u = db.query(User).filter(User.email == email).first()
    db.close()
    return u


def make_package(name="Paket 100", coin_amount=100, price=50000, is_active=True):
    db = TestSessionLocal()
    p = CoinPackage(name=name, coin_amount=coin_amount, price=price, is_active=is_active)
    db.add(p)
    db.commit()
    db.refresh(p)
    db.close()
    return p


def make_purchase(user_id, pkg, status="pending", buyer_name="Budi",
                  buyer_phone="0812345678", payment_method="GoPay"):
    db = TestSessionLocal()
    p = CoinPurchase(
        order_number=f"INV-TEST-{uuid.uuid4().hex[:6].upper()}",
        user_id=user_id, package_id=pkg.id,
        buyer_name=buyer_name, buyer_phone=buyer_phone,
        payment_method=payment_method,
        package_name=pkg.name, coin_amount=pkg.coin_amount, price=pkg.price,
        status=status,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    db.close()
    return p


def db_query(model, **filters):
    db = TestSessionLocal()
    rows = db.query(model).filter_by(**filters).all()
    db.close()
    return rows
